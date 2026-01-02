"""
Impersonation Configuration and Rules
--------------------------------------
Defines rules, restrictions, and allowed actions for impersonation sessions.
"""

from enum import Enum
from typing import Dict, List, Set

# ==============================================================================
# Impersonation Configuration
# ==============================================================================

IMPERSONATION_CONFIG = {
    # Session settings
    "max_duration_hours": 4,        # Tự động hết hạn sau 4h
    "max_duration_seconds": 4 * 60 * 60,  # 14400 seconds
    
    # Security requirements
    "require_reason": True,         # Bắt buộc nhập lý do
    "min_reason_length": 10,        # Lý do phải có ít nhất 10 ký tự
    
    # Logging
    "log_all_actions": True,        # Log mọi thao tác
    
    # Notifications
    "notify_tenant": False,         # Có thông báo cho tenant không?
    
    # Session management
    "max_concurrent_sessions": 1,   # Chỉ 1 session cùng lúc
    "auto_extend": False,           # Không tự động gia hạn
    
    # Token settings
    "short_token_expiry_hours": 4,  # Token ngắn hơn bình thường
}


class ImpersonationAction(str, Enum):
    """Enum for impersonation action types."""
    # View actions (allowed)
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_AGENTS = "view_agents"
    VIEW_AGENT_DETAIL = "view_agent_detail"
    VIEW_LOGS = "view_logs"
    VIEW_WHITELIST = "view_whitelist"
    VIEW_GROUPS = "view_groups"
    VIEW_SETTINGS = "view_settings"
    VIEW_API_KEYS = "view_api_keys"
    
    # Modify actions (restricted)
    CREATE_AGENT = "create_agent"
    UPDATE_AGENT = "update_agent"
    DELETE_AGENT = "delete_agent"
    CREATE_WHITELIST = "create_whitelist"
    UPDATE_WHITELIST = "update_whitelist"
    DELETE_WHITELIST = "delete_whitelist"
    CREATE_GROUP = "create_group"
    UPDATE_GROUP = "update_group"
    DELETE_GROUP = "delete_group"
    CREATE_API_KEY = "create_api_key"
    DELETE_API_KEY = "delete_api_key"
    
    # Admin actions (forbidden)
    CREATE_ADMIN = "create_admin"
    UPDATE_ADMIN = "update_admin"
    DELETE_ADMIN = "delete_admin"
    UPDATE_SETTINGS = "update_settings"
    DELETE_TENANT = "delete_tenant"


# Allowed actions during impersonation
IMPERSONATION_ALLOWED_ACTIONS: Set[str] = {
    # View actions - always allowed
    ImpersonationAction.VIEW_DASHBOARD,
    ImpersonationAction.VIEW_AGENTS,
    ImpersonationAction.VIEW_AGENT_DETAIL,
    ImpersonationAction.VIEW_LOGS,
    ImpersonationAction.VIEW_WHITELIST,
    ImpersonationAction.VIEW_GROUPS,
    ImpersonationAction.VIEW_SETTINGS,
    ImpersonationAction.VIEW_API_KEYS,
    
    # Limited modify actions (for troubleshooting)
    ImpersonationAction.CREATE_WHITELIST,
    ImpersonationAction.UPDATE_WHITELIST,
    ImpersonationAction.CREATE_GROUP,
    ImpersonationAction.UPDATE_GROUP,
}

# Forbidden actions during impersonation
IMPERSONATION_FORBIDDEN_ACTIONS: Set[str] = {
    # Delete operations
    ImpersonationAction.DELETE_AGENT,
    ImpersonationAction.DELETE_WHITELIST,
    ImpersonationAction.DELETE_GROUP,
    ImpersonationAction.DELETE_API_KEY,
    
    # Admin operations
    ImpersonationAction.CREATE_ADMIN,
    ImpersonationAction.UPDATE_ADMIN,
    ImpersonationAction.DELETE_ADMIN,
    ImpersonationAction.UPDATE_SETTINGS,
    ImpersonationAction.DELETE_TENANT,
    
    # Sensitive operations
    ImpersonationAction.CREATE_API_KEY,
}


# ==============================================================================
# Route to Action Mapping
# ==============================================================================

