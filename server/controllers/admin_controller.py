"""
Admin Controller - handles admin HTTP requests
-----------------------------------------------
Handles admin authentication, management, and multi-tenant operations.
"""

import logging
from flask import Blueprint, request, jsonify, g
from typing import Dict, Tuple

from models.admin_model import AdminModel
from models.tenant_model import TenantModel
from services.admin_service import AdminService
from middleware.security import require_rate_limit, sanitize_request_data, add_security_headers
from time_utils import now_iso

logger = logging.getLogger(__name__)


class AdminController:
    """Controller for admin operations."""
    
    def __init__(self, admin_model: AdminModel, tenant_model: TenantModel, admin_service: AdminService, socketio=None):
        self.admin_model = admin_model
        self.tenant_model = tenant_model
        self.admin_service = admin_service
        self.socketio = socketio
        self.blueprint = Blueprint('admin', __name__)  # No url_prefix here, set in app.py
        self._register_routes()
    
    def _register_routes(self):
        """Register all admin routes."""
        
        # Authentication
        self.blueprint.route('/login', methods=['POST'])(
            require_rate_limit('login')(
                sanitize_request_data(self.login)
            )
        )
        self.blueprint.route('/register', methods=['POST'])(
            require_rate_limit('register')(
                sanitize_request_data(self.register)
            )
        )
        self.blueprint.route('/logout', methods=['POST'])(self.logout)
        self.blueprint.route('/verify-2fa', methods=['POST'])(
            require_rate_limit('login')(
                sanitize_request_data(self.verify_2fa)
            )
        )
        self.blueprint.route('/set-session', methods=['POST'])(self.set_session)
        
        # Profile management
        self.blueprint.route('/profile', methods=['GET'])(self.get_profile)
        self.blueprint.route('/profile', methods=['PUT'])(
            sanitize_request_data(self.update_profile)
        )
        self.blueprint.route('/change-password', methods=['POST'])(
            sanitize_request_data(self.change_password)
        )
        
        # 2FA management
        self.blueprint.route('/2fa/enable', methods=['POST'])(
            sanitize_request_data(self.enable_2fa)
        )
        self.blueprint.route('/2fa/disable', methods=['POST'])(self.disable_2fa)
        
        # Admin management (requires admin role)
        self.blueprint.route('/list', methods=['GET'])(self.list_admins)
        self.blueprint.route('/create', methods=['POST'])(
            sanitize_request_data(self.create_admin)
        )
        self.blueprint.route('/<admin_id>', methods=['PUT'])(
            sanitize_request_data(self.update_admin)
        )
        self.blueprint.route('/<admin_id>/suspend', methods=['POST'])(self.suspend_admin)
        self.blueprint.route('/<admin_id>/activate', methods=['POST'])(self.activate_admin)
        
        # Add security headers to all responses
        @self.blueprint.after_request
        def after_request(response):
            return add_security_headers(response)
    
    def login(self):
        """
        POST /admin/login
        Body: {"email": "...", "password": "..."}
        """
        data = request.sanitized_data
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return self._error_response("Email and password are required", 400)
        
        # Get client IP
        ip_address = request.remote_addr
        
        result = self.admin_service.authenticate(email, password, ip_address)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 401)
        
        if result.get('requires_2fa'):
            return self._success_response({
                "requires_2fa": True,
                "admin_id": result['admin_id'],
                "email": result['email'],
                "message": result['message']
            }, "2FA required", 200)
        
        return self._success_response({
            "admin": result['admin'],
            "tenant": result['tenant'],
            "access_token": result['access_token'],
            "refresh_token": result['refresh_token']
        }, "Login successful")
    
    def verify_2fa(self):
        """
        POST /admin/verify-2fa
        Body: {"admin_id": "...", "code": "123456"}
        """
        data = request.sanitized_data
        admin_id = data.get('admin_id')
        code = data.get('code')
        
        if not admin_id or not code:
            return self._error_response("Admin ID and code are required", 400)
        
        ip_address = request.remote_addr
        
        result = self.admin_service.verify_2fa(admin_id, code, ip_address)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 401)
        
        return self._success_response({
            "admin": result['admin'],
            "tenant": result['tenant'],
            "access_token": result['access_token'],
            "refresh_token": result['refresh_token']
        }, "Login successful")
    
    def register(self):
        """
        POST /admin/register
        Body: {
            "email": "...",
            "password": "...",
            "full_name": "...",
            "tenant_id": "..." (optional, creates new tenant if not provided)
        }
        """
        data = request.sanitized_data
        email = data.get('email')
        password = data.get('password')
        full_name = data.get('full_name')
        tenant_id = data.get('tenant_id')
        
        if not email or not password:
            return self._error_response("Email and password are required", 400)
        
        # If no tenant_id, create new tenant
        if not tenant_id:
            tenant_name = data.get('tenant_name') or f"{full_name or email.split('@')[0]}'s Organization"
            try:
                tenant = self.tenant_model.create_tenant({
                    "name": tenant_name,
                    "plan": "free"
                })
                tenant_id = str(tenant['_id'])
            except Exception as e:
                logger.error(f"Failed to create tenant: {e}")
                return self._error_response(f"Failed to create organization: {str(e)}", 500)
        
        # Create admin (each admin is owner of their tenant)
        admin_data = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "tenant_id": tenant_id,
            "role": "admin"  # Only admin role now (no super_admin)
        }
        
        result = self.admin_service.create_admin(admin_data)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(result['admin'], "Admin created successfully", 201)
    
    def logout(self):
        """POST /admin/logout"""
        # Clear session
        from flask import session
        session.clear()
        
        # In JWT-based auth, logout is handled client-side by removing tokens
        # Optionally, you can implement token blacklisting here
        return self._success_response(None, "Logged out successfully")
    
    def set_session(self):
        """POST /api/admin/set-session - Set session cookie after login"""
        from flask import session
        
        data = request.get_json() or {}
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return self._error_response("Admin ID is required", 400)
        
        # Verify admin exists
        admin = self.admin_model.get_by_id(admin_id)
        if not admin:
            return self._error_response("Admin not found", 404)
        
        # Set session with all required fields including role
        session['admin_id'] = admin_id
        session['email'] = admin['email']
        session['role'] = admin.get('role', 'tenant_admin')  # Store role in session
        session['full_name'] = admin.get('full_name', '')
        
        # Handle tenant_id (super_admin may not have tenant_id)
        tenant_id = admin.get('tenant_id')
        session['tenant_id'] = str(tenant_id) if tenant_id else None
        
        session.permanent = True  # Session persists across browser restarts
        
        logger.info(f"Session established for {admin['email']} with role {session['role']}")
        
        return self._success_response({
            "role": session['role'],
            "tenant_id": session['tenant_id']
        }, "Session established")
    
    def get_profile(self):
        """GET /admin/profile"""
        # TODO: Add JWT authentication middleware to get current admin
        # For now, require admin_id in query params
        admin_id = request.args.get('admin_id')
        
        if not admin_id:
            return self._error_response("Admin ID is required", 400)
        
        admin = self.admin_model.get_by_id(admin_id)
        
        if not admin:
            return self._error_response("Admin not found", 404)
        
        return self._success_response(self.admin_service._sanitize_admin(admin))
    
    def update_profile(self):
        """PUT /admin/profile"""
        data = request.sanitized_data
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return self._error_response("Admin ID is required", 400)
        
        # Remove fields that can't be updated via profile
        update_data = {}
        allowed_fields = ['full_name', 'phone']
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return self._error_response("No valid fields to update", 400)
        
        result = self.admin_service.update_admin(admin_id, update_data, admin_id)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(result['admin'], "Profile updated successfully")
    
    def change_password(self):
        """POST /admin/change-password"""
        data = request.sanitized_data
        admin_id = data.get('admin_id')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not admin_id or not old_password or not new_password:
            return self._error_response("Admin ID, old password, and new password are required", 400)
        
        result = self.admin_service.change_password(admin_id, old_password, new_password)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(None, result['message'])
    
    def enable_2fa(self):
        """POST /admin/2fa/enable"""
        data = request.sanitized_data
        admin_id = data.get('admin_id')
        method = data.get('method', 'email')
        
        if not admin_id:
            return self._error_response("Admin ID is required", 400)
        
        result = self.admin_service.enable_2fa(admin_id, method)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(None, result['message'])
    
    def disable_2fa(self):
        """POST /admin/2fa/disable"""
        data = request.get_json() or {}
        admin_id = data.get('admin_id')
        
        if not admin_id:
            return self._error_response("Admin ID is required", 400)
        
        result = self.admin_service.disable_2fa(admin_id)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(None, result['message'])
    
    def list_admins(self):
        """GET /admin/list?tenant_id=...&skip=0&limit=50"""
        tenant_id = request.args.get('tenant_id')
        
        if not tenant_id:
            return self._error_response("Tenant ID is required", 400)
        
        try:
            skip = int(request.args.get('skip', 0))
            limit = int(request.args.get('limit', 50))
        except ValueError:
            return self._error_response("Invalid skip or limit", 400)
        
        result = self.admin_service.list_admins(tenant_id, skip, limit)
        
        return self._success_response(result)
    
    def create_admin(self):
        """POST /admin/create"""
        data = request.sanitized_data
        
        required = ['email', 'password', 'tenant_id']
        for field in required:
            if field not in data:
                return self._error_response(f"{field} is required", 400)
        
        created_by = data.get('created_by')  # Should come from JWT token
        
        result = self.admin_service.create_admin(data, created_by)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(result['admin'], "Admin created successfully", 201)
    
    def update_admin(self, admin_id: str):
        """PUT /admin/<admin_id>"""
        data = request.sanitized_data
        
        updated_by = data.get('updated_by')  # Should come from JWT token
        
        # Remove fields that can't be updated
        data.pop('email', None)
        data.pop('password', None)
        data.pop('tenant_id', None)
        data.pop('created_by', None)
        data.pop('updated_by', None)
        
        if not data:
            return self._error_response("No valid fields to update", 400)
        
        result = self.admin_service.update_admin(admin_id, data, updated_by)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(result['admin'], "Admin updated successfully")
    
    def suspend_admin(self, admin_id: str):
        """POST /admin/<admin_id>/suspend"""
        data = request.get_json() or {}
        reason = data.get('reason', 'Suspended by administrator')
        suspended_by = data.get('suspended_by')  # Should come from JWT token
        
        result = self.admin_service.suspend_admin(admin_id, reason, suspended_by)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(None, result['message'])
    
    def activate_admin(self, admin_id: str):
        """POST /admin/<admin_id>/activate"""
        data = request.get_json() or {}
        activated_by = data.get('activated_by')  # Should come from JWT token
        
        result = self.admin_service.activate_admin(admin_id, activated_by)
        
        if not result.get('success'):
            return self._error_response(result.get('error'), 400)
        
        return self._success_response(None, result['message'])
    
    def _success_response(self, data=None, message="Success", status_code=200) -> Tuple:
        """Standard success response."""
        return jsonify({
            "success": True,
            "message": message,
            "data": data,
            "timestamp": now_iso()
        }), status_code
    
    def _error_response(self, message: str, status_code=400) -> Tuple:
        """Standard error response."""
        return jsonify({
            "success": False,
            "error": message,
            "timestamp": now_iso()
        }), status_code
