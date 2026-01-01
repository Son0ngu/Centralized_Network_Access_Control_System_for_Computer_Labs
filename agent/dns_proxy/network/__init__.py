"""
Network Configuration Module
-----------------------------
Manages network adapter DNS configuration for DNS Proxy.

Features:
- Network adapter detection with IPv4/IPv6 support
- DNS enforcement (127.0.0.1 / ::1)
- DoH/DoT blocking
- DNS drift monitoring and auto-restore
- Monitor (read-only) mode for testing

Usage:
    from dns_proxy.network import NetworkManager, NetworkMode
    
    # Create manager in monitor mode (safe)
    manager = NetworkManager()
    
    # Analyze what would change
    report = manager.analyze()
    print(f"Changes needed: {report.total_changes}")
    
    # If safe, apply changes
    if report.safe_to_apply:
        manager.set_mode(NetworkMode.ACTIVE)
        manager.apply()
    
    # Later, rollback if needed
    manager.rollback()
"""

from .adapter_config import (
    AdapterType,
    AdapterStatus,
    DNSConfig,
    NetworkAdapter,
    AdapterPriority,
    NetworkAdapterManager,
)

from .dns_enforcer import (
    EnforcementMode,
    DNSChange,
    EnforcementResult,
    DNSEnforcer,
    check_dns_admin_required,
)

from .doh_blocker import (
    DoHProvider,
    DOH_PROVIDERS,
    BlockRule,
    BlockerResult,
    DoHBlocker,
)

from .drift_monitor import (
    DriftAction,
    DriftEvent,
    MonitorConfig,
    DNSDriftMonitor,
)

from .network_manager import (
    NetworkMode,
    NetworkConfig,
    NetworkStatus,
    MonitorReport,
    NetworkManager,
)


__all__ = [
    # Adapter config
    "AdapterType",
    "AdapterStatus",
    "DNSConfig",
    "NetworkAdapter",
    "AdapterPriority",
    "NetworkAdapterManager",
    
    # DNS enforcer
    "EnforcementMode",
    "DNSChange",
    "EnforcementResult",
    "DNSEnforcer",
    "check_dns_admin_required",
    
    # DoH blocker
    "DoHProvider",
    "DOH_PROVIDERS",
    "BlockRule",
    "BlockerResult",
    "DoHBlocker",
    
    # Drift monitor
    "DriftAction",
    "DriftEvent",
    "MonitorConfig",
    "DNSDriftMonitor",
    
    # Network manager
    "NetworkMode",
    "NetworkConfig",
    "NetworkStatus",
    "MonitorReport",
    "NetworkManager",
]


__version__ = "1.0.0"
