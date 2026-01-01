"""
DNS Proxy Agent Orchestrator
----------------------------
Central coordinator for the entire DNS Proxy system.

Manages lifecycle of:
- DNS Proxy Server
- Network Manager  
- Security Manager
- Enhanced Firewall Sync

Modes:
- DISABLED: All components off
- MONITOR: Read-only mode for testing
- ACTIVE: Full enforcement
- PARALLEL: Run alongside PacketSniffer for comparison
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("dns_proxy.integration.orchestrator")


class OrchestratorMode(Enum):
    """Operating modes for the DNS Proxy system."""
    DISABLED = "disabled"       # All components disabled
    MONITOR = "monitor"         # Monitor mode - log only, no enforcement
    ACTIVE = "active"           # Full enforcement mode
    PARALLEL = "parallel"       # Run alongside existing PacketSniffer


class ComponentStatus(Enum):
    """Status of individual components."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class OrchestratorConfig:
    """Configuration for DNS Proxy Orchestrator."""
    # Mode
    mode: OrchestratorMode = OrchestratorMode.ACTIVE
    
    # DNS Proxy settings
    dns_proxy_enabled: bool = True
    dns_bind_address: str = "127.0.0.1"
    dns_port: int = 53
    dns_ipv6_enabled: bool = True
    
    # Network Manager settings
    network_manager_enabled: bool = True
    auto_configure_dns: bool = True
    dns_drift_monitor: bool = True
    
    # Security settings
    security_enabled: bool = True
    block_doh: bool = True
    block_dot: bool = True
    auto_update_providers: bool = True
    
    # Firewall settings
    firewall_sync_enabled: bool = True
    default_grace_period: int = 60
    connection_aware_cleanup: bool = True
    
    # Upstream resolvers
    upstream_resolvers: List[str] = field(default_factory=lambda: [
        "8.8.8.8", "1.1.1.1", "208.67.222.222"
    ])
    
    # Timeouts
    startup_timeout: int = 30
    shutdown_timeout: int = 10
    component_timeout: int = 10


@dataclass
class ComponentState:
    """State of a managed component."""
    name: str
    status: ComponentStatus = ComponentStatus.STOPPED
    instance: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    
    @property
    def is_running(self) -> bool:
        return self.status == ComponentStatus.RUNNING
    
    @property
    def uptime(self) -> float:
        if self.start_time and self.is_running:
            return time.time() - self.start_time
        return 0.0


