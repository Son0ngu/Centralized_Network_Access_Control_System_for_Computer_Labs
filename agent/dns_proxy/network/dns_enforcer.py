"""
DNS Enforcer
-------------
Sets and enforces DNS configuration on network adapters.
Supports IPv4 (127.0.0.1) and IPv6 (::1).
"""

import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .adapter_config import (
    NetworkAdapter,
    NetworkAdapterManager,
    AdapterPriority,
    AdapterType,
)

logger = logging.getLogger("dns_proxy.network.enforcer")


class EnforcementMode(Enum):
    """DNS enforcement mode."""
    DISABLED = "disabled"       # Do nothing
    MONITOR = "monitor"         # Read-only, log what would change
    ENFORCE = "enforce"         # Apply DNS changes
    ENFORCE_LOCK = "lock"       # Apply and prevent changes


@dataclass
class DNSChange:
    """Represents a DNS configuration change."""
    adapter_name: str
    address_family: str  # "ipv4" or "ipv6"
    old_servers: List[str]
    new_servers: List[str]
    success: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class EnforcementResult:
    """Result of DNS enforcement operation."""
    success: bool
    changes: List[DNSChange] = field(default_factory=list)
    adapters_configured: int = 0
    adapters_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    mode: EnforcementMode = EnforcementMode.MONITOR


