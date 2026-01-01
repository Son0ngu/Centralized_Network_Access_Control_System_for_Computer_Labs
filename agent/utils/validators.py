import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("utils.validators")


def validate_configuration(config: Dict) -> bool:
    logger.info("Validating configuration...")
    errors: List[str] = []      # Critical errors - agent will not start
    warnings: List[str] = []    # Non-critical issues
    
    try:
        # 1. Server configuration validation
        errors_s, warnings_s = _validate_server_config(config)
        errors.extend(errors_s)
        warnings.extend(warnings_s)
        
        # 2. Logging configuration validation
        errors_l, warnings_l = _validate_logging_config(config)
        errors.extend(errors_l)
        warnings.extend(warnings_l)
        
        # 3. Whitelist configuration validation
        warnings_w = _validate_whitelist_config(config)
        warnings.extend(warnings_w)
        
        # 4. Heartbeat configuration validation
        warnings_h = _validate_heartbeat_config(config)
        warnings.extend(warnings_h)
        
        # Log validation results
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"   - {error}")
            return False
        
        if warnings:
            logger.warning("Configuration warnings:")
            for warning in warnings:
                logger.warning(f"   - {warning}")
        
        logger.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Error during configuration validation: {e}")
        return False


def _validate_server_config(config: Dict) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []
    
    server_config = config.get("server", {})
    
    if not server_config.get("url") and not server_config.get("urls"):
        errors.append("Server URL is required (either 'url' or 'urls')")
    
    urls_to_check = server_config.get("urls", [])
    if server_config.get("url"):
        urls_to_check.append(server_config["url"])
    
    for url in urls_to_check:
        if not url.startswith(("http://", "https://")):
            warnings.append(f"URL should start with http:// or https://: {url}")
    
    return errors, warnings

def _validate_logging_config(config: Dict) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []
    
    logging_config = config.get("logging", {})
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_level = logging_config.get("level", "INFO")
    
    if log_level not in valid_levels:
        warnings.append(f"Invalid log level: {log_level}. Using INFO instead")
        config["logging"]["level"] = "INFO"
    
    return errors, warnings


def _validate_whitelist_config(config: Dict) -> List[str]:
    warnings = []
    
    whitelist_config = config.get("whitelist", {})
    if whitelist_config.get("update_interval", 0) < 30:
        warnings.append(
            "Whitelist update interval too low (<30s) - may cause server overload"
        )
    
    return warnings


def _validate_heartbeat_config(config: Dict) -> List[str]:
    warnings = []
    
    heartbeat_config = config.get("heartbeat", {})
    if heartbeat_config.get("interval", 0) < 10:
        warnings.append(
            "Heartbeat interval too low (<10s) - may cause server overload"
        )
    
    return warnings