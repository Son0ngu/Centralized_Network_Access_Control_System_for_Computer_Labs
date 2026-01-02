"""
Security Middleware
-------------------
Input sanitization, rate limiting, and security headers.
"""

import re
import html
import logging
from functools import wraps
from typing import Any, Callable, Dict, List
from flask import request, jsonify, g
from datetime import datetime, timedelta

from config.security_config import (
    SANITIZATION_CONFIG,
    RATE_LIMIT_CONFIG,
)
from time_utils import now_vietnam

logger = logging.getLogger(__name__)

# In-memory rate limit storage (use Redis in production)
_rate_limit_store = {}


class InputSanitizer:
    """Sanitizes user input to prevent injection attacks."""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = None) -> str:
        """
        Sanitize string input.
        - Strip HTML tags
        - Escape special characters
        - Limit length
        """
        if not isinstance(value, str):
            return str(value)
        
        # Strip leading/trailing whitespace
        if SANITIZATION_CONFIG["strip_whitespace"]:
            value = value.strip()
        
        # Normalize unicode
        if SANITIZATION_CONFIG["normalize_unicode"]:
            import unicodedata
            value = unicodedata.normalize('NFKC', value)
        
        # Remove HTML tags
        value = re.sub(r'<[^>]*>', '', value)
        
        # Escape HTML entities
        value = html.escape(value)
        
        # Limit length
        max_len = max_length or SANITIZATION_CONFIG["max_string_length"]
        if len(value) > max_len:
            value = value[:max_len]
        
        return value
    
    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize and validate email address."""
        if not isinstance(email, str):
            raise ValueError("Email must be a string")
        
        email = email.strip().lower()
        
        # Basic email validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise ValueError("Invalid email format")
        
        # Prevent email header injection
        if '\n' in email or '\r' in email:
            raise ValueError("Invalid characters in email")
        
        return email
    
    @staticmethod
    def sanitize_dict(data: Dict, max_depth: int = None) -> Dict:
        """
        Recursively sanitize dictionary.
        - Limit nesting depth
        - Sanitize string values
        - Remove null bytes
        """
        max_depth = max_depth or SANITIZATION_CONFIG["max_json_depth"]
        
        def _sanitize(obj, depth=0):
            if depth > max_depth:
                raise ValueError(f"JSON nesting too deep (max: {max_depth})")
            
            if isinstance(obj, dict):
                return {
                    InputSanitizer.sanitize_string(k): _sanitize(v, depth + 1)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                if len(obj) > SANITIZATION_CONFIG["max_array_length"]:
                    raise ValueError(f"Array too large (max: {SANITIZATION_CONFIG['max_array_length']})")
                return [_sanitize(item, depth + 1) for item in obj]
            elif isinstance(obj, str):
                # Remove null bytes
                obj = obj.replace('\x00', '')
                return InputSanitizer.sanitize_string(obj)
            else:
                return obj
        
        return _sanitize(data)
    
    @staticmethod
    def sanitize_sql(value: str) -> str:
        """
        Prevent SQL injection (defense in depth - use parameterized queries).
        """
        dangerous_patterns = [
            r"('\s*(OR|AND)\s*'?1'?\s*=\s*'?1)",
            r"(;\s*(DROP|DELETE|INSERT|UPDATE|ALTER)\s+)",
            r"(--\s*$)",
            r"(/\*.*\*/)",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError("Potential SQL injection detected")
        
        return value
    
    @staticmethod
    def sanitize_nosql(data: Any, max_depth: int = 10) -> Any:
        """
        Prevent NoSQL injection by stripping MongoDB operators.
        
        MongoDB operators start with $ and can be used for injection:
        - $gt, $gte, $lt, $lte: comparison operators
        - $ne: not equal (bypass authentication)
        - $regex: pattern matching
        - $where: JavaScript execution
        - $or, $and: logical operators
        """
        dangerous_keys = {
            '$gt', '$gte', '$lt', '$lte', '$eq', '$ne',
            '$in', '$nin', '$regex', '$where', '$exists',
            '$type', '$expr', '$mod', '$text', '$geoNear',
            '$or', '$and', '$nor', '$not', '$elemMatch',
            '$size', '$all', '$bitsAllClear', '$bitsAllSet',
        }
        
        def _sanitize(obj, depth=0):
            if depth > max_depth:
                return None
            
            if isinstance(obj, dict):
                # Remove dangerous keys
                sanitized = {}
                for key, value in obj.items():
                    # Strip keys that start with $
                    if isinstance(key, str) and key.startswith('$'):
                        if key.lower() in dangerous_keys:
                            logger.warning(f"NoSQL injection attempt blocked: {key}")
                            continue
                    sanitized[key] = _sanitize(value, depth + 1)
                return sanitized
            elif isinstance(obj, list):
                return [_sanitize(item, depth + 1) for item in obj]
            elif isinstance(obj, str):
                # Check for JSON-encoded injection
                if obj.startswith('{') and '$' in obj:
                    try:
                        import json
                        parsed = json.loads(obj)
                        if isinstance(parsed, dict) and any(k.startswith('$') for k in parsed.keys()):
                            logger.warning(f"NoSQL injection in string blocked: {obj[:50]}")
                            return InputSanitizer.sanitize_string(obj)
                    except json.JSONDecodeError:
                        pass
                return obj
            else:
                return obj
        
        return _sanitize(data)
    
    @staticmethod
    def sanitize_input(value: Any) -> Any:
        """
        Universal input sanitizer - handles all types.
        Applies XSS, NoSQL injection, and length protections.
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            # Sanitize string
            return InputSanitizer.sanitize_string(value)
        elif isinstance(value, dict):
            # Sanitize dict (NoSQL + XSS)
            sanitized = InputSanitizer.sanitize_nosql(value)
            return InputSanitizer.sanitize_dict(sanitized)
        elif isinstance(value, list):
            # Sanitize list
            if len(value) > SANITIZATION_CONFIG["max_array_length"]:
                value = value[:SANITIZATION_CONFIG["max_array_length"]]
            return [InputSanitizer.sanitize_input(item) for item in value]
        elif isinstance(value, (int, float, bool)):
            return value
        else:
            # Convert to string and sanitize
            return InputSanitizer.sanitize_string(str(value))


