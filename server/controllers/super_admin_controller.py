"""
Super Admin Controller - API endpoints for platform administration
-------------------------------------------------------------------
All endpoints require @require_super_admin decorator.

Routes:
- /api/super/dashboard         - Platform stats
- /api/super/health            - System health
- /api/super/tenants           - Tenant CRUD
- /api/super/admins            - Admin management
- /api/super/impersonate       - Impersonation
- /api/super/broadcasts        - System broadcasts
"""

import logging
from flask import Blueprint, request, jsonify, render_template, g
from typing import Dict, Tuple

from services.super_admin_service import SuperAdminService
from middleware.authorization import require_super_admin, require_any_admin
from time_utils import now_iso

logger = logging.getLogger(__name__)


class SuperAdminController:
    """Controller for Super Admin operations."""
    
    def __init__(self, super_admin_service: SuperAdminService, socketio=None):
        self.service = super_admin_service
        self.socketio = socketio
        self.blueprint = Blueprint('super_admin', __name__, url_prefix='/api/super')
        self.view_blueprint = Blueprint('super_admin_views', __name__, url_prefix='/super-admin')
        self._register_routes()
        self._register_view_routes()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _register_routes(self):
        """Register API routes."""
        # Dashboard & Health
        self.blueprint.add_url_rule(
            '/dashboard', 'dashboard', self.get_dashboard, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/health', 'health', self.get_system_health, methods=['GET']
        )
        
        # Tenant Management
        self.blueprint.add_url_rule(
            '/tenants', 'list_tenants', self.list_tenants, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/tenants', 'create_tenant', self.create_tenant, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/tenants/<tenant_id>', 'get_tenant', self.get_tenant, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/tenants/<tenant_id>', 'update_tenant', self.update_tenant, methods=['PATCH']
        )
        self.blueprint.add_url_rule(
            '/tenants/<tenant_id>', 'delete_tenant', self.delete_tenant, methods=['DELETE']
        )
        self.blueprint.add_url_rule(
            '/tenants/<tenant_id>/suspend', 'suspend_tenant', self.suspend_tenant, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/tenants/<tenant_id>/activate', 'activate_tenant', self.activate_tenant, methods=['POST']
        )
        
        # Admin Management
        self.blueprint.add_url_rule(
            '/admins', 'list_admins', self.list_admins, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/admins', 'create_admin', self.create_admin, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/admins/<admin_id>', 'update_admin', self.update_admin, methods=['PATCH']
        )
        self.blueprint.add_url_rule(
            '/admins/<admin_id>/suspend', 'suspend_admin', self.suspend_admin, methods=['POST']
        )
        
        # Impersonation
        self.blueprint.add_url_rule(
            '/impersonate/<tenant_id>', 'start_impersonation', 
            self.start_impersonation, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/end-impersonation', 'end_impersonation', 
            self.end_impersonation, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/impersonation-logs', 'impersonation_logs', 
            self.get_impersonation_logs, methods=['GET']
        )
        
        # Broadcasts
        self.blueprint.add_url_rule(
            '/broadcasts', 'list_broadcasts', self.list_broadcasts, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/broadcasts', 'create_broadcast', self.create_broadcast, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/broadcasts/<broadcast_id>', 'update_broadcast', 
            self.update_broadcast, methods=['PATCH']
        )
        self.blueprint.add_url_rule(
            '/broadcasts/<broadcast_id>', 'delete_broadcast', 
            self.delete_broadcast, methods=['DELETE']
        )
    
    def _register_view_routes(self):
        """Register view routes for Super Admin UI."""
        self.view_blueprint.add_url_rule(
            '/', 'dashboard_view', self.dashboard_view, methods=['GET']
        )
        self.view_blueprint.add_url_rule(
            '/tenants', 'tenants_view', self.tenants_view, methods=['GET']
        )
        self.view_blueprint.add_url_rule(
            '/admins', 'admins_view', self.admins_view, methods=['GET']
        )
        self.view_blueprint.add_url_rule(
            '/health', 'health_view', self.health_view, methods=['GET']
        )
        self.view_blueprint.add_url_rule(
            '/broadcasts', 'broadcasts_view', self.broadcasts_view, methods=['GET']
        )
        self.view_blueprint.add_url_rule(
            '/impersonation-logs', 'impersonation_logs_view', 
            self.impersonation_logs_view, methods=['GET']
        )
    
    # ========================================================================
    # Response Helpers
    # ========================================================================
    
    def _success_response(self, data=None, message="Success", status_code=200) -> Tuple:
        return jsonify({
            "success": True,
            "message": message,
            "data": data,
            "timestamp": now_iso()
        }), status_code
    
    def _error_response(self, message: str, status_code=400) -> Tuple:
        return jsonify({
            "success": False,
            "error": message,
            "timestamp": now_iso()
        }), status_code
    
    # ========================================================================
    # Dashboard & Health APIs
    # ========================================================================
    
    @require_super_admin
    def get_dashboard(self):
        """Get platform-wide dashboard statistics."""
        result = self.service.get_dashboard_stats()
        if result.get("success"):
            return self._success_response(result.get("data"))
        return self._error_response(result.get("error", "Failed to get stats"))
    
    @require_super_admin
    def get_system_health(self):
        """Get system health for all tenants."""
        result = self.service.get_system_health()
        if result.get("success"):
            return self._success_response(result.get("data"))
        return self._error_response(result.get("error", "Failed to get health"))
    
    # ========================================================================
    # Tenant Management APIs
    # ========================================================================
    
    @require_super_admin
    def list_tenants(self):
        """List all tenants."""
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        status = request.args.get('status')
        
        filters = {}
        if status:
            filters['status'] = status
        
        result = self.service.list_tenants(filters=filters, page=page, limit=limit)
        if result.get("success"):
            return jsonify(result)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def create_tenant(self):
        """Create a new tenant with optional first admin."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        if not data.get("name"):
            return self._error_response("Tenant name is required")
        
        tenant_data = {
            "name": data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "plan": data.get("plan", "free"),
            "max_admins": data.get("max_admins", 5),
            "max_agents": data.get("max_agents", 10),
        }
        
        # Optional first admin
        first_admin = None
        if data.get("admin_email") and data.get("admin_password"):
            first_admin = {
                "email": data.get("admin_email"),
                "password": data.get("admin_password"),
                "full_name": data.get("admin_name", ""),
            }
        
        result = self.service.create_tenant(tenant_data, first_admin)
        if result.get("success"):
            return self._success_response(result, "Tenant created", 201)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def get_tenant(self, tenant_id: str):
        """Get tenant details."""
        result = self.service.get_tenant(tenant_id)
        if result.get("success"):
            return self._success_response(result.get("data"))
        return self._error_response(result.get("error"), 404)
    
    @require_super_admin
    def update_tenant(self, tenant_id: str):
        """Update tenant information."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        result = self.service.update_tenant(tenant_id, data)
        if result.get("success"):
            return self._success_response(result.get("data"), "Tenant updated")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def delete_tenant(self, tenant_id: str):
        """Soft delete a tenant."""
        result = self.service.delete_tenant(tenant_id)
        if result.get("success"):
            return self._success_response(message="Tenant deleted")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def suspend_tenant(self, tenant_id: str):
        """Suspend a tenant."""
        data = request.get_json() or {}
        reason = data.get("reason", "Suspended by Super Admin")
        
        result = self.service.suspend_tenant(tenant_id, reason)
        if result.get("success"):
            return self._success_response(message="Tenant suspended")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def activate_tenant(self, tenant_id: str):
        """Activate a suspended tenant."""
        result = self.service.activate_tenant(tenant_id)
        if result.get("success"):
            return self._success_response(message="Tenant activated")
        return self._error_response(result.get("error"))
    
    # ========================================================================
    # Admin Management APIs
    # ========================================================================
    
    @require_super_admin
    def list_admins(self):
        """List all tenant admins."""
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        tenant_id = request.args.get('tenant_id')
        status = request.args.get('status')
        
        filters = {}
        if tenant_id:
            from bson import ObjectId
            filters['tenant_id'] = ObjectId(tenant_id)
        if status:
            filters['status'] = status
        
        result = self.service.list_all_admins(filters=filters, page=page, limit=limit)
        if result.get("success"):
            return jsonify(result)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def create_admin(self):
        """Create a tenant admin."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        required = ["email", "password", "tenant_id"]
        for field in required:
            if not data.get(field):
                return self._error_response(f"{field} is required")
        
        result = self.service.create_admin(data)
        if result.get("success"):
            return self._success_response(result.get("data"), "Admin created", 201)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def update_admin(self, admin_id: str):
        """Update a tenant admin."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        result = self.service.update_admin(admin_id, data)
        if result.get("success"):
            return self._success_response(result.get("data"), "Admin updated")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def suspend_admin(self, admin_id: str):
        """Suspend a tenant admin."""
        data = request.get_json() or {}
        reason = data.get("reason", "Suspended by Super Admin")
        
        result = self.service.suspend_admin(admin_id, reason)
        if result.get("success"):
            return self._success_response(message="Admin suspended")
        return self._error_response(result.get("error"))
    
    # ========================================================================
    # Impersonation APIs
    # ========================================================================
    
    @require_super_admin
    def start_impersonation(self, tenant_id: str):
        """Start impersonating a tenant."""
        data = request.get_json() or {}
        reason = data.get("reason")
        
        if not reason:
            return self._error_response("Reason is required for impersonation")
        
        admin_context = g.get('admin_context', {})
        super_admin_id = admin_context.get('admin_id')
        
        if not super_admin_id:
            return self._error_response("Not authenticated", 401)
        
        result = self.service.start_impersonation(
            super_admin_id=super_admin_id,
            target_tenant_id=tenant_id,
            reason=reason,
            ip_address=request.remote_addr
        )
        
        if result.get("success"):
            return self._success_response(result, "Impersonation started")
        return self._error_response(result.get("error"))
    
    @require_any_admin  # Allow from impersonation context
    def end_impersonation(self):
        """End current impersonation session."""
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        # Get from JWT if not provided
        if not session_id and hasattr(g, 'impersonation_session_id'):
            session_id = g.impersonation_session_id
        
        if not session_id:
            return self._error_response("Session ID required")
        
        result = self.service.end_impersonation(session_id)
        if result.get("success"):
            return self._success_response(message="Impersonation ended")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def get_impersonation_logs(self):
        """Get impersonation audit logs."""
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        tenant_id = request.args.get('tenant_id')
        
        result = self.service.get_impersonation_logs(
            tenant_id=tenant_id,
            page=page,
            limit=limit
        )
        
        if result.get("success"):
            return jsonify(result)
        return self._error_response(result.get("error"))
    
    # ========================================================================
    # Broadcast APIs
    # ========================================================================
    
    @require_super_admin
    def list_broadcasts(self):
        """List all broadcasts."""
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        result = self.service.list_broadcasts(
            include_inactive=include_inactive,
            page=page,
            limit=limit
        )
        
        if result.get("success"):
            return jsonify(result)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def create_broadcast(self):
        """Create a system broadcast."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        if not data.get("title") or not data.get("message"):
            return self._error_response("Title and message are required")
        
        admin_context = g.get('admin_context', {})
        created_by = admin_context.get('admin_id')
        
        result = self.service.create_broadcast(data, created_by)
        if result.get("success"):
            return self._success_response(result.get("data"), "Broadcast created", 201)
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def update_broadcast(self, broadcast_id: str):
        """Update a broadcast."""
        data = request.get_json()
        if not data:
            return self._error_response("Request body required")
        
        result = self.service.update_broadcast(broadcast_id, data)
        if result.get("success"):
            return self._success_response(result.get("data"), "Broadcast updated")
        return self._error_response(result.get("error"))
    
    @require_super_admin
    def delete_broadcast(self, broadcast_id: str):
        """Deactivate a broadcast."""
        result = self.service.delete_broadcast(broadcast_id)
        if result.get("success"):
            return self._success_response(message="Broadcast deactivated")
        return self._error_response(result.get("error"))
    
    # ========================================================================
    # View Routes (HTML pages)
    # ========================================================================
    
    def dashboard_view(self):
        """Render Super Admin dashboard page."""
        return render_template('super_admin/dashboard.html')
    
    def tenants_view(self):
        """Render tenant management page."""
        return render_template('super_admin/tenants.html')
    
    def admins_view(self):
        """Render admin management page."""
        return render_template('super_admin/admins.html')
    
    def health_view(self):
        """Render system health page."""
        return render_template('super_admin/health.html')
    
    def broadcasts_view(self):
        """Render broadcasts management page."""
        return render_template('super_admin/broadcasts.html')
    
    def impersonation_logs_view(self):
        """Render impersonation logs page."""
        return render_template('super_admin/impersonation_logs.html')
