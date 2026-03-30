"""
Whitelist Profile Model - Per-teacher whitelist profiles within a group.

Each teacher can have multiple profiles per group (e.g., different subjects).
Only ONE profile can be active per group at any time.
When active, the profile's domains replace the group's base whitelist for agent sync.
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database

from time_utils import now_vietnam


class WhitelistProfileModel:
    """Model for per-teacher whitelist profiles."""

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection = self.db.whitelist_profiles
        self._setup_indexes()

    def _setup_indexes(self):
        try:
            self.collection.create_index([("group_id", ASCENDING), ("teacher_id", ASCENDING)])
            self.collection.create_index([("group_id", ASCENDING), ("is_active", ASCENDING)])
            self.collection.create_index([("teacher_id", ASCENDING)])
            self.collection.create_index([("created_at", DESCENDING)])
        except Exception as e:
            self.logger.warning(f"Error creating whitelist_profile indexes: {e}")

    def create_profile(self, group_id, teacher_id, teacher_username: str,
                       name: str, domains: List[Dict] = None) -> Dict:
        now = now_vietnam()
        profile = {
            "group_id": ObjectId(group_id) if isinstance(group_id, str) else group_id,
            "teacher_id": ObjectId(teacher_id) if (teacher_id and isinstance(teacher_id, str)) else teacher_id,
            "teacher_username": teacher_username,
            "name": name,
            "domains": domains or [],
            "is_active": False,
            "activated_at": None,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        result = self.collection.insert_one(profile)
        profile["_id"] = result.inserted_id
        return profile

    def find_by_id(self, profile_id: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({"_id": ObjectId(profile_id)})
        except Exception:
            return None

    def list_by_group(self, group_id: str, teacher_id=None) -> List[Dict]:
        """List profiles for a group, optionally filtered by teacher."""
        query = {"group_id": ObjectId(group_id)}
        if teacher_id:
            query["teacher_id"] = ObjectId(teacher_id) if isinstance(teacher_id, str) else teacher_id
        return list(self.collection.find(query).sort("created_at", DESCENDING))

    def update_profile(self, profile_id: str, update_data: Dict) -> Optional[Dict]:
        payload = {"updated_at": now_vietnam()}
        if "name" in update_data:
            payload["name"] = update_data["name"]
        if "domains" in update_data:
            payload["domains"] = update_data["domains"]
            payload["version"] = update_data.get("version", 1)

        return self.collection.find_one_and_update(
            {"_id": ObjectId(profile_id)},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )

    def bump_version(self, profile_id: str) -> Optional[Dict]:
        return self.collection.find_one_and_update(
            {"_id": ObjectId(profile_id)},
            {"$inc": {"version": 1}, "$set": {"updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def delete_profile(self, profile_id: str) -> bool:
        result = self.collection.delete_one({"_id": ObjectId(profile_id)})
        return result.deleted_count > 0

    def activate(self, profile_id: str) -> Optional[Dict]:
        """Activate a profile. Caller must deactivate others in group first."""
        return self.collection.find_one_and_update(
            {"_id": ObjectId(profile_id)},
            {"$set": {"is_active": True, "activated_at": now_vietnam(), "updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def deactivate(self, profile_id: str) -> Optional[Dict]:
        return self.collection.find_one_and_update(
            {"_id": ObjectId(profile_id)},
            {"$set": {"is_active": False, "activated_at": None, "updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def deactivate_all_in_group(self, group_id: str) -> int:
        """Deactivate all active profiles in a group. Returns count updated."""
        result = self.collection.update_many(
            {"group_id": ObjectId(group_id), "is_active": True},
            {"$set": {"is_active": False, "activated_at": None, "updated_at": now_vietnam()}},
        )
        return result.modified_count

    def get_active_profile(self, group_id: str) -> Optional[Dict]:
        """Get the currently active profile for a group (for agent sync)."""
        return self.collection.find_one({
            "group_id": ObjectId(group_id),
            "is_active": True,
        })

