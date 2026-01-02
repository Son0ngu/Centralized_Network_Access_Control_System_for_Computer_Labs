"""
Impersonation Log Model - Audit trail for Super Admin impersonation
--------------------------------------------------------------------
Tracks when Super Admin "logs in as" a Tenant Admin for debugging/support.

Security features:
- All impersonation sessions are logged with reason
- Actions performed during impersonation are tracked
- Sessions auto-expire after max_duration
- Full audit trail for compliance
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam

logger = logging.getLogger(__name__)

# Impersonation configuration
IMPERSONATION_MAX_DURATION_HOURS = 4
IMPERSONATION_ALLOWED_ACTIONS = [
    "view_dashboard",
    "view_agents",
    "view_logs",
    "view_whitelist",
    "view_groups",
    "view_api_keys",
    # Note: No write/delete actions allowed during impersonation
]


class ImpersonationLogModel:
    """Model for impersonation audit logging."""
    
    def __init__(self, db: Database):
        self.db = db
        self.collection: Collection = db.impersonation_logs
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create database indexes."""
        self.collection.create_index([("super_admin_id", ASCENDING)])
        self.collection.create_index([("target_tenant_id", ASCENDING)])
        self.collection.create_index([("target_admin_id", ASCENDING)])
        self.collection.create_index([("started_at", DESCENDING)])
        self.collection.create_index([("ended_at", ASCENDING)])
        self.collection.create_index([("session_id", ASCENDING)], unique=True)
        self.collection.create_index([("is_active", ASCENDING)])
    
    def start_impersonation(self, impersonation_data: Dict) -> Dict:
        """
        Start an impersonation session.
        
        Args:
            impersonation_data: {
                "super_admin_id": "ObjectId of Super Admin",
                "target_tenant_id": "ObjectId of target Tenant",
                "target_admin_id": "ObjectId of target Tenant Admin (optional)",
                "reason": "Support ticket #123 - debugging agent sync issue",
                "ip_address": "192.168.1.100"
            }
        
        Returns:
            Impersonation session document with session_id
        """
        import secrets
        
        if not impersonation_data.get("reason"):
            raise ValueError("Reason is required for impersonation")
        
        now = now_vietnam()
        
        # Generate unique session ID
        session_id = secrets.token_urlsafe(32)
        
        # Calculate expiry time
        expires_at = now + timedelta(hours=IMPERSONATION_MAX_DURATION_HOURS)
        
        session = {
            "session_id": session_id,
            "super_admin_id": ObjectId(impersonation_data["super_admin_id"]),
            "target_tenant_id": ObjectId(impersonation_data["target_tenant_id"]),
            "target_admin_id": ObjectId(impersonation_data["target_admin_id"]) 
                if impersonation_data.get("target_admin_id") else None,
            "reason": impersonation_data["reason"],
            "ip_address": impersonation_data.get("ip_address"),
            "started_at": now,
            "ended_at": None,
            "expires_at": expires_at,
            "is_active": True,
            "actions_performed": [],  # Will be updated as actions happen
            "end_reason": None,  # manual, expired, error
        }
        
        result = self.collection.insert_one(session)
        session["_id"] = result.inserted_id
        
        logger.warning(
            f"IMPERSONATION STARTED: Super Admin {impersonation_data['super_admin_id']} "
            f"→ Tenant {impersonation_data['target_tenant_id']} "
            f"| Reason: {impersonation_data['reason']} "
            f"| Session: {session_id[:16]}..."
        )
        
        return session
    
    def end_impersonation(self, session_id: str, end_reason: str = "manual") -> bool:
        """
        End an impersonation session.
        
        Args:
            session_id: The impersonation session ID
            end_reason: "manual" | "expired" | "error"
        
        Returns:
            True if successful
        """
        now = now_vietnam()
        
        result = self.collection.update_one(
            {"session_id": session_id, "is_active": True},
            {"$set": {
                "ended_at": now,
                "is_active": False,
                "end_reason": end_reason
            }}
        )
        
        if result.modified_count > 0:
            session = self.get_by_session_id(session_id)
            if session:
                duration = (now - session["started_at"]).total_seconds() / 60
                actions_count = len(session.get("actions_performed", []))
                logger.warning(
                    f"IMPERSONATION ENDED: Session {session_id[:16]}... "
                    f"| Duration: {duration:.1f} min "
                    f"| Actions: {actions_count} "
                    f"| Reason: {end_reason}"
                )
            return True
        return False
    
    def log_action(self, session_id: str, action: str, details: Dict = None) -> bool:
        """
        Log an action performed during impersonation.
        
        Args:
            session_id: The impersonation session ID
            action: Action type (e.g., "view_agents", "view_logs")
            details: Additional details about the action
        """
        now = now_vietnam()
        
        action_log = {
            "action": action,
            "timestamp": now,
            "details": details or {}
        }
        
        result = self.collection.update_one(
            {"session_id": session_id, "is_active": True},
            {"$push": {"actions_performed": action_log}}
        )
        
        return result.modified_count > 0
    
    def add_action_to_session(self, session_id: str, action_log: Dict) -> bool:
        """
        Add a detailed action log to a session.
        
        Args:
            session_id: The impersonation session ID
            action_log: {
                "timestamp": datetime,
                "action": str,
                "method": str,
                "path": str,
                "request_summary": dict (optional),
                "response_status": int,
                "success": bool,
                "error": str (optional)
            }
        """
        result = self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"actions_performed": action_log},
                "$inc": {"action_count": 1}
            }
        )
        return result.modified_count > 0
    
    def expire_old_sessions(self) -> int:
        """
        Expire sessions that have exceeded max duration.
        Called by scheduler or manually.
        
        Returns:
            Number of sessions expired
        """
        now = now_vietnam()
        
        result = self.collection.update_many(
            {
                "is_active": True,
                "expires_at": {"$lte": now}
            },
            {"$set": {
                "is_active": False,
                "ended_at": now,
                "end_reason": "expired"
            }}
        )
        
        if result.modified_count > 0:
            logger.warning(f"AUTO-EXPIRED: {result.modified_count} impersonation session(s)")
        
        return result.modified_count
    
    def get_by_session_id(self, session_id: str) -> Optional[Dict]:
        """Get impersonation session by session ID."""
        return self.collection.find_one({"session_id": session_id})
    
    def get_active_session(self, super_admin_id: str) -> Optional[Dict]:
        """Get active impersonation session for a Super Admin."""
        now = now_vietnam()
        
        # Also check for expired sessions and end them
        self._expire_old_sessions()
        
        return self.collection.find_one({
            "super_admin_id": ObjectId(super_admin_id),
            "is_active": True,
            "expires_at": {"$gt": now}
        })
    
    def _expire_old_sessions(self):
        """Expire sessions that have exceeded max duration."""
        now = now_vietnam()
        
        result = self.collection.update_many(
            {
                "is_active": True,
                "expires_at": {"$lte": now}
            },
            {"$set": {
                "is_active": False,
                "ended_at": now,
                "end_reason": "expired"
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Auto-expired {result.modified_count} impersonation session(s)")
    
    def is_valid_session(self, session_id: str) -> bool:
        """Check if a session is valid and active."""
        now = now_vietnam()
        
        session = self.collection.find_one({
            "session_id": session_id,
            "is_active": True,
            "expires_at": {"$gt": now}
        })
        
        return session is not None
    
    def list_sessions(self, filters: Dict = None, skip: int = 0, limit: int = 50) -> List[Dict]:
        """
        List impersonation sessions (for audit purposes).
        
        Args:
            filters: {
                "super_admin_id": Filter by Super Admin,
                "target_tenant_id": Filter by target tenant,
                "is_active": True/False,
                "from_date": datetime,
                "to_date": datetime
            }
        """
        query = {}
        
        if filters:
            if filters.get("super_admin_id"):
                query["super_admin_id"] = ObjectId(filters["super_admin_id"])
            if filters.get("target_tenant_id"):
                query["target_tenant_id"] = ObjectId(filters["target_tenant_id"])
            if "is_active" in filters:
                query["is_active"] = filters["is_active"]
            if filters.get("from_date"):
                query["started_at"] = {"$gte": filters["from_date"]}
            if filters.get("to_date"):
                query.setdefault("started_at", {})
                query["started_at"]["$lte"] = filters["to_date"]
        
        cursor = self.collection.find(query).skip(skip).limit(limit).sort("started_at", DESCENDING)
        return list(cursor)
    
    def count_sessions(self, filters: Dict = None) -> int:
        """Count impersonation sessions."""
        query = {}
        
        if filters:
            if filters.get("super_admin_id"):
                query["super_admin_id"] = ObjectId(filters["super_admin_id"])
            if filters.get("target_tenant_id"):
                query["target_tenant_id"] = ObjectId(filters["target_tenant_id"])
            if "is_active" in filters:
                query["is_active"] = filters["is_active"]
        
        return self.collection.count_documents(query)
    
    def get_session_with_details(self, session_id: str) -> Optional[Dict]:
        """
        Get session with Super Admin and Tenant details (aggregation).
        """
        try:
            pipeline = [
                {"$match": {"session_id": session_id}},
                {"$lookup": {
                    "from": "admins",
                    "localField": "super_admin_id",
                    "foreignField": "_id",
                    "as": "super_admin"
                }},
                {"$lookup": {
                    "from": "tenants",
                    "localField": "target_tenant_id",
                    "foreignField": "_id",
                    "as": "target_tenant"
                }},
                {"$unwind": {"path": "$super_admin", "preserveNullAndEmptyArrays": True}},
                {"$unwind": {"path": "$target_tenant", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "super_admin.password_hash": 0,
                    "super_admin.password_history": 0,
                    "super_admin.2fa_secret": 0,
                    "super_admin.backup_codes": 0
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting session details: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get impersonation statistics."""
        now = now_vietnam()
        
        return {
            "total_sessions": self.collection.count_documents({}),
            "active_sessions": self.collection.count_documents({
                "is_active": True,
                "expires_at": {"$gt": now}
            }),
            "sessions_today": self.collection.count_documents({
                "started_at": {"$gte": now.replace(hour=0, minute=0, second=0)}
            }),
            "average_duration_minutes": self._calculate_average_duration()
        }
    
    def _calculate_average_duration(self) -> float:
        """Calculate average session duration in minutes."""
        try:
            pipeline = [
                {"$match": {"ended_at": {"$ne": None}}},
                {"$project": {
                    "duration": {
                        "$divide": [
                            {"$subtract": ["$ended_at", "$started_at"]},
                            60000  # Convert ms to minutes
                        ]
                    }
                }},
                {"$group": {
                    "_id": None,
                    "avg_duration": {"$avg": "$duration"}
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            return round(result[0]["avg_duration"], 2) if result else 0
        except:
            return 0
