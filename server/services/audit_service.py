"""
Audit Service - Ghi log moi hanh dong thay doi du lieu.
- Format action: resource.action (e.g. user.create, whitelist.update)
- Ghi nhan user, role, IP, timestamp, change details
"""

import logging
from typing import Dict, List, Optional

from bson import ObjectId
from flask import request as flask_request

from models.audit_model import AuditModel

logger = logging.getLogger(__name__)


class AuditService:
    """Service for audit logging"""

    def __init__(self, audit_model: AuditModel):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audit_model = audit_model

    def log_action(self, user: Dict, action: str, resource_type: str,
                   resource_id: str = None, details: Dict = None,
                   ip_address: str = None):
        """
        Log an action to the audit trail.

        Args:
            user: User dict (must have _id, username, role)
            action: Action string (e.g. "user.create", "auth.login", "whitelist.update")
            resource_type: Resource type (e.g. "users", "groups", "whitelist", "auth")
            resource_id: ID of the affected resource (optional)
            details: Change diff or additional info (optional)
            ip_address: Client IP address (optional, auto-detect from request)
        """
        try:
            # Auto-detect IP if not provided
            if ip_address is None:
                try:
                    ip_address = flask_request.remote_addr
                except RuntimeError:
                    ip_address = "unknown"

            audit_data = {
                "user_id": user.get("_id") if isinstance(user.get("_id"), ObjectId)
                           else ObjectId(user["_id"]) if user.get("_id") else None,
                "username": user.get("username", "unknown"),
                "role": user.get("role", "unknown"),
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "details": details or {},
                "ip_address": ip_address,
            }

            self.audit_model.log(audit_data)

            self.logger.debug(
                f"Audit: {user.get('username')}({user.get('role')}) "
                f"{action} on {resource_type}"
                f"{f'/{resource_id}' if resource_id else ''}"
            )

        except Exception as e:
            # Audit logging should NEVER block the main operation
            self.logger.error(f"Audit logging failed: {e}")

    def get_logs(self, query: Dict = None, limit: int = 100,
                 skip: int = 0) -> List[Dict]:
        """Get audit logs with optional filtering"""
        logs = self.audit_model.get_logs(query, limit, skip)
        return [self._serialize(log) for log in logs]

    def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get activity logs for a specific user"""
        logs = self.audit_model.get_user_activity(user_id, limit)
        return [self._serialize(log) for log in logs]

    def count_logs(self, query: Dict = None) -> int:
        """Count audit logs"""
        return self.audit_model.count_logs(query)

    @staticmethod
    def _serialize(log: Dict) -> Dict:
        """Convert ObjectId to string for JSON serialization"""
        if "_id" in log:
            log["_id"] = str(log["_id"])
        if "user_id" in log and log["user_id"]:
            log["user_id"] = str(log["user_id"])
        return log
