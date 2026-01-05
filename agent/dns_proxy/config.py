"""
DNS Proxy Configuration
-----------------------
Configuration schema and defaults for the DNS Proxy module.
Includes timeout settings, TTL management, and upstream resolver config.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("dns_proxy.config")


@dataclass
class UpstreamResolverConfig:
    """Configuration for a single upstream DNS resolver."""
    address: str
    port: int = 53
    priority: int = 1
    enabled: bool = True


@dataclass
class CacheConfig:
    """DNS Cache configuration with TTL management."""
    enabled: bool = True
    max_entries: int = 10000
    
    # TTL settings (seconds)
    min_ttl: int = 60           # Minimum TTL to prevent too-frequent rule removal
    max_ttl: int = 86400        # Maximum TTL (1 day)
    negative_ttl: int = 300     # TTL for NXDOMAIN/blocked responses
    
    # Cleanup interval
    cleanup_interval: int = 60  # How often to clean expired entries


@dataclass
class FirewallSyncConfig:
    """Firewall synchronization configuration."""
    # Enable/disable firewall sync (DNS-only mode when False)
    enabled: bool = True
    # Timeout for adding firewall rule before returning DNS response
    # CRITICAL: This prevents hanging queries if firewall fails
    timeout: float = 3.0        # 2-5 seconds recommended
    
    # Retry settings
    retry_on_failure: bool = True
    max_retries: int = 2
    retry_delay: float = 0.5
    
    # Grace period before removing expired rules (extra buffer)
    grace_period: int = 60      # Additional seconds after TTL expires
    
    # Batch operations
    batch_add_enabled: bool = True
    batch_size: int = 50
    
    # Firewall requirement mode
    # If False: Allow DNS resolution even without firewall manager (Phase 1 DNS-only)
    # If True: Require firewall manager - fail if not available (strict mode)
    require_firewall: bool = False


@dataclass  
class DNSServerConfig:
    """DNS Server listener configuration (IPv4 only)."""
    bind_address: str = "127.0.0.1"
    port: int = 53
    
    # Threading
    max_workers: int = 20
    
    # Query handling
    query_timeout: float = 10.0  # Max time for entire query processing
    
    # UDP/TCP settings
    enable_tcp: bool = True  # Enable TCP DNS (in addition to UDP)
    udp_buffer_size: int = 4096
    tcp_timeout: float = 30.0
    tcp_backlog: int = 10  # TCP listen backlog
    
    # Property aliases for compatibility with server.py
    @property
    def listen_ip(self) -> str:
        """Alias for bind_address (used by server.py)."""
        return self.bind_address
    
    @property
    def buffer_size(self) -> int:
        """Alias for udp_buffer_size (used by server.py)."""
        return self.udp_buffer_size


@dataclass
class DNSProxyConfig:
    """Main DNS Proxy configuration."""
    enabled: bool = True
    
    # Sub-configurations
    server: DNSServerConfig = field(default_factory=DNSServerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    firewall_sync: FirewallSyncConfig = field(default_factory=FirewallSyncConfig)
    
    # Upstream resolvers
    upstream_resolvers: List[UpstreamResolverConfig] = field(default_factory=lambda: [
        UpstreamResolverConfig(address="8.8.8.8", port=53, priority=1),
        UpstreamResolverConfig(address="1.1.1.1", port=53, priority=2),
        UpstreamResolverConfig(address="208.67.222.222", port=53, priority=3),
    ])
    
    # Upstream settings
    upstream_timeout: float = 8.0  # Increased for reliability
    upstream_retries: int = 3  # More retries for better reliability
    
    # Logging
    log_queries: bool = True
    log_blocked: bool = True
    
    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'DNSProxyConfig':
        """Create config from dictionary (typically from agent_config.json)."""
        dns_config = config_dict.get("dns_proxy", {})
        
        if not dns_config:
            logger.info("No dns_proxy config found, using defaults")
            return cls()
        
        # Parse server config (IPv4 only)
        server_dict = dns_config.get("server", {})
        server_config = DNSServerConfig(
            bind_address=server_dict.get("bind_address", "127.0.0.1"),
            port=server_dict.get("port", 53),
            max_workers=server_dict.get("max_workers", 20),
            query_timeout=server_dict.get("query_timeout", 10.0),
            udp_buffer_size=server_dict.get("udp_buffer_size", 4096),
            tcp_timeout=server_dict.get("tcp_timeout", 30.0),
        )
        
        # Parse cache config
        cache_dict = dns_config.get("cache", {})
        cache_config = CacheConfig(
            enabled=cache_dict.get("enabled", True),
            max_entries=cache_dict.get("max_entries", 10000),
            min_ttl=cache_dict.get("min_ttl", 60),
            max_ttl=cache_dict.get("max_ttl", 86400),
            negative_ttl=cache_dict.get("negative_ttl", 300),
            cleanup_interval=cache_dict.get("cleanup_interval", 60),
        )
        
        # Parse firewall sync config
        fw_dict = dns_config.get("firewall_sync", {})
        firewall_config = FirewallSyncConfig(
            enabled=fw_dict.get("enabled", True),
            timeout=fw_dict.get("timeout", 3.0),
            retry_on_failure=fw_dict.get("retry_on_failure", True),
            max_retries=fw_dict.get("max_retries", 2),
            retry_delay=fw_dict.get("retry_delay", 0.5),
            grace_period=fw_dict.get("grace_period", 60),
            batch_add_enabled=fw_dict.get("batch_add_enabled", True),
            batch_size=fw_dict.get("batch_size", 50),
        )
        
        # Parse upstream resolvers
        upstream_list = dns_config.get("upstream_resolvers", [])
        resolvers = []
        for r in upstream_list:
            if isinstance(r, dict):
                resolvers.append(UpstreamResolverConfig(
                    address=r.get("address", "8.8.8.8"),
                    port=r.get("port", 53),
                    priority=r.get("priority", 1),
                    enabled=r.get("enabled", True),
                ))
            elif isinstance(r, str):
                resolvers.append(UpstreamResolverConfig(address=r))
        
        if not resolvers:
            resolvers = [
                UpstreamResolverConfig(address="8.8.8.8", port=53, priority=1),
                UpstreamResolverConfig(address="1.1.1.1", port=53, priority=2),
            ]
        
        return cls(
            enabled=dns_config.get("enabled", True),
            server=server_config,
            cache=cache_config,
            firewall_sync=firewall_config,
            upstream_resolvers=resolvers,
            upstream_timeout=dns_config.get("upstream_timeout", 8.0),
            upstream_retries=dns_config.get("upstream_retries", 3),
            log_queries=dns_config.get("log_queries", True),
            log_blocked=dns_config.get("log_blocked", True),
        )
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "server": {
                "bind_address": self.server.bind_address,
                "port": self.server.port,
                "max_workers": self.server.max_workers,
                "query_timeout": self.server.query_timeout,
            },
            "cache": {
                "enabled": self.cache.enabled,
                "max_entries": self.cache.max_entries,
                "min_ttl": self.cache.min_ttl,
                "max_ttl": self.cache.max_ttl,
                "negative_ttl": self.cache.negative_ttl,
            },
            "firewall_sync": {
                "enabled": self.firewall_sync.enabled,
                "timeout": self.firewall_sync.timeout,
                "retry_on_failure": self.firewall_sync.retry_on_failure,
                "max_retries": self.firewall_sync.max_retries,
                "retry_delay": self.firewall_sync.retry_delay,
                "grace_period": self.firewall_sync.grace_period,
            },
            "upstream_resolvers": [
                {"address": r.address, "port": r.port, "priority": r.priority}
                for r in self.upstream_resolvers
            ],
            "upstream_timeout": self.upstream_timeout,
            "upstream_retries": self.upstream_retries,
        }


# Default configuration instance
DEFAULT_DNS_PROXY_CONFIG = DNSProxyConfig()
