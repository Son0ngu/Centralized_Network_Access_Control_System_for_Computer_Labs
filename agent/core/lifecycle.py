"""
Lifecycle management - Agent initialization and cleanup.
- Clean implementation with DNS Proxy Architecture (Phase 1).
"""

import logging
from typing import Dict, Optional

from shared.time_utils import now, now_iso
from utils import check_admin_privileges, get_local_ip
from .agent import get_agent, agent_state, AGENT_DEVICE_ID, AGENT_HOSTNAME
from .token_manager import init_token_manager, get_token_manager

logger = logging.getLogger("core.lifecycle")

# Profile manager for backup/restore
_profile_manager = None


def _init_profile_manager():
    """Initialize profile manager for system backup."""
    global _profile_manager
    try:
        from utils.profile_manager import get_profile_manager
        _profile_manager = get_profile_manager()
        return True
    except ImportError:
        logger.warning("Profile Manager not available - system backup disabled")
        return False


def _backup_system_profile():
    """Backup system settings before agent starts."""
    if _profile_manager:
        try:
            success = _profile_manager.backup_all()
            if success:
                logger.info("System profile backed up successfully")
            return success
        except Exception as e:
            logger.warning(f"Failed to backup system profile: {e}")
    return False


def initialize_components(config: Dict) -> bool:
    """
    Initialize all agent components in correct order.
    
    NEW ARCHITECTURE (Phase 1 - DNS Proxy/Sinkhole):
    - DNS Proxy is PRIMARY for whitelist enforcement
    - PacketSniffer is OPTIONAL (bypass detection only)
    - No Default Deny firewall policy needed (Sinkhole handles blocking)
    
    Initialization Order:
    0. Backup system profile (DNS, firewall settings)
    1. Register with server
    2. Initialize Token Manager
    3. Initialize Whitelist Manager + Sync
    4. Initialize DNS Proxy Orchestrator (PRIMARY)
    5. Initialize LogSender
    6. Initialize HeartbeatSender
    7. Initialize PacketSniffer (OPTIONAL - bypass detection only)
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if initialization successful
    """
    agent = get_agent()
    agent.config = config  # Store config in agent
    
    try:
        logger.info("=" * 60)
        logger.info("INITIALIZING AGENT COMPONENTS (DNS Proxy Architecture)")
        logger.info("=" * 60)
        
        # 0. Initialize Profile Manager and backup system settings
        logger.info("Step 0: Backing up system profile...")
        _init_profile_manager()
        _backup_system_profile()
        
        # 1. Register with server first
        logger.info("Step 1: Registering with server...")
        from .registry import register_agent
        
        if not register_agent(config):
            logger.error("Failed to register with server")
            logger.warning("Continuing with offline mode...")
        else:
            logger.info(f"Registered successfully - Agent ID: {config.get('agent_id')}")
        
        # 2. Initialize Token Manager for JWT auto-refresh
        logger.info("Step 2: Initializing Token Manager...")
        token_manager = init_token_manager(config)
        
        def on_token_expired():
            """Handle token expiry - trigger re-registration"""
            logger.warning("JWT tokens expired - triggering re-registration")
            if register_agent(config):
                logger.info("Re-registration successful")
                token_manager.reset_reregistration_flag()
                token_manager._load_tokens_from_config()
            else:
                logger.error("Re-registration failed")
        
        def on_token_refreshed():
            logger.debug("JWT tokens refreshed successfully")
        
        token_manager.start_auto_refresh(
            on_refreshed=on_token_refreshed,
            on_expired=on_token_expired
        )
        logger.info("Token Manager initialized with auto-refresh")
        
        # 3. Initialize WhitelistManager and SYNC
        logger.info("Step 3: Initializing whitelist manager...")
        from whitelist import WhitelistManager
        agent.whitelist = WhitelistManager(config)
        logger.info("Whitelist manager initialized")
        
        # 3.5. Sync whitelist immediately
        if config.get("whitelist", {}).get("auto_sync", True):
            logger.info("Step 3.5: Syncing whitelist from server...")
            try:
                sync_success = agent.whitelist.sync_now()
                if sync_success:
                    stats = agent.whitelist.get_stats()
                    logger.info(f"Whitelist synced: {stats.get('domain_count', 0)} domains, {stats.get('ip_count', 0)} IPs")
                else:
                    logger.warning("⚠️ Whitelist sync failed")
            except Exception as e:
                logger.warning(f"⚠️ Whitelist sync error: {e}")
        
        # 4. Start periodic whitelist sync
        if config.get("whitelist", {}).get("auto_sync", True):
            agent.whitelist.start_sync()
            logger.info(f"Whitelist periodic sync started (interval: {config.get('whitelist', {}).get('update_interval', 60)}s)")
        
         # 4. Initialize DNS Proxy Orchestrator (PRIMARY - Phase 1 Architecture)
        dns_proxy_config = config.get("dns_proxy", {})
        if dns_proxy_config.get("enabled", True) and check_admin_privileges():
            logger.info("Step 4: Initializing DNS Proxy System (PRIMARY)...")
            try:
                from dns_proxy import (
                    DNSProxyOrchestrator,
                    OrchestratorConfig,
                    OrchestratorMode,
                )
                
                # Build orchestrator config from agent config
                mode_str = dns_proxy_config.get("mode", "active")
                mode_map = {
                    "disabled": OrchestratorMode.DISABLED,
                    "monitor": OrchestratorMode.MONITOR,
                    "active": OrchestratorMode.ACTIVE,
                    "parallel": OrchestratorMode.PARALLEL,
                }
                orchestrator_mode = mode_map.get(mode_str, OrchestratorMode.ACTIVE)
                
                # Network manager config
                network_config = config.get("network_manager", {})
                
                # Security config
                security_config = config.get("security", {})
                
                # Firewall sync config
                firewall_sync_config = dns_proxy_config.get("firewall_sync", {})
                
                orch_config = OrchestratorConfig(
                    mode=orchestrator_mode,
                    dns_proxy_enabled=True,
                    dns_bind_address=dns_proxy_config.get("bind_address", "127.0.0.1"),
                    dns_port=dns_proxy_config.get("port", 53),
                    network_manager_enabled=network_config.get("enabled", True),
                    auto_configure_dns=network_config.get("auto_configure_dns", True),
                    dns_drift_monitor=True,
                    security_enabled=security_config.get("enabled", True),
                    block_doh=security_config.get("block_doh", True),
                    block_dot=security_config.get("block_dot", True),
                    firewall_sync_enabled=firewall_sync_config.get("enabled", True),
                    default_grace_period=firewall_sync_config.get("grace_period", 60),
                    upstream_resolvers=[
                        r.get("address", "8.8.8.8") 
                        for r in dns_proxy_config.get("upstream_resolvers", [{"address": "8.8.8.8"}])
                    ],
                )
                
                # Create orchestrator
                agent.dns_proxy_orchestrator = DNSProxyOrchestrator(orch_config)
                
                # Add server URLs as essential domains (bypass whitelist)
                # This is critical - agent needs to connect to server for whitelist sync
                server_config = config.get("server", {})
                server_urls = []
                if server_config.get("url"):
                    server_urls.append(server_config["url"])
                if isinstance(server_config.get("urls"), list):
                    server_urls.extend(server_config["urls"])
                if server_urls:
                    agent.dns_proxy_orchestrator.add_essential_domains_from_urls(server_urls)
                    logger.info(f"Added {len(server_urls)} server URL(s) as essential domains")
                
                # Connect to whitelist state
                if agent.whitelist and hasattr(agent.whitelist, '_state'):
                    agent.dns_proxy_orchestrator.set_whitelist_state(agent.whitelist._state)
                    logger.info("DNS Proxy connected to whitelist state")
                
                # Start the DNS Proxy system
                if agent.dns_proxy_orchestrator.start():
                    agent_state['dns_proxy_mode'] = mode_str
                    logger.info(f"✓ DNS Proxy System started (mode: {mode_str})")
                    logger.info("  → All DNS queries now go through 127.0.0.1:53")
                    logger.info("  → Whitelist enforcement at DNS level (Sinkhole)")
                    logger.info("  → DoH/DoT blocking enabled")
                else:
                    logger.error("Failed to start DNS Proxy System")
                    
            except ImportError as e:
                logger.error(f"DNS Proxy module not available: {e}")
                logger.warning("Falling back to legacy mode (PacketSniffer)")
            except Exception as e:
                logger.error(f"Could not initialize DNS Proxy: {e}", exc_info=True)
                logger.warning("Falling back to legacy mode (PacketSniffer)")
        else:
            if not dns_proxy_config.get("enabled", True):
                logger.info("Step 4: DNS Proxy disabled in config")
            elif not check_admin_privileges():
                logger.warning("Step 4: DNS Proxy requires admin privileges")
        
        # 5. Initialize LogSender
        logger.info("Step 5: Initializing log sender...")
        from logging_module import LogSender
        
        server_url = config.get("server_url") or config.get("server", {}).get("url")
        agent_id = config.get("agent_id")
        
        if server_url and agent_id:
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
        
        # 7. Initialize PacketSniffer (OPTIONAL - bypass detection only)
        capture_config = config.get("capture", config.get("packet_capture", {}))
        capture_mode = capture_config.get("mode", "bypass_detection_only")
        
        # Only start PacketSniffer if:
        # - Explicitly enabled in config, OR
        # - DNS Proxy is not running (fallback mode)
        should_start_sniffer = (
            capture_config.get("enabled", False) or 
            (agent.dns_proxy_orchestrator is None and capture_mode == "full")
        )
        
        if should_start_sniffer:
            logger.info(f"Step 7: Initializing packet sniffer (mode: {capture_mode})...")
            try:
                from capture import PacketSniffer
                from .handlers import create_domain_handler
                
                # Create handler based on mode
                if capture_mode == "bypass_detection_only":
                    # Bypass detection handler - only logs, no blocking decisions
                    domain_handler = create_bypass_detection_handler(config, agent)
                else:
                    # Full mode handler (legacy)
                    domain_handler = create_domain_handler(config, agent)
                
                agent.sniffer = PacketSniffer(callback=domain_handler, mode=capture_mode)
                agent.sniffer.start()
                logger.info(f"Packet sniffer initialized (mode: {capture_mode})")
            except Exception as e:
                logger.warning(f"Could not initialize packet sniffer: {e}")
                logger.warning("Continuing without packet capture...")
        else:
            logger.info("Step 7: Packet capture disabled (DNS Proxy handles whitelist enforcement)")
        
        # Mark agent as running
        agent.running = True
        agent_state['initialization_completed'] = True
        agent_state['initialization_time'] = now()
        
        logger.info("=" * 60)
        logger.info("ALL COMPONENTS INITIALIZED SUCCESSFULLY")
        if agent.dns_proxy_orchestrator:
            logger.info("→ DNS Proxy is PRIMARY for whitelist enforcement")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during component initialization: {e}", exc_info=True)
        return False


