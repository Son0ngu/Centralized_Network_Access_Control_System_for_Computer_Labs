"""
Log Controller - handles log HTTP requests
RBAC: inject_current_user on web-facing endpoints for teacher data filtering.
- Agent endpoint (receive_logs via POST) keeps require_jwt - NOT affected
- Web-facing endpoints apply teacher ownership filter (logs from teacher's agents only)
- Teacher does NOT have logs:delete or logs:export permissions
"""

from datetime import timedelta
from flask import Blueprint, request, jsonify, Response, g
from typing import Dict, Tuple
from models.log_model import LogModel
from services.log_service import LogService
from services.rbac_service import RBACService
from utils.request_ip import get_client_ip
import logging

# Import time utilities - vietnam ONLY
from time_utils import now_iso, now_vietnam

# Import auth middleware for JWT validation
from middleware.auth import require_jwt
from middleware.rbac import inject_current_user

from config.rbac_config import check_permission


class LogController:
    """Controller for log operations"""

    def __init__(self, log_model: LogModel, log_service: LogService,
                 rbac_service: RBACService, socketio=None):
        self.model = log_model
        self.service = log_service
        self.rbac_service = rbac_service
        self.socketio = socketio
        self.logger = logging.getLogger(self.__class__.__name__)

        self.blueprint = Blueprint('logs', __name__)
        self._register_routes()

    def _register_routes(self):
        """Register all log routes.

        Canonical endpoints:
          - GET    /api/logs/stats   — statistics
          - POST   /api/logs         — agents push logs (JWT)
          - GET    /api/logs         — list logs (web)
          - DELETE /api/logs/clear   — clear logs (admin)
          - GET    /api/logs/export  — export (admin)

        Legacy alias ``DELETE /api/logs`` now returns 410 Gone (kept registered
        only so reverse-proxy logs surface the deprecation cleanly). Drop the
        route entirely once stale clients are gone.
        """

        # Stats route MUST be before generic /logs route
        self.blueprint.add_url_rule('/logs/stats',
                                   methods=['GET'],
                                   view_func=inject_current_user(self.get_log_statistics))

        # POST /api/logs - Receive logs from agents (requires JWT - NOT affected)
        self.blueprint.add_url_rule('/logs',
                                   methods=['POST'],
                                   view_func=require_jwt(self.receive_logs))

        # GET /api/logs - List logs (web-facing - teacher filtered)
        self.blueprint.add_url_rule('/logs',
                                   methods=['GET'],
                                   view_func=inject_current_user(self.list_logs))

        # DELETE /api/logs/clear - Clear logs (web-facing - teacher blocked)
        self.blueprint.add_url_rule('/logs/clear',
                                   methods=['DELETE'],
                                   endpoint='clear_logs',
                                   view_func=inject_current_user(self.clear_logs))

        # DELETE /api/logs - DEPRECATED. Returns 410 Gone pointing at /logs/clear.
        self.blueprint.add_url_rule('/logs',
                                   methods=['DELETE'],
                                   endpoint='clear_logs_legacy',
                                   view_func=self._gone_clear_logs_legacy)

        # GET /api/logs/export - Export logs (web-facing - teacher blocked)
        self.blueprint.add_url_rule('/logs/export',
                                   methods=['GET'],
                                   view_func=inject_current_user(self.export_logs))

    def _gone_clear_logs_legacy(self):
        """Deprecated DELETE /api/logs → 410 Gone.

        Old clients hitting this endpoint should be migrated to DELETE /api/logs/clear.
        We emit a Deprecation hint header so reverse-proxy access logs can surface
        which client is still calling the old path before it is removed entirely.
        """
        self.logger.warning(
            "Deprecated endpoint hit: DELETE /api/logs (use /api/logs/clear). "
            "Caller=%s UA=%s",
            get_client_ip(),
            request.headers.get("User-Agent", "?"),
        )
        resp = jsonify({
            "success": False,
            "error": "DELETE /api/logs is deprecated. Use DELETE /api/logs/clear.",
            "code": "ENDPOINT_GONE",
            "replacement": "/api/logs/clear",
            "timestamp": now_iso(),
        })
        resp.status_code = 410
        # RFC 8594 deprecation signalling
        resp.headers["Deprecation"] = "true"
        resp.headers["Link"] = '</api/logs/clear>; rel="successor-version"'
        return resp

    # ========================================================================
    # RBAC HELPERS
    # ========================================================================

    def _is_teacher(self):
        """Thin wrapper — calls ``RBACService.is_teacher_request`` statically.

        Static so a mocked ``rbac_service`` in tests doesn't swallow the call
        and return a MagicMock instead of the expected ``(bool, user)`` tuple.
        """
        return RBACService.is_teacher_request(getattr(g, 'current_user', None))

    def _get_teacher_log_filter(self, user):
        """Get log filter for teacher - only logs from agents in teacher's groups."""
        return self.rbac_service.get_log_query_filter(user)

    # ========================================================================
    # AGENT ENDPOINT (NOT affected by RBAC)
    # ========================================================================

    def receive_logs(self):
        """Receive logs from agent"""
        try:
            if not request.is_json:
                return self._error_response("Request must be JSON", 400)

            data = request.get_json()
            if not data:
                return self._error_response("Invalid JSON data", 400)

            agent_id = request.headers.get('X-Agent-ID') or data.get('agent_id')
            client_ip = get_client_ip()

            self.logger.info(f"Receiving logs from agent {agent_id} at {client_ip}")

            result = self.service.receive_logs(data, agent_id)

            if result.get("success"):
                return jsonify(result), 201
            else:
                return self._error_response(result.get("error", "Failed to process logs"), 400)

        except Exception as e:
            self.logger.error(f"Error receiving logs: {e}")
            return self._error_response("Failed to receive logs", 500)

    # ========================================================================
    # WEB-FACING ENDPOINTS (with teacher data filtering)
    # ========================================================================

    def list_logs(self):
        """Get all logs with filtering and pagination"""
        try:
            filters = self._get_filter_params()
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))

            self.logger.info(f"List logs called with filters: {filters}")

            # RBAC: Teacher only sees logs from agents in their groups
            is_teacher, user = self._is_teacher()
            if is_teacher:
                teacher_filter = self._get_teacher_log_filter(user)
                if teacher_filter:
                    # Use $and to avoid overwriting user-supplied filters
                    if filters:
                        filters = {"$and": [teacher_filter, filters]}
                    else:
                        filters = teacher_filter

            result = self.service.get_all_logs(filters, limit, offset)

            response_data = {
                **result,
                'applied_filters': str(filters)
            }

            return jsonify(response_data), 200

        except Exception as e:
            self.logger.error(f"Error listing logs: {e}")
            return self._error_response("Failed to list logs", 500)

    def clear_logs(self):
        """Clear logs with optional filters"""
        try:
            # RBAC: Teacher does NOT have logs:delete permission
            is_teacher, user = self._is_teacher()
            if is_teacher:
                return self._error_response("Insufficient permissions to delete logs", 403)

            if request.is_json:
                data = request.get_json() or {}
            else:
                data = {}

            filters = {}
            query_filters = self._get_filter_params()
            if query_filters:
                filters.update(query_filters)
            if data.get('filters'):
                filters.update(data['filters'])

            clear_action = data.get('action', 'all')

            if clear_action == 'selected' and data.get('log_ids'):
                from bson import ObjectId
                log_ids = data['log_ids']
                object_ids = []
                for log_id in log_ids:
                    try:
                        object_ids.append(ObjectId(log_id))
                    except Exception:
                        pass
                if object_ids:
                    filters['_id'] = {'$in': object_ids}

            elif clear_action == 'old':
                cutoff_time = now_vietnam() - timedelta(days=30)
                filters['timestamp'] = {'$lt': cutoff_time}

            self.logger.info(f"Clearing logs with action: {clear_action}, filters: {filters}")

            result = self.service.clear_logs(filters)

            if result.get("success"):
                if self.socketio:
                    self.socketio.emit('logs_cleared', {
                        'action': clear_action,
                        'deleted_count': result.get('deleted_count', 0),
                        'timestamp': now_iso()
                    })
                return jsonify(result), 200
            else:
                return self._error_response(result.get("error", "Failed to clear logs"), 500)

        except Exception as e:
            self.logger.error(f"Error clearing logs: {e}")
            import traceback
            traceback.print_exc()
            return self._error_response("Failed to clear logs", 500)

    def export_logs(self):
        """Export logs"""
        try:
            # RBAC: Teacher does NOT have logs:export permission
            is_teacher, user = self._is_teacher()
            if is_teacher:
                return self._error_response("Insufficient permissions to export logs", 403)

            filters = self._get_filter_params()
            format = request.args.get('format', 'json')

            result = self.service.export_logs(filters, format)

            if result.get("success"):
                if format == 'csv':
                    return Response(
                        result["data"], mimetype="text/csv",
                        headers={"Content-disposition": "attachment; filename=logs.csv"}
                    )
                else:
                    return jsonify(result), 200
            else:
                return self._error_response(result.get("error", "Failed to export logs"), 500)

        except Exception as e:
            self.logger.error(f"Error exporting logs: {e}")
            return self._error_response("Failed to export logs", 500)

    def get_log_statistics(self):
        """Get comprehensive log statistics for frontend"""
        try:
            filters = self._get_filter_params()

            # RBAC: Teacher only sees stats from their agents
            is_teacher, user = self._is_teacher()
            if is_teacher:
                teacher_filter = self._get_teacher_log_filter(user)
                if teacher_filter:
                    if filters:
                        filters = {"$and": [teacher_filter, filters]}
                    else:
                        filters = teacher_filter

            self.logger.info(f"Getting log statistics with filters: {filters}")
            stats = self.service.get_comprehensive_statistics(filters)
            self.logger.info(f"Statistics calculated: {stats}")

            return jsonify({
                "success": True,
                "total": stats.get("total", 0),
                "allowed": stats.get("allowed", 0),
                "blocked": stats.get("blocked", 0),
                "warnings": stats.get("warnings", 0),
                "filtered_total": stats.get("filtered_total", 0),
                "filtered_allowed": stats.get("filtered_allowed", 0),
                "filtered_blocked": stats.get("filtered_blocked", 0),
                "filtered_warnings": stats.get("filtered_warnings", 0),
                "has_filters": stats.get("has_filters", False),
                "timestamp": now_iso()
            }), 200

        except Exception as e:
            self.logger.error(f"Error getting log statistics: {e}")
            return jsonify({
                "success": False, "error": str(e),
                "total": 0, "allowed": 0, "blocked": 0, "warnings": 0,
                "timestamp": now_iso()
            }), 500

    # Backwards-compat alias. ``get_statistics`` used to be a separate route
    # wrapper that just delegated to ``get_log_statistics``. The route now
    # binds directly to ``get_log_statistics`` (see ``_register_routes``), but
    # tests still call ``ctrl.get_statistics()`` so we keep the method.
    get_statistics = get_log_statistics

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _get_filter_params(self) -> Dict:
        """Extract filter parameters from request"""
        filters = {}
        if request.args.get('level'):
            filters['level'] = request.args.get('level')
        if request.args.get('action'):
            filters['action'] = request.args.get('action')
        if request.args.get('agent_id'):
            filters['agent_id'] = request.args.get('agent_id')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        if request.args.get('time_range'):
            filters['time_range'] = request.args.get('time_range')
        if request.args.get('start_date'):
            filters['start_date'] = request.args.get('start_date')
        if request.args.get('end_date'):
            filters['end_date'] = request.args.get('end_date')
        return filters

    def _error_response(self, message: str, status_code: int) -> Tuple:
        """Create error response - vietnam only"""
        return jsonify({
            "success": False, "error": message, "timestamp": now_iso()
        }), status_code
