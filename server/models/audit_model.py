"""
Audit Model - Records every data-changing action.
- Format action: resource.action (e.g. user.create, whitelist.update)
- Stores change diff JSON in the details field
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam


class AuditModel:
    """Model for audit log operations (collection: audit_logs)"""

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.audit_logs
        self._setup_indexes()

    def _setup_indexes(self):
        """Setup indexes for audit_logs collection"""
        try:
            self.collection.create_index([("timestamp", DESCENDING)])
            self.collection.create_index([("user_id", ASCENDING)])
            self.collection.create_index([("action", ASCENDING)])
            self.collection.create_index([("resource_type", ASCENDING)])
            self.collection.create_index([("resource_id", ASCENDING)])
            # Compound for querying by user + time range
            self.collection.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            self.logger.info("Audit indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating audit indexes: {e}")

    # ========================================================================
    # CREATE
    # ========================================================================

    def log(self, audit_data: Dict) -> Dict:
        """Create an audit log entry"""
        try:
            audit_data["timestamp"] = now_vietnam()
            result = self.collection.insert_one(audit_data)
            audit_data["_id"] = result.inserted_id
            return audit_data
        except Exception as e:
            self.logger.error(f"Error creating audit log: {e}")
            # Audit logging should never block the main operation
            return {}

    # ========================================================================
    # READ
    # ========================================================================

    def get_logs(self, query: Dict = None, limit: int = 100, skip: int = 0) -> List[Dict]:
        """Get audit logs with optional filtering"""
        try:
            if query is None:
                query = {}
            return list(
                self.collection.find(query)
                .sort("timestamp", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
        except Exception as e:
            self.logger.error(f"Error getting audit logs: {e}")
            return []

    def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get audit logs for a specific user"""
        try:
            return list(
                self.collection.find({"user_id": ObjectId(user_id)})
                .sort("timestamp", DESCENDING)
                .limit(limit)
            )
        except Exception as e:
            self.logger.error(f"Error getting user activity: {e}")
            return []

    def count_logs(self, query: Dict = None) -> int:
        """Count audit logs"""
        try:
            if query is None:
                query = {}
            return self.collection.count_documents(query)
        except Exception as e:
            self.logger.error(f"Error counting audit logs: {e}")
            return 0
