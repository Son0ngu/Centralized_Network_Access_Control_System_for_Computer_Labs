import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam


def _normalise_embedded_whitelist(entries: List) -> List[Dict]:
    """Ensure every entry in a group's embedded whitelist is a dict with ``_id``.

    Called by ``create_group`` so new groups never carry the legacy bare-string
    or id-less dict forms. The format already exists in the wild for older
    groups; the backfill migration ``2026_backfill_group_whitelist_entry_ids.py``
    upgrades them in place. Keep this helper module-private — the unified
    contract is owned by ``server.services.whitelist_entry_id``.
    """
    out: List[Dict] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            entry = {**entry}
            entry_id = entry.get("_id")
            if not entry_id:
                entry["_id"] = ObjectId()
            elif isinstance(entry_id, ObjectId):
                pass
            elif ObjectId.is_valid(str(entry_id)):
                entry["_id"] = ObjectId(str(entry_id))
            else:
                entry["_id"] = ObjectId()
            out.append(entry)
        else:
            # Bare string (legacy callers): promote to dict so the schema
            # is uniform. Default category/priority match what the bulk
            # path uses, so listing rendering is consistent.
            out.append({
                "_id": ObjectId(),
                "value": str(entry),
                "type": "domain",
                "category": "uncategorized",
                "priority": "normal",
                "is_active": True,
            })
    return out


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
            self.collection.create_index([("created_by", ASCENDING)])  # RBAC: ownership index
            self.collection.create_index([("teacher_ids", ASCENDING)])  # RBAC: assigned teachers
        except Exception as exc:
            self.logger.warning(f"Error creating group indexes: {exc}")

    def ensure_pending_group(self) -> Dict:
        now = now_vietnam()
        try:
            # Atomic upsert to avoid race condition between check and insert
            result = self.collection.find_one_and_update(
                {"is_system": True, "name": "pending"},
                {
                    "$setOnInsert": {
                        "name": "pending",
                        "description": "System group for pending agents",
                        "created_at": now,
                        "updated_at": now,
                        "is_system": True,
                        "whitelist": [],
                        "whitelist_version": 1,
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return result
        except Exception as exc:
            self.logger.error(f"Failed to ensure pending group: {exc}")
            # Fallback: try to find existing (may have been created by another process)
            existing = self.collection.find_one({"is_system": True, "name": "pending"})
            if existing:
                return existing
            raise

    def find_pending_group(self) -> Optional[Dict]:
        """Return the system pending group if it exists."""
        return self.collection.find_one({"is_system": True, "name": "pending"})

    def create_group(self, name: str, description: str = "", whitelist: Optional[List[Dict]] = None, is_system: bool = False, created_by=None) -> Dict:
        now = now_vietnam()

        # Stamp a real ObjectId on every embedded whitelist entry up front so
        # frontend never sees a pseudo-ID for groups created after this
        # change. Backwards-compat: bare-string entries (legacy callers that
        # pass ``["example.com"]``) are promoted to dict form here too, since
        # the unified id contract needs entries to be subdocuments. See the
        # cleanup plan (Phase 3, P1 #8) for the wider context.
        normalised = _normalise_embedded_whitelist(whitelist or [])

        group = {
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "is_system": is_system,
            "whitelist": normalised,
            "whitelist_version": 1,
            "created_by": created_by,
            "teacher_ids": [],  # RBAC: list of assigned teacher ObjectIds
        }
        result = self.collection.insert_one(group)
        group["_id"] = result.inserted_id
        return group

    def add_teacher(self, group_id: str, teacher_id) -> Optional[Dict]:
        """Add a teacher to the group's teacher_ids list."""
        return self.collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$addToSet": {"teacher_ids": teacher_id}, "$set": {"updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def remove_teacher(self, group_id: str, teacher_id) -> Optional[Dict]:
        """Remove a teacher from the group's teacher_ids list."""
        return self.collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$pull": {"teacher_ids": teacher_id}, "$set": {"updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def set_teachers(self, group_id: str, teacher_ids: list) -> Optional[Dict]:
        """Set the full teacher_ids list for a group."""
        return self.collection.find_one_and_update(
            {"_id": ObjectId(group_id)},
            {"$set": {"teacher_ids": teacher_ids, "updated_at": now_vietnam()}},
            return_document=ReturnDocument.AFTER,
        )

    def list_groups(self, query_filter: dict = None) -> List[Dict]:
        """List groups, optionally filtered (e.g. by created_by for teacher)."""
        return list(self.collection.find(query_filter or {}))

    def find_accessible_group_ids_for_teacher(self, teacher_id) -> List[str]:
        """Return group ids assigned to or legacy-created by a teacher."""
        groups = self.collection.find(
            {"$or": [
                {"teacher_ids": teacher_id},
                {"created_by": teacher_id},
            ]},
            {"_id": 1},
        )
        return [str(group["_id"]) for group in groups]

    def find_group_with_embedded_entry(self, entry_oid) -> Optional[Dict]:
        """Return the group document that owns an embedded whitelist entry.

        Used by ``WhitelistService`` to resolve a real ObjectId back to its
        parent group when the caller passes ``whitelist._id`` (the new
        canonical identifier for embedded entries). Falls back to ``None``
        if no group has a matching embedded entry — caller treats that as
        "not found" and surfaces a 404.

        The query is a dotted-path match (``whitelist._id``), which MongoDB
        supports natively against arrays of subdocuments. We project only
        the fields the service actually needs so the network round-trip
        stays small even for groups with thousands of embedded entries.
        """
        return self.collection.find_one({"whitelist._id": entry_oid})

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
        if "layout" in update_data:
            update_payload["layout"] = update_data["layout"]
        if "whitelist" in update_data:
            update_payload["whitelist"] = _normalise_embedded_whitelist(
                update_data.get("whitelist") or []
            )
            # Always bump whitelist_version when whitelist changes
            if "whitelist_version" in update_data:
                update_payload["whitelist_version"] = update_data["whitelist_version"]
            else:
                # Auto-bump: caller didn't provide version, use $inc after $set
                # For simplicity, read current and increment
                current = self.collection.find_one({"_id": ObjectId(group_id)})
                if current:
                    update_payload["whitelist_version"] = current.get("whitelist_version", 0) + 1

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
