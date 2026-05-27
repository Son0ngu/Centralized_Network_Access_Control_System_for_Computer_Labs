"""
RBAC Middleware - Decorators cho Admin/Teacher web routes.
- Cookie-based JWT authentication (httpOnly)
- Permission check theo resource:action format
- Ownership check: Teacher chỉ thao tác trên Group được gán hoặc legacy owned.
- Hoat dong SONG SONG voi middleware/auth.py (cho Agent API)
"""

import logging
from functools import wraps
from typing import Callable, Optional

from flask import request, jsonify, g, redirect

from config.rbac_config import check_permission, is_admin

logger = logging.getLogger(__name__)

# Global references (set during init)
_admin_auth_service = None
_rbac_service = None
_jwt_service = None
_user_model = None


def init_rbac_middleware(admin_auth_service, rbac_service, jwt_service, user_model):
    """
    Initialize RBAC middleware with required services.
    Called once during app startup in register_controllers().
    """
    global _admin_auth_service, _rbac_service, _jwt_service, _user_model
    _admin_auth_service = admin_auth_service
    _rbac_service = rbac_service
    _jwt_service = jwt_service
    _user_model = user_model
    logger.info("RBAC middleware initialized")


def get_rbac_service():
    """Get the RBAC service instance (for controllers that need ownership validation)."""
    return _rbac_service


def _extract_token() -> Optional[str]:
    """
    Extract JWT token from request.
    Priority: httpOnly cookie > Authorization header (Bearer)
    """
    # 1. httpOnly cookie (preferred for web UI)
    token = request.cookies.get("access_token")
    if token:
        return token.strip()

    # 2. Authorization header (fallback, for API calls)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def _validate_admin_token(token: str):
    """
    Validate token and ensure it belongs to an admin/teacher user.
    Returns: (success, user_dict, error_message)
    """
    if _jwt_service is None or _user_model is None:
        return False, None, "RBAC middleware not initialized"

    # Decode JWT
    is_valid, payload, error = _jwt_service.validate_access_token(token)
    if not is_valid:
        return False, None, error

    # Must be admin_user token (not agent token)
    if payload.get("token_for") != "admin_user":
        return False, None, "Token does not belong to admin user"

    # Get user from DB
    user_id = payload.get("sub")
    user = _user_model.find_by_id(user_id)
    if not user:
        return False, None, "User not found"

    if not user.get("is_active", True):
        return False, None, "Account has been disabled"

    if _user_model.is_locked(user):
        return False, None, "Account temporarily locked"

    return True, user, None


# ============================================================================
# DECORATORS
# ============================================================================

def require_login(f: Callable) -> Callable:
    """
    Decorator: Require valid admin/teacher JWT.
    Sets g.current_user with authenticated user data.

    Usage:
        @require_login
        def dashboard():
            user = g.current_user
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            # Check if this is an API call or page request
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Authentication required",
                }), 401
            # For web pages, redirect to login
            return redirect("/login")

        success, user, error = _validate_admin_token(token)
        if not success:
            if not request.path.startswith("/api/"):
                return redirect("/login")
            if "expired" in (error or "").lower():
                return jsonify({
                    "success": False,
                    "error": "Token expired",
                    "code": "TOKEN_EXPIRED",
                }), 401
            return jsonify({
                "success": False,
                "error": error or "Authentication failed",
            }), 401

        # Store user in Flask g context
        g.current_user = user
        g.current_user_id = str(user["_id"])
        g.current_role = user.get("role")

        return f(*args, **kwargs)

    return decorated


def require_admin(f: Callable) -> Callable:
    """
    Decorator: Require admin role.
    Must be used AFTER @require_login.

    Usage:
        @require_login
        @require_admin
        def manage_users():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        role = getattr(g, "current_role", None)
        if not role or not is_admin(role):
            logger.warning(f"Admin access denied: role={role} for {request.endpoint}")
            return jsonify({
                "success": False,
                "error": "Admin access only",
            }), 403
        return f(*args, **kwargs)
    return decorated


def require_permission(permission: str):
    """
    Decorator: Require specific permission (resource:action format).
    Must be used AFTER @require_login.

    Usage:
        @require_login
        @require_permission("whitelist:create")
        def create_whitelist():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            role = getattr(g, "current_role", None)
            if not role:
                return jsonify({"success": False, "error": "Authentication required"}), 401

            if not check_permission(role, permission):
                logger.warning(
                    f"Permission denied: role={role} missing '{permission}' "
                    f"for {request.endpoint}"
                )
                return jsonify({
                    "success": False,
                    "error": "Insufficient permissions",
                    "required": permission,
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def inject_current_user(f: Callable) -> Callable:
    """
    Decorator: Inject g.current_user without blocking.
    If token is valid, sets g.current_user. If not, g.current_user = None.
    For pages that show different content based on login status.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = None
        g.current_user_id = None
        g.current_role = None

        token = _extract_token()
        if token:
            success, user, _ = _validate_admin_token(token)
            if success:
                g.current_user = user
                g.current_user_id = str(user["_id"])
                g.current_role = user.get("role")

        return f(*args, **kwargs)
    return decorated


def require_group_ownership(group_id_param: str = "group_id"):
    """
    Decorator: Check Teacher ownership on Group.
    - Admin: always pass (full access)
    - Teacher: must be assigned via teacher_ids or legacy created_by
    Must be used AFTER @require_login.

    Usage:
        @require_login
        @require_group_ownership("group_id")
        def edit_group(group_id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"success": False, "error": "Authentication required"}), 401

            # Admin bypasses ownership check
            if is_admin(user.get("role", "")):
                return f(*args, **kwargs)

            # Get group_id from URL params or request body
            group_id = kwargs.get(group_id_param)
            if not group_id and request.is_json:
                group_id = request.get_json().get(group_id_param)

            if not group_id:
                return jsonify({"success": False, "error": "Group ID required"}), 400

            # Check ownership via RBACService
            if _rbac_service:
                group_model = _rbac_service.group_model
                if group_model:
                    group = group_model.find_by_id(group_id)

                    if not group:
                        return jsonify({"success": False, "error": "Group not found"}), 404

                    if not _rbac_service.can_access_group(user, group):
                        logger.warning(
                            f"Ownership denied: {user.get('username')} on group {group_id}"
                        )
                        return jsonify({
                            "success": False,
                            "error": "No permission for this Group",
                        }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
