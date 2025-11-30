"""
Lifecycle management - Agent initialization and cleanup.
Vietnam ONLY - Clean implementation.
"""

import logging
from typing import Dict, Optional

from shared.time_utils import now, now_iso
from utils import check_admin_privileges, get_local_ip
from .agent import get_agent, agent_state, AGENT_DEVICE_ID, AGENT_HOSTNAME

logger = logging.getLogger("core.lifecycle")


def initialize_components(config: Dict) -> bool:
    """
    Initialize all agent components in correct order.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if initialization successful
    """
    agent = get_agent()
    agent.config = config  # Store config in agent
    
    try:
        logger.info("=" * 50)
        logger.info("INITIALIZING AGENT COMPONENTS")
        logger.info("=" * 50)
        
        # 1. Register with server first
        logger.info("Step 1: Registering with server...")
        from .registry import register_agent
        
        if not register_agent(config):
            logger.error("Failed to register with server")
            # Continue anyway - can work offline with cached whitelist
            logger.warning("Continuing with offline mode...")
        else:
            logger.info(f"Registered successfully - Agent ID: {config.get('agent_id')}")
        
        # 2. Initialize WhitelistManager (but don't start sync yet)
        logger.info("Step 2: Initializing whitelist manager...")
        from whitelist import WhitelistManager
        agent.whitelist = WhitelistManager(config)
        logger.info("Whitelist manager initialized")
        
        # 3. Initialize FirewallManager (if enabled and has admin) - BEFORE starting sync
        admin_status = check_admin_privileges()
        firewall_config = config.get("firewall", {})
        
        if firewall_config.get("enabled") and admin_status:
            logger.info("Step 3: Initializing firewall manager...")
            from firewall import FirewallManager
            agent.firewall = FirewallManager(firewall_config.get("rule_prefix", "FirewallController"))
            
            # Link firewall to whitelist BEFORE starting sync
            if agent.whitelist:
                agent.whitelist.set_firewall_manager(agent.firewall)
                logger.info("Firewall manager linked to whitelist")
            
            # Enable whitelist-only mode if configured
            firewall_mode = firewall_config.get("mode", "monitor")
            if firewall_mode == "whitelist_only":
                logger.info("🔒 Firewall mode: whitelist_only - Enabling Default Deny policy...")
                if agent.firewall.enable_whitelist_mode():
                    logger.info("✅ Default Deny policy enabled - All non-whitelisted traffic will be blocked")
                else:
                    logger.error("❌ Failed to enable Default Deny policy")
            else:
                logger.info(f"Firewall mode: {firewall_mode} (not whitelist_only)")
        else:
            if not firewall_config.get("enabled"):
                logger.info("Step 3: Firewall disabled in config")
            else:
                logger.warning("Step 3: Firewall enabled but no admin privileges")
        
        # 4. NOW start whitelist sync (after firewall is linked)
        if config.get("whitelist", {}).get("auto_sync", True):
            agent.whitelist.start_sync()
            logger.info(f"Whitelist sync started (interval: {config.get('whitelist', {}).get('sync_interval', 60)}s)")
        
        # 5. Initialize LogSender
        logger.info("Step 5: Initializing log sender...")
        from logging_module import LogSender
        
        server_url = config.get("server_url") or config.get("server", {}).get("url")
        agent_id = config.get("agent_id")
        
        if server_url and agent_id:
            # FIX: Build config dict for LogSender
            log_sender_config = {
                "server": config.get("server", {}),
                "server_url": server_url,
                "agent_id": agent_id,
                "batch_size": config.get("logging", {}).get("sender", {}).get("batch_size", 100),
                "max_queue_size": config.get("logging", {}).get("sender", {}).get("max_queue_size", 1000),
                "send_interval": config.get("logging", {}).get("sender", {}).get("send_interval", 2),
            }
            agent.log_sender = LogSender(log_sender_config)
            agent.log_sender.start()
            logger.info("Log sender initialized and started")
        else:
            logger.warning("Log sender not initialized - missing server_url or agent_id")
        
        # 6. Initialize HeartbeatSender
        logger.info("Step 6: Initializing heartbeat sender...")
        from services import HeartbeatSender
        
        if server_url and agent_id:
            # FIX: Build config dict for HeartbeatSender
            heartbeat_config = {
                "server": config.get("server", {}),
                "heartbeat": config.get("heartbeat", {}),
                "device_id": config.get("device_id", AGENT_DEVICE_ID),
            }
            agent.heartbeat = HeartbeatSender(heartbeat_config)
            agent.heartbeat.set_agent_credentials(agent_id, config.get("agent_token", ""))
            agent.heartbeat.start()
            logger.info("Heartbeat sender initialized and started")
        else:
            logger.warning("Heartbeat sender not initialized - missing server_url or agent_id")
        
        # 7. Initialize PacketSniffer (if capture enabled)
        capture_config = config.get("capture", config.get("packet_capture", {}))
        if capture_config.get("enabled", True):
            logger.info("Step 7: Initializing packet sniffer...")
            try:
                from capture import PacketSniffer
                
                # Create domain detection handler
                from .handlers import create_domain_handler
                domain_handler = create_domain_handler(config, agent)
                
                agent.sniffer = PacketSniffer(callback=domain_handler)
                agent.sniffer.start()
                logger.info("Packet sniffer initialized and started")
            except Exception as e:
                logger.warning(f"Could not initialize packet sniffer: {e}")
                logger.warning("Continuing without packet capture...")
        else:
            logger.info("Step 7: Packet capture disabled in config")
        
        # Mark agent as running
        agent.running = True
        agent_state['initialization_completed'] = True
        agent_state['initialization_time'] = now()
        
        logger.info("=" * 50)
        logger.info("ALL COMPONENTS INITIALIZED SUCCESSFULLY")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during component initialization: {e}", exc_info=True)
        return False


