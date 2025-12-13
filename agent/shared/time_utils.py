import logging
import time
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("shared.time_utils")


def _load_vietnam_timezone() -> tzinfo:
    """
    Return the Vietnam timezone, falling back to a fixed offset.
    """
    try:
        return ZoneInfo("Asia/Ho_Chi_Minh")
    except ZoneInfoNotFoundError:
        logger.warning(
            "tzdata package is missing; falling back to fixed UTC+7 offset"
        )
        return timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


# Vietnam timezone constant
VIETNAM_TZ = _load_vietnam_timezone()

# Agent start time for uptime calculation
_start_time: float = time.time()


# ========================================
# CORE TIME FUNCTIONS
# ========================================

def now() -> float:
    """
    Get current Unix timestamp.
    
    Returns:
        float: Current Unix timestamp in seconds
    """
    return time.time()


def now_vietnam() -> datetime:
    """
    Get current Vietnam datetime (Asia/Ho_Chi_Minh).
    
    Returns:
        datetime: Current datetime in Vietnam timezone
    """
    return datetime.now(VIETNAM_TZ)


def now_iso() -> str:
    """
    Get current Vietnam time as ISO 8601 string.
    
    Returns:
        str: ISO 8601 formatted timestamp with timezone
    """
    return datetime.now(VIETNAM_TZ).isoformat()


def now_server_compatible(ts: Optional[float] = None) -> str:
    """
    Return Vietnam ISO timestamp, optionally from Unix timestamp.
    
    Args:
        ts: Optional Unix timestamp. Uses current time if None.
        
    Returns:
        str: ISO 8601 formatted timestamp
    """
    if ts is None:
        return now_iso()
    return datetime.fromtimestamp(ts, VIETNAM_TZ).isoformat()


def sleep(duration: float) -> None:
    """
    Sleep for specified duration.
    
    Args:
        duration: Sleep duration in seconds
    """
    if duration > 0:
        time.sleep(duration)


# ========================================
# CACHE & VALIDATION
# ========================================

def is_cache_valid(timestamp: float, ttl: float) -> bool:
    """
    Check if cache is still valid based on TTL.
    
    Args:
        timestamp: Cache creation Unix timestamp
        ttl: Time-to-live in seconds
        
    Returns:
        bool: True if cache is still valid
    """
    return (now() - timestamp) < ttl


def cache_age(timestamp: float) -> float:
    """
    Get cache age in seconds.
    
    Args:
        timestamp: Cache creation Unix timestamp
        
    Returns:
        float: Age in seconds
    """
    return now() - timestamp


# ========================================
# AGENT UPTIME
# ========================================

def uptime() -> float:
    """
    Get agent uptime in seconds.
    
    Returns:
        float: Uptime in seconds since agent start
    """
    return now() - _start_time


def uptime_string() -> str:
    """
    Get agent uptime as readable string.
    
    Returns:
        str: Human-readable uptime (e.g., "2h 30m 15s")
    """
    secs = uptime()
    hours = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    secs_remaining = int(secs % 60)
    return f"{hours}h {mins}m {secs_remaining}s"


def reset_uptime() -> None:
    """Reset uptime counter (for testing)."""
    global _start_time
    _start_time = now()


# ========================================
# DEBUG & DIAGNOSTICS
# ========================================

def debug_time_info() -> dict:
    """
    Get debug time information.
    
    Returns:
        dict: Dictionary with current time info
    """
    return {
        "unix": now(),
        "vietnam_iso": now_iso(),
        "uptime": uptime_string(),
        "timezone": str(VIETNAM_TZ)
    }


# ========================================
# COMPATIBILITY ALIASES
# ========================================

# Maintain compatibility with existing code
agent_time = now_iso
cache_time = now