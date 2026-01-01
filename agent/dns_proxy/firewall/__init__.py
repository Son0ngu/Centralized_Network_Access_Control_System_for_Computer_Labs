"""
DNS Proxy Firewall Module
-------------------------
Basic firewall synchronization (enhanced modules removed - not used).

Note: firewall_sync_enhanced.py, profile_rules.py, and ttl_manager.py
were removed as they were only used in tests and not in production code.
The basic FirewallDNSSync in dns_proxy.firewall_sync is sufficient.
"""

# This module now only re-exports from parent for backward compatibility
# Actual firewall sync is in dns_proxy.firewall_sync

__all__ = []