class RateLimiter:
    """Rate limiting to prevent abuse."""
    
    @staticmethod
    def check_rate_limit(key: str, limit_type: str) -> bool:
        """
        Check if request exceeds rate limit.
        
        Args:
            key: Unique identifier (e.g., IP address, user ID)
            limit_type: Type of limit (login, register, etc.)
        
        Returns:
            True if allowed, False if rate limited
        """
        if limit_type not in RATE_LIMIT_CONFIG:
            return True
        
        config = RATE_LIMIT_CONFIG[limit_type]
        max_requests = config["requests"]
        window_seconds = config["window"]
        
        now = now_vietnam()
        cache_key = f"{limit_type}:{key}"
        
        # Get request history
        if cache_key not in _rate_limit_store:
            _rate_limit_store[cache_key] = []
        
        requests = _rate_limit_store[cache_key]
        
        # Remove old requests outside window
        cutoff = now - timedelta(seconds=window_seconds)
        requests = [req_time for req_time in requests if req_time > cutoff]
        
        # Check limit
        if len(requests) >= max_requests:
            logger.warning(f"Rate limit exceeded for {cache_key}: {len(requests)}/{max_requests}")
            return False
        
        # Add current request
        requests.append(now)
        _rate_limit_store[cache_key] = requests
        
        return True
    
    @staticmethod
    def get_client_key() -> str:
        """Get unique key for current client."""
        # Try to get user ID first
        if hasattr(g, 'user_id'):
            return f"user:{g.user_id}"
        
        # Fall back to IP address
        if request.environ.get('HTTP_X_FORWARDED_FOR'):
            ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        else:
            ip = request.environ.get('REMOTE_ADDR', 'unknown')
        
        return f"ip:{ip}"


def require_rate_limit(limit_type: str):
    """Decorator to enforce rate limiting."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_key = RateLimiter.get_client_key()
            
            if not RateLimiter.check_rate_limit(client_key, limit_type):
                config = RATE_LIMIT_CONFIG[limit_type]
                return jsonify({
                    "success": False,
                    "error": "Rate limit exceeded",
                    "retry_after": config["window"]
                }), 429
            
            return f(*args, **kwargs)
        return wrapped
    return decorator


def sanitize_request_data(f: Callable) -> Callable:
    """Decorator to sanitize request JSON data."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if request.is_json:
            try:
                request.sanitized_data = InputSanitizer.sanitize_dict(request.get_json())
            except ValueError as e:
                return jsonify({
                    "success": False,
                    "error": f"Invalid input: {str(e)}"
                }), 400
        return f(*args, **kwargs)
    return wrapped


def add_security_headers(response):
    """Add security headers to response."""
    # Basic security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    return response


def audit_log(event_type: str, details: Dict = None):
    """Log security audit event."""
    log_entry = {
        "timestamp": now_vietnam().isoformat(),
        "event_type": event_type,
        "ip_address": request.environ.get('REMOTE_ADDR', 'unknown'),
    }
    logger.info(f"AUDIT: {event_type}")


# Initialize security middleware
def init_security_middleware(app):
    """Initialize security middleware for Flask app."""
    
    # Add security headers to all responses
    app.after_request(add_security_headers)
    
    logger.info("Security middleware initialized")
