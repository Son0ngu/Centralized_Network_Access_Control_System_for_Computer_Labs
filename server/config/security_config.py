"""
Security Configuration
----------------------
Simple security settings for the application.
"""

import os
from typing import Dict

# Password Policy (Simple)
PASSWORD_CONFIG = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_special": True,
    "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?",
    "max_length": 128,
    "min_entropy": 40,
}

# Account Security
ACCOUNT_CONFIG = {
    "max_login_attempts": 5,
    "lockout_duration": 900,  # 15 minutes
    "session_timeout": 3600,  # 1 hour
}

# Rate Limiting
RATE_LIMIT_CONFIG = {
    "login": {"requests": 5, "window": 300},
    "register": {"requests": 5, "window": 300},
    "api_call": {"requests": 100, "window": 60},
}

# Input Sanitization
SANITIZATION_CONFIG = {
    "max_string_length": 1000,
    "strip_whitespace": True,
    "normalize_unicode": True,
    "max_json_depth": 10,
    "max_array_length": 1000,
}

# CORS Settings
CORS_CONFIG = {
    "origins": ["*"],
    "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
    "allow_credentials": True,
}


def get_security_config() -> Dict:
    """Get security configuration."""
    return {
        "password": PASSWORD_CONFIG,
        "account": ACCOUNT_CONFIG,
        "rate_limit": RATE_LIMIT_CONFIG,
        "sanitization": SANITIZATION_CONFIG,
        "cors": CORS_CONFIG,
    }
