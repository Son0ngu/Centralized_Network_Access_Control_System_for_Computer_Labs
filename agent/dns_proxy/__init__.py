"""
DNS Proxy Module
----------------
Proactive DNS Proxy/Sinkhole for whitelist-based firewall control.

Key Features:
- DNS Proxy on 127.0.0.1:53
- Whitelist check BEFORE forwarding
- Firewall rules added BEFORE returning DNS response
- TTL-based rule management with min-TTL enforcement
- Negative caching for blocked domains

Architecture:
    Client → DNS Proxy → Whitelist Check → Upstream DNS → Firewall Sync → Response
                            ↓
                       [Blocked] → NXDOMAIN

Usage:
    from dns_proxy import DNSProxyServer, DNSProxyConfig
    
    config = DNSProxyConfig()
    server = DNSProxyServer(config)
    
    # Connect to whitelist
    server.query_handler.set_whitelist_state(whitelist_state)
    
    # Start serving
    server.start()
    
    # ... 
    
    server.stop()
"""

from .config import (
    DNSProxyConfig,
    CacheConfig,
    FirewallSyncConfig,
    DNSServerConfig,
    UpstreamResolverConfig,
)

from .cache import (
    DNSCache,
    DNSCacheEntry,
)

from .resolver import (
    UpstreamResolver,
    DNSResult,
    ResolverHealth,
)

from .firewall_sync import (
    FirewallDNSSync,
    FirewallRule,
    SyncResult,
)

from .handler import (
    DNSQueryHandler,
    QueryResult,
)

from .server import (
    DNSProxyServer,
    check_admin_rights,
    check_port_available,
)

# Network configuration module
from .network import (
    NetworkManager,
    NetworkMode,
    NetworkConfig,
    NetworkStatus,
    MonitorReport,
    NetworkAdapterManager,
    DNSEnforcer,
    EnforcementMode,
    DoHBlocker,
    DNSDriftMonitor,
    DriftAction,
)

# Security module - Enhanced DoH/DoT blocking
from .security import (
    SecurityManager,
    SecurityConfig,
    SecurityLevel,
    SecurityStatus,
    EnhancedDoHBlocker,
    DoHProviderEntry,
    DNSFirewall,
    DNSFirewallConfig,
    ProviderUpdater,
    UpdaterConfig,
)

# Integration module - Orchestration only (startup/status/migration removed)
from .integration import (
    DNSProxyOrchestrator,
    OrchestratorConfig,
    OrchestratorMode,
    ComponentStatus,
)


__all__ = [
    # Config
    "DNSProxyConfig",
    "CacheConfig", 
    "FirewallSyncConfig",
    "DNSServerConfig",
    "UpstreamResolverConfig",
    
    # Cache
    "DNSCache",
    "DNSCacheEntry",
    
    # Resolver
    "UpstreamResolver",
    "DNSResult",
    "ResolverHealth",
    
    # Firewall Sync
    "FirewallDNSSync",
    "FirewallRule",
    "SyncResult",
    
    # Handler
    "DNSQueryHandler",
    "QueryResult",
    
    # Server
    "DNSProxyServer",
    "check_admin_rights",
    "check_port_available",
    
    # Network
    "NetworkManager",
    "NetworkMode",
    "NetworkConfig",
    "NetworkStatus",
    "MonitorReport",
    "NetworkAdapterManager",
    "DNSEnforcer",
    "EnforcementMode",
    "DoHBlocker",
    "DNSDriftMonitor",
    "DriftAction",
    
    # Security
    "SecurityManager",
    "SecurityConfig",
    "SecurityLevel",
    "SecurityStatus",
    "EnhancedDoHBlocker",
    "DoHProviderEntry",
    "DNSFirewall",
    "DNSFirewallConfig",
    "ProviderUpdater",
    "UpdaterConfig",
    
    # Integration (only orchestrator - other modules removed)
    "DNSProxyOrchestrator",
    "OrchestratorConfig",
    "OrchestratorMode",
    "ComponentStatus",
]


__version__ = "1.0.0"
