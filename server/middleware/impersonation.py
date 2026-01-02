"""
Impersonation Middleware - Action logging and restriction enforcement
----------------------------------------------------------------------
Logs all actions during impersonation and enforces action restrictions.
"""

import logging
from functools import wraps
from flask import request, g, jsonify
from typing import Callable, Optional
from datetime import datetime
from bson import ObjectId

from config.impersonation_config import (
    IMPERSONATION_CONFIG,
    get_action_for_route,
    is_action_allowed,
    is_action_forbidden,
)
from time_utils import now_vietnam

logger = logging.getLogger(__name__)

# Global reference to impersonation log model
_impersonation_model = None
_admin_model = None


def init_impersonation_middleware(impersonation_model, admin_model=None):
    """Initialize impersonation middleware with required models."""
    global _impersonation_model, _admin_model
    _impersonation_model = impersonation_model
    _admin_model = admin_model
    logger.info("Impersonation middleware initialized")


def is_impersonating() -> bool:
    """Check if current request is from an impersonation session."""
    return getattr(g, 'is_impersonating', False)


def get_impersonation_context() -> dict:
    """Get current impersonation context."""
    if not is_impersonating():
        return {}
    return {
        'is_impersonating': True,
        'original_admin_id': getattr(g, 'original_admin_id', None),
        'impersonation_session_id': getattr(g, 'impersonation_session_id', None),
        'impersonated_tenant_id': getattr(g, 'tenant_id', None),
    }


def log_impersonation_action(
    session_id: str,
    action: str,
    method: str,
    path: str,
    request_data: dict = None,
    response_status: int = None,
    response_data: dict = None,
    error: str = None
) -> bool:
    """
    Log an action performed during impersonation.
    
    Args:
        session_id: Impersonation session ID
        action: Action type from ImpersonationAction
        method: HTTP method
        path: Request path
        request_data: Request body/params (sanitized)
        response_status: Response status code
        response_data: Response data (sanitized)
        error: Error message if failed
        
    Returns:
        True if logged successfully
    """
    if not _impersonation_model:
        logger.warning("Impersonation model not initialized, skipping action log")
        return False
    
    try:
        action_log = {
            "timestamp": now_vietnam(),
            "action": action or "unknown",
            "method": method,
            "path": path,
            "request_summary": _sanitize_for_log(request_data) if request_data else None,
            "response_status": response_status,
            "success": response_status and 200 <= response_status < 400,
            "error": error,
        }
        
        _impersonation_model.add_action_to_session(session_id, action_log)
        logger.debug(f"Logged impersonation action: {action} on {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to log impersonation action: {e}")
        return False