class DNSProxyOrchestrator:
    """
    Central orchestrator for DNS Proxy system.
    
    Features:
    - Manages component lifecycle (start/stop in correct order)
    - Provides unified status reporting
    - Handles errors and recovery
    - Supports different operating modes
    
    Usage:
        orchestrator = DNSProxyOrchestrator(config)
        
        # Connect to existing components
        orchestrator.set_whitelist_state(whitelist_state)
        orchestrator.set_firewall_manager(firewall_manager)
        
        # Start all components
        orchestrator.start()
        
        # Get status
        status = orchestrator.get_status()
        
        # Stop gracefully
        orchestrator.stop()
    """
    
    def __init__(self, config: OrchestratorConfig = None):
        self._config = config or OrchestratorConfig()
        
        # Component states
        self._components: Dict[str, ComponentState] = {
            "dns_proxy": ComponentState(name="DNS Proxy Server"),
            "network_manager": ComponentState(name="Network Manager"),
            "security_manager": ComponentState(name="Security Manager"),
            "firewall_sync": ComponentState(name="Enhanced Firewall Sync"),
        }
        
        # External references
        self._whitelist_state = None
        self._firewall_manager = None
        
        # Essential domains that bypass whitelist (e.g., server URLs)
        self._essential_domains: List[str] = []
        
        # State
        self._mode = self._config.mode
        self._running = False
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_status_change: List[Callable[[str, ComponentStatus], None]] = []
        self._on_error: List[Callable[[str, str], None]] = []
        
        logger.info(f"DNS Proxy Orchestrator initialized (mode: {self._mode.value})")
    
    def set_whitelist_state(self, state) -> None:
        """Set the whitelist state reference."""
        self._whitelist_state = state
        logger.info("Whitelist state connected to orchestrator")
    
    def set_firewall_manager(self, manager) -> None:
        """Set the firewall manager reference."""
        self._firewall_manager = manager
        logger.info("Firewall manager connected to orchestrator")
    
    def add_essential_domain(self, domain: str) -> None:
        """
        Add a domain that bypasses whitelist check.
        Used for server URLs that agent needs to connect to.
        """
        if domain and domain not in self._essential_domains:
            self._essential_domains.append(domain)
            logger.info(f"Added essential domain: {domain}")
    
    def add_essential_domains_from_urls(self, urls: list) -> None:
        """
        Extract and add domains from URLs as essential domains.
        e.g., https://server.example.com:5000 -> server.example.com
        """
        from urllib.parse import urlparse
        
        for url in urls:
            try:
                if not url:
                    continue
                # Add scheme if missing for proper parsing
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                parsed = urlparse(url)
                if parsed.hostname:
                    self.add_essential_domain(parsed.hostname)
            except Exception as e:
                logger.warning(f"Could not parse URL {url}: {e}")
    
    def set_mode(self, mode: OrchestratorMode) -> None:
        """Change operating mode."""
        if mode == self._mode:
            return
        
        old_mode = self._mode
        self._mode = mode
        
        logger.info(f"Mode changed: {old_mode.value} → {mode.value}")
        
        # Apply mode changes if running
        if self._running:
            self._apply_mode_changes()
    
    def start(self) -> bool:
        """
        Start all components in correct order.
        
        Order:
        1. Enhanced Firewall Sync (needs to be ready first)
        2. Security Manager (block DoH/DoT)
        3. DNS Proxy Server (start listening) <- MUST be before Network Manager!
        4. Network Manager (configure DNS to point to our server)
        
        Returns:
            True if all components started successfully
        """
        if self._running:
            logger.warning("Orchestrator already running")
            return True
        
        if self._mode == OrchestratorMode.DISABLED:
            logger.info("Orchestrator in DISABLED mode")
            return True
        
        logger.info(f"Starting DNS Proxy system (mode: {self._mode.value})...")
        
        success = True
        
        # Start in order
        try:
            # 1. Enhanced Firewall Sync
            if self._config.firewall_sync_enabled:
                success &= self._start_firewall_sync()
            
            # 2. Security Manager (block DoH/DoT)
            if self._config.security_enabled:
                success &= self._start_security_manager()
            
            # 3. DNS Proxy Server - MUST start BEFORE Network Manager
            # so it's listening when DNS gets redirected
            if self._config.dns_proxy_enabled:
                success &= self._start_dns_proxy()
            
            # 4. Network Manager - LAST because it redirects DNS to our server
            if self._config.network_manager_enabled:
                success &= self._start_network_manager()
            
            if success:
                self._running = True
                logger.info("DNS Proxy system started successfully")
            else:
                logger.error("Some components failed to start")
                # Try to stop what we started
                self._partial_stop()
            
        except Exception as e:
            logger.error(f"Error starting DNS Proxy system: {e}")
            self._partial_stop()
            success = False
        
        return success
    
    def stop(self) -> bool:
        """
        Stop all components in reverse order.
        
        Order (reverse of start):
        1. Network Manager (restore DNS first so traffic doesn't go to dead server)
        2. DNS Proxy Server (stop listening)
        3. Security Manager (remove blocks)
        4. Enhanced Firewall Sync (cleanup rules)
        
        Returns:
            True if all stopped successfully
        """
        if not self._running and self._mode != OrchestratorMode.DISABLED:
            return True
        
        logger.info("Stopping DNS Proxy system...")
        
        success = True
        
        # Stop in reverse order
        try:
            # 1. Network Manager FIRST - restore DNS before stopping server
            success &= self._stop_component("network_manager")
            
            # 2. DNS Proxy Server
            success &= self._stop_component("dns_proxy")
            
            # 3. Security Manager
            success &= self._stop_component("security_manager")
            
            # 4. Enhanced Firewall Sync
            success &= self._stop_component("firewall_sync")
            
            self._running = False
            
            if success:
                logger.info("DNS Proxy system stopped successfully")
            else:
                logger.warning("Some components had errors during shutdown")
            
        except Exception as e:
            logger.error(f"Error stopping DNS Proxy system: {e}")
            success = False
        
        return success
    
    def _start_firewall_sync(self) -> bool:
        """Initialize and start Enhanced Firewall Sync."""
        component = self._components["firewall_sync"]
        component.status = ComponentStatus.STARTING
        
        try:
            from ..firewall import EnhancedFirewallSync, EnhancedSyncConfig
            
            config = EnhancedSyncConfig(
                default_grace_period=self._config.default_grace_period,
                connection_check_enabled=self._config.connection_aware_cleanup,
            )
            
            sync = EnhancedFirewallSync(config=config)
            
            if self._firewall_manager:
                sync.set_firewall_manager(self._firewall_manager)
            
            # Only start if not in monitor mode
            if self._mode != OrchestratorMode.MONITOR:
                sync.start()
            
            component.instance = sync
            component.status = ComponentStatus.RUNNING
            component.start_time = time.time()
            
            logger.info("Enhanced Firewall Sync started")
            return True
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error = str(e)
            logger.error(f"Failed to start Enhanced Firewall Sync: {e}")
            return False
    
    def _start_security_manager(self) -> bool:
        """Initialize and start Security Manager."""
        component = self._components["security_manager"]
        component.status = ComponentStatus.STARTING
        
        try:
            from ..security import SecurityManager, SecurityConfig, SecurityLevel
            
            # Determine security level based on mode
            if self._mode == OrchestratorMode.MONITOR:
                level = SecurityLevel.MONITOR
            elif self._mode == OrchestratorMode.ACTIVE:
                level = SecurityLevel.STRICT if self._config.auto_update_providers else SecurityLevel.STANDARD
            else:
                level = SecurityLevel.STANDARD
            
            config = SecurityConfig(
                level=level,
                block_doh_domains=self._config.block_doh,
                block_doh_ips=self._config.block_doh,
                block_dot_port=self._config.block_dot,
                upstream_resolvers=self._config.upstream_resolvers.copy(),
                auto_update_providers=self._config.auto_update_providers,
            )
            
            manager = SecurityManager(config=config)
            
            # Only enable if not in monitor mode
            if self._mode != OrchestratorMode.MONITOR:
                manager.enable()
            
            component.instance = manager
            component.status = ComponentStatus.RUNNING
            component.start_time = time.time()
            
            logger.info("Security Manager started")
            return True
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error = str(e)
            logger.error(f"Failed to start Security Manager: {e}")
            return False
    
    def _start_network_manager(self) -> bool:
        """Initialize and start Network Manager."""
        component = self._components["network_manager"]
        component.status = ComponentStatus.STARTING
        
        try:
            from ..network import NetworkManager, NetworkConfig, NetworkMode
            
            # Determine network mode
            if self._mode == OrchestratorMode.MONITOR:
                net_mode = NetworkMode.MONITOR
            elif self._mode == OrchestratorMode.ACTIVE:
                net_mode = NetworkMode.ACTIVE
            else:
                net_mode = NetworkMode.MONITOR
            
            config = NetworkConfig(
                mode=net_mode,
                auto_configure_dns=self._config.auto_configure_dns,
                dns_address=self._config.dns_bind_address,
                enable_ipv6=self._config.dns_ipv6_enabled,
            )
            
            manager = NetworkManager(config=config)
            
            # Enable if in active mode
            if self._mode == OrchestratorMode.ACTIVE:
                manager.enable()
            
            component.instance = manager
            component.status = ComponentStatus.RUNNING
            component.start_time = time.time()
            
            logger.info("Network Manager started")
            return True
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error = str(e)
            logger.error(f"Failed to start Network Manager: {e}")
            return False
    
    def _start_dns_proxy(self) -> bool:
        """Initialize and start DNS Proxy Server."""
        component = self._components["dns_proxy"]
        component.status = ComponentStatus.STARTING
        
        try:
            from ..server import DNSProxyServer
            from ..config import DNSProxyConfig, DNSServerConfig
            
            server_config = DNSServerConfig(
                bind_address=self._config.dns_bind_address,
                port=self._config.dns_port,
                ipv6_enabled=self._config.dns_ipv6_enabled,
            )
            
            config = DNSProxyConfig(
                enabled=True,
                server=server_config,
            )
            
            server = DNSProxyServer(config=config)
            
            # Add essential domains (server URLs that bypass whitelist)
            if self._essential_domains:
                server.query_handler.add_essential_domains(self._essential_domains)
            
            # Connect whitelist state
            if self._whitelist_state:
                server.query_handler.set_whitelist_state(self._whitelist_state)
            
            # Connect firewall sync
            firewall_sync = self._components["firewall_sync"].instance
            if firewall_sync:
                server.query_handler.set_firewall_sync(firewall_sync)
            
            # Start listening
            server.start()
            
            component.instance = server
            component.status = ComponentStatus.RUNNING
            component.start_time = time.time()
            
            logger.info("DNS Proxy Server started")
            return True
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error = str(e)
            logger.error(f"Failed to start DNS Proxy Server: {e}")
            return False
    
    def _stop_component(self, name: str) -> bool:
        """Stop a single component."""
        component = self._components.get(name)
        if not component or not component.instance:
            return True
        
        component.status = ComponentStatus.STOPPING
        
        try:
            instance = component.instance
            
            # Call appropriate stop method
            # Priority: disable > shutdown > stop (disable often includes cleanup)
            if hasattr(instance, "disable"):
                instance.disable()
            elif hasattr(instance, "shutdown"):
                instance.shutdown()
            elif hasattr(instance, "stop"):
                instance.stop()
            
            component.instance = None
            component.status = ComponentStatus.STOPPED
            component.start_time = None
            
            logger.debug(f"Component {name} stopped")
            return True
            
        except Exception as e:
            component.status = ComponentStatus.ERROR
            component.error = str(e)
            logger.error(f"Error stopping {name}: {e}")
            return False
    
    def _partial_stop(self) -> None:
        """Stop components that were started during a failed startup."""
        for name in reversed(list(self._components.keys())):
            component = self._components[name]
            if component.status in (ComponentStatus.RUNNING, ComponentStatus.STARTING):
                self._stop_component(name)
    
    def _apply_mode_changes(self) -> None:
        """Apply configuration changes when mode changes."""
        # This would handle live mode transitions
        pass
    
    def get_status(self) -> Dict:
        """Get comprehensive system status."""
        component_statuses = {}
        
        for name, component in self._components.items():
            stats = {}
            if component.instance and hasattr(component.instance, "get_stats"):
                try:
                    stats = component.instance.get_stats()
                except Exception:
                    pass
            
            component_statuses[name] = {
                "status": component.status.value,
                "running": component.is_running,
                "uptime": round(component.uptime, 2),
                "error": component.error,
                "stats": stats,
            }
        
        return {
            "mode": self._mode.value,
            "running": self._running,
            "components": component_statuses,
            "config": {
                "dns_enabled": self._config.dns_proxy_enabled,
                "network_enabled": self._config.network_manager_enabled,
                "security_enabled": self._config.security_enabled,
                "firewall_enabled": self._config.firewall_sync_enabled,
            },
        }
    
    def get_dns_proxy(self):
        """Get the DNS Proxy Server instance."""
        return self._components["dns_proxy"].instance
    
    def get_network_manager(self):
        """Get the Network Manager instance."""
        return self._components["network_manager"].instance
    
    def get_security_manager(self):
        """Get the Security Manager instance."""
        return self._components["security_manager"].instance
    
    def get_firewall_sync(self):
        """Get the Enhanced Firewall Sync instance."""
        return self._components["firewall_sync"].instance
    
    def on_status_change(self, callback: Callable[[str, ComponentStatus], None]) -> None:
        """Register callback for component status changes."""
        self._on_status_change.append(callback)
    
    def on_error(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for component errors."""
        self._on_error.append(callback)
    
    @property
    def is_running(self) -> bool:
        """Check if the system is running."""
        return self._running
    
    @property
    def mode(self) -> OrchestratorMode:
        """Get current operating mode."""
        return self._mode
