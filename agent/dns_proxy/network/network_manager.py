"""
Network Manager
---------------
Central coordinator for network configuration.
Supports monitor (read-only) mode for testing before applying changes.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .adapter_config import NetworkAdapterManager, NetworkAdapter, AdapterPriority
from .dns_enforcer import DNSEnforcer, EnforcementMode, EnforcementResult
from .doh_blocker import DoHBlocker, BlockerResult
from .drift_monitor import DNSDriftMonitor, DriftAction, DriftEvent, MonitorConfig

logger = logging.getLogger("dns_proxy.network.manager")


class NetworkMode(Enum):
    """Network configuration mode."""
    DISABLED = "disabled"       # Do nothing
    MONITOR = "monitor"         # Read-only, analyze what would change
    ACTIVE = "active"           # Apply changes, monitor drift, restore
    

@dataclass
class NetworkConfig:
    """Network manager configuration (IPv4 only)."""
    mode: NetworkMode = NetworkMode.MONITOR
    
    # DNS configuration (IPv4 only)
    configure_ipv4: bool = True
    configure_secondary_adapters: bool = True
    
    # Auto-configure DNS settings (used by orchestrator)
    auto_configure_dns: bool = True
    dns_address: str = "127.0.0.1"
    
    # DoH/DoT blocking
    block_doh: bool = True
    block_dot: bool = True
    
    # Drift monitoring
    drift_check_interval: float = 30.0
    drift_action: DriftAction = DriftAction.AUTO_RESTORE
    max_restore_attempts: int = 3
    
    # Safety
    require_confirmation: bool = True
    backup_before_change: bool = True


@dataclass
class NetworkStatus:
    """Current network status (IPv4 only)."""
    mode: NetworkMode
    adapters_total: int = 0
    adapters_configured: int = 0
    adapters_need_config: int = 0
    doh_rules_active: int = 0
    drift_monitor_running: bool = False
    last_check_time: float = 0
    pending_changes: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class MonitorReport:
    """Report from monitor mode analysis (IPv4 only)."""
    timestamp: float = field(default_factory=time.time)
    
    # Adapters
    adapters_scanned: int = 0
    adapters_need_ipv4_change: List[str] = field(default_factory=list)
    
    # DNS changes that would be made
    dns_changes: List[Dict] = field(default_factory=list)
    
    # DoH/DoT
    doh_ips_to_block: int = 0
    doh_rules_to_create: int = 0
    
    # Summary
    total_changes: int = 0
    safe_to_apply: bool = True
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class NetworkManager:
    """
    Central network configuration manager.
    
    Features:
    - Monitor mode for safe testing
    - Coordinate adapter config, DNS enforcement, DoH blocking
    - Unified status and reporting
    - Easy mode switching
    
    Usage:
        manager = NetworkManager()
        
        # First, analyze in monitor mode
        report = manager.analyze()
        print(report)
        
        # If safe, switch to active mode
        if report.safe_to_apply:
            manager.set_mode(NetworkMode.ACTIVE)
            manager.apply()
    """
    
    def __init__(self, config: NetworkConfig = None):
        self._config = config or NetworkConfig()
        
        # Initialize components
        self._adapter_manager = NetworkAdapterManager()
        
        self._enforcer = DNSEnforcer(
            adapter_manager=self._adapter_manager,
            mode=self._mode_to_enforcement(self._config.mode)
        )
        
        self._doh_blocker = DoHBlocker(
            block_doh=self._config.block_doh,
            block_dot=self._config.block_dot
        )
        
        self._drift_monitor = DNSDriftMonitor(
            adapter_manager=self._adapter_manager,
            enforcer=self._enforcer,
            config=MonitorConfig(
                check_interval=self._config.drift_check_interval,
                action=self._config.drift_action,
                max_restore_attempts=self._config.max_restore_attempts,
            )
        )
        
        # State
        self._initialized = False
        self._last_report: Optional[MonitorReport] = None
        
        # Callbacks
        self._on_mode_change: List[Callable[[NetworkMode, NetworkMode], None]] = []
        self._on_status_change: List[Callable[[NetworkStatus], None]] = []
        
        logger.info(f"Network Manager initialized in {self._config.mode.value} mode")
    
    def _mode_to_enforcement(self, mode: NetworkMode) -> EnforcementMode:
        """Convert NetworkMode to EnforcementMode."""
        if mode == NetworkMode.DISABLED:
            return EnforcementMode.DISABLED
        elif mode == NetworkMode.MONITOR:
            return EnforcementMode.MONITOR
        else:
            return EnforcementMode.ENFORCE
    
    @property
    def mode(self) -> NetworkMode:
        return self._config.mode
    
    def set_mode(self, mode: NetworkMode) -> None:
        """
        Change the network configuration mode.
        
        Args:
            mode: New mode to set
        """
        old_mode = self._config.mode
        if old_mode == mode:
            return
        
        self._config.mode = mode
        
        # Update component modes
        self._enforcer.set_mode(self._mode_to_enforcement(mode))
        
        # Update drift monitor
        if mode == NetworkMode.ACTIVE:
            self._drift_monitor.set_action(self._config.drift_action)
        else:
            self._drift_monitor.set_action(DriftAction.LOG_ONLY)
        
        logger.info(f"Network mode changed: {old_mode.value} → {mode.value}")
        
        # Notify callbacks
        for callback in self._on_mode_change:
            try:
                callback(old_mode, mode)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")
    
    def analyze(self) -> MonitorReport:
        """
        Analyze current network state and what changes would be made.
        Safe to call in any mode.
        
        Returns:
            MonitorReport with analysis results
        """
        report = MonitorReport()
        
        try:
            # Scan adapters
            self._adapter_manager.refresh()
            priorities = self._adapter_manager.get_adapters_for_dns_config()
            
            report.adapters_scanned = len(priorities)
            
            for priority in priorities:
                adapter = priority.adapter
                
                # Check IPv4 only
                if adapter.has_ipv4:
                    if DNSEnforcer.PROXY_DNS_IPV4 not in adapter.dns_config.ipv4_servers:
                        report.adapters_need_ipv4_change.append(adapter.name)
                        report.dns_changes.append({
                            "adapter": adapter.name,
                            "family": "ipv4",
                            "current": adapter.dns_config.ipv4_servers,
                            "new": [DNSEnforcer.PROXY_DNS_IPV4],
                            "reason": priority.reason,
                        })
            
            # DoH/DoT analysis (IPv4 only)
            if self._config.block_doh or self._config.block_dot:
                providers = self._doh_blocker.get_providers()
                ipv4_count = sum(len(p.ipv4_addresses) for p in providers)
                
                report.doh_ips_to_block = ipv4_count
                
                # Estimate rules
                rules = 0
                if self._config.block_doh:
                    rules += 1  # IPv4 DoH only
                if self._config.block_dot:
                    rules += 1  # IPv4 port 853
                report.doh_rules_to_create = rules
            
            # Calculate totals
            report.total_changes = len(report.dns_changes)
            
            # Safety checks
            if len(report.adapters_need_ipv4_change) > 3:
                report.warnings.append(
                    f"Many adapters ({len(report.adapters_need_ipv4_change)}) will be modified"
                )
            
            # Check for VPN adapters
            vpn_adapters = [
                a for a in self._adapter_manager.get_active_adapters()
                if "vpn" in a.name.lower()
            ]
            if vpn_adapters:
                report.warnings.append(
                    f"VPN adapters detected: {[a.name for a in vpn_adapters]}"
                )
            
            # Recommendations
            if report.total_changes > 0:
                report.recommendations.append(
                    "Review DNS changes carefully before applying"
                )
            
            if not self._doh_blocker.check_rules_exist().get("DNS_Proxy_Block_DoH_IPv4"):
                report.recommendations.append(
                    "Consider enabling DoH/DoT blocking to prevent bypass"
                )
            
            report.safe_to_apply = len(report.warnings) <= 2
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}", exc_info=True)
            report.warnings.append(f"Analysis error: {e}")
            report.safe_to_apply = False
        
        self._last_report = report
        return report
    
    def apply(self, force: bool = False) -> Dict:
        """
        Apply network configuration changes.
        
        Args:
            force: If True, apply even if already configured
            
        Returns:
            Dict with results from each component
        """
        if self._config.mode == NetworkMode.DISABLED:
            return {"error": "Network manager is disabled"}
        
        if self._config.mode == NetworkMode.MONITOR:
            # In monitor mode, just analyze
            return {"report": self.analyze().__dict__}
        
        results = {
            "dns_enforcement": None,
            "doh_blocking": None,
            "drift_monitor": None,
            "errors": [],
        }
        
        try:
            # Apply DNS configuration
            enforcement_result = self._enforcer.enforce_dns(force=force)
            results["dns_enforcement"] = {
                "success": enforcement_result.success,
                "adapters_configured": enforcement_result.adapters_configured,
                "adapters_skipped": enforcement_result.adapters_skipped,
                "errors": enforcement_result.errors,
            }
            
            if not enforcement_result.success:
                results["errors"].extend(enforcement_result.errors)
            
        except Exception as e:
            logger.error(f"DNS enforcement failed: {e}")
            results["errors"].append(f"DNS enforcement: {e}")
        
        try:
            # Apply DoH/DoT blocking (IPv4 only)
            if self._config.block_doh or self._config.block_dot:
                block_result = self._doh_blocker.block_all_providers(
                    include_ipv6=False
                )
                results["doh_blocking"] = {
                    "success": block_result.success,
                    "rules_created": block_result.rules_created,
                    "ips_blocked": block_result.ips_blocked,
                    "errors": block_result.errors,
                }
                
                if not block_result.success:
                    results["errors"].extend(block_result.errors)
            
        except Exception as e:
            logger.error(f"DoH blocking failed: {e}")
            results["errors"].append(f"DoH blocking: {e}")
        
        try:
            # Start drift monitor
            if not self._drift_monitor.is_running:
                self._drift_monitor.start()
                results["drift_monitor"] = {"started": True}
            
        except Exception as e:
            logger.error(f"Drift monitor failed: {e}")
            results["errors"].append(f"Drift monitor: {e}")
        
        self._initialized = True
        
        return results
    
    def rollback(self) -> Dict:
        """
        Rollback all network changes.
        
        Returns:
            Dict with rollback results
        """
        results = {
            "dns_rollback": None,
            "doh_rollback": None,
            "errors": [],
        }
        
        try:
            # Stop drift monitor first
            if self._drift_monitor.is_running:
                self._drift_monitor.stop()
            
            # Rollback DNS
            dns_result = self._enforcer.rollback_all()
            results["dns_rollback"] = {
                "success": dns_result.success,
                "adapters_restored": dns_result.adapters_configured,
            }
            
        except Exception as e:
            logger.error(f"DNS rollback failed: {e}")
            results["errors"].append(f"DNS rollback: {e}")
        
        try:
            # Remove DoH/DoT rules
            removed = self._doh_blocker.remove_all_rules()
            results["doh_rollback"] = {
                "rules_removed": removed,
            }
            
        except Exception as e:
            logger.error(f"DoH rollback failed: {e}")
            results["errors"].append(f"DoH rollback: {e}")
        
        self._initialized = False
        
        logger.info("Network configuration rolled back")
        return results
    
    def restore(self) -> Dict:
        """
        Restore network configuration (alias for rollback).
        Used by disable() for cleanup on shutdown.
        """
        return self.rollback()
    
    def get_status(self) -> NetworkStatus:
        """Get current network status (IPv4 only)."""
        self._adapter_manager.refresh()
        
        adapters = self._adapter_manager.get_active_adapters()
        configured = [
            a for a in adapters
            if a.dns_config.is_proxy_configured
        ]
        need_config = [
            a for a in adapters
            if a.needs_dns_config
        ]
        
        doh_rules = self._doh_blocker.check_rules_exist()
        active_rules = sum(1 for v in doh_rules.values() if v)
        
        return NetworkStatus(
            mode=self._config.mode,
            adapters_total=len(adapters),
            adapters_configured=len(configured),
            adapters_need_config=len(need_config),
            doh_rules_active=active_rules,
            drift_monitor_running=self._drift_monitor.is_running,
            last_check_time=time.time(),
            pending_changes=len(need_config),
        )
    
    def start(self) -> None:
        """Start the network manager."""
        if self._config.mode == NetworkMode.ACTIVE:
            self.apply()
        else:
            self.analyze()
    
    def enable(self) -> bool:
        """
        Enable and apply network configuration.
        This is an alias for start() with ACTIVE mode.
        Used by orchestrator for consistent API.
        """
        try:
            if self._config.mode == NetworkMode.ACTIVE:
                self.apply()
            else:
                self.analyze()
            return True
        except Exception as e:
            logger.error(f"Failed to enable Network Manager: {e}")
            return False
    
    def disable(self) -> bool:
        """
        Disable and restore network configuration.
        Used by orchestrator for consistent API.
        """
        try:
            self.restore()
            self.stop()
            return True
        except Exception as e:
            logger.error(f"Failed to disable Network Manager: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the network manager."""
        if self._drift_monitor.is_running:
            self._drift_monitor.stop()
    
    def on_mode_change(self, callback: Callable[[NetworkMode, NetworkMode], None]) -> None:
        """Register callback for mode changes."""
        self._on_mode_change.append(callback)
    
    def on_drift(self, callback: Callable[[DriftEvent], None]) -> None:
        """Register callback for drift events."""
        self._drift_monitor.on_drift(callback)
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics."""
        adapter_summary = self._adapter_manager.get_summary()
        enforcer_stats = self._enforcer.get_stats()
        doh_stats = self._doh_blocker.get_stats()
        drift_stats = self._drift_monitor.get_stats()
        
        return {
            "mode": self._config.mode.value,
            "initialized": self._initialized,
            "adapters": adapter_summary,
            "enforcer": enforcer_stats,
            "doh_blocker": doh_stats,
            "drift_monitor": drift_stats,
        }
    
    @property
    def config(self) -> NetworkConfig:
        return self._config
    
    @property
    def adapter_manager(self) -> NetworkAdapterManager:
        return self._adapter_manager
    
    @property
    def enforcer(self) -> DNSEnforcer:
        return self._enforcer
    
    @property
    def doh_blocker(self) -> DoHBlocker:
        return self._doh_blocker
    
    @property
    def drift_monitor(self) -> DNSDriftMonitor:
        return self._drift_monitor
    
    @property
    def last_report(self) -> Optional[MonitorReport]:
        return self._last_report
