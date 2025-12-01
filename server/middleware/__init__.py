"""
Middleware module for authentication and authorization.
Vietnam ONLY - Clean and simple
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
    'init_auth_middleware'
]