def _sanitize_for_log(data: dict) -> dict:
    """Sanitize request/response data for logging (remove sensitive info)."""
    if not data:
        return None
    
    sensitive_keys = {'password', 'api_key', 'token', 'secret', 'credential', 'auth'}
    sanitized = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        if any(s in key_lower for s in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_for_log(value)
        else:
            sanitized[key] = value
    
    return sanitized


def check_impersonation_restrictions(f: Callable) -> Callable:
    """
    Decorator to check and enforce impersonation restrictions.
    - Logs all actions
    - Blocks forbidden actions
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only check if impersonating
        if not is_impersonating():
            return f(*args, **kwargs)
        
        method = request.method
        path = request.path
        action = get_action_for_route(method, path)
        session_id = getattr(g, 'impersonation_session_id', None)
        
        # Check if action is forbidden
        if is_action_forbidden(action):
            logger.warning(
                f"Forbidden action during impersonation: {action} "
                f"(session: {session_id})"
            )
            
            # Log the blocked attempt
            if session_id:
                log_impersonation_action(
                    session_id=session_id,
                    action=action,
                    method=method,
                    path=path,
                    request_data=_get_request_summary(),
                    response_status=403,
                    error="Action forbidden during impersonation"
                )
            
            return jsonify({
                "success": False,
                "error": "This action is not allowed during impersonation",
                "action": action,
                "impersonation_restriction": True
            }), 403
        
        # Execute the function
        try:
            response = f(*args, **kwargs)
            
            # Log successful action (if logging is enabled)
            if IMPERSONATION_CONFIG.get("log_all_actions") and session_id:
                # Get response status
                status = 200
                if hasattr(response, 'status_code'):
                    status = response.status_code
                elif isinstance(response, tuple) and len(response) > 1:
                    status = response[1]
                
                log_impersonation_action(
                    session_id=session_id,
                    action=action,
                    method=method,
                    path=path,
                    request_data=_get_request_summary(),
                    response_status=status
                )
            
            return response
        except Exception as e:
            # Log failed action
            if session_id:
                log_impersonation_action(
                    session_id=session_id,
                    action=action,
                    method=method,
                    path=path,
                    request_data=_get_request_summary(),
                    response_status=500,
                    error=str(e)
                )
            raise
    
    return decorated_function


def _get_request_summary() -> dict:
    """Get a summary of the current request for logging."""
    summary = {
        "method": request.method,
        "path": request.path,
        "args": dict(request.args) if request.args else None,
    }
    
    # Include request body for write operations
    if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        try:
            if request.is_json:
                summary["body"] = request.get_json(silent=True)
            elif request.form:
                summary["form"] = dict(request.form)
        except:
            pass
    
    return summary


def require_not_impersonating(f: Callable) -> Callable:
    """Decorator to block endpoint entirely during impersonation."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_impersonating():
            session_id = getattr(g, 'impersonation_session_id', None)
            
            # Log the blocked attempt
            if session_id:
                log_impersonation_action(
                    session_id=session_id,
                    action="blocked_endpoint",
                    method=request.method,
                    path=request.path,
                    response_status=403,
                    error="Endpoint blocked during impersonation"
                )
            
            return jsonify({
                "success": False,
                "error": "This endpoint is not accessible during impersonation",
                "impersonation_restriction": True
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


class ImpersonationActionLogger:
    """Context manager for logging impersonation actions."""
    
    def __init__(self, action: str, details: dict = None):
        self.action = action
        self.details = details or {}
        self.session_id = None
        self.start_time = None
    
    def __enter__(self):
        if is_impersonating():
            self.session_id = getattr(g, 'impersonation_session_id', None)
            self.start_time = now_vietnam()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session_id:
            error = str(exc_val) if exc_val else None
            success = exc_type is None
            
            log_impersonation_action(
                session_id=self.session_id,
                action=self.action,
                method=request.method if request else "UNKNOWN",
                path=request.path if request else "UNKNOWN",
                request_data=self.details,
                response_status=200 if success else 500,
                error=error
            )
        
        return False  # Don't suppress exceptions


def get_impersonation_banner_data() -> Optional[dict]:
    """
    Get data for rendering impersonation banner.
    Returns None if not impersonating.
    """
    if not is_impersonating():
        return None
    
    original_admin_id = getattr(g, 'original_admin_id', None)
    tenant_id = getattr(g, 'tenant_id', None)
    session_id = getattr(g, 'impersonation_session_id', None)
    
    # Get tenant and admin names if models available
    tenant_name = None
    admin_name = None
    
    if _admin_model and original_admin_id:
        try:
            admin = _admin_model.get_by_id(original_admin_id)
            if admin:
                admin_name = admin.get('username') or admin.get('email')
        except:
            pass
    
    return {
        "is_impersonating": True,
        "original_admin_id": original_admin_id,
        "original_admin_name": admin_name,
        "impersonated_tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "session_id": session_id,
        "exit_url": "/api/super/end-impersonation",
    }


def auto_expire_sessions():
    """
    Check and expire old impersonation sessions.
    Should be called periodically (e.g., by a scheduler).
    """
    if not _impersonation_model:
        return 0
    
    try:
        count = _impersonation_model.expire_old_sessions()
        if count > 0:
            logger.info(f"Auto-expired {count} impersonation sessions")
        return count
    except Exception as e:
        logger.error(f"Error auto-expiring sessions: {e}")
        return 0
