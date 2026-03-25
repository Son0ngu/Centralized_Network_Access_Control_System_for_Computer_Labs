"""
RBAC Service - Permission check & ownership check.
- Admin: full access, not limited by ownership
- Teacher: can only operate on Groups they are assigned to (teacher_ids)
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
    # OWNERSHIP CHECK (core logic for Teacher)
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
        - Teacher: if user._id in group.teacher_ids OR group.created_by == user._id (legacy)
        """
        if user.get("role") == "admin":
            return True
        user_id = user.get("_id")
        teacher_ids = group.get("teacher_ids") or []
        if any(str(tid) == str(user_id) for tid in teacher_ids):
            return True
        # Legacy fallback: created_by
        return self.is_owner(str(user_id), group)

    def filter_groups_for_user(self, user: Dict, groups: List[Dict]) -> List[Dict]:
        """
        Filter groups list based on user access.
        - Admin: return all groups
        - Teacher: return only groups where user is in teacher_ids (or legacy created_by)
        """
        if user.get("role") == "admin":
            return groups

        user_id = str(user.get("_id"))
        result = []
        for g in groups:
            teacher_ids = g.get("teacher_ids") or []
            if any(str(tid) == user_id for tid in teacher_ids):
                result.append(g)
            elif str(g.get("created_by")) == user_id:
                result.append(g)
        return result

    # ========================================================================
    # HELPER: get teacher's group IDs
    # ========================================================================

    def get_teacher_group_ids(self, user: Dict) -> Optional[List[str]]:
        """
        Return list of group_id strings that the teacher is assigned to.
        Returns None for admin (meaning all).
        Returns [] if group_model is not available.
        """
        if user.get("role") == "admin":
            return None  # Admin sees all

        if self.group_model:
            user_id = user.get("_id")
            groups = list(self.group_model.collection.find(
                {"$or": [
                    {"teacher_ids": user_id},
                    {"created_by": user_id},  # legacy fallback
                ]},
                {"_id": 1}
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
            None for admin (no filter needed - full access)
            Filter by teacher_ids for teacher
        """
        if user.get("role") == "admin":
            return None  # Admin sees all
        user_id = user.get("_id")
        return {"$or": [
            {"teacher_ids": user_id},
            {"created_by": user_id},  # legacy fallback
        ]}

    def get_agent_query_filter(self, user: Dict) -> Optional[Dict]:
        """
        Get MongoDB query filter for agents based on user role.
        Teacher only sees agents in their own groups.
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
        Teacher only sees logs from agents in their own groups.
        Query chain: teacher -> groups -> agents -> logs
        """
        if user.get("role") == "admin":
            return None

        # Step 1: Get teacher's group_ids
        group_ids = self.get_teacher_group_ids(user)
        if group_ids is None:
            return None
        if not group_ids:
            return {"agent_id": {"$in": []}}

        # Step 2: Get agent_ids in those groups
        if self.agent_model:
            # agent_model stores group_id as string or ObjectId
            # Need to match both formats
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
        Teacher sees: global + entries in their own groups.
        Returns:
            None for admin (full access)
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