ROUTE_ACTION_MAP: Dict[str, str] = {
    # Dashboard
    "GET:/dashboard": ImpersonationAction.VIEW_DASHBOARD,
    "GET:/api/dashboard/stats": ImpersonationAction.VIEW_DASHBOARD,
    
    # Agents
    "GET:/api/agents": ImpersonationAction.VIEW_AGENTS,
    "GET:/api/agents/*": ImpersonationAction.VIEW_AGENT_DETAIL,
    "POST:/api/agents": ImpersonationAction.CREATE_AGENT,
    "PUT:/api/agents/*": ImpersonationAction.UPDATE_AGENT,
    "DELETE:/api/agents/*": ImpersonationAction.DELETE_AGENT,
    
    # Logs
    "GET:/api/logs": ImpersonationAction.VIEW_LOGS,
    "GET:/api/logs/*": ImpersonationAction.VIEW_LOGS,
    
    # Whitelist
    "GET:/api/whitelist": ImpersonationAction.VIEW_WHITELIST,
    "GET:/api/whitelist/*": ImpersonationAction.VIEW_WHITELIST,
    "POST:/api/whitelist": ImpersonationAction.CREATE_WHITELIST,
    "PUT:/api/whitelist/*": ImpersonationAction.UPDATE_WHITELIST,
    "DELETE:/api/whitelist/*": ImpersonationAction.DELETE_WHITELIST,
    
    # Groups
    "GET:/api/groups": ImpersonationAction.VIEW_GROUPS,
    "GET:/api/groups/*": ImpersonationAction.VIEW_GROUPS,
    "POST:/api/groups": ImpersonationAction.CREATE_GROUP,
    "PUT:/api/groups/*": ImpersonationAction.UPDATE_GROUP,
    "DELETE:/api/groups/*": ImpersonationAction.DELETE_GROUP,
    
    # API Keys
    "GET:/api/api-keys": ImpersonationAction.VIEW_API_KEYS,
    "POST:/api/api-keys": ImpersonationAction.CREATE_API_KEY,
    "DELETE:/api/api-keys/*": ImpersonationAction.DELETE_API_KEY,
    
    # Settings
    "GET:/api/settings": ImpersonationAction.VIEW_SETTINGS,
    "PUT:/api/settings": ImpersonationAction.UPDATE_SETTINGS,
    
    # Admin management
    "POST:/api/admin/admins": ImpersonationAction.CREATE_ADMIN,
    "PUT:/api/admin/admins/*": ImpersonationAction.UPDATE_ADMIN,
    "DELETE:/api/admin/admins/*": ImpersonationAction.DELETE_ADMIN,
}


def get_action_for_route(method: str, path: str) -> str:
    """
    Get the action type for a given HTTP method and path.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: Request path
        
    Returns:
        Action string or None if not mapped
    """
    route_key = f"{method}:{path}"
    
    # Try exact match first
    if route_key in ROUTE_ACTION_MAP:
        return ROUTE_ACTION_MAP[route_key]
    
    # Try wildcard matching
    for pattern, action in ROUTE_ACTION_MAP.items():
        if "*" in pattern:
            pattern_method, pattern_path = pattern.split(":", 1)
            if method == pattern_method:
                # Convert wildcard pattern to check
                base_path = pattern_path.replace("/*", "")
                if path.startswith(base_path) and path != base_path:
                    return action
    
    return None


def is_action_allowed(action: str) -> bool:
    """Check if an action is allowed during impersonation."""
    if action is None:
        return True  # If no action mapping, allow by default
    return action in IMPERSONATION_ALLOWED_ACTIONS


def is_action_forbidden(action: str) -> bool:
    """Check if an action is forbidden during impersonation."""
    if action is None:
        return False  # If no action mapping, not forbidden by default
    return action in IMPERSONATION_FORBIDDEN_ACTIONS


def validate_impersonation_reason(reason: str) -> tuple[bool, str]:
    """
    Validate impersonation reason.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not IMPERSONATION_CONFIG["require_reason"]:
        return True, ""
    
    if not reason:
        return False, "Reason is required for impersonation"
    
    reason = reason.strip()
    if len(reason) < IMPERSONATION_CONFIG["min_reason_length"]:
        return False, f"Reason must be at least {IMPERSONATION_CONFIG['min_reason_length']} characters"
    
    return True, ""


def get_impersonation_duration() -> int:
    """Get impersonation session duration in seconds."""
    return IMPERSONATION_CONFIG["max_duration_seconds"]


def get_impersonation_hours() -> int:
    """Get impersonation session duration in hours."""
    return IMPERSONATION_CONFIG["max_duration_hours"]
