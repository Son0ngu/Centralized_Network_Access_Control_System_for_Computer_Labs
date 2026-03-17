"""
RBAC Configuration - Role hierarchy, permissions mapping.
Chi 2 role: admin (toan quyen) va teacher (gioi han boi ownership).
Format permission: resource:action
"""

# ============================================================================
# ROLE HIERARCHY
# ============================================================================

ROLE_HIERARCHY = {
    "admin": 100,    # Toan quyen
    "teacher": 50,   # Gioi han boi ownership
}

VALID_ROLES = list(ROLE_HIERARCHY.keys())

# ============================================================================
# PERMISSION DEFINITIONS - resource:action format
# ============================================================================

TEACHER_PERMISSIONS = [
    # Profile
    "profile:read",
    "profile:change_password",

    # Dashboard
    "dashboard:read",

    # Groups (gioi han boi ownership - chi Group minh tao)
    "groups:read",
    "groups:create",
    "groups:update",
    "groups:delete",
    "groups:manage_agents",

    # Agents (chi xem Agents trong Group cua minh)
    "agents:read",
    "agents:detail",

    # Whitelist (gioi han boi ownership - chi Group minh tao)
    "whitelist:read",
    "whitelist:create",
    "whitelist:update",
    "whitelist:delete",
    "whitelist:sync",

    # Logs (chi thay logs tu Agents trong Group minh)
    "logs:read",
]

ADMIN_EXTRA_PERMISSIONS = [
    # User management (chi Admin)
    "users:create",
    "users:read",
    "users:update",
    "users:delete",
    "users:reset_password",

    # Agent management day du
    "agents:delete",
    "agents:command",

    # API Keys
    "api_keys:read",
    "api_keys:create",
    "api_keys:revoke",

    # Logs day du
    "logs:export",
    "logs:delete",

    # System
    "system:config",
    "audit:read",
]

# Admin ke thua toan bo quyen teacher + quyen rieng
ROLE_PERMISSIONS = {
    "teacher": TEACHER_PERMISSIONS,
    "admin": TEACHER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS,
}

# All permissions in the system
ALL_PERMISSIONS = list(set(TEACHER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS))
ALL_PERMISSIONS.sort()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_permissions(role: str) -> list:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, [])


def check_permission(role: str, permission: str) -> bool:
    """Check if role has specific permission."""
    return permission in get_all_permissions(role)


def can_access_group(user: dict, group: dict) -> bool:
    """
    Check if user can access a specific group.
    Admin: always True (toan quyen)
    Teacher: only if group.created_by == user._id (ownership)
    """
    if user.get("role") == "admin":
        return True
    return str(group.get("created_by")) == str(user.get("_id"))


def is_admin(role: str) -> bool:
    """Check if role is admin."""
    return role == "admin"
