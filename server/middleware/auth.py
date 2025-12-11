"""
Authentication Middleware - API Key and JWT validation for agent requests.
- Clean and simple
"""

import logging
from functools import wraps
from typing import Callable, Optional
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# Global reference to API Key Service (set during init)
_api_key_service = None

# Global reference to JWT Service (set during init)
_jwt_service = None


def init_auth_middleware(api_key_service, jwt_service=None):
    """
    Initialize the auth middleware with the API Key Service and JWT Service.
    
    Args:
        api_key_service: APIKeyService instance
        jwt_service: JWTService instance (optional)
    """
    global _api_key_service, _jwt_service
    _api_key_service = api_key_service
    _jwt_service = jwt_service
    logger.info("Auth middleware initialized with API Key Service" + 
                (" and JWT Service" if jwt_service else ""))


def get_api_key_from_request() -> Optional[str]:
    """
    Extract API key from request.
    
    Checks in order:
    1. X-API-Key header
    2. Authorization header (Bearer token)
    3. api_key query parameter
    
    Returns:
        API key string or None
    """
    # Check X-API-Key header (preferred)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key.strip()
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        # Support both "Bearer <key>" and just "<key>"
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        elif auth_header.startswith("ApiKey "):
            return auth_header[7:].strip()
        else:
            return auth_header.strip()
    
    # Check query parameter (least preferred, for debugging)
    api_key = request.args.get("api_key")
    if api_key:
        return api_key.strip()
    
    return None


def require_api_key(permission: str = "register"):
    """
    Decorator to require valid API key for endpoint access.
    
    Args:
        permission: Required permission (e.g., "register", "sync", "logs")
        
    Usage:
        @app.route('/api/agents/register')
        @require_api_key("register")
        def register_agent():
            # g.api_key_info contains validated key info
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if middleware is initialized
            if _api_key_service is None:
                logger.error("Auth middleware not initialized!")
                return jsonify({
                    "success": False,
                    "error": "Server configuration error"
                }), 500
            
            # Extract API key
            api_key = get_api_key_from_request()
            
            if not api_key:
                logger.warning(f"Missing API key for {request.endpoint} from {request.remote_addr}")
                return jsonify({
                    "success": False,
                    "error": "API key required",
                    "message": "Please provide API key in X-API-Key header"
                }), 401
            
            # Validate API key
            validation = _api_key_service.validate_api_key(api_key, permission)
            
            if not validation.get("valid"):
                error_msg = validation.get("error", "Invalid API key")
                logger.warning(
                    f"Invalid API key for {request.endpoint} from {request.remote_addr}: {error_msg}"
                )
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 401
            
            # Store validated key info in Flask's g object for use in endpoint
            g.api_key_info = validation
            g.api_key_id = validation.get("key_id")
            g.api_key_name = validation.get("name")
            
            logger.debug(
                f"API key validated for {request.endpoint}: "
                f"key={validation.get('name')} ({validation.get('key_id')[:8]}...)"
            )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_api_key(f: Callable) -> Callable:
    """
    Decorator that validates API key if provided, but doesn't require it.
    Useful for endpoints that have different behavior based on authentication.
    
    Usage:
        @app.route('/api/public')
        @optional_api_key
        def public_endpoint():
            if g.api_key_info:
                # Authenticated request
                ...
            else:
                # Anonymous request
                ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.api_key_info = None
        g.api_key_id = None
        g.api_key_name = None
        
        api_key = get_api_key_from_request()
        
        if api_key and _api_key_service:
            validation = _api_key_service.validate_api_key(api_key)
            if validation.get("valid"):
                g.api_key_info = validation
                g.api_key_id = validation.get("key_id")
                g.api_key_name = validation.get("name")
        
        return f(*args, **kwargs)
    
    return decorated_function


class APIKeyMiddleware:
    """
    Flask middleware class for API key authentication.
    Can be used as a before_request handler.
    """
    
    def __init__(self, api_key_service, protected_prefixes: list = None):
        """
        Initialize middleware.
        
        Args:
            api_key_service: APIKeyService instance
            protected_prefixes: List of URL prefixes that require API key
                               e.g., ['/api/agents', '/api/whitelist']
        """
        self.api_key_service = api_key_service
        self.protected_prefixes = protected_prefixes or []
        logger.info(f"APIKeyMiddleware initialized for prefixes: {self.protected_prefixes}")
    
    def before_request(self):
        """
        Check API key before each request.
        Call this in Flask's before_request.
        """
        # Check if this path needs protection
        path = request.path
        needs_protection = any(
            path.startswith(prefix) for prefix in self.protected_prefixes
        )
        
        if not needs_protection:
            return None  # Continue to endpoint
        
        # Skip certain safe endpoints
        safe_endpoints = [
            '/api/health',
            '/api/status'
        ]
        if path in safe_endpoints:
            return None
        
        # Check API key
        api_key = get_api_key_from_request()
        
        if not api_key:
            return jsonify({
                "success": False,
                "error": "API key required"
            }), 401
        
        validation = self.api_key_service.validate_api_key(api_key)
        
        if not validation.get("valid"):
            return jsonify({
                "success": False,
                "error": validation.get("error", "Invalid API key")
            }), 401
        
        # Store for later use
        g.api_key_info = validation
        g.api_key_id = validation.get("key_id")
        
        return None  # Continue to endpoint


