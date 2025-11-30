"""
Packet Detection Handler - Process detected network traffic.
Vietnam ONLY - Clean implementation.
"""

import logging
from typing import Callable, Dict, Optional

from shared.time_utils import now, now_iso, uptime_string

from .agent import AGENT_HOSTNAME
from utils.ip_detector import get_local_ip, check_admin_privileges
from utils.error_handler import CriticalErrorHandler

logger = logging.getLogger("core.handlers")


def create_domain_handler(config: Dict, agent) -> Callable[[Dict], None]:
    """
    Create a domain detection handler function.
    
    Args:
        config: Configuration dictionary
        agent: Agent instance
        
    Returns:
        Callable handler function
    """
    def handler(record: Dict) -> None:
        handle_domain_detection(
            record=record,
            config=config,
            whitelist=agent.whitelist,
            log_sender=agent.log_sender
        )
    
    return handler


def handle_domain_detection(
    record: Dict,
    config: Dict,
    whitelist,
    log_sender
):
    """
    Handle detected domain/IP traffic with UTC timestamps.
    """
    try:
        # Extract packet information
        domain = record.get("domain")
        dest_ip = record.get("dest_ip")
        src_ip = record.get("src_ip", "unknown")
        protocol = record.get("protocol", "TCP")
        port = record.get("port", "unknown")
        
        # Use consolidated IP detection if src_ip not available
        if src_ip == "unknown" or not src_ip:
            src_ip = get_local_ip()
        
        # Enhanced protocol detection
        if port != "unknown":
            port_str = str(port)
            if port_str == "443":
                protocol = "HTTPS"
            elif port_str == "80":
                protocol = "HTTP"
            elif port_str == "53":
                protocol = "DNS"
        
        # Whitelist checking with error handling
        domain_allowed = False
        ip_allowed = False
        
        if domain and whitelist:
            domain_allowed = CriticalErrorHandler.safe_execute(
                whitelist.is_allowed,
                domain,
                error_msg=f"Error checking domain {domain}",
                return_on_error=False
            )
        
        if dest_ip and whitelist:
            ip_allowed = CriticalErrorHandler.safe_execute(
                whitelist.is_ip_allowed,
                dest_ip,
                error_msg=f"Error checking IP {dest_ip}",
                return_on_error=False
            )
        
        # Determine action based on firewall mode
        firewall_config = config.get("firewall", {})
        firewall_mode = firewall_config.get("mode", "monitor")
        firewall_enabled = firewall_config.get("enabled", False)
        
        if firewall_enabled and firewall_mode == "whitelist_only":
            action = "ALLOWED" if (domain_allowed or ip_allowed) else "BLOCKED"
            level = "INFO" if action == "ALLOWED" else "WARNING"
        elif firewall_enabled and firewall_mode == "block":
            action = "BLOCKED" if not (domain_allowed or ip_allowed) else "ALLOWED"
            level = "WARNING" if action == "BLOCKED" else "INFO"
        else:
            action = "MONITORED"
            level = "INFO" if (domain_allowed or ip_allowed) else "WARNING"
        
        # Create enhanced log record with UTC timestamps
        enhanced_record = {
            "timestamp": now_iso(),
            "timestamp_unix": now(),
            "agent_id": config.get("agent_id", "unknown"),
            "level": level,
            "action": action,
            "domain": domain or "unknown",
            "destination": domain or dest_ip or "unknown",
            "source_ip": src_ip,
            "dest_ip": dest_ip or "unknown",
            "protocol": protocol,
            "port": str(port),
            "firewall_mode": firewall_mode,
            "firewall_enabled": firewall_enabled,
            "admin_privileges": check_admin_privileges(),
            "domain_allowed": domain_allowed,
            "ip_allowed": ip_allowed,
            "source": "domain_detection",
            "agent_uptime": uptime_string(),
            "agent_host": AGENT_HOSTNAME,
            "hostname": AGENT_HOSTNAME
        }
        
        # Queue log with error handling
        if log_sender:
            success = CriticalErrorHandler.safe_execute(
                log_sender.queue_log,
                enhanced_record,
                error_msg="Failed to queue detection log",
                return_on_error=False
            )
            
            if not success:
                logger.warning(f"Failed to queue log for {domain or dest_ip}")
        
        # Local logging
        log_message = f"{action}: {domain or dest_ip} -> {dest_ip} ({protocol}:{port})"
        if level == "WARNING":
            logger.warning(log_message)
        else:
            logger.debug(log_message)
    
    except Exception as e:
        logger.error(f"Error in domain detection handler: {e}", exc_info=True)