"""
Whitelist Profile Service - Business logic for per-teacher whitelist profiles.
"""

import logging
from typing import Dict, List, Optional

from models.whitelist_profile_model import WhitelistProfileModel
from models.group_model import GroupModel


class WhitelistProfileService:
    """Service for managing per-teacher whitelist profiles within groups."""

    def __init__(self, profile_model: WhitelistProfileModel, group_model: GroupModel, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = profile_model
        self.group_model = group_model
        self.socketio = socketio

    def _serialize(self, profile: Dict) -> Dict:
        """Convert ObjectIds to strings for JSON response."""
        if not profile:
            return profile
        profile["_id"] = str(profile.get("_id", ""))
        profile["group_id"] = str(profile.get("group_id", ""))
        profile["teacher_id"] = str(profile.get("teacher_id", ""))
        return profile

    def list_profiles(self, group_id: str, teacher_id: str = None) -> List[Dict]:
        profiles = self.model.list_by_group(group_id, teacher_id=teacher_id)
        return [self._serialize(p) for p in profiles]

    def create_profile(self, group_id: str, teacher_id, teacher_username: str,
                       name: str, domains: List[Dict] = None) -> Dict:
        # Validate group exists
        group = self.group_model.find_by_id(group_id)
        if not group:
            raise ValueError("Group not found")

        profile = self.model.create_profile(
            group_id=group_id,
            teacher_id=teacher_id,
            teacher_username=teacher_username,
            name=name,
            domains=domains or [],
        )
        self.logger.info(f"Profile created: {name} by {teacher_username} in group {group_id}")
        return self._serialize(profile)

    def update_profile(self, profile_id: str, payload: Dict, user=None) -> Dict:
        profile = self.model.find_by_id(profile_id)
        if not profile:
            raise ValueError("Profile not found")

        # Teacher can only update their own profiles
        if user and user.get("role") == "teacher":
            if str(profile.get("teacher_id")) != str(user.get("_id")):
                raise PermissionError("Cannot update another teacher's profile")

        # If domains changed, bump version
        if "domains" in payload:
            payload["version"] = profile.get("version", 1) + 1

        updated = self.model.update_profile(profile_id, payload)
        if not updated:
            raise ValueError("Failed to update profile")

        # Bump group whitelist version when domains change and profile is active
        if "domains" in payload and updated.get("is_active"):
            self.group_model.bump_whitelist_version(str(updated["group_id"]))
            self._notify_group_update(str(updated["group_id"]))

        return self._serialize(updated)

    def delete_profile(self, profile_id: str, user=None) -> bool:
        profile = self.model.find_by_id(profile_id)
        if not profile:
            raise ValueError("Profile not found")

        if user and user.get("role") == "teacher":
            if str(profile.get("teacher_id")) != str(user.get("_id")):
                raise PermissionError("Cannot delete another teacher's profile")

        if profile.get("is_active"):
            raise ValueError("Cannot delete an active profile. Deactivate it first.")

        return self.model.delete_profile(profile_id)

    def activate_profile(self, profile_id: str, user=None) -> Dict:
        """Activate a profile. Returns dict with profile + deactivated_profile info."""
        profile = self.model.find_by_id(profile_id)
        if not profile:
            raise ValueError("Profile not found")

        group_id = str(profile["group_id"])

        # Check if another profile is active
        current_active = self.model.get_active_profile(group_id)
        deactivated_info = None
        if current_active and str(current_active["_id"]) != profile_id:
            deactivated_info = {
                "teacher_username": current_active.get("teacher_username", ""),
                "name": current_active.get("name", ""),
            }

        # Deactivate all in group, then activate this one
        self.model.deactivate_all_in_group(group_id)
        activated = self.model.activate(profile_id)

        # Bump group whitelist version so agents re-sync
        self.group_model.bump_whitelist_version(group_id)
        self._notify_group_update(group_id)

        result = self._serialize(activated)
        result["deactivated_profile"] = deactivated_info
        return result

    def deactivate_profile(self, profile_id: str, user=None) -> Dict:
        profile = self.model.find_by_id(profile_id)
        if not profile:
            raise ValueError("Profile not found")

        if not profile.get("is_active"):
            raise ValueError("Profile is not active")

        deactivated = self.model.deactivate(profile_id)

        # Bump version so agents fall back to base whitelist
        group_id = str(profile["group_id"])
        self.group_model.bump_whitelist_version(group_id)
        self._notify_group_update(group_id)

        return self._serialize(deactivated)

    def get_active_profile(self, group_id: str) -> Optional[Dict]:
        """Get the active profile for a group (used by agent sync)."""
        profile = self.model.get_active_profile(group_id)
        return self._serialize(profile) if profile else None

    def get_teacher_profiles(self, teacher_id, group_ids: List[str]) -> List[Dict]:
        """Get all profiles owned by this teacher across specified groups.
        Used by /whitelist page to populate the profile selector dropdown."""
        if not group_ids:
            return []

        profiles = self.model.list_by_teacher_groups(teacher_id, group_ids)

        # Attach group_name to each profile
        group_map = {}
        for gid in group_ids:
            grp = self.group_model.find_by_id(gid)
            if grp:
                group_map[gid] = grp.get("name", "Unknown")

        result = []
        for p in profiles:
            sp = self._serialize(p)
            sp["group_name"] = group_map.get(sp["group_id"], "Unknown")
            result.append(sp)

        return result

    def _notify_group_update(self, group_id: str):
        """Notify agents in this group to re-sync whitelist."""
        if self.socketio:
            try:
                self.socketio.emit("whitelist_updated", {"group_id": group_id})
            except Exception as e:
                self.logger.warning(f"Failed to emit whitelist_updated: {e}")
