"""
Middleware module for authentication and authorization.
- Clean and simple
"""

from .auth import (
    # API Key authentication
    require_api_key, 
    get_api_key_from_request, 
    optional_api_key,
    # JWT authentication
    require_jwt,
    get_jwt_from_request,
    optional_jwt,
    require_jwt_or_api_key,
    # Tenant utilities
    get_current_tenant_id,
    get_current_admin_id,
    require_tenant,
    # Initialization
    init_auth_middleware
)

from .authorization import (
    # Role-based access control
    require_super_admin,
    require_tenant_admin,
    require_any_admin,
    check_impersonation,
    # Utilities
    get_current_role,
    get_current_admin_context,
    is_super_admin,
    is_tenant_admin,
    is_impersonating,
    check_permission,
    get_impersonation_banner_data,
    log_impersonation_action,
    # Initialization
    init_authorization_middleware
)

__all__ = [
    # API Key
    'require_api_key',
    'get_api_key_from_request',
    'optional_api_key',
    # JWT
    'require_jwt',
    'get_jwt_from_request',
    'optional_jwt',
    'require_jwt_or_api_key',
    # Tenant
    'get_current_tenant_id',
    'get_current_admin_id',
    'require_tenant',
    # Authorization decorators
    'require_super_admin',
    'require_tenant_admin',
    'require_any_admin',
    'check_impersonation',
    # Authorization utilities
    'get_current_role',
    'get_current_admin_context',
    'is_super_admin',
    'is_tenant_admin',
    'is_impersonating',
    'check_permission',
    'get_impersonation_banner_data',
    'log_impersonation_action',
    # Init
    'init_auth_middleware',
    'init_authorization_middleware'
]
