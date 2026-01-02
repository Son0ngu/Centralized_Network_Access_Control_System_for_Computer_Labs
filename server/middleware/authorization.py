"""
Authorization Middleware - Role-based access control
-----------------------------------------------------
Decorators for Super Admin, Tenant Admin, and impersonation handling.

Roles:
- super_admin: Platform-wide access, manages all tenants
- tenant_admin: Full access within their tenant only
"""

import logging
from functools import wraps
from typing import Callable, Optional
from flask import request, jsonify, g, session

from models.admin_model import ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN

logger = logging.getLogger(__name__)

# Global reference to ImpersonationLogModel (set during init)
_impersonation_model = None


def init_authorization_middleware(impersonation_model=None):
    """
    Initialize the authorization middleware with impersonation model.
    
    Args:
        impersonation_model: ImpersonationLogModel instance for logging impersonation actions
    """
    global _impersonation_model
    _impersonation_model = impersonation_model
    logger.info("Authorization middleware initialized")


def get_current_role() -> Optional[str]:
    """
    Get the current admin's role from JWT payload or session.
    
    Returns:
        Role string ('super_admin' or 'tenant_admin') or None
    """
    # Check JWT payload first
    if hasattr(g, 'jwt_payload') and g.jwt_payload:
        return g.jwt_payload.get('role')
    
    # Then check session
    return session.get('role')


def get_current_admin_context() -> dict:
    """
    Get full context of current authenticated admin.
    
    Returns:
        Dict with admin_id, role, tenant_id, impersonation info
    """
    context = {
        'admin_id': None,
        'role': None,
        'tenant_id': None,
        'is_impersonating': False,
        'original_admin_id': None,
        'impersonation_session_id': None,
    }
    
    # From JWT payload
    if hasattr(g, 'jwt_payload') and g.jwt_payload:
        payload = g.jwt_payload
        context.update({
            'admin_id': payload.get('admin_id') or payload.get('sub'),
            'role': payload.get('role'),
            'tenant_id': payload.get('tenant_id'),
            'is_impersonating': payload.get('is_impersonating', False),
            'original_admin_id': payload.get('original_admin_id'),
            'impersonation_session_id': payload.get('impersonation_session_id'),
        })
    # From session
    elif session.get('admin_id'):
        context.update({
            'admin_id': session.get('admin_id'),
            'role': session.get('role'),
            'tenant_id': session.get('tenant_id'),
            'is_impersonating': session.get('is_impersonating', False),
            'original_admin_id': session.get('original_admin_id'),
            'impersonation_session_id': session.get('impersonation_session_id'),
        })
    
    return context


def is_super_admin() -> bool:
    """Check if current user is Super Admin."""
    return get_current_role() == ROLE_SUPER_ADMIN


def is_tenant_admin() -> bool:
    """Check if current user is Tenant Admin."""
    return get_current_role() == ROLE_TENANT_ADMIN


def is_impersonating() -> bool:
    """Check if current session is an impersonation session."""
    context = get_current_admin_context()
    return context.get('is_impersonating', False)


