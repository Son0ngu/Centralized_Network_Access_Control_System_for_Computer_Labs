"""
DNS Proxy Security Module
-------------------------
Enhanced security features for the DNS Proxy system.

Components:
- EnhancedDoHBlocker: Comprehensive DoH/DoT blocking
- DNSFirewall: DNS outbound traffic restrictions
- ProviderUpdater: Remote blocklist updates
- SecurityManager: Central coordinator

Usage:
    from dns_proxy.security import SecurityManager, SecurityLevel
    
    # Quick start with STRICT security
    manager = SecurityManager.from_dict({
        "level": "strict",
        "upstream_resolvers": ["1.1.1.1"]
    })
    manager.enable()
    
    # Get status
    status = manager.get_status()
    print(f"DoH domains blocked: {status.doh_domains_blocked}")
"""

# Enhanced DoH/DoT Blocker
from .doh_blocker_enhanced import (
    EnhancedDoHBlocker,
    DoHProviderEntry,
    DOH_PROVIDERS_DATABASE,
)

# DNS Firewall Rules
from .dns_firewall import (
    DNSFirewall,
    DNSFirewallConfig,
)

# Provider Updates
from .provider_updater import (
    ProviderUpdater,
    UpdaterConfig,
    RemoteSource,
    UpdateResult,
)

# Security Manager
from .security_manager import (
    SecurityManager,
    SecurityConfig,
    SecurityLevel,
    SecurityStatus,
)

__all__ = [
    # DoH Blocker
    "EnhancedDoHBlocker",
    "DoHProviderEntry",
    "DOH_PROVIDERS_DATABASE",
    
    # DNS Firewall
    "DNSFirewall",
    "DNSFirewallConfig",
    
    # Provider Updater
    "ProviderUpdater",
    "UpdaterConfig",
    "RemoteSource",
    "UpdateResult",
    
    # Security Manager
    "SecurityManager",
    "SecurityConfig",
    "SecurityLevel",
    "SecurityStatus",
]
