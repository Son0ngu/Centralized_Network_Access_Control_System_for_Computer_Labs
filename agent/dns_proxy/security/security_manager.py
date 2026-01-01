"""
Security Manager
----------------
Central coordinator for all DNS proxy security components.

Integrates:
- EnhancedDoHBlocker: DoH/DoT provider blocking
- DNSFirewall: DNS outbound restrictions
- ProviderUpdater: Blocklist updates

Usage:
    manager = SecurityManager()
    manager.enable()  # Enable all security features
    manager.status()  # Get comprehensive status
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from pathlib import Path

from .doh_blocker_enhanced import (
    EnhancedDoHBlocker,
    DoHProviderEntry,
    DOH_PROVIDERS_DATABASE,
)
from .dns_firewall import DNSFirewall, DNSFirewallConfig
from .provider_updater import ProviderUpdater, UpdaterConfig

logger = logging.getLogger("dns_proxy.security.manager")


class SecurityLevel(Enum):
    """Security enforcement level."""
    DISABLED = "disabled"       # No security features
    MONITOR = "monitor"         # Log only, no enforcement
    STANDARD = "standard"       # Basic DoH blocking + DNS rules
    STRICT = "strict"           # Full blocking + auto-updates
    CUSTOM = "custom"           # User-defined configuration


@dataclass
class SecurityConfig:
    """Security manager configuration."""
    # General
    level: SecurityLevel = SecurityLevel.STANDARD
    
    # DoH Blocker
    block_doh_domains: bool = True
    block_doh_ips: bool = True
    block_dot_port: bool = True
    use_hosts_file: bool = True
    
    # DNS Firewall
    enforce_dns_rules: bool = True
    proxy_address: str = "127.0.0.1"
    proxy_port: int = 53
    upstream_resolvers: List[str] = field(default_factory=lambda: [
        "1.1.1.1", "8.8.8.8"
    ])
    block_bypass_ports: bool = True  # 5353, 5355, etc.
    
    # Provider Updates
    auto_update_providers: bool = True
    update_interval_hours: int = 24
    
    # Paths
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".dns_proxy" / "security")


@dataclass
class SecurityStatus:
    """Current security status."""
    enabled: bool = False
    level: SecurityLevel = SecurityLevel.DISABLED
    
    # Component status
    doh_blocker_active: bool = False
    doh_domains_blocked: int = 0
    doh_ips_blocked: int = 0
    
    dns_firewall_active: bool = False
    dns_rules_count: int = 0
    
    provider_updater_active: bool = False
    last_update: Optional[str] = None
    
    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SecurityManager:
    """
    Central coordinator for DNS proxy security.
    
    Features:
    - Unified security level configuration
    - Component lifecycle management
    - Status reporting
    - Error handling and recovery
    
    Example:
        manager = SecurityManager(SecurityConfig(
            level=SecurityLevel.STRICT,
            upstream_resolvers=["1.1.1.1"]
        ))
        
        # Enable security
        manager.enable()
        
        # Check status
        status = manager.get_status()
        print(f"DoH domains blocked: {status.doh_domains_blocked}")
        
        # Add custom upstream resolver
        manager.add_upstream_resolver("9.9.9.9")
        
        # Disable when done
        manager.disable()
    """
    
    def __init__(self, config: SecurityConfig = None):
        self._config = config or SecurityConfig()
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self._doh_blocker: Optional[EnhancedDoHBlocker] = None
        self._dns_firewall: Optional[DNSFirewall] = None
        self._provider_updater: Optional[ProviderUpdater] = None
        
        # State
        self._enabled = False
        self._errors: List[str] = []
        self._warnings: List[str] = []
        
        logger.info(f"Security Manager initialized (level: {self._config.level.value})")
    
    def enable(self) -> bool:
        """
        Enable security features based on configuration.
        
        Returns:
            True if all components enabled successfully
        """
        if self._enabled:
            logger.warning("Security already enabled")
            return True
        
        self._errors.clear()
        self._warnings.clear()
        
        success = True
        
        # Apply level-based defaults
        self._apply_level_defaults()
        
        if self._config.level == SecurityLevel.DISABLED:
            logger.info("Security level is DISABLED")
            return True
        
        if self._config.level == SecurityLevel.MONITOR:
            logger.info("Security in MONITOR mode - logging only")
            self._enabled = True
            return True
        
        # Initialize and enable components
        try:
            # 1. Provider Updater (if auto-update enabled)
            if self._config.auto_update_providers:
                success &= self._enable_provider_updater()
            
            # 2. DoH Blocker
            if self._config.block_doh_domains or self._config.block_doh_ips:
                success &= self._enable_doh_blocker()
            
            # 3. DNS Firewall
            if self._config.enforce_dns_rules:
                success &= self._enable_dns_firewall()
            
            self._enabled = success
            
            if success:
                logger.info("Security enabled successfully")
            else:
                logger.warning(f"Security enabled with errors: {self._errors}")
            
        except Exception as e:
            logger.error(f"Failed to enable security: {e}")
            self._errors.append(str(e))
            success = False
        
        return success
    
    def disable(self) -> bool:
        """
        Disable all security features.
        
        Returns:
            True if disabled successfully
        """
        if not self._enabled:
            return True
        
        success = True
        
        # Disable components in reverse order
        try:
            if self._dns_firewall:
                self._dns_firewall.remove_all_rules()
                self._dns_firewall = None
            
            if self._doh_blocker:
                self._doh_blocker.unblock_all()
                self._doh_blocker = None
            
            if self._provider_updater:
                self._provider_updater.stop_auto_update()
                self._provider_updater = None
            
            self._enabled = False
            logger.info("Security disabled")
            
        except Exception as e:
            logger.error(f"Error disabling security: {e}")
            self._errors.append(str(e))
            success = False
        
        return success
    
    def _apply_level_defaults(self) -> None:
        """Apply configuration defaults based on security level."""
        level = self._config.level
        
        if level == SecurityLevel.DISABLED:
            self._config.block_doh_domains = False
            self._config.block_doh_ips = False
            self._config.enforce_dns_rules = False
            self._config.auto_update_providers = False
            
        elif level == SecurityLevel.MONITOR:
            self._config.block_doh_domains = False
            self._config.block_doh_ips = False
            self._config.enforce_dns_rules = False
            
        elif level == SecurityLevel.STANDARD:
            self._config.block_doh_domains = True
            self._config.block_doh_ips = True
            self._config.enforce_dns_rules = True
            self._config.auto_update_providers = False
            
        elif level == SecurityLevel.STRICT:
            self._config.block_doh_domains = True
            self._config.block_doh_ips = True
            self._config.block_dot_port = True
            self._config.enforce_dns_rules = True
            self._config.block_bypass_ports = True
            self._config.auto_update_providers = True
    
    def _enable_provider_updater(self) -> bool:
        """Initialize and start provider updater."""
        try:
            updater_config = UpdaterConfig(
                cache_dir=self._config.cache_dir / "blocklists",
                update_interval_hours=self._config.update_interval_hours,
            )
            
            self._provider_updater = ProviderUpdater(
                config=updater_config,
                builtin_providers=list(DOH_PROVIDERS_DATABASE),
            )
            
            # Register update callback
            self._provider_updater.on_update(self._on_providers_updated)
            
            # Initial update
            results = self._provider_updater.update_all()
            
            # Start auto-update
            if self._config.auto_update_providers:
                self._provider_updater.start_auto_update()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable provider updater: {e}")
            self._errors.append(f"Provider Updater: {e}")
            return False
    
    def _enable_doh_blocker(self) -> bool:
        """Initialize and enable DoH blocker."""
        try:
            # Get providers
            providers = list(DOH_PROVIDERS_DATABASE)
            if self._provider_updater:
                providers = self._provider_updater.get_providers()
            
            self._doh_blocker = EnhancedDoHBlocker(providers=providers)
            
            # Apply blocking based on configuration
            if self._config.block_doh_ips:
                self._doh_blocker.block_by_firewall()
            
            if self._config.block_doh_domains and self._config.use_hosts_file:
                self._doh_blocker.block_by_hosts_file()
            
            if self._config.block_dot_port:
                self._doh_blocker.block_dot_port()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable DoH blocker: {e}")
            self._errors.append(f"DoH Blocker: {e}")
            return False
    
    def _enable_dns_firewall(self) -> bool:
        """Initialize and enable DNS firewall rules."""
        try:
            firewall_config = DNSFirewallConfig(
                proxy_address_ipv4=self._config.proxy_address,
                upstream_resolvers=self._config.upstream_resolvers.copy(),
            )
            
            self._dns_firewall = DNSFirewall(config=firewall_config)
            
            # Apply rules
            success = self._dns_firewall.apply_rules()
            
            if not success:
                self._warnings.append("Some DNS firewall rules may have failed")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable DNS firewall: {e}")
            self._errors.append(f"DNS Firewall: {e}")
            return False
    
    def _on_providers_updated(self, providers: List[DoHProviderEntry]) -> None:
        """Handle provider list updates."""
        logger.info(f"Providers updated: {len(providers)} entries")
        
        if self._doh_blocker and self._enabled:
            # Refresh blocking rules
            try:
                self._doh_blocker = EnhancedDoHBlocker(providers=providers)
                
                if self._config.block_doh_ips:
                    self._doh_blocker.block_by_firewall()
                
                if self._config.block_doh_domains:
                    self._doh_blocker.block_by_hosts_file()
                    
            except Exception as e:
                logger.error(f"Failed to refresh DoH blocker: {e}")
    
    def add_upstream_resolver(self, resolver: str) -> bool:
        """
        Add an upstream resolver to the allowed list.
        
        Args:
            resolver: IP address of the resolver
            
        Returns:
            True if added successfully
        """
        if resolver in self._config.upstream_resolvers:
            return True
        
        self._config.upstream_resolvers.append(resolver)
        
        if self._dns_firewall:
            try:
                self._dns_firewall.update_upstream_resolvers(
                    self._config.upstream_resolvers
                )
                return True
            except Exception as e:
                logger.error(f"Failed to add upstream resolver: {e}")
                return False
        
        return True
    
    def remove_upstream_resolver(self, resolver: str) -> bool:
        """
        Remove an upstream resolver from the allowed list.
        
        Args:
            resolver: IP address to remove
            
        Returns:
            True if removed successfully
        """
        if resolver not in self._config.upstream_resolvers:
            return True
        
        self._config.upstream_resolvers.remove(resolver)
        
        if self._dns_firewall:
            try:
                self._dns_firewall.update_upstream_resolvers(
                    self._config.upstream_resolvers
                )
                return True
            except Exception as e:
                logger.error(f"Failed to remove upstream resolver: {e}")
                return False
        
        return True
    
    def get_status(self) -> SecurityStatus:
        """
        Get comprehensive security status.
        
        Returns:
            SecurityStatus with all component details
        """
        status = SecurityStatus(
            enabled=self._enabled,
            level=self._config.level,
            errors=self._errors.copy(),
            warnings=self._warnings.copy(),
        )
        
        if self._doh_blocker:
            status.doh_blocker_active = True
            stats = self._doh_blocker.get_stats()
            status.doh_domains_blocked = stats.get("total_domains", 0)
            status.doh_ips_blocked = stats.get("total_ipv4", 0) + stats.get("total_ipv6", 0)
        
        if self._dns_firewall:
            status.dns_firewall_active = True
            fw_status = self._dns_firewall.get_status()
            status.dns_rules_count = fw_status.get("total_rules", 0)
        
        if self._provider_updater:
            status.provider_updater_active = True
            updater_stats = self._provider_updater.get_stats()
            status.last_update = updater_stats.get("last_update")
        
        return status
    
    def get_blocked_domains(self) -> Set[str]:
        """Get all blocked DoH domains."""
        if self._doh_blocker:
            return self._doh_blocker.get_all_domains()
        return set()
    
    def get_blocked_ips(self) -> Set[str]:
        """Get all blocked DoH IPs."""
        if self._doh_blocker:
            return self._doh_blocker.get_all_ipv4() | self._doh_blocker.get_all_ipv6()
        return set()
    
    def get_allowed_dns_destinations(self) -> List[str]:
        """Get list of allowed DNS destinations."""
        allowed = [f"{self._config.proxy_address}:{self._config.proxy_port}"]
        allowed.extend(self._config.upstream_resolvers)
        return allowed
    
    def force_update_providers(self) -> bool:
        """Force an immediate provider list update."""
        if self._provider_updater:
            try:
                results = self._provider_updater.update_all()
                return all(r.success for r in results)
            except Exception as e:
                logger.error(f"Force update failed: {e}")
                return False
        return False
    
    def export_configuration(self) -> Dict:
        """Export current configuration as dictionary."""
        return {
            "level": self._config.level.value,
            "block_doh_domains": self._config.block_doh_domains,
            "block_doh_ips": self._config.block_doh_ips,
            "block_dot_port": self._config.block_dot_port,
            "enforce_dns_rules": self._config.enforce_dns_rules,
            "proxy_address": self._config.proxy_address,
            "proxy_port": self._config.proxy_port,
            "upstream_resolvers": self._config.upstream_resolvers,
            "auto_update_providers": self._config.auto_update_providers,
            "update_interval_hours": self._config.update_interval_hours,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SecurityManager":
        """Create SecurityManager from configuration dictionary."""
        config = SecurityConfig(
            level=SecurityLevel(data.get("level", "standard")),
            block_doh_domains=data.get("block_doh_domains", True),
            block_doh_ips=data.get("block_doh_ips", True),
            block_dot_port=data.get("block_dot_port", True),
            enforce_dns_rules=data.get("enforce_dns_rules", True),
            proxy_address=data.get("proxy_address", "127.0.0.1"),
            proxy_port=data.get("proxy_port", 53),
            upstream_resolvers=data.get("upstream_resolvers", ["1.1.1.1", "8.8.8.8"]),
            auto_update_providers=data.get("auto_update_providers", True),
            update_interval_hours=data.get("update_interval_hours", 24),
        )
        return cls(config=config)
