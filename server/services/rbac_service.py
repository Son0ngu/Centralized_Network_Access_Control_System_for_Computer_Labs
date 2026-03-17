"""
RBAC Service - Permission check & ownership check.
- Admin: toan quyen, khong bi gioi han boi ownership
- Teacher: chi thao tac tren Group ma minh tao (created_by)
"""

import logging
from typing import Dict, List, Optional

from bson import ObjectId

from config.rbac_config import (
    check_permission,
    get_all_permissions,
    is_admin,
    ROLE_HIERARCHY,
)

logger = logging.getLogger(__name__)


class RBACService:
    """Service for role-based access control logic"""

    def __init__(self, group_model=None, agent_model=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.group_model = group_model
        self.agent_model = agent_model

    # ========================================================================
    # PERMISSION CHECK
    # ========================================================================

    def check_permission(self, user_role: str, permission: str) -> bool:
        """Check if role has a specific permission"""
        return check_permission(user_role, permission)

    def get_permissions(self, role: str) -> List[str]:
        """Get all permissions for a role"""
        return get_all_permissions(role)

    def is_admin(self, role: str) -> bool:
        """Check if role is admin"""
        return is_admin(role)

    # ========================================================================
    # OWNERSHIP CHECK (core logic cho Teacher)
    # ========================================================================

    def is_owner(self, user_id: str, resource: Dict) -> bool:
        """
        Check if user is the owner of a resource.
        Compares resource.created_by with user._id
        """
        resource_owner = resource.get("created_by")
        if resource_owner is None:
            return False
        return str(resource_owner) == str(user_id)

    def can_access_group(self, user: Dict, group: Dict) -> bool:
        """
        Check if user can access a specific group.
        - Admin: always True
        - Teacher: only if group.created_by == user._id
        """
        if user.get("role") == "admin":
            return True
        return self.is_owner(str(user.get("_id")), group)

    def filter_groups_for_user(self, user: Dict, groups: List[Dict]) -> List[Dict]:
        """
        Filter groups list based on user access.
        - Admin: return all groups
        - Teacher: return only groups created by this teacher
        """
        if user.get("role") == "admin":
            return groups

        user_id = str(user.get("_id"))
        return [g for g in groups if str(g.get("created_by")) == user_id]

    # ========================================================================
    # HELPER: get teacher's group IDs
    # ========================================================================

    def get_teacher_group_ids(self, user: Dict) -> Optional[List[str]]:
        """
        Tra ve list string group_ids ma teacher tao.
        Returns None cho admin (nghia la tat ca).
        Returns [] neu khong co group_model.
        """
        if user.get("role") == "admin":
            return None  # Admin thay tat ca

        if self.group_model:
            user_id = user.get("_id")
            groups = list(self.group_model.collection.find(
                {"created_by": user_id}, {"_id": 1}
            ))
            return [str(g["_id"]) for g in groups]

        return []

    # ========================================================================
    # QUERY HELPERS (for controllers to filter data)
    # ========================================================================

    def get_group_query_filter(self, user: Dict) -> Optional[Dict]:
        """
        Get MongoDB query filter for groups based on user role.
        Returns:
            None for admin (no filter needed - toan quyen)
            {"created_by": ObjectId(...)} for teacher
        """
        if user.get("role") == "admin":
            return None  # Admin sees all
        return {"created_by": user.get("_id")}

    def get_agent_query_filter(self, user: Dict) -> Optional[Dict]:
        """
        Get MongoDB query filter for agents based on user role.
        Teacher chi thay agents trong groups minh tao.
        Returns:
            None for admin
            {"group_id": {"$in": [...]}} for teacher
        """
        if user.get("role") == "admin":
            return None

        group_ids = self.get_teacher_group_ids(user)
        if group_ids is None:
            return None
        return {"group_id": {"$in": group_ids}}

    def get_log_query_filter(self, user: Dict) -> Optional[Dict]:
        """
        Get MongoDB query filter for logs based on user role.
        Teacher chi thay logs tu agents trong groups minh tao.
        Query chain: teacher -> groups -> agents -> logs
        """
        if user.get("role") == "admin":
            return None

        # Buoc 1: Lay group_ids cua teacher
        group_ids = self.get_teacher_group_ids(user)
        if group_ids is None:
            return None
        if not group_ids:
            return {"agent_id": {"$in": []}}

        # Buoc 2: Lay agent_ids trong cac groups do
        if self.agent_model:
            # agent_model luu group_id dang string hoac ObjectId
            # Can match ca 2 format
            group_id_variants = []
            for gid in group_ids:
                group_id_variants.append(gid)
                try:
                    group_id_variants.append(ObjectId(gid))
                except Exception:
                    pass

            agents = list(self.agent_model.collection.find(
                {"group_id": {"$in": group_id_variants}},
                {"agent_id": 1}
            ))
            agent_ids = [a["agent_id"] for a in agents if a.get("agent_id")]
            return {"agent_id": {"$in": agent_ids}}

        return {"agent_id": {"$in": []}}

    def get_whitelist_query_filter(self, user: Dict) -> Optional[Dict]:
        """
        Get query filter for whitelist based on user role.
        Teacher thay: global + entries trong groups minh.
        Returns:
            None for admin (toan quyen)
            {"$or": [{"scope": "global"}, {"group_id": {"$in": [...]}}]} for teacher
        """
        if user.get("role") == "admin":
            return None

        group_ids = self.get_teacher_group_ids(user)
        if group_ids is None:
            return None

        return {
            "$or": [
                {"scope": "global"},
                {"group_id": {"$in": group_ids}},
            ]
        }

    def validate_group_ids_ownership(self, user: Dict, group_ids: List[str]) -> tuple:
        """
        Validate that ALL group_ids belong to the current user.
        Admin bypasses this check.

        Args:
            user: User dict (must have _id, role)
            group_ids: List of group_id strings to validate

        Returns:
            (is_valid: bool, invalid_ids: List[str])
            - Admin: always (True, [])
            - Teacher: (True, []) if all group_ids are owned, else (False, [bad_ids])
        """
        if not group_ids:
            return True, []

        if user.get("role") == "admin":
            return True, []

        owned_ids = self.get_teacher_group_ids(user)
        if owned_ids is None:
            return True, []  # Safety fallback

        owned_set = set(owned_ids)
        invalid = [gid for gid in group_ids if str(gid) not in owned_set]

        return (len(invalid) == 0), invalid

    def can_teacher_access_agent(self, user: Dict, agent: Dict) -> bool:
        """
        Check if teacher can access a specific agent.
        Agent must belong to a group the teacher created.
        """
        if user.get("role") == "admin":
            return True

        agent_group_id = agent.get("group_id")
        if not agent_group_id:
            return False

        group_ids = self.get_teacher_group_ids(user)
        if group_ids is None:
            return True
        return str(agent_group_id) in group_ids
