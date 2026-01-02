"""
Broadcast Configuration
-----------------------
Configuration for system broadcast types and display settings.
"""

from enum import Enum
from typing import Dict, Any


class BroadcastType(Enum):
    """Broadcast type enum."""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


# Broadcast type display configurations
BROADCAST_TYPES: Dict[str, Dict[str, Any]] = {
    "info": {
        "color": "blue",
        "bg_class": "alert-info",
        "icon": "fa-info-circle",
        "icon_class": "text-info",
        "dismissible": True,
        "priority": 1,
        "description": "General information"
    },
    "warning": {
        "color": "yellow",
        "bg_class": "alert-warning",
        "icon": "fa-exclamation-triangle",
        "icon_class": "text-warning",
        "dismissible": True,
        "priority": 2,
        "description": "Important notices"
    },
    "danger": {
        "color": "red",
        "bg_class": "alert-danger",
        "icon": "fa-exclamation-circle",
        "icon_class": "text-danger",
        "dismissible": False,  # Cannot be dismissed
        "priority": 3,  # Highest priority, shown first
        "description": "Critical alerts - cannot be dismissed"
    }
}


# Broadcast priority levels
BROADCAST_PRIORITY = {
    "normal": 1,
    "high": 2
}


# Targeting options
BROADCAST_TARGET_ALL = "all"
BROADCAST_TARGET_SPECIFIC = "specific"


# Display settings
BROADCAST_DISPLAY_CONFIG = {
    "max_visible": 3,  # Maximum broadcasts to show at once
    "auto_refresh_interval": 60000,  # Check for new broadcasts every 60 seconds (ms)
    "animation_duration": 300,  # Dismiss animation duration (ms)
    "position": "top",  # Display position: top, bottom
    "stack_order": "priority",  # priority, chronological
}


# API rate limits
BROADCAST_RATE_LIMITS = {
    "create_per_hour": 10,  # Max broadcasts a super admin can create per hour
    "dismiss_per_minute": 20,  # Max dismissals per admin per minute
}


def get_broadcast_type_config(broadcast_type: str) -> Dict[str, Any]:
    """
    Get configuration for a broadcast type.
    
    Args:
        broadcast_type: Type of broadcast (info, warning, danger)
        
    Returns:
        Configuration dict or default (info) if type not found
    """
    return BROADCAST_TYPES.get(broadcast_type, BROADCAST_TYPES["info"])


def is_dismissible(broadcast_type: str) -> bool:
    """
    Check if a broadcast type can be dismissed.
    
    Args:
        broadcast_type: Type of broadcast
        
    Returns:
        True if dismissible, False otherwise
    """
    config = get_broadcast_type_config(broadcast_type)
    return config.get("dismissible", True)


def get_alert_class(broadcast_type: str) -> str:
    """
    Get Bootstrap alert class for broadcast type.
    
    Args:
        broadcast_type: Type of broadcast
        
    Returns:
        CSS class for alert
    """
    config = get_broadcast_type_config(broadcast_type)
    return config.get("bg_class", "alert-info")


def get_icon_class(broadcast_type: str) -> str:
    """
    Get Font Awesome icon class for broadcast type.
    
    Args:
        broadcast_type: Type of broadcast
        
    Returns:
        Icon class (e.g., "fa-info-circle")
    """
    config = get_broadcast_type_config(broadcast_type)
    return config.get("icon", "fa-info-circle")


def sort_broadcasts_by_priority(broadcasts: list) -> list:
    """
    Sort broadcasts by priority (danger first, then warning, then info).
    
    Args:
        broadcasts: List of broadcast dicts
        
    Returns:
        Sorted list
    """
    def get_priority(b):
        type_priority = BROADCAST_TYPES.get(b.get("type", "info"), {}).get("priority", 1)
        custom_priority = BROADCAST_PRIORITY.get(b.get("priority", "normal"), 1)
        return (type_priority * 10 + custom_priority, b.get("created_at"))
    
    return sorted(broadcasts, key=get_priority, reverse=True)


# Export for client-side use (JSON serializable)
def get_client_config() -> Dict[str, Any]:
    """
    Get configuration for client-side JavaScript.
    
    Returns:
        Dict with client-safe configuration
    """
    return {
        "types": {
            k: {
                "color": v["color"],
                "bgClass": v["bg_class"],
                "icon": v["icon"],
                "iconClass": v["icon_class"],
                "dismissible": v["dismissible"]
            }
            for k, v in BROADCAST_TYPES.items()
        },
        "display": {
            "maxVisible": BROADCAST_DISPLAY_CONFIG["max_visible"],
            "autoRefreshInterval": BROADCAST_DISPLAY_CONFIG["auto_refresh_interval"],
            "animationDuration": BROADCAST_DISPLAY_CONFIG["animation_duration"],
            "position": BROADCAST_DISPLAY_CONFIG["position"]
        }
    }
