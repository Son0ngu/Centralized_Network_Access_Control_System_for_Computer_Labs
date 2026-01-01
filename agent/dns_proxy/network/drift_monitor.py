"""
DNS Drift Monitor
-----------------
Monitors DNS configuration for unauthorized changes.
Auto-restores DNS settings when drift is detected.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .adapter_config import NetworkAdapterManager, NetworkAdapter, AdapterType
from .dns_enforcer import DNSEnforcer, EnforcementMode

logger = logging.getLogger("dns_proxy.network.drift_monitor")


class DriftAction(Enum):
    """Action to take when drift is detected."""
    LOG_ONLY = "log"        # Just log the drift
    ALERT = "alert"         # Log and trigger callback
    AUTO_RESTORE = "restore"  # Automatically restore DNS


@dataclass
class DriftEvent:
    """DNS drift event."""
    adapter_name: str
    address_family: str  # "ipv4" or "ipv6"
    expected_dns: List[str]
    actual_dns: List[str]
    timestamp: float = field(default_factory=time.time)
    restored: bool = False
    
    @property
    def is_drift(self) -> bool:
        """Check if there's actually a drift."""
        return set(self.expected_dns) != set(self.actual_dns)


@dataclass
class MonitorConfig:
    """Drift monitor configuration."""
    check_interval: float = 30.0  # Seconds between checks
    action: DriftAction = DriftAction.AUTO_RESTORE
    max_restore_attempts: int = 3
    restore_cooldown: float = 60.0  # Seconds between restore attempts
    enabled: bool = True