class DNSEnforcer:
    """
    Enforces DNS configuration on network adapters.
    
    Features:
    - Set DNS to 127.0.0.1 (IPv4) and ::1 (IPv6)
    - Multi-adapter support with priority handling
    - Monitor mode for testing
    - Rollback capability
    """
    
    # DNS proxy addresses
    PROXY_DNS_IPV4 = "127.0.0.1"
    PROXY_DNS_IPV6 = "::1"
    
    def __init__(
        self,
        adapter_manager: NetworkAdapterManager = None,
        mode: EnforcementMode = EnforcementMode.MONITOR
    ):
        self._adapter_manager = adapter_manager or NetworkAdapterManager()
        self._mode = mode
        
        # Track original DNS for rollback
        self._original_dns: Dict[str, Dict] = {}
        
        # Change history
        self._change_history: List[DNSChange] = []
        
        logger.info(f"DNS Enforcer initialized in {mode.value} mode")
    
    @property
    def mode(self) -> EnforcementMode:
        return self._mode
    
    @mode.setter
    def mode(self, value: EnforcementMode) -> None:
        old_mode = self._mode
        self._mode = value
        logger.info(f"DNS Enforcer mode changed: {old_mode.value} → {value.value}")
    
    def set_mode(self, mode: EnforcementMode) -> None:
        """Set enforcement mode."""
        self.mode = mode
    
    def enforce_dns(self, force: bool = False) -> EnforcementResult:
        """
        Enforce DNS configuration on all eligible adapters.
        
        Args:
            force: If True, reconfigure even if already configured
            
        Returns:
            EnforcementResult with details of changes made
        """
        result = EnforcementResult(success=True, mode=self._mode)
        
        if self._mode == EnforcementMode.DISABLED:
            logger.info("DNS enforcement is disabled")
            return result
        
        # Refresh adapter list
        self._adapter_manager.refresh()
        
        # Get prioritized adapters
        priorities = self._adapter_manager.get_adapters_for_dns_config()
        
        logger.info(f"Found {len(priorities)} adapters to configure")
        
        for priority in priorities:
            adapter = priority.adapter
            
            # Check if already configured
            if not force and adapter.dns_config.is_proxy_configured:
                logger.debug(f"Skipping {adapter.name}: already configured")
                result.adapters_skipped += 1
                continue
            
            # Store original DNS for rollback
            self._store_original_dns(adapter)
            
            # Configure IPv4
            if adapter.has_ipv4:
                change = self._configure_dns(
                    adapter=adapter,
                    address_family="ipv4",
                    dns_servers=[self.PROXY_DNS_IPV4]
                )
                result.changes.append(change)
                
                if not change.success:
                    result.errors.append(f"{adapter.name} IPv4: {change.error}")
            
            # Configure IPv6
            if adapter.has_ipv6:
                change = self._configure_dns(
                    adapter=adapter,
                    address_family="ipv6",
                    dns_servers=[self.PROXY_DNS_IPV6]
                )
                result.changes.append(change)
                
                if not change.success:
                    result.errors.append(f"{adapter.name} IPv6: {change.error}")
            
            result.adapters_configured += 1
        
        result.success = len(result.errors) == 0
        
        self._log_result(result)
        
        return result
    
    def _configure_dns(
        self,
        adapter: NetworkAdapter,
        address_family: str,
        dns_servers: List[str]
    ) -> DNSChange:
        """Configure DNS for a specific adapter and address family."""
        # Get current servers
        if address_family == "ipv4":
            old_servers = adapter.dns_config.ipv4_servers.copy()
        else:
            old_servers = adapter.dns_config.ipv6_servers.copy()
        
        change = DNSChange(
            adapter_name=adapter.name,
            address_family=address_family,
            old_servers=old_servers,
            new_servers=dns_servers.copy()
        )
        
        # Check if already correct
        if old_servers == dns_servers:
            change.success = True
            return change
        
        # Monitor mode - just log
        if self._mode == EnforcementMode.MONITOR:
            logger.info(
                f"[MONITOR] Would set {adapter.name} {address_family} DNS: "
                f"{old_servers} → {dns_servers}"
            )
            change.success = True
            return change
        
        # Apply the change
        try:
            if address_family == "ipv4":
                self._set_dns_ipv4(adapter.name, dns_servers)
            else:
                self._set_dns_ipv6(adapter.name, dns_servers)
            
            change.success = True
            logger.info(
                f"Set {adapter.name} {address_family} DNS: "
                f"{old_servers} → {dns_servers}"
            )
            
        except Exception as e:
            change.success = False
            change.error = str(e)
            logger.error(f"Failed to set DNS on {adapter.name}: {e}")
        
        self._change_history.append(change)
        
        return change
    
    def _set_dns_ipv4(self, adapter_name: str, servers: List[str]) -> None:
        """Set IPv4 DNS servers using netsh."""
        if not servers:
            # Clear DNS (set to DHCP)
            cmd = [
                "netsh", "interface", "ipv4", "set", "dnsservers",
                f"name={adapter_name}",
                "source=dhcp"
            ]
            logger.info(f"Restoring {adapter_name} IPv4 DNS to DHCP")
        else:
            # Set primary DNS
            cmd = [
                "netsh", "interface", "ipv4", "set", "dnsservers",
                f"name={adapter_name}",
                "source=static",
                f"address={servers[0]}",
                "validate=no"
            ]
            logger.info(f"Restoring {adapter_name} IPv4 DNS to {servers}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            raise Exception(f"netsh failed: {result.stderr.strip()}")
        
        # Add secondary DNS servers with incrementing index
        for idx, server in enumerate(servers[1:], start=2):
            cmd = [
                "netsh", "interface", "ipv4", "add", "dnsservers",
                f"name={adapter_name}",
                f"address={server}",
                f"index={idx}",
                "validate=no"
            ]
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
    
    def _set_dns_ipv6(self, adapter_name: str, servers: List[str]) -> None:
        """Set IPv6 DNS servers using netsh."""
        if not servers:
            cmd = [
                "netsh", "interface", "ipv6", "set", "dnsservers",
                f"name={adapter_name}",
                "source=dhcp"
            ]
            logger.info(f"Restoring {adapter_name} IPv6 DNS to DHCP")
        else:
            cmd = [
                "netsh", "interface", "ipv6", "set", "dnsservers",
                f"name={adapter_name}",
                "source=static",
                f"address={servers[0]}",
                "validate=no"
            ]
            logger.info(f"Restoring {adapter_name} IPv6 DNS to {servers}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            raise Exception(f"netsh failed: {result.stderr.strip()}")
        
        # Add secondary DNS servers with incrementing index
        for idx, server in enumerate(servers[1:], start=2):
            cmd = [
                "netsh", "interface", "ipv6", "add", "dnsservers",
                f"name={adapter_name}",
                f"address={server}",
                f"index={idx}",
                "validate=no"
            ]
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
    
    def _store_original_dns(self, adapter: NetworkAdapter) -> None:
        """Store original DNS configuration for rollback."""
        if adapter.name not in self._original_dns:
            self._original_dns[adapter.name] = {
                "ipv4": adapter.dns_config.ipv4_servers.copy(),
                "ipv6": adapter.dns_config.ipv6_servers.copy(),
                "is_dhcp_v4": adapter.dns_config.is_dhcp_v4,
                "is_dhcp_v6": adapter.dns_config.is_dhcp_v6,
            }
            logger.info(
                f"Stored original DNS for {adapter.name}: "
                f"IPv4={adapter.dns_config.ipv4_servers}, "
                f"IPv6={adapter.dns_config.ipv6_servers}, "
                f"DHCPv4={adapter.dns_config.is_dhcp_v4}, "
                f"DHCPv6={adapter.dns_config.is_dhcp_v6}"
            )
    
    def rollback(self, adapter_name: str = None) -> EnforcementResult:
        """
        Rollback DNS changes to original configuration.
        
        Args:
            adapter_name: Specific adapter to rollback, or None for all
            
        Returns:
            EnforcementResult with rollback details
        """
        result = EnforcementResult(success=True, mode=self._mode)
        
        logger.info(f"Rolling back DNS configuration (stored adapters: {list(self._original_dns.keys())})")
        
        if not self._original_dns:
            logger.warning("No original DNS configuration stored - nothing to rollback")
            return result
        
        adapters_to_rollback = (
            {adapter_name: self._original_dns.get(adapter_name)}
            if adapter_name
            else self._original_dns.copy()
        )
        
        for name, original in adapters_to_rollback.items():
            if not original:
                logger.warning(f"No original config for adapter {name}")
                continue
            
            try:
                logger.info(f"Rolling back DNS for adapter: {name}")
                
                # Restore IPv4
                if original.get("is_dhcp_v4", True):
                    self._set_dns_ipv4(name, [])  # DHCP
                else:
                    self._set_dns_ipv4(name, original.get("ipv4", []))
                
                # Restore IPv6
                if original.get("is_dhcp_v6", True):
                    self._set_dns_ipv6(name, [])  # DHCP
                else:
                    self._set_dns_ipv6(name, original.get("ipv6", []))
                
                result.adapters_configured += 1
                logger.info(f"✓ Rolled back DNS for {name}")
                
                # Remove from original storage
                if name in self._original_dns:
                    del self._original_dns[name]
                    
            except Exception as e:
                result.errors.append(f"{name}: {e}")
                logger.error(f"✗ Failed to rollback {name}: {e}")
        
        result.success = len(result.errors) == 0
        logger.info(f"Rollback complete: {result.adapters_configured} adapters restored, {len(result.errors)} errors")
        
        return result
    
    def rollback_all(self) -> EnforcementResult:
        """Rollback all DNS changes."""
        return self.rollback()
    
    def check_configuration(self) -> Dict:
        """
        Check current DNS configuration status.
        
        Returns:
            Dict with configuration status for each adapter
        """
        self._adapter_manager.refresh()
        
        status = {}
        
        for adapter in self._adapter_manager.get_active_adapters():
            if adapter.adapter_type == AdapterType.LOOPBACK:
                continue
            
            ipv4_ok = self.PROXY_DNS_IPV4 in adapter.dns_config.ipv4_servers
            ipv6_ok = (
                not adapter.has_ipv6 or
                self.PROXY_DNS_IPV6 in adapter.dns_config.ipv6_servers
            )
            
            status[adapter.name] = {
                "has_ipv4": adapter.has_ipv4,
                "has_ipv6": adapter.has_ipv6,
                "ipv4_configured": ipv4_ok,
                "ipv6_configured": ipv6_ok,
                "current_ipv4_dns": adapter.dns_config.ipv4_servers,
                "current_ipv6_dns": adapter.dns_config.ipv6_servers,
                "is_default_route": adapter.is_default_route,
                "fully_configured": ipv4_ok and ipv6_ok,
            }
        
        return status
    
    def _log_result(self, result: EnforcementResult) -> None:
        """Log enforcement result summary."""
        if result.success:
            logger.info(
                f"DNS enforcement complete: "
                f"{result.adapters_configured} configured, "
                f"{result.adapters_skipped} skipped"
            )
        else:
            logger.warning(
                f"DNS enforcement had errors: "
                f"{result.adapters_configured} configured, "
                f"{len(result.errors)} errors"
            )
    
    def get_change_history(self) -> List[DNSChange]:
        """Get history of DNS changes."""
        return self._change_history.copy()
    
    def clear_change_history(self) -> None:
        """Clear change history."""
        self._change_history.clear()
    
    def get_stats(self) -> Dict:
        """Get enforcer statistics."""
        return {
            "mode": self._mode.value,
            "adapters_with_stored_dns": len(self._original_dns),
            "total_changes": len(self._change_history),
            "successful_changes": len([c for c in self._change_history if c.success]),
            "failed_changes": len([c for c in self._change_history if not c.success]),
        }


def check_dns_admin_required() -> Tuple[bool, str]:
    """
    Check if admin rights are required for DNS changes.
    
    Returns:
        Tuple of (is_admin, message)
    """
    import ctypes
    
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if is_admin:
            return True, "Running with administrator privileges"
        else:
            return False, "Administrator privileges required to change DNS settings"
    except:
        return False, "Could not determine admin status"