def create_bypass_detection_handler(config: Dict, agent):
    """
    Create a handler for bypass detection mode.
    Only logs suspicious activity, no blocking decisions.
    """
    from .handlers import handle_domain_detection
    
    def bypass_detection_callback(record: Dict):
        """Handle detected traffic for bypass analysis."""
        domain = record.get("domain")
        dest_ip = record.get("dest_ip")
        protocol = record.get("protocol")
        
        # Log suspicious activity (direct IP connections, etc.)
        if not domain and dest_ip:
            # Direct IP connection - potential bypass attempt
            logger.warning(f"⚠️ BYPASS DETECTION: Direct IP connection to {dest_ip} ({protocol})")
            
            # Queue for logging but don't make blocking decision
            if agent.log_sender:
                log_record = {
                    **record,
                    "event_type": "bypass_detection",
                    "action": "ALERT",
                    "message": f"Direct IP connection detected: {dest_ip}",
                }
                agent.log_sender.queue_log(log_record)
        
        # For domains, just log - DNS Proxy handles blocking
        elif domain:
            logger.debug(f"Bypass monitor: {domain} -> {dest_ip}")
    
    return bypass_detection_callback


def cleanup(config: Optional[Dict] = None) -> None:
    """
    Cleanup all agent resources in correct order.
    
    Shutdown Order (reverse of initialization):
    1. Stop whitelist sync
    2. Stop HeartbeatSender
    3. Flush and stop LogSender
    4. Stop Token Manager
    5. Stop PacketSniffer (optional)
    6. Stop DNS Proxy System (restores DNS, removes security rules)
    
    Args:
        config: Optional configuration for shutdown logging
    """
    agent = get_agent()
    
    logger.info("=" * 60)
    logger.info("SHUTTING DOWN AGENT")
    logger.info("=" * 60)
    
    try:
        # IMPORTANT: Stop components that make network requests FIRST
        # to avoid them trying to resolve domains after DNS proxy stops
        
        # 1. Stop whitelist sync FIRST (prevents it from trying to resolve)
        if hasattr(agent, 'whitelist') and agent.whitelist:
            logger.info("Step 1: Stopping whitelist sync...")
            agent.whitelist.stop_sync()
            agent.whitelist = None
        
        # 2. Stop heartbeat sender (also makes network requests)
        if hasattr(agent, 'heartbeat') and agent.heartbeat:
            logger.info("Step 2: Stopping heartbeat sender...")
            agent.heartbeat.stop()
            agent.heartbeat = None
        
        # 3. Flush and stop log sender
        if hasattr(agent, 'log_sender') and agent.log_sender:
            logger.info("Step 3: Flushing and stopping log sender...")
            
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
        
        # 4. Stop token manager auto-refresh
        token_manager = get_token_manager()
        if token_manager:
            logger.info("Step 4: Stopping token manager...")
            token_manager.stop_auto_refresh()
        
        # 5. Stop packet sniffer (if running)
        if hasattr(agent, 'sniffer') and agent.sniffer:
            logger.info("Step 5: Stopping packet sniffer...")
            agent.sniffer.stop()
            agent.sniffer = None
        
        # 6. Stop DNS Proxy System (LAST - restores DNS settings)
        if hasattr(agent, 'dns_proxy_orchestrator') and agent.dns_proxy_orchestrator:
            logger.info("Step 6: Stopping DNS Proxy System...")
            try:
                agent.dns_proxy_orchestrator.stop()
                logger.info("  → DNS Proxy stopped")
                logger.info("  → DNS settings restored")
                logger.info("  → Security rules removed")
            except Exception as e:
                logger.error(f"Error stopping DNS Proxy: {e}")
            finally:
                agent.dns_proxy_orchestrator = None
                agent_state['dns_proxy_mode'] = None
        
        # 7. Restore system profile (DNS, firewall from backup)
        if _profile_manager and _profile_manager.has_backup():
            logger.info("Step 7: Restoring system profile from backup...")
            try:
                success, errors = _profile_manager.restore_all()
                if success:
                    logger.info("  → System profile restored successfully")
                else:
                    for error in errors:
                        logger.warning(f"  → Restore issue: {error}")
            except Exception as e:
                logger.error(f"Error restoring system profile: {e}")
        
        agent.running = False
        
        logger.info("=" * 60)
        logger.info("AGENT SHUTDOWN COMPLETE")
        logger.info("=" * 60)
        
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
        "dns_proxy_mode": config.get("dns_proxy", {}).get("mode", "disabled"),
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