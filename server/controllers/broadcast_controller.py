"""
Broadcast Controller - handles broadcast HTTP requests
-------------------------------------------------------
Handles system broadcast APIs for Super Admin and Tenant Admin.
"""

import logging
from flask import Blueprint, request, jsonify, g
from functools import wraps

from middleware.auth import require_jwt
from middleware.authorization import require_super_admin
from middleware.security import require_rate_limit, sanitize_request_data, add_security_headers

logger = logging.getLogger(__name__)


def require_tenant_admin(f):
    """Decorator to require tenant admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'admin') or not g.admin:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        if g.admin.get("role") not in ["tenant_admin", "super_admin"]:
            return jsonify({"success": False, "error": "Tenant admin access required"}), 403
        
        return f(*args, **kwargs)
    return decorated


class BroadcastController:
    """Controller for broadcast operations."""
    
    def __init__(self, broadcast_service, socketio=None):
        self.broadcast_service = broadcast_service
        self.socketio = socketio
        self.blueprint = Blueprint('broadcasts', __name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register all broadcast routes."""
        
        # ============ Super Admin Routes ============
        
        # Create broadcast
        self.blueprint.route('/create', methods=['POST'])(
            require_jwt(
                require_super_admin(
                    require_rate_limit('api_call')(
                        sanitize_request_data(self.create_broadcast)
                    )
                )
            )
        )
        
        # Update broadcast
        self.blueprint.route('/<broadcast_id>', methods=['PUT'])(
            require_jwt(
                require_super_admin(
                    sanitize_request_data(self.update_broadcast)
                )
            )
        )
        
        # Deactivate broadcast
        self.blueprint.route('/<broadcast_id>/deactivate', methods=['POST'])(
            require_jwt(
                require_super_admin(self.deactivate_broadcast)
            )
        )
        
        # Delete broadcast
        self.blueprint.route('/<broadcast_id>', methods=['DELETE'])(
            require_jwt(
                require_super_admin(self.delete_broadcast)
            )
        )
        
        # List all broadcasts (Super Admin)
        self.blueprint.route('/list', methods=['GET'])(
            require_jwt(
                require_super_admin(self.list_broadcasts)
            )
        )
        
        # Get broadcast by ID (Super Admin)
        self.blueprint.route('/<broadcast_id>', methods=['GET'])(
            require_jwt(
                require_super_admin(self.get_broadcast)
            )
        )
        
        # Get broadcast stats (Super Admin)
        self.blueprint.route('/stats', methods=['GET'])(
            require_jwt(
                require_super_admin(self.get_broadcast_stats)
            )
        )
        
        # ============ Tenant Admin Routes ============
        
        # Get active broadcasts for current admin
        self.blueprint.route('/active', methods=['GET'])(
            require_jwt(
                require_tenant_admin(self.get_active_broadcasts)
            )
        )
        
        # Dismiss a broadcast
        self.blueprint.route('/<broadcast_id>/dismiss', methods=['POST'])(
            require_jwt(
                require_tenant_admin(self.dismiss_broadcast)
            )
        )
        
        # Get client config
        self.blueprint.route('/config', methods=['GET'])(
            require_jwt(self.get_client_config)
        )
        
        # Add security headers to all responses
        @self.blueprint.after_request
        def after_request(response):
            return add_security_headers(response)
    
    # ============ Super Admin Endpoints ============
    
    def create_broadcast(self):
        """
        Create a new system broadcast.
        
        POST /api/broadcasts/create
        
        Body:
            {
                "title": "System Maintenance",
                "message": "The system will be under maintenance from 12:00 to 14:00",
                "type": "warning",  // info, warning, danger
                "priority": "normal",  // normal, high
                "target": "all",  // all, specific
                "target_tenants": [],  // if target=specific
                "start_time": "2026-01-03T00:00:00",  // optional
                "end_time": "2026-01-03T02:00:00"  // optional
            }
        
        Returns:
            Created broadcast
        """
        data = request.get_json() or {}
        admin_id = str(g.admin["_id"])
        
        result = self.broadcast_service.create_broadcast(data, admin_id)
        
        if result.get("success"):
            # Emit WebSocket event for real-time update
            if self.socketio:
                self._emit_broadcast_event("new_broadcast", result["data"])
            
            return jsonify(result), 201
        
        return jsonify(result), 400
    
    def update_broadcast(self, broadcast_id):
        """
        Update an existing broadcast.
        
        PUT /api/broadcasts/<broadcast_id>
        
        Body:
            {
                "title": "Updated Title",
                "message": "Updated message",
                "type": "danger",
                "is_active": true
            }
        
        Returns:
            Updated broadcast
        """
        data = request.get_json() or {}
        admin_id = str(g.admin["_id"])
        
        result = self.broadcast_service.update_broadcast(broadcast_id, data, admin_id)
        
        if result.get("success"):
            # Emit WebSocket event for real-time update
            if self.socketio:
                self._emit_broadcast_event("update_broadcast", result["data"])
            
            return jsonify(result), 200
        
        return jsonify(result), 400
    
    def deactivate_broadcast(self, broadcast_id):
        """
        Deactivate a broadcast (soft delete).
        
        POST /api/broadcasts/<broadcast_id>/deactivate
        
        Returns:
            Success status
        """
        result = self.broadcast_service.deactivate_broadcast(broadcast_id)
        
        if result.get("success"):
            # Emit WebSocket event for real-time update
            if self.socketio:
                self._emit_broadcast_event("remove_broadcast", {"id": broadcast_id})
            
            return jsonify(result), 200
        
        return jsonify(result), 400
    
    def delete_broadcast(self, broadcast_id):
        """
        Permanently delete a broadcast.
        
        DELETE /api/broadcasts/<broadcast_id>
        
        Returns:
            Success status
        """
        result = self.broadcast_service.delete_broadcast(broadcast_id)
        
        if result.get("success"):
            return jsonify(result), 200
        
        return jsonify(result), 400
    
    def list_broadcasts(self):
        """
        List all broadcasts for Super Admin.
        
        GET /api/broadcasts/list?page=1&limit=20&include_inactive=true
        
        Returns:
            List of broadcasts with pagination
        """
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        include_inactive = request.args.get('include_inactive', 'true').lower() == 'true'
        
        # Validate pagination
        page = max(1, page)
        limit = min(100, max(1, limit))
        
        result = self.broadcast_service.list_broadcasts(
            page=page,
            limit=limit,
            include_inactive=include_inactive
        )
        
        return jsonify(result), 200
    
    def get_broadcast(self, broadcast_id):
        """
        Get a single broadcast by ID.
        
        GET /api/broadcasts/<broadcast_id>
        
        Returns:
            Broadcast details
        """
        result = self.broadcast_service.get_broadcast_by_id(broadcast_id)
        
        if result.get("success"):
            return jsonify(result), 200
        
        return jsonify(result), 404
    
    def get_broadcast_stats(self):
        """
        Get broadcast statistics for Super Admin dashboard.
        
        GET /api/broadcasts/stats
        
        Returns:
            Broadcast statistics
        """
        result = self.broadcast_service.get_broadcast_stats()
        return jsonify(result), 200
    
    # ============ Tenant Admin Endpoints ============
    
    def get_active_broadcasts(self):
        """
        Get active broadcasts for the current admin.
        
        GET /api/broadcasts/active
        
        Returns:
            List of active broadcasts for this tenant admin
        """
        admin_id = str(g.admin["_id"])
        tenant_id = str(g.admin.get("tenant_id", ""))
        
        result = self.broadcast_service.get_active_broadcasts_for_admin(
            admin_id=admin_id,
            tenant_id=tenant_id
        )
        
        return jsonify(result), 200
    
    def dismiss_broadcast(self, broadcast_id):
        """
        Dismiss a broadcast for the current admin.
        
        POST /api/broadcasts/<broadcast_id>/dismiss
        
        Returns:
            Success status
        """
        admin_id = str(g.admin["_id"])
        
        result = self.broadcast_service.dismiss_broadcast(broadcast_id, admin_id)
        
        if result.get("success"):
            return jsonify(result), 200
        
        return jsonify(result), 400
    
    def get_client_config(self):
        """
        Get broadcast configuration for client-side JavaScript.
        
        GET /api/broadcasts/config
        
        Returns:
            Client configuration
        """
        result = self.broadcast_service.get_client_config()
        return jsonify(result), 200
    
    # ============ WebSocket Helpers ============
    
    def _emit_broadcast_event(self, event_type: str, data: dict):
        """
        Emit WebSocket event for real-time broadcast updates.
        
        Args:
            event_type: Event name (new_broadcast, update_broadcast, remove_broadcast)
            data: Event data
        """
        if not self.socketio:
            return
        
        try:
            # Determine target room based on broadcast target
            target = data.get("target", "all")
            target_tenants = data.get("target_tenants", [])
            
            if target == "all":
                # Broadcast to all connected admins
                self.socketio.emit(
                    "broadcast_update",
                    {"type": event_type, "data": data},
                    namespace="/admin"
                )
            else:
                # Broadcast to specific tenant rooms
                for tenant_id in target_tenants:
                    self.socketio.emit(
                        "broadcast_update",
                        {"type": event_type, "data": data},
                        room=f"tenant_{tenant_id}",
                        namespace="/admin"
                    )
                    
            logger.info(f"Emitted broadcast event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error emitting broadcast event: {e}")
    
    def send_broadcast_to_all(self, broadcast_data: dict):
        """
        Send a new broadcast to all connected clients immediately.
        Used when a new broadcast is created.
        
        Args:
            broadcast_data: Serialized broadcast data
        """
        self._emit_broadcast_event("new_broadcast", broadcast_data)
