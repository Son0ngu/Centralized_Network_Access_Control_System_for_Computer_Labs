"""
Lifecycle management - Agent initialization and cleanup.
- Clean implementation.
"""

import logging
from typing import Dict, Optional

from shared.time_utils import now, now_iso
from utils import check_admin_privileges, get_local_ip
from .agent import get_agent, agent_state, AGENT_DEVICE_ID, AGENT_HOSTNAME
from .token_manager import init_token_manager, get_token_manager

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
        
        # 1.5. Initialize Token Manager for JWT auto-refresh
        logger.info("Step 1.5: Initializing Token Manager...")
        token_manager = init_token_manager(config)
        
        # Setup re-registration callback
        def on_token_expired():
            """Handle token expiry - trigger re-registration"""
            logger.warning("JWT tokens expired - triggering re-registration")
            if register_agent(config):
                logger.info("Re-registration successful")
                # Reset token manager with new tokens
                token_manager.reset_reregistration_flag()
                # Reload tokens from updated config
                token_manager._load_tokens_from_config()
            else:
                logger.error("Re-registration failed")
        
        def on_token_refreshed():
            """Handle successful token refresh"""
            logger.debug("JWT tokens refreshed successfully")
        
        # Start auto-refresh with callbacks
        token_manager.start_auto_refresh(
            on_refreshed=on_token_refreshed,
            on_expired=on_token_expired
        )
        logger.info("Token Manager initialized with auto-refresh")
        
        # 2. Initialize WhitelistManager and SYNC FIRST (before firewall)
        logger.info("Step 2: Initializing whitelist manager...")
        from whitelist import WhitelistManager
        agent.whitelist = WhitelistManager(config)
        logger.info("Whitelist manager initialized")
        
        # 2.5. SYNC WHITELIST IMMEDIATELY (before enabling firewall)
        # This is critical - we need whitelist data BEFORE enabling Default Deny
        if config.get("whitelist", {}).get("auto_sync", True):
            logger.info("Step 2.5: Syncing whitelist from server (BEFORE firewall)...")
            try:
                sync_success = agent.whitelist.sync_now()
                if sync_success:
                    stats = agent.whitelist.get_stats()
                    logger.info(f"Whitelist synced: {stats.get('domain_count', 0)} domains, {stats.get('ip_count', 0)} IPs")
                else:
                    logger.warning("⚠️ Whitelist sync failed - firewall may block connections")
            except Exception as e:
                logger.warning(f"⚠️ Whitelist sync error: {e}")
        
        # 3. Initialize FirewallManager (if enabled and has admin)
        admin_status = check_admin_privileges()
        firewall_config = config.get("firewall", {})
        firewall_mode = firewall_config.get("mode", "monitor")
        
        # 3.1. Auto-install WinPcap if whitelist_only mode with admin
        if firewall_config.get("enabled") and admin_status and firewall_mode == "whitelist_only":
            logger.info("Step 3.1: Checking WinPcap for packet capture...")
            try:
                from capture.winpcap_installer import ensure_winpcap_available, is_winpcap_installed
                
                if not is_winpcap_installed():
                    logger.info("WinPcap not found - attempting auto-installation...")
                    success, message = ensure_winpcap_available()
                    if success:
                        logger.info(f"{message}")
                    else:
                        logger.warning(f"⚠️ WinPcap auto-install: {message}")
                        logger.warning("Packet capture may not work without WinPcap/Npcap")
                else:
                    logger.info("WinPcap/Npcap already installed")
            except Exception as e:
                logger.warning(f"WinPcap check/install failed: {e}")
        
        if firewall_config.get("enabled") and admin_status:
            logger.info("Step 3: Initializing firewall manager...")
            from firewall import FirewallManager
            agent.firewall = FirewallManager(firewall_config.get("rule_prefix", "FirewallController"))
            
            # Backup / Restore Hook
            backup_cfg = firewall_config.get("backup", {})
            if backup_cfg.get("enabled", False):
                backup_path = backup_cfg.get("path", "profiles/backup.wfw")
                
                if backup_cfg.get("restore_on_startup", False):
                    logger.info("Backup: restore_on_startup is enabled. Attempting restore...")
                    agent.firewall.restore_snapshot(backup_path)
                else:
                    # Create initial backup if it doesn't exist (Preserve clean state)
                    from pathlib import Path
                    if not Path(backup_path).exists():
                        logger.info("Backup: No existing backup found. Creating initial snapshot...")
                        agent.firewall.save_snapshot(backup_path)

            # Link firewall to whitelist
            if agent.whitelist:
                agent.whitelist.set_firewall_manager(agent.firewall)
                logger.info("Firewall manager linked to whitelist")
            
            # Enable whitelist-only mode if configured
            if firewall_mode == "whitelist_only":
                logger.info("Firewall mode: whitelist_only - Enabling Default Deny policy...")
                
                # Collect server URLs for allow rules
                server_config = config.get("server", {})
                server_urls = []
                if server_config.get("urls"):
                    server_urls.extend(server_config["urls"])
                if server_config.get("url"):
                    server_urls.append(server_config["url"])
                
                # Collect ALL whitelist data from synced data
                whitelist_ips = set()
                whitelist_domains = set()
                if agent.whitelist and hasattr(agent.whitelist, '_state'):
                    # Get direct IPs
                    whitelist_ips = agent.whitelist._state.get_all_ips()
                    # Get domains to resolve
                    whitelist_domains = agent.whitelist._state.get_all_domains()
                    # Get patterns (wildcard domains)
                    whitelist_domains.update(agent.whitelist._state.get_all_patterns())
                    
                logger.info(f"Whitelist data: {len(whitelist_ips)} IPs, {len(whitelist_domains)} domains/patterns")
                
                # Enable with server URLs, whitelist IPs AND domains
                if agent.firewall.enable_whitelist_mode(
                    server_urls=server_urls, 
                    whitelist_ips=whitelist_ips,
                    whitelist_domains=whitelist_domains
                ):
                    logger.info("Default Deny policy enabled - All non-whitelisted traffic will be blocked")
                else:
                    logger.error("Failed to enable Default Deny policy")
            else:
                logger.info(f"Firewall mode: {firewall_mode} (not whitelist_only)")
        else:
            if not firewall_config.get("enabled"):
                logger.info("Step 3: Firewall disabled in config")
            else:
                logger.warning("Step 3: Firewall enabled but no admin privileges")
        
        # 4. Start periodic whitelist sync (initial sync already done in Step 2.5)
        if config.get("whitelist", {}).get("auto_sync", True):
            agent.whitelist.start_sync()
            logger.info(f"Whitelist periodic sync started (interval: {config.get('whitelist', {}).get('update_interval', 60)}s)")
        
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
            # Wire force_sync callback: khi server yêu cầu re-sync (policy changed)
            if agent.whitelist and hasattr(agent.whitelist, 'sync_now'):
                agent.heartbeat.on_force_sync = agent.whitelist.sync_now
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
        # Stop token manager auto-refresh
        token_manager = get_token_manager()
        if token_manager:
            logger.info("Stopping token manager...")
            token_manager.stop_auto_refresh()
        
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
        
        # Cleanup WinPcap if we installed it
        try:
            from capture.winpcap_installer import cleanup_winpcap, was_installed_by_us
            if was_installed_by_us():
                logger.info("Cleaning up WinPcap (auto-installed)...")
                cleanup_winpcap()
        except Exception as e:
            logger.warning(f"WinPcap cleanup failed: {e}")
        
        agent.running = False
        
        logger.info("=" * 50)
        logger.info("AGENT SHUTDOWN COMPLETE")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


def build_lifecycle_log(config: Dict, event_type: str, action: str, message: str) -> Dict:
    """Build a lifecycle log entry with proper field values."""
    from shared.time_utils import now_iso, uptime_string
    
    local_ip = get_local_ip()
    
    return {
        "timestamp": now_iso(),
        "event_type": event_type,
        "action": action,
        "message": message,
        "level": "INFO",
        "agent_id": config.get("agent_id", "unknown"),
        "device_id": AGENT_DEVICE_ID,
        "hostname": AGENT_HOSTNAME,
        "ip_address": local_ip,
        "uptime": uptime_string(),
        "firewall_mode": config.get("firewall", {}).get("mode", "monitor"),
        # Lifecycle events use agent as source/destination
        "source": "agent",
        "source_ip": local_ip,
        "dest_ip": "N/A",
        "destination": "N/A",
        "domain": "N/A",
        "protocol": "N/A",
        "port": "N/A",
        "is_lifecycle_event": True
    }