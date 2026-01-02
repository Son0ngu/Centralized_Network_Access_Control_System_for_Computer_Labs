"""
Broadcast Model - System-wide announcements
--------------------------------------------
Manages broadcasts from Super Admin to Tenant Admins.

Types:
- info: General information (blue, dismissible)
- warning: Important notices (yellow, dismissible)
- danger: Critical alerts (red, not dismissible)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam

logger = logging.getLogger(__name__)

# Broadcast type constants
BROADCAST_INFO = "info"
BROADCAST_WARNING = "warning"
BROADCAST_DANGER = "danger"
VALID_BROADCAST_TYPES = [BROADCAST_INFO, BROADCAST_WARNING, BROADCAST_DANGER]

# Broadcast targeting
TARGET_ALL = "all"
TARGET_SPECIFIC = "specific"


class BroadcastModel:
    """Model for system broadcast operations."""
    
    def __init__(self, db: Database):
        self.db = db
        self.collection: Collection = db.broadcasts
        self.dismissals: Collection = db.broadcast_dismissals
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create database indexes."""
        # Broadcasts collection
        self.collection.create_index([("is_active", ASCENDING)])
        self.collection.create_index([("start_time", ASCENDING)])
        self.collection.create_index([("end_time", ASCENDING)])
        self.collection.create_index([("created_at", DESCENDING)])
        self.collection.create_index([("type", ASCENDING)])
        
        # Dismissals collection (track which admins dismissed which broadcasts)
        self.dismissals.create_index([
            ("broadcast_id", ASCENDING),
            ("admin_id", ASCENDING)
        ], unique=True)
        self.dismissals.create_index([("dismissed_at", DESCENDING)])
    
    def create_broadcast(self, broadcast_data: Dict) -> Dict:
        """
        Create a new system broadcast.
        
        Args:
            broadcast_data: {
                "title": "System Maintenance",
                "message": "The system will be down from 12:00 AM to 2:00 AM",
                "type": "warning",  # info, warning, danger
                "target": "all",  # all, specific
                "target_tenants": [],  # List of tenant_ids if target=specific
                "start_time": datetime,  # When to start showing
                "end_time": datetime,  # When to stop showing (optional)
                "created_by": "super_admin_id"
            }
        
        Returns:
            Created broadcast document
        """
        broadcast_type = broadcast_data.get("type", BROADCAST_INFO)
        if broadcast_type not in VALID_BROADCAST_TYPES:
            raise ValueError(f"Invalid type: {broadcast_type}. Must be one of {VALID_BROADCAST_TYPES}")
        
        target = broadcast_data.get("target", TARGET_ALL)
        if target not in [TARGET_ALL, TARGET_SPECIFIC]:
            raise ValueError(f"Invalid target: {target}. Must be 'all' or 'specific'")
        
        now = now_vietnam()
        
        # Convert target_tenants to ObjectIds if provided
        target_tenants = []
        if target == TARGET_SPECIFIC:
            for tid in broadcast_data.get("target_tenants", []):
                try:
                    target_tenants.append(ObjectId(tid))
                except:
                    pass
        
        broadcast = {
            "title": broadcast_data["title"],
            "message": broadcast_data["message"],
            "type": broadcast_type,
            "priority": broadcast_data.get("priority", "normal"),  # normal, high
            "target": target,
            "target_tenants": target_tenants,
            "start_time": broadcast_data.get("start_time", now),
            "end_time": broadcast_data.get("end_time"),  # None = no expiry
            "is_active": True,
            "is_dismissible": broadcast_type != BROADCAST_DANGER,  # Danger cannot be dismissed
            "created_by": ObjectId(broadcast_data["created_by"]),
            "created_at": now,
            "updated_at": now,
        }
        
        result = self.collection.insert_one(broadcast)
        broadcast["_id"] = result.inserted_id
        
        logger.info(f"Created broadcast: {broadcast['title']} (type: {broadcast_type})")
        return broadcast
    
    def get_by_id(self, broadcast_id: str) -> Optional[Dict]:
        """Get broadcast by ID."""
        try:
            return self.collection.find_one({"_id": ObjectId(broadcast_id)})
        except:
            return None
    
    def get_active_broadcasts(self, tenant_id: str = None, admin_id: str = None) -> List[Dict]:
        """
        Get all active broadcasts for a tenant/admin.
        
        Args:
            tenant_id: Filter by tenant (for tenant admins)
            admin_id: Exclude dismissed broadcasts for this admin
        
        Returns:
            List of active broadcasts
        """
        now = now_vietnam()
        
        query = {
            "is_active": True,
            "start_time": {"$lte": now},
            "$or": [
                {"end_time": None},
                {"end_time": {"$gt": now}}
            ]
        }
        
        # Filter by target
        if tenant_id:
            query["$and"] = [
                {"$or": [
                    {"target": TARGET_ALL},
                    {"target_tenants": ObjectId(tenant_id)}
                ]}
            ]
        
        broadcasts = list(self.collection.find(query).sort("created_at", DESCENDING))
        
        # Filter out dismissed broadcasts for this admin
        if admin_id:
            dismissed_ids = self._get_dismissed_broadcast_ids(admin_id)
            broadcasts = [b for b in broadcasts 
                         if b.get("is_dismissible") == False or str(b["_id"]) not in dismissed_ids]
        
        return broadcasts
    
    def _get_dismissed_broadcast_ids(self, admin_id: str) -> set:
        """Get set of broadcast IDs dismissed by an admin."""
        try:
            dismissals = self.dismissals.find({"admin_id": ObjectId(admin_id)})
            return {str(d["broadcast_id"]) for d in dismissals}
        except:
            return set()
    
    def dismiss_broadcast(self, broadcast_id: str, admin_id: str) -> bool:
        """
        Dismiss a broadcast for an admin.
        
        Returns:
            True if successful, False if broadcast is not dismissible
        """
        broadcast = self.get_by_id(broadcast_id)
        if not broadcast:
            return False
        
        if not broadcast.get("is_dismissible", True):
            logger.warning(f"Attempted to dismiss non-dismissible broadcast: {broadcast_id}")
            return False
        
        try:
            self.dismissals.update_one(
                {
                    "broadcast_id": ObjectId(broadcast_id),
                    "admin_id": ObjectId(admin_id)
                },
                {
                    "$set": {
                        "broadcast_id": ObjectId(broadcast_id),
                        "admin_id": ObjectId(admin_id),
                        "dismissed_at": now_vietnam()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error dismissing broadcast: {e}")
            return False
    
    def update_broadcast(self, broadcast_id: str, update_data: Dict) -> bool:
        """Update broadcast."""
        update_data["updated_at"] = now_vietnam()
        
        # Don't allow changing created_by
        update_data.pop("created_by", None)
        update_data.pop("created_at", None)
        
        result = self.collection.update_one(
            {"_id": ObjectId(broadcast_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated broadcast: {broadcast_id}")
            return True
        return False
    
    def deactivate_broadcast(self, broadcast_id: str) -> bool:
        """Deactivate (soft delete) a broadcast."""
        return self.update_broadcast(broadcast_id, {"is_active": False})
    
    def delete_broadcast(self, broadcast_id: str) -> bool:
        """Permanently delete a broadcast and its dismissals."""
        try:
            bid = ObjectId(broadcast_id)
            
            # Delete dismissals
            self.dismissals.delete_many({"broadcast_id": bid})
            
            # Delete broadcast
            result = self.collection.delete_one({"_id": bid})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted broadcast: {broadcast_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting broadcast: {e}")
            return False
    
    def list_broadcasts(self, skip: int = 0, limit: int = 50, 
                        include_inactive: bool = False) -> List[Dict]:
        """List all broadcasts (for Super Admin)."""
        query = {} if include_inactive else {"is_active": True}
        
        cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", DESCENDING)
        return list(cursor)
    
    def count_broadcasts(self, include_inactive: bool = False) -> int:
        """Count all broadcasts."""
        query = {} if include_inactive else {"is_active": True}
        return self.collection.count_documents(query)
    
    def get_broadcast_stats(self) -> Dict:
        """Get broadcast statistics."""
        now = now_vietnam()
        
        return {
            "total": self.collection.count_documents({}),
            "active": self.collection.count_documents({
                "is_active": True,
                "start_time": {"$lte": now},
                "$or": [
                    {"end_time": None},
                    {"end_time": {"$gt": now}}
                ]
            }),
            "scheduled": self.collection.count_documents({
                "is_active": True,
                "start_time": {"$gt": now}
            }),
            "expired": self.collection.count_documents({
                "is_active": True,
                "end_time": {"$lt": now}
            }),
            "by_type": {
                "info": self.collection.count_documents({"type": BROADCAST_INFO, "is_active": True}),
                "warning": self.collection.count_documents({"type": BROADCAST_WARNING, "is_active": True}),
                "danger": self.collection.count_documents({"type": BROADCAST_DANGER, "is_active": True}),
            }
        }
