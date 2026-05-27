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
    # Initialization
    init_auth_middleware
)
from .csrf import (
    register_csrf,
    set_csrf_cookie,
    delete_csrf_cookie,
    mint_csrf_token,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
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
    # Init
    'init_auth_middleware',
    # CSRF
    'register_csrf',
    'set_csrf_cookie',
    'delete_csrf_cookie',
    'mint_csrf_token',
    'CSRF_COOKIE_NAME',
    'CSRF_HEADER_NAME',
]