def require_super_admin(f: Callable) -> Callable:
    """
    Decorator that requires Super Admin role.
    
    Usage:
        @app.route('/api/admin/tenants')
        @require_super_admin
        def list_all_tenants():
            # Only Super Admin can access
            ...
    
    Returns 403 if:
        - Not authenticated
        - Role is not 'super_admin'
        - Currently impersonating (cannot use super_admin privileges while impersonating)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = get_current_admin_context()
        
        # Check if authenticated
        if not context.get('admin_id'):
            logger.warning(f"Unauthenticated access attempt to super_admin endpoint: {request.endpoint}")
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Please login to access this resource"
            }), 401
        
        # Check role
        if context.get('role') != ROLE_SUPER_ADMIN:
            logger.warning(
                f"Non-super_admin access attempt to {request.endpoint} by admin_id={context.get('admin_id')}"
            )
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Super Admin access required"
            }), 403
        
        # Cannot use super_admin privileges while impersonating
        if context.get('is_impersonating'):
            logger.warning(
                f"Super Admin endpoint access denied during impersonation: {request.endpoint}"
            )
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Cannot access Super Admin features while impersonating. End impersonation first."
            }), 403
        
        # Store context in g for easy access
        g.admin_context = context
        
        logger.debug(f"Super Admin access granted to {request.endpoint}")
        return f(*args, **kwargs)
    
    return decorated_function


def require_tenant_admin(f: Callable) -> Callable:
    """
    Decorator that requires Tenant Admin role (or Super Admin impersonating a tenant).
    
    Automatically filters data by tenant_id stored in g.tenant_id.
    
    Usage:
        @app.route('/api/whitelist')
        @require_tenant_admin
        def list_whitelist():
            tenant_id = g.tenant_id  # Automatically set
            ...
    
    Returns 403 if:
        - Not authenticated
        - Role is not 'tenant_admin' AND not impersonating
        - No tenant_id available
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = get_current_admin_context()
        
        # Check if authenticated
        if not context.get('admin_id'):
            logger.warning(f"Unauthenticated access attempt to tenant_admin endpoint: {request.endpoint}")
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Please login to access this resource"
            }), 401
        
        role = context.get('role')
        is_impersonation = context.get('is_impersonating', False)
        
        # Allow access if:
        # 1. Role is tenant_admin
        # 2. Super Admin is impersonating a tenant
        if role == ROLE_TENANT_ADMIN:
            # Regular tenant admin - must have tenant_id
            if not context.get('tenant_id'):
                logger.error(f"Tenant Admin without tenant_id: admin_id={context.get('admin_id')}")
                return jsonify({
                    "success": False,
                    "error": "Configuration error",
                    "message": "Your account is not properly associated with a tenant"
                }), 403
        
        elif role == ROLE_SUPER_ADMIN and is_impersonation:
            # Super Admin impersonating - use impersonated tenant_id
            if not context.get('tenant_id'):
                logger.error(f"Impersonation session without tenant_id: session={context.get('impersonation_session_id')}")
                return jsonify({
                    "success": False,
                    "error": "Invalid impersonation session",
                    "message": "Impersonation session is invalid or expired"
                }), 403
        
        else:
            # Neither tenant_admin nor valid impersonation
            logger.warning(
                f"Unauthorized tenant access attempt to {request.endpoint} by admin_id={context.get('admin_id')}"
            )
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Tenant Admin access required"
            }), 403
        
        # Store context in g for easy access
        g.admin_context = context
        g.tenant_id = context.get('tenant_id')  # For data filtering
        
        logger.debug(f"Tenant Admin access granted to {request.endpoint} for tenant_id={g.tenant_id}")
        return f(*args, **kwargs)
    
    return decorated_function