class DNSDriftMonitor:
    """
    Monitors DNS configuration and detects unauthorized changes.
    
    Features:
    - Periodic DNS configuration checking
    - Drift detection with expected vs actual comparison
    - Auto-restore capability
    - Event callbacks for alerting
    """
    
    def __init__(
        self,
        adapter_manager: NetworkAdapterManager = None,
        enforcer: DNSEnforcer = None,
        config: MonitorConfig = None
    ):
        self._adapter_manager = adapter_manager or NetworkAdapterManager()
        self._enforcer = enforcer or DNSEnforcer(
            adapter_manager=self._adapter_manager,
            mode=EnforcementMode.ENFORCE
        )
        self._config = config or MonitorConfig()
        
        # Expected DNS configuration
        self._expected_ipv4 = [DNSEnforcer.PROXY_DNS_IPV4]
        self._expected_ipv6 = [DNSEnforcer.PROXY_DNS_IPV6]
        
        # Monitoring state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Drift tracking
        self._drift_events: List[DriftEvent] = []
        self._restore_attempts: Dict[str, int] = {}  # adapter_name -> attempts
        self._last_restore_time: Dict[str, float] = {}  # adapter_name -> timestamp
        
        # Callbacks
        self._on_drift_callbacks: List[Callable[[DriftEvent], None]] = []
        self._on_restore_callbacks: List[Callable[[DriftEvent, bool], None]] = []
        
        logger.info("DNS Drift Monitor initialized")
    
    def start(self) -> None:
        """Start the drift monitor."""
        if self._running:
            logger.warning("Drift monitor already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="DNSDriftMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        logger.info(
            f"DNS Drift Monitor started (interval: {self._config.check_interval}s, "
            f"action: {self._config.action.value})"
        )
    
    def stop(self) -> None:
        """Stop the drift monitor."""
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)  # Reduced for faster shutdown
            self._monitor_thread = None
        
        logger.info("DNS Drift Monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                if self._config.enabled:
                    self._check_for_drift()
                
            except Exception as e:
                logger.error(f"Error in drift monitor: {e}", exc_info=True)
            
            # Sleep with periodic wake-ups for faster shutdown
            sleep_time = self._config.check_interval
            while sleep_time > 0 and self._running:
                time.sleep(min(1.0, sleep_time))
                sleep_time -= 1.0
    
    def _check_for_drift(self) -> List[DriftEvent]:
        """
        Check all adapters for DNS drift.
        
        Returns:
            List of drift events detected
        """
        # Refresh adapter data
        self._adapter_manager.refresh()
        
        drift_events = []
        
        for adapter in self._adapter_manager.get_active_adapters():
            # Skip adapters that don't need DNS config
            if adapter.adapter_type in (AdapterType.LOOPBACK,):
                continue
            
            # Check IPv4 drift
            if adapter.has_ipv4:
                event = self._check_adapter_drift(adapter, "ipv4")
                if event and event.is_drift:
                    drift_events.append(event)
                    self._handle_drift(event)
            
            # Check IPv6 drift
            if adapter.has_ipv6:
                event = self._check_adapter_drift(adapter, "ipv6")
                if event and event.is_drift:
                    drift_events.append(event)
                    self._handle_drift(event)
        
        return drift_events
    
    def _check_adapter_drift(
        self,
        adapter: NetworkAdapter,
        address_family: str
    ) -> Optional[DriftEvent]:
        """Check a specific adapter for DNS drift."""
        if address_family == "ipv4":
            expected = self._expected_ipv4
            actual = adapter.dns_config.ipv4_servers
        else:
            expected = self._expected_ipv6
            actual = adapter.dns_config.ipv6_servers
        
        # Check if expected DNS is in actual config
        # We consider it OK if our DNS is at least present
        if expected[0] in actual:
            return None  # No drift
        
        event = DriftEvent(
            adapter_name=adapter.name,
            address_family=address_family,
            expected_dns=expected,
            actual_dns=actual
        )
        
        return event
    
    def _handle_drift(self, event: DriftEvent) -> None:
        """Handle a drift event based on configured action."""
        self._drift_events.append(event)
        
        logger.warning(
            f"DNS DRIFT detected on {event.adapter_name} ({event.address_family}): "
            f"expected {event.expected_dns}, got {event.actual_dns}"
        )
        
        # Notify callbacks
        for callback in self._on_drift_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Drift callback error: {e}")
        
        if self._config.action == DriftAction.LOG_ONLY:
            return
        
        if self._config.action == DriftAction.ALERT:
            # Just triggered callbacks above
            return
        
        if self._config.action == DriftAction.AUTO_RESTORE:
            self._attempt_restore(event)
    
    def _attempt_restore(self, event: DriftEvent) -> bool:
        """Attempt to restore DNS configuration."""
        adapter_key = f"{event.adapter_name}_{event.address_family}"
        
        # Check cooldown
        last_restore = self._last_restore_time.get(adapter_key, 0)
        if time.time() - last_restore < self._config.restore_cooldown:
            logger.debug(f"Restore cooldown active for {adapter_key}")
            return False
        
        # Check attempt limit
        attempts = self._restore_attempts.get(adapter_key, 0)
        if attempts >= self._config.max_restore_attempts:
            logger.error(
                f"Max restore attempts ({self._config.max_restore_attempts}) "
                f"reached for {adapter_key}"
            )
            return False
        
        # Attempt restore
        self._restore_attempts[adapter_key] = attempts + 1
        self._last_restore_time[adapter_key] = time.time()
        
        try:
            result = self._enforcer.enforce_dns(force=True)
            
            if result.success:
                event.restored = True
                logger.info(f"DNS restored on {event.adapter_name}")
                
                # Reset attempt counter on success
                self._restore_attempts[adapter_key] = 0
                
            # Notify restore callbacks
            for callback in self._on_restore_callbacks:
                try:
                    callback(event, result.success)
                except Exception as e:
                    logger.error(f"Restore callback error: {e}")
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to restore DNS on {event.adapter_name}: {e}")
            return False
    
    def check_now(self) -> List[DriftEvent]:
        """Perform an immediate drift check."""
        return self._check_for_drift()
    
    def on_drift(self, callback: Callable[[DriftEvent], None]) -> None:
        """Register a callback for drift events."""
        self._on_drift_callbacks.append(callback)
    
    def on_restore(self, callback: Callable[[DriftEvent, bool], None]) -> None:
        """Register a callback for restore events."""
        self._on_restore_callbacks.append(callback)
    
    def set_action(self, action: DriftAction) -> None:
        """Change the drift action."""
        old_action = self._config.action
        self._config.action = action
        logger.info(f"Drift action changed: {old_action.value} → {action.value}")
    
    def set_interval(self, interval: float) -> None:
        """Change the check interval."""
        self._config.check_interval = max(5.0, interval)  # Minimum 5 seconds
        logger.info(f"Drift check interval set to {self._config.check_interval}s")
    
    def enable(self) -> None:
        """Enable drift monitoring."""
        self._config.enabled = True
        logger.info("Drift monitoring enabled")
    
    def disable(self) -> None:
        """Disable drift monitoring."""
        self._config.enabled = False
        logger.info("Drift monitoring disabled")
    
    def reset_attempts(self, adapter_name: str = None) -> None:
        """Reset restore attempt counters."""
        if adapter_name:
            keys_to_remove = [k for k in self._restore_attempts if k.startswith(adapter_name)]
            for key in keys_to_remove:
                del self._restore_attempts[key]
                if key in self._last_restore_time:
                    del self._last_restore_time[key]
        else:
            self._restore_attempts.clear()
            self._last_restore_time.clear()
        
        logger.debug("Restore attempt counters reset")
    
    def get_drift_history(self, limit: int = 100) -> List[DriftEvent]:
        """Get drift event history."""
        return self._drift_events[-limit:]
    
    def clear_history(self) -> None:
        """Clear drift event history."""
        self._drift_events.clear()
    
    def get_stats(self) -> Dict:
        """Get monitor statistics."""
        return {
            "enabled": self._config.enabled,
            "running": self._running,
            "check_interval": self._config.check_interval,
            "action": self._config.action.value,
            "total_drift_events": len(self._drift_events),
            "restored_events": len([e for e in self._drift_events if e.restored]),
            "pending_restores": sum(self._restore_attempts.values()),
        }
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def config(self) -> MonitorConfig:
        return self._config
