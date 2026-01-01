"""
DNS Proxy Integration Module
----------------------------
Central orchestrator integrating all DNS Proxy components.

Components Managed:
- DNS Proxy Server (UDP/TCP listener)
- Network Manager (adapter DNS configuration)
- Security Manager (DoH/DoT blocking)

Note: startup.py, status.py, and migration.py were removed as they were
only used in tests. Lifecycle.py handles startup/shutdown in production.

Usage:
    from dns_proxy.integration import DNSProxyOrchestrator
    
    orchestrator = DNSProxyOrchestrator()
    orchestrator.start()
    
    # ... application running ...
    
    orchestrator.stop()
"""

from .dns_proxy_agent import (
    DNSProxyOrchestrator,
    OrchestratorConfig,
    OrchestratorMode,
    ComponentStatus,
)

__all__ = [
    # Orchestrator (only component actually used in production)
    "DNSProxyOrchestrator",
    "OrchestratorConfig",
    "OrchestratorMode",
    "ComponentStatus",
]
