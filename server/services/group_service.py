import logging
from typing import Dict, List

from models.group_model import GroupModel
from models.agent_model import AgentModel

from time_utils import now_iso


class GroupService:
    """Business logic for group management."""

    def __init__(self, group_model: GroupModel, agent_model: AgentModel, user_model=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = group_model
        self.agent_model = agent_model
        self.user_model = user_model
        self.pending_group = self.model.ensure_pending_group()

    def _enrich_owner(self, group: Dict) -> Dict:
        """Add created_by_username to group if user_model available."""
        if self.user_model and group.get("created_by"):
            user = self.user_model.find_by_id(str(group["created_by"]))
            if user:
                group["created_by_username"] = user.get("username", "")
                group["created_by_role"] = user.get("role", "")
        return group

    def list_groups(self, query_filter: dict = None) -> List[Dict]:
        groups = self.model.list_groups(query_filter=query_filter)
        formatted = []
        for group in groups:
            group["_id"] = str(group.get("_id"))
            if group.get("created_by"):
                group["created_by"] = str(group["created_by"])
            if group.get("teacher_ids"):
                group["teacher_ids"] = [str(tid) for tid in group["teacher_ids"]]
            self._enrich_owner(group)
            formatted.append(group)
        return formatted

    def create_group(self, name: str, description: str = "", whitelist: List[Dict] = None, created_by=None) -> Dict:
        group = self.model.create_group(name, description, whitelist or [], created_by=created_by)
        group["_id"] = str(group.get("_id"))
        if group.get("created_by"):
            group["created_by"] = str(group["created_by"])
        return group

    def update_group(self, group_id: str, payload: Dict) -> Dict:
        group = self.model.find_by_id(group_id)
        if not group:
            raise ValueError("Group not found")
        if group.get("is_system") and payload.get("is_system") is False:
            raise ValueError("System group flags cannot be changed")

        if "whitelist" in payload:
            payload["whitelist_version"] = group.get("whitelist_version", 1) + 1

        updated = self.model.update_group(group_id, payload)
        if not updated:
            raise ValueError("Failed to update group")
        updated["_id"] = str(updated.get("_id"))
        if updated.get("created_by"):
            updated["created_by"] = str(updated["created_by"])
        return updated

    def delete_group(self, group_id: str) -> bool:
        group = self.model.find_by_id(group_id)
        if not group:
            raise ValueError("Group not found")
        if group.get("is_system"):
            raise ValueError("Cannot delete system groups")
        agent_count = self.agent_model.count_by_group(group_id)
        if agent_count > 0:
            raise ValueError("Cannot delete group with assigned agents")
        return self.model.delete_group(group_id)

    def bump_group_whitelist_version(self, group_id: str) -> Dict:
        updated = self.model.bump_whitelist_version(group_id)
        if not updated:
            raise ValueError("Group not found")
        updated["_id"] = str(updated.get("_id"))
        return updated

    def get_pending_group_id(self) -> str:
        return str(self.pending_group.get("_id"))

    def get_group(self, group_id: str) -> Dict:
        group = self.model.find_by_id(group_id)
        if not group:
            raise ValueError("Group not found")
        group["_id"] = str(group.get("_id"))
        if group.get("created_by"):
            group["created_by"] = str(group["created_by"])
        if group.get("teacher_ids"):
            group["teacher_ids"] = [str(tid) for tid in group["teacher_ids"]]
        self._enrich_owner(group)
        return group

    def get_default_metadata(self) -> Dict:
        return {
            "pending_group_id": self.get_pending_group_id(),
            "timestamp": now_iso(),
        }