def require_any_admin(f: Callable) -> Callable:
    """
    Decorator that requires any authenticated admin (Super Admin or Tenant Admin).
    
    Use for endpoints common to all admins like:
        - Profile view/update
        - Change password
        - Logout
    
    Usage:
        @app.route('/api/admin/profile')
        @require_any_admin
        def get_profile():
            admin_id = g.admin_context['admin_id']
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = get_current_admin_context()
        
        # Check if authenticated
        if not context.get('admin_id'):
            logger.warning(f"Unauthenticated access attempt to admin endpoint: {request.endpoint}")
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Please login to access this resource"
            }), 401
        
        # Check valid role
        role = context.get('role')
        if role not in [ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN]:
            logger.warning(
                f"Invalid role '{role}' for admin_id={context.get('admin_id')}"
            )
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Valid admin role required"
            }), 403
        
        # Store context in g for easy access
        g.admin_context = context
        
        # Set tenant_id if available (for tenant_admin or impersonation)
        if context.get('tenant_id'):
            g.tenant_id = context.get('tenant_id')
        
        logger.debug(f"Admin access granted to {request.endpoint} for admin_id={context.get('admin_id')}")
        return f(*args, **kwargs)
    
    return decorated_function


def check_impersonation(f: Callable) -> Callable:
    """
    Decorator to check and log impersonation context.
    
    If the current session is an impersonation:
        - Validates the impersonation session is still valid
        - Logs the action to impersonation_log
        - Adds impersonation banner data to response context
    
    Usage:
        @app.route('/api/agents')
        @require_tenant_admin
        @check_impersonation
        def list_agents():
            # Actions are logged if impersonating
            ...
    
    Note: Should be used AFTER authentication decorators.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = get_current_admin_context()
        
        if not context.get('is_impersonating'):
            # Not impersonating, proceed normally
            return f(*args, **kwargs)
        
        session_id = context.get('impersonation_session_id')
        original_admin_id = context.get('original_admin_id')
        
        # Validate impersonation session
        if _impersonation_model:
            is_valid = _impersonation_model.is_valid_session(session_id)
            if not is_valid:
                logger.warning(f"Invalid impersonation session: {session_id}")
                return jsonify({
                    "success": False,
                    "error": "Impersonation session expired",
                    "message": "Your impersonation session has expired. Please start a new session.",
                    "code": "IMPERSONATION_EXPIRED"
                }), 401
            
            # Log the action
            action_details = {
                'endpoint': request.endpoint,
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.args),
            }
            
            # Only log request body for non-GET requests
            if request.method != 'GET' and request.is_json:
                try:
                    body = request.get_json(silent=True)
                    if body:
                        # Sanitize sensitive fields
                        sanitized_body = {k: v for k, v in body.items() 
                                         if k not in ['password', 'secret', 'token', 'api_key']}
                        action_details['request_body'] = sanitized_body
                except:
                    pass
            
            _impersonation_model.log_action(
                session_id=session_id,
                action=f"{request.method} {request.path}",
                details=action_details,
                ip_address=request.remote_addr
            )
        
        # Add impersonation context to g
        g.is_impersonating = True
        g.original_admin_id = original_admin_id
        g.impersonation_session_id = session_id
        
        logger.debug(
            f"Impersonation action logged: {request.method} {request.path} "
            f"by original_admin={original_admin_id}"
        )
        
        return f(*args, **kwargs)
    
    return decorated_function


def log_impersonation_action(action: str, details: dict = None):
    """
    Manually log an impersonation action.
    
    Useful for actions that need explicit logging outside of request context.
    
    Args:
        action: Action description
        details: Additional action details
    """
    context = get_current_admin_context()
    
    if not context.get('is_impersonating'):
        return
    
    if _impersonation_model:
        _impersonation_model.log_action(
            session_id=context.get('impersonation_session_id'),
            action=action,
            details=details or {},
            ip_address=request.remote_addr if request else None
        )


# ============================================================================
# Role checking utilities for use in views/controllers
# ============================================================================

def check_permission(required_role: str) -> tuple:
    """
    Check if current user has the required role.
    
    Args:
        required_role: 'super_admin', 'tenant_admin', or 'any'
    
    Returns:
        Tuple of (allowed: bool, error_response: tuple or None)
    """
    context = get_current_admin_context()
    
    if not context.get('admin_id'):
        return False, (jsonify({
            "success": False,
            "error": "Authentication required"
        }), 401)
    
    current_role = context.get('role')
    
    if required_role == 'any':
        if current_role in [ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN]:
            return True, None
    
    elif required_role == ROLE_SUPER_ADMIN:
        if current_role == ROLE_SUPER_ADMIN and not context.get('is_impersonating'):
            return True, None
    
    elif required_role == ROLE_TENANT_ADMIN:
        if current_role == ROLE_TENANT_ADMIN:
            return True, None
        # Also allow impersonating super admin
        if current_role == ROLE_SUPER_ADMIN and context.get('is_impersonating'):
            return True, None
    
    return False, (jsonify({
        "success": False,
        "error": "Forbidden",
        "message": f"{required_role} access required"
    }), 403)


def get_impersonation_banner_data() -> Optional[dict]:
    """
    Get data for impersonation banner display in UI.
    
    Returns:
        Dict with impersonation info or None if not impersonating
    """
    context = get_current_admin_context()
    
    if not context.get('is_impersonating'):
        return None
    
    return {
        'is_impersonating': True,
        'session_id': context.get('impersonation_session_id'),
        'original_admin_id': context.get('original_admin_id'),
        'tenant_id': context.get('tenant_id'),
    }
