import logging
from typing import Callable, Dict, Optional

from shared.time_utils import now, now_iso, uptime_string

from .agent import AGENT_HOSTNAME
from utils.ip_detector import get_local_ip, check_admin_privileges
from utils.error_handler import CriticalErrorHandler

logger = logging.getLogger("core.handlers")


def create_domain_handler(config: Dict, agent) -> Callable[[Dict], None]:

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

    try:
        # Extract packet information
        domain = record.get("domain")
        dest_ip = record.get("dest_ip")
        src_ip = record.get("src_ip", "unknown")
        protocol = record.get("protocol", "TCP")
        port = record.get("port", "unknown")
        
        if src_ip == "unknown" or not src_ip:
            src_ip = get_local_ip()
        
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
        
        firewall_config = config.get("firewall", {})
        firewall_mode = firewall_config.get("mode", "whitelist_only")
        firewall_enabled = firewall_config.get("enabled", False)

        is_whitelisted = domain_allowed or ip_allowed

        # The agent supports a single enforcement mode: whitelist_only.
        # When the firewall component is disabled (e.g. no admin), we still
        # observe and log traffic but never claim it was blocked.
        #
        # Compliance levels (Preventive Layer 3 + Detective Layer 7):
        #   ALLOWED        - domain explicitly in whitelist (compliant).
        #   ALLOWED_BY_IP  - destination IP is whitelisted but domain (SNI/Host)
        #                    is NOT in whitelist. This indicates CDN/shared-IP
        #                    bleed-through (e.g. phimlau.com served from the same
        #                    Cloudflare IP as an allowed school site). Layer 3
        #                    cannot distinguish; this WARNING surfaces it so
        #                    admins can investigate and tighten policy.
        #   BLOCKED        - neither domain nor IP whitelisted; firewall dropped.
        #   OBSERVED       - passive mode (no admin / firewall disabled).
        if firewall_enabled:
            if domain_allowed:
                action, level = "ALLOWED", "INFO"
            elif ip_allowed and domain and not domain_allowed:
                # IP let through, but SNI/Host points to a non-whitelisted
                # domain - likely CDN co-tenant. Detective signal for admin.
                action, level = "ALLOWED_BY_IP", "WARNING"
            elif is_whitelisted:
                # ip_allowed without identifiable domain (e.g. raw IP traffic
                # to a whitelisted host) - legitimate non-DNS connection.
                action, level = "ALLOWED", "INFO"
            else:
                action, level = "BLOCKED", "BLOCKED"
        else:
            # Passive observe mode: agent has no enforcement power, only logs.
            action = "OBSERVED"
            level = "INFO" if is_whitelisted else "WARNING"
        
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