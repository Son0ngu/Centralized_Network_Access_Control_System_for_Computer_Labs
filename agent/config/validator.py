import ctypes
import logging
import subprocess
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("config.validator")


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate configuration and return issues.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    _validate_server_config(config, errors, warnings)
    
    _validate_firewall_config(config, errors, warnings)
    
    _validate_logging_config(config, warnings)
    
    _validate_whitelist_config(config, warnings)
    
    _validate_heartbeat_config(config, warnings)
    
    return len(errors) == 0, errors, warnings


def _validate_server_config(
    config: Dict, 
    errors: List[str], 
    warnings: List[str]
) -> None:
    """Validate server configuration."""
    server_config = config.get("server", {})
    
    if not server_config.get("url") and not server_config.get("urls"):
        errors.append("Server URL is required (either 'url' or 'urls')")
    
    # Validate URLs format
    urls_to_check = list(server_config.get("urls", []))
    if server_config.get("url"):
        urls_to_check.append(server_config["url"])
    
    for url in urls_to_check:
        if not url.startswith(("http://", "https://")):
            warnings.append(f"URL should start with http:// or https://: {url}")


def _validate_firewall_config(
    config: Dict, 
    errors: List[str], 
    warnings: List[str]
) -> None:
    """Validate firewall configuration."""
    firewall_config = config.get("firewall", {})
    valid_modes = ["block", "warn", "monitor", "whitelist_only"]
    current_mode = firewall_config.get("mode", "monitor")
    
    if current_mode not in valid_modes:
        errors.append(f"Invalid firewall mode: {current_mode}. Valid: {valid_modes}")
        config["firewall"]["mode"] = "monitor"
    
    # Admin privileges check
    admin_required_modes = ["block", "whitelist_only"]
    if current_mode in admin_required_modes:
        if not _has_admin_privileges():
            warnings.append(
                f"Mode '{current_mode}' requires admin privileges - "
                "will auto-switch to 'monitor'"
            )


def _validate_logging_config(config: Dict, warnings: List[str]) -> None:
    """Validate logging configuration."""
    logging_config = config.get("logging", {})
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_level = logging_config.get("level", "INFO")
    
    if log_level.upper() not in valid_levels:
        warnings.append(f"Invalid log level: {log_level}. Using INFO")
        config["logging"]["level"] = "INFO"


def _validate_whitelist_config(config: Dict, warnings: List[str]) -> None:
    """Validate whitelist configuration."""
    whitelist_config = config.get("whitelist", {})
    
    interval = whitelist_config.get("update_interval", 60)
    if interval < 30:
        warnings.append(
            f"Whitelist update interval ({interval}s) too low - may overload server"
        )


def _validate_heartbeat_config(config: Dict, warnings: List[str]) -> None:
    """Validate heartbeat configuration."""
    heartbeat_config = config.get("heartbeat", {})
    
    interval = heartbeat_config.get("interval", 20)
    if interval < 10:
        warnings.append(
            f"Heartbeat interval ({interval}s) too low - may overload server"
        )


def _has_admin_privileges() -> bool:
    """Check if running with administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "currentprofile"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False