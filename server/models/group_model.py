import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam


class GroupModel:
    """Model for managing agent groups and their whitelists."""

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.groups
        self._setup_indexes()

    def _setup_indexes(self) -> None:
        try:
            self.collection.create_index([("name", ASCENDING)], unique=True)
            self.collection.create_index([("is_system", ASCENDING)])
            self.collection.create_index([("created_at", ASCENDING)])
        except Exception as exc:
            self.logger.warning(f"Error creating group indexes: {exc}")

    def ensure_pending_group(self) -> Dict:
        existing = self.collection.find_one({"is_system": True, "name": "pending"})
        if existing:
            return existing

        now = now_vietnam()
        group = {
            "name": "pending",
            "description": "System group for pending agents",
            "created_at": now,
            "updated_at": now,
            "is_system": True,
            "whitelist": [],
            "whitelist_version": 1,
        }
        try:
            inserted = self.collection.insert_one(group)
            group["_id"] = inserted.inserted_id
            return group
        except Exception as exc:
            self.logger.error(f"Failed to create pending group: {exc}")
            raise

    def create_group(self, name: str, description: str = "", whitelist: Optional[List[Dict]] = None, is_system: bool = False) -> Dict:
        now = now_vietnam()
        group = {
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "is_system": is_system,
            "whitelist": whitelist or [],
            "whitelist_version": 1,
        }
        result = self.collection.insert_one(group)
        group["_id"] = result.inserted_id
        return group

    def list_groups(self) -> List[Dict]:
        return list(self.collection.find())

    def find_by_id(self, group_id: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({"_id": ObjectId(group_id)})
        except Exception:
            return None

    def update_group(self, group_id: str, update_data: Dict) -> Optional[Dict]:
        update_payload = {"updated_at": now_vietnam()}

        if "name" in update_data:
            update_payload["name"] = update_data["name"]
        if "description" in update_data:
            update_payload["description"] = update_data["description"]
        if "whitelist" in update_data:
            update_payload["whitelist"] = update_data.get("whitelist") or []
            if "whitelist_version" in update_data:
                update_payload["whitelist_version"] = update_data.get("whitelist_version")

        result = self.collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$set": update_payload},
            return_document=ReturnDocument.AFTER,
        )
        return result

    def delete_group(self, group_id: str) -> bool:
        result = self.collection.delete_one({"_id": ObjectId(group_id)})
        return result.deleted_count > 0

    def bump_whitelist_version(self, group_id: str) -> Optional[Dict]:
        return self.collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$inc": {"whitelist_version": 1}, "$set": {"updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )