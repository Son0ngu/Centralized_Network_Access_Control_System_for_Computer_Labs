"""
Audit Controller - Xem audit logs (Admin only).
- /admin/audit/*
"""

import logging
from flask import Blueprint, request, jsonify, g
from typing import Tuple

from services.audit_service import AuditService
from middleware.rbac import require_login, require_permission

logger = logging.getLogger(__name__)


class AuditController:
    """Controller for audit log viewing (Admin only)"""

    def __init__(self, audit_service: AuditService, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audit_service = audit_service
        self.socketio = socketio
        self.blueprint = Blueprint('admin_audit', __name__)
        self._register_routes()

    def _register_routes(self):
        """Register routes"""
        self.blueprint.add_url_rule(
            '/admin/audit', 'list', self.list_logs, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/admin/audit/user/<user_id>', 'user_activity',
            self.user_activity, methods=['GET']
        )

    def _success(self, data=None, message="Success", status_code=200) -> Tuple:
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return jsonify(response), status_code

    def _error(self, message: str, status_code=400) -> Tuple:
        return jsonify({"success": False, "error": message}), status_code

    # ========================================================================
    # ENDPOINTS
    # ========================================================================

    @require_login
    @require_permission("audit:read")
    def list_logs(self):
        """
        GET /api/admin/audit?action=user.create&resource_type=users&limit=100&skip=0
        """
        try:
            query = {}

            action = request.args.get("action")
            if action:
                query["action"] = action

            resource_type = request.args.get("resource_type")
            if resource_type:
                query["resource_type"] = resource_type

            username = request.args.get("username")
            if username:
                query["username"] = {"$regex": username, "$options": "i"}

            limit = min(int(request.args.get("limit", 100)), 500)
            skip = int(request.args.get("skip", 0))

            logs = self.audit_service.get_logs(query, limit, skip)
            total = self.audit_service.count_logs(query)

            return self._success({
                "logs": logs,
                "total": total,
                "limit": limit,
                "skip": skip,
            })

        except Exception as e:
            self.logger.error(f"List audit logs error: {e}")
            return self._error("Lay audit logs that bai", 500)

    @require_login
    @require_permission("audit:read")
    def user_activity(self, user_id):
        """
        GET /api/admin/audit/user/<user_id>?limit=50
        """
        try:
            limit = min(int(request.args.get("limit", 50)), 200)
            logs = self.audit_service.get_user_activity(user_id, limit)
            return self._success({"logs": logs})
        except Exception as e:
            self.logger.error(f"User activity error: {e}")
            return self._error("Lay activity that bai", 500)
