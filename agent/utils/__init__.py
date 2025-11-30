"""
Utilities module - Common utilities and helpers.
Vietnam ONLY - Modular implementation.
"""

from .ip_detector import IPDetector, get_local_ip, check_admin_privileges, get_ip_detector
from .error_handler import CriticalErrorHandler
from .validators import validate_configuration

__all__ = [
    'IPDetector',
    'get_local_ip',
    'check_admin_privileges',
    'get_ip_detector',
    'CriticalErrorHandler',
    'validate_configuration'
]