def cleanup(config: Optional[Dict] = None) -> None:
    """
    Cleanup all agent resources.
    
    Args:
        config: Optional configuration for shutdown logging
    """
    agent = get_agent()
    
    logger.info("=" * 50)
    logger.info("SHUTTING DOWN AGENT")
    logger.info("=" * 50)
    
    try:
        # Stop packet sniffer
        if hasattr(agent, 'sniffer') and agent.sniffer:
            logger.info("Stopping packet sniffer...")
            agent.sniffer.stop()
            agent.sniffer = None
        
        # Stop whitelist sync
        if hasattr(agent, 'whitelist') and agent.whitelist:
            logger.info("Stopping whitelist sync...")
            agent.whitelist.stop_sync()
            agent.whitelist = None
        
        # Stop heartbeat sender
        if hasattr(agent, 'heartbeat') and agent.heartbeat:
            logger.info("Stopping heartbeat sender...")
            agent.heartbeat.stop()
            agent.heartbeat = None
        
        # Flush and stop log sender
        if hasattr(agent, 'log_sender') and agent.log_sender:
            logger.info("Flushing and stopping log sender...")
            
            # Send shutdown log
            if config and config.get("agent_id"):
                shutdown_log = build_lifecycle_log(
                    config,
                    event_type="agent_shutdown",
                    action="SHUTDOWN",
                    message="Agent shutdown"
                )
                agent.log_sender.queue_log(shutdown_log)
            
            agent.log_sender.stop()
            agent.log_sender = None
        
        # Cleanup firewall (if needed)
        if hasattr(agent, 'firewall') and agent.firewall:
            logger.info("Cleaning up firewall...")
            if hasattr(agent.firewall, 'cleanup'):
                agent.firewall.cleanup()
            elif hasattr(agent.firewall, 'cleanup_whitelist_firewall'):
                agent.firewall.cleanup_whitelist_firewall()
            agent.firewall = None
        
        agent.running = False
        
        logger.info("=" * 50)
        logger.info("AGENT SHUTDOWN COMPLETE")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


def build_lifecycle_log(config: Dict, event_type: str, action: str, message: str) -> Dict:
    """Build a lifecycle log entry."""
    from shared.time_utils import now_iso, uptime_string
    
    return {
        "timestamp": now_iso(),
        "event_type": event_type,
        "action": action,
        "message": message,
        "agent_id": config.get("agent_id", "unknown"),
        "device_id": AGENT_DEVICE_ID,
        "hostname": AGENT_HOSTNAME,
        "ip_address": get_local_ip(),
        "uptime": uptime_string(),
        "firewall_mode": config.get("firewall", {}).get("mode", "monitor")
    }