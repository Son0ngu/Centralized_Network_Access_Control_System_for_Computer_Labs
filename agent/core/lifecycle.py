"""
Lifecycle management - Agent initialization and cleanup.
- Clean implementation.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from shared.time_utils import now, now_iso
from utils import check_admin_privileges, get_local_ip
from .agent import (
    AgentRuntime,
    get_agent,
    agent_state,
    DeviceIdentityProvider,
)
from .token_manager import init_token_manager, get_token_manager

logger = logging.getLogger("core.lifecycle")

# Component status values
STATUS_OK = "ok"            # initialized and working
STATUS_SKIPPED = "skipped"  # intentionally not run (disabled in config / no admin)
STATUS_DEGRADED = "degraded"  # tried but failed in a non-critical way (offline mode)
STATUS_FAILED = "failed"    # critical failure - agent cannot operate safely

_STATUS_ICON = {
    STATUS_OK: "[+]",
    STATUS_SKIPPED: "[-]",
    STATUS_DEGRADED: "[!]",
    STATUS_FAILED: "[x]",
}


@dataclass
class ComponentStatus:
    """Outcome of initializing a single agent component."""
    name: str
    status: str
    detail: str = ""


@dataclass
class InitResult:
    """
    Aggregate result of `initialize_components`.

    Truthy unless a critical component failed (so existing
    `if not initialize_components(...)` callers still work).
    """
    components: List[ComponentStatus] = field(default_factory=list)

    def record(self, name: str, status: str, detail: str = "") -> None:
        self.components.append(ComponentStatus(name=name, status=status, detail=detail))

    @property
    def overall(self) -> str:
        if any(c.status == STATUS_FAILED for c in self.components):
            return STATUS_FAILED
        if any(c.status in (STATUS_DEGRADED, STATUS_SKIPPED) for c in self.components):
            return STATUS_DEGRADED
        return STATUS_OK

    def has_failure(self) -> bool:
        return self.overall == STATUS_FAILED

    @property
    def issues(self) -> List[ComponentStatus]:
        """Components that are not fully ok - useful for surfacing to the user."""
        return [c for c in self.components if c.status != STATUS_OK]

    def __bool__(self) -> bool:
        return not self.has_failure()


def initialize_components(config: Dict,
                          runtime: Optional[AgentRuntime] = None) -> InitResult:
    """
    Initialize all agent components in correct order.

    Returns an :class:`InitResult` describing the outcome of each step.
    The result is truthy unless a *critical* component failed, so legacy
    callers using ``if not initialize_components(...)`` keep working.

    ``runtime`` is an optional injected :class:`AgentRuntime`. Production
    callers omit it and we fall back to :func:`get_agent` (the singleton);
    tests or harnesses that need isolation construct their own via
    :func:`agent.core.make_runtime` and pass it in. Either path stores
    ``config`` on the runtime and attaches the started components to it.
    """
    agent = runtime if runtime is not None else get_agent()
    agent.config = config  # Store config in agent
    result = InitResult()

    try:
        logger.info("=" * 50)
        logger.info("INITIALIZING AGENT COMPONENTS")
        logger.info("=" * 50)

        # 1. Register with server first
        logger.info("Step 1: Registering with server...")
        from .registry import register_agent, _collect_server_urls

        configured_urls = _collect_server_urls(config)
        if not configured_urls:
            # First-run state: no server URL set yet. Do NOT attempt to call
            # any default endpoint - this protects the user from leaking
            # device info to an unconfigured server. The GUI should prompt
            # the user to set a URL in Settings.
            logger.warning(
                "Server URL is empty - agent will start in OFFLINE mode. "
                "Open Settings → enter a Server URL → Save to enable sync."
            )
            result.record("registration", STATUS_SKIPPED,
                          "no server URL configured (Settings → Server URL)")
        elif not register_agent(config):
            logger.error("Failed to register with server")
            # Continue anyway - can work offline with cached whitelist
            logger.warning("Continuing with offline mode...")
            result.record("registration", STATUS_DEGRADED,
                          "server unreachable, continuing offline")
        else:
            logger.info(f"Registered successfully - Agent ID: {config.get('agent_id')}")
            result.record("registration", STATUS_OK,
                          f"agent_id={config.get('agent_id')}")

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
        result.record("token_manager", STATUS_OK)

        # 2. Initialize WhitelistManager and SYNC FIRST (before firewall)
        logger.info("Step 2: Initializing whitelist manager...")
        from whitelist import WhitelistManager
        try:
            agent.whitelist = WhitelistManager(config)
            logger.info("Whitelist manager initialized")
            result.record("whitelist_manager", STATUS_OK)
        except Exception as e:
            logger.error(f"Whitelist manager init failed: {e}", exc_info=True)
            result.record("whitelist_manager", STATUS_FAILED, str(e))
            # Critical: without a whitelist manager nothing else can run safely
            raise

        # 2.5. SYNC WHITELIST IMMEDIATELY (before enabling firewall)
        # This is critical - we need whitelist data BEFORE enabling Default Deny
        if config.get("whitelist", {}).get("auto_sync", True):
            logger.info("Step 2.5: Syncing whitelist from server (BEFORE firewall)...")
            try:
                sync_success = agent.whitelist.sync_now()
                if sync_success:
                    stats = agent.whitelist.get_stats()
                    domains = stats.get('domain_count', 0)
                    ips = stats.get('ip_count', 0)
                    logger.info(f"Whitelist synced: {domains} domains, {ips} IPs")
                    result.record("whitelist_sync", STATUS_OK,
                                  f"{domains} domains, {ips} IPs")
                else:
                    logger.warning("Whitelist sync failed - firewall may block connections")
                    result.record("whitelist_sync", STATUS_DEGRADED,
                                  "sync failed (auth or server unreachable)")
            except Exception as e:
                logger.warning(f"Whitelist sync error: {e}")
                result.record("whitelist_sync", STATUS_DEGRADED, str(e))
        else:
            result.record("whitelist_sync", STATUS_SKIPPED,
                          "auto_sync disabled in config")
        
        # 3. Initialize FirewallManager (only when enabled + admin).
        # The agent supports a single firewall mode: `whitelist_only`. Any
        # other value in config has already been coerced by the validator.
        admin_status = check_admin_privileges()
        firewall_config = config.get("firewall", {})
        firewall_enabled = bool(firewall_config.get("enabled"))

        if firewall_enabled and admin_status:
            # 3.1. Auto-install WinPcap so packet capture works
            logger.info("Step 3.1: Checking WinPcap for packet capture...")
            try:
                from capture.winpcap_installer import (
                    ensure_winpcap_available, is_winpcap_installed,
                )
                if not is_winpcap_installed():
                    logger.info("WinPcap not found - attempting auto-installation...")
                    success, message = ensure_winpcap_available()
                    if success:
                        logger.info(message)
                    else:
                        logger.warning("⚠️ WinPcap auto-install: %s", message)
                        logger.warning("Packet capture may not work without WinPcap/Npcap")
                else:
                    logger.info("WinPcap/Npcap already installed")
            except Exception as e:
                logger.warning("WinPcap check/install failed: %s", e)

            logger.info("Step 3: Initializing firewall manager...")
            from firewall import FirewallManager
            agent.firewall = FirewallManager(
                firewall_config.get("rule_prefix", "FirewallController")
            )

            # Save pre-SAINT firewall state once so Restore can revert to it.
            # Skip-if-exists prevents clobbering the genuine baseline after a
            # crashed run.
            backup_cfg = firewall_config.get("backup", {}) or {}
            if backup_cfg.get("enabled", True):
                backup_path = backup_cfg.get(
                    "path", "profiles/backup.saint-snapshot.json"
                )
                logger.info("Saving pre-SAINT firewall snapshot (if missing)...")
                agent.firewall.save_snapshot(backup_path)
            else:
                logger.info("Firewall backup disabled by config; skipping snapshot.")

            # Link firewall to whitelist
            if agent.whitelist:
                agent.whitelist.set_firewall_manager(agent.firewall)
                logger.info("Firewall manager linked to whitelist")

            # Enable whitelist_only mode (the only supported mode).
            logger.info("Enabling whitelist_only mode (Default Deny + allow whitelist)...")
            server_config = config.get("server", {})
            server_urls = []
            if server_config.get("urls"):
                server_urls.extend(server_config["urls"])
            if server_config.get("url"):
                server_urls.append(server_config["url"])

            whitelist_ips: set = set()
            whitelist_domains: set = set()
            if agent.whitelist and hasattr(agent.whitelist, "_state"):
                whitelist_ips = agent.whitelist._state.get_all_ips()
                whitelist_domains = agent.whitelist._state.get_all_domains()
                whitelist_domains.update(
                    agent.whitelist._state.get_all_patterns()
                )

            logger.info(
                "Whitelist data: %d IPs, %d domains/patterns",
                len(whitelist_ips), len(whitelist_domains),
            )

            if agent.firewall.enable_whitelist_mode(
                server_urls=server_urls,
                whitelist_ips=whitelist_ips,
                whitelist_domains=whitelist_domains,
            ):
                logger.info(
                    "Default Deny enabled - non-whitelisted traffic will be blocked"
                )
                result.record("firewall", STATUS_OK,
                              f"whitelist_only mode ({len(whitelist_ips)} IPs, "
                              f"{len(whitelist_domains)} domains)")
            else:
                logger.error("Failed to enable Default Deny policy")
                result.record("firewall", STATUS_FAILED,
                              "enable_whitelist_mode returned False")
        else:
            if not firewall_enabled:
                logger.info("Step 3: Firewall disabled in config")
                result.record("firewall", STATUS_SKIPPED, "disabled in config")
            else:
                logger.warning(
                    "Step 3: Firewall requires administrator privileges - "
                    "running without enforcement. Relaunch as admin to apply rules."
                )
                result.record("firewall", STATUS_SKIPPED,
                              "no admin privileges (relaunch as administrator)")
        
        # 4. Start periodic whitelist sync (initial sync already done in Step 2.5)
        if config.get("whitelist", {}).get("auto_sync", True):
            agent.whitelist.start_sync()
            logger.info(f"Whitelist periodic sync started (interval: {config.get('whitelist', {}).get('update_interval', 60)}s)")
        
        # 5. Initialize LogSender
        logger.info("Step 5: Initializing log sender...")
        from logging_module import LogSender

        server_url = config.get("server_url") or config.get("server", {}).get("url")
        agent_id = config.get("agent_id")
        missing_creds = _missing_server_creds(server_url, agent_id)

        if not missing_creds:
            try:
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
                result.record("log_sender", STATUS_OK)
            except Exception as e:
                logger.warning(f"Log sender init failed: {e}")
                result.record("log_sender", STATUS_DEGRADED, str(e))
        else:
            msg = f"missing config: {', '.join(missing_creds)}"
            logger.warning(f"Log sender not initialized - {msg}")
            result.record("log_sender", STATUS_DEGRADED, msg)

        # 6. Initialize HeartbeatSender
        logger.info("Step 6: Initializing heartbeat sender...")
        from services import HeartbeatSender

        if not missing_creds:
            try:
                # FIX: Build config dict for HeartbeatSender
                heartbeat_config = {
                    "server": config.get("server", {}),
                    "heartbeat": config.get("heartbeat", {}),
                    "device_id": config.get("device_id") or agent.device_id,
                }
                agent.heartbeat = HeartbeatSender(heartbeat_config)
                agent.heartbeat.set_agent_credentials(agent_id, config.get("agent_token", ""))
                # Wire force_sync callback: when server requests re-sync (policy/whitelist changed)
                if agent.whitelist and hasattr(agent.whitelist, 'sync_now'):
                    agent.heartbeat.on_force_sync = agent.whitelist.sync_now
                # Wire whitelist version getter so heartbeat reports current versions
                if agent.whitelist and hasattr(agent.whitelist, '_state'):
                    agent.heartbeat.get_whitelist_versions = lambda: {
                        "global_version": agent.whitelist._state._version or None,
                        "group_version": agent.whitelist._state._group_version or None,
                    }
                agent.heartbeat.start()
                logger.info("Heartbeat sender initialized and started")
                result.record("heartbeat_sender", STATUS_OK)
            except Exception as e:
                logger.warning(f"Heartbeat sender init failed: {e}")
                result.record("heartbeat_sender", STATUS_DEGRADED, str(e))
        else:
            msg = f"missing config: {', '.join(missing_creds)}"
            logger.warning(f"Heartbeat sender not initialized - {msg}")
            result.record("heartbeat_sender", STATUS_DEGRADED, msg)
        
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
                result.record("packet_sniffer", STATUS_OK)
            except Exception as e:
                logger.warning(f"Could not initialize packet sniffer: {e}")
                logger.warning("Continuing without packet capture...")
                result.record("packet_sniffer", STATUS_DEGRADED, str(e))
        else:
            logger.info("Step 7: Packet capture disabled in config")
            result.record("packet_sniffer", STATUS_SKIPPED, "disabled in config")

        # Mark agent as running
        agent.running = True
        agent_state['initialization_completed'] = True
        agent_state['initialization_time'] = now()

        _log_init_summary(result)
        return result

    except Exception as e:
        logger.error(f"Error during component initialization: {e}", exc_info=True)
        result.record("initialization", STATUS_FAILED, str(e))
        _log_init_summary(result)
        return result


def _missing_server_creds(server_url: Optional[str], agent_id: Optional[str]) -> List[str]:
    """Return the names of server-side credentials that are missing."""
    missing: List[str] = []
    if not server_url:
        missing.append("server_url")
    if not agent_id:
        missing.append("agent_id")
    return missing


def _log_init_summary(result: InitResult) -> None:
    """Log a per-component summary table after initialization."""
    overall = result.overall
    issue_count = sum(1 for c in result.components if c.status != STATUS_OK)

    if overall == STATUS_OK:
        headline = "ALL COMPONENTS INITIALIZED SUCCESSFULLY"
    elif overall == STATUS_DEGRADED:
        headline = f"AGENT INITIALIZED (DEGRADED) - {issue_count} issue(s)"
    else:
        headline = f"AGENT INITIALIZATION FAILED - {issue_count} issue(s)"

    logger.info("=" * 60)
    logger.info(headline)
    name_width = max((len(c.name) for c in result.components), default=0)
    for c in result.components:
        icon = _STATUS_ICON.get(c.status, "[?]")
        line = f"  {icon} {c.name.ljust(name_width)}  {c.status}"
        if c.detail:
            line = f"{line} - {c.detail}"
        if c.status == STATUS_FAILED:
            logger.error(line)
        elif c.status in (STATUS_DEGRADED, STATUS_SKIPPED):
            logger.warning(line)
        else:
            logger.info(line)
    logger.info("=" * 60)


def cleanup(config: Optional[Dict] = None,
            runtime: Optional[AgentRuntime] = None) -> None:
    """
    Cleanup all agent resources.

    Args:
        config: Optional configuration for shutdown logging
        runtime: Optional :class:`AgentRuntime` to clean up. Defaults to the
            singleton so existing callers don't change; tests that
            constructed their own runtime via :func:`make_runtime` should
            pass it explicitly to avoid touching the process singleton.
    """
    agent = runtime if runtime is not None else get_agent()
    
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
        "device_id": DeviceIdentityProvider.get_device_id(),
        "hostname": DeviceIdentityProvider.get_hostname(),
        "ip_address": local_ip,
        "uptime": uptime_string(),
        "firewall_mode": config.get("firewall", {}).get("mode", "whitelist_only"),
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