# ============================================================================
# JWT Authentication
# ============================================================================

def get_jwt_from_request() -> Optional[str]:
    """
    Extract JWT token from request.
    
    Checks in order:
    1. Authorization header (Bearer token)
    2. X-Access-Token header
    3. access_token query parameter
    
    Returns:
        JWT token string or None
    """
    # Check Authorization header (preferred)
    auth_header = request.headers.get("Authorization")
    if auth_header:
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        # Don't return non-Bearer auth headers (might be API key)
    
    # Check X-Access-Token header
    token = request.headers.get("X-Access-Token")
    if token:
        return token.strip()
    
    # Check query parameter (for debugging only)
    token = request.args.get("access_token")
    if token:
        return token.strip()
    
    return None


def require_jwt(f: Callable) -> Callable:
    """
    Decorator to require valid JWT token for endpoint access.
    
    Usage:
        @app.route('/api/agents/heartbeat')
        @require_jwt
        def heartbeat():
            # g.jwt_payload contains validated token payload
            # g.agent_id contains the agent ID from token
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if JWT service is initialized
        if _jwt_service is None:
            logger.error("JWT service not initialized!")
            return jsonify({
                "success": False,
                "error": "Server configuration error"
            }), 500
        
        # Extract JWT token
        token = get_jwt_from_request()
        
        if not token:
            logger.warning(f"Missing JWT token for {request.endpoint} from {request.remote_addr}")
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Please provide JWT token in Authorization header (Bearer <token>)"
            }), 401
        
        # Validate token
        is_valid, payload, error = _jwt_service.validate_access_token(token)
        
        if not is_valid:
            logger.warning(
                f"Invalid JWT for {request.endpoint} from {request.remote_addr}: {error}"
            )
            
            # Check if token is expired for special handling
            if error == "Token has expired":
                return jsonify({
                    "success": False,
                    "error": "Token expired",
                    "message": "Please refresh your token using the refresh endpoint",
                    "code": "TOKEN_EXPIRED"
                }), 401
            
            return jsonify({
                "success": False,
                "error": error or "Invalid token"
            }), 401
        
        # Store validated payload in Flask's g object
        g.jwt_payload = payload
        g.agent_id = payload.get("sub")
        g.user_id = payload.get("user_id")
        g.token_jti = payload.get("jti")
        
        logger.debug(
            f"JWT validated for {request.endpoint}: agent={g.agent_id}"
        )
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_jwt(f: Callable) -> Callable:
    """
    Decorator that validates JWT if provided, but doesn't require it.
    Useful for endpoints that have different behavior based on authentication.
    
    Usage:
        @app.route('/api/public')
        @optional_jwt
        def public_endpoint():
            if g.agent_id:
                # Authenticated request
                ...
            else:
                # Anonymous request
                ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.jwt_payload = None
        g.agent_id = None
        g.user_id = None
        g.token_jti = None
        
        token = get_jwt_from_request()
        
        if token and _jwt_service:
            is_valid, payload, _ = _jwt_service.validate_access_token(token)
            if is_valid:
                g.jwt_payload = payload
                g.agent_id = payload.get("sub")
                g.user_id = payload.get("user_id")
                g.token_jti = payload.get("jti")
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_jwt_or_api_key(permission: str = None):
    """
    Decorator that accepts either JWT token or API key.
    Useful for endpoints that support both authentication methods.
    
    Args:
        permission: Required permission for API key (if used)
        
    Usage:
        @app.route('/api/endpoint')
        @require_jwt_or_api_key(permission='sync')
        def endpoint():
            if g.agent_id:
                # JWT authenticated
                ...
            elif g.api_key_id:
                # API key authenticated
                ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Try JWT first
            token = get_jwt_from_request()
            
            if token and _jwt_service:
                is_valid, payload, _ = _jwt_service.validate_access_token(token)
                if is_valid:
                    g.jwt_payload = payload
                    g.agent_id = payload.get("sub")
                    g.user_id = payload.get("user_id")
                    g.token_jti = payload.get("jti")
                    g.api_key_info = None
                    g.api_key_id = None
                    return f(*args, **kwargs)
            
            # Try API key
            api_key = get_api_key_from_request()
            
            if api_key and _api_key_service:
                validation = _api_key_service.validate_api_key(api_key, permission)
                if validation.get("valid"):
                    g.api_key_info = validation
                    g.api_key_id = validation.get("key_id")
                    g.api_key_name = validation.get("name")
                    g.jwt_payload = None
                    g.agent_id = None
                    return f(*args, **kwargs)
            
            # Neither valid
            logger.warning(
                f"No valid auth for {request.endpoint} from {request.remote_addr}"
            )
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Please provide valid JWT token or API key"
            }), 401
        
        return decorated_function
    return decorator
