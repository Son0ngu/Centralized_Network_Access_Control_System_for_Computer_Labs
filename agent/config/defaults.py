from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    # Server connection configuration
    "server": {
        "urls": [
            "https://firewall-controller.onrender.com",
            "http://localhost:5000"
        ],
        "url": "https://firewall-controller.onrender.com",
        "connect_timeout": 15,
        "read_timeout": 45,
        "retry_interval": 60,
        "max_retries": 5,
    },
    
    # Authentication configuration
    "auth": {
        "api_key": "",
        "auth_method": "none",
        "jwt_refresh_interval": 3600,
    },
    
    # Whitelist configuration
    "whitelist": {
        "auto_sync": True,
        "sync_on_startup": True,
        "update_interval": 60,
        "retry_interval": 30,
        "max_retries": 5,
        "timeout": 30,
    },
    
    # ==========================================================================
    # DNS PROXY CONFIGURATION (Phase 1 - Proactive DNS Control)
    # ==========================================================================
    "dns_proxy": {
        "enabled": True,
        "mode": "active",  # disabled | monitor | active | parallel
        
        # DNS Server settings
        "bind_address": "127.0.0.1",
        "port": 53,
        "ipv6_enabled": True,
        "ipv6_bind_address": "::1",
        
        # Upstream resolvers (fallback order)
        "upstream_resolvers": [
            {"address": "8.8.8.8", "port": 53, "priority": 1},
            {"address": "1.1.1.1", "port": 53, "priority": 2},
            {"address": "208.67.222.222", "port": 53, "priority": 3}
        ],
        "upstream_timeout": 5.0,
        "upstream_retries": 2,
        
        # DNS Cache settings
        "cache": {
            "enabled": True,
            "max_entries": 10000,
            "min_ttl": 60,
            "max_ttl": 86400,
            "negative_ttl": 300,  # TTL for blocked domains (NXDOMAIN)
        },
        
        # Firewall synchronization (add IP rules from DNS responses)
        "firewall_sync": {
            "enabled": True,
            "timeout": 5.0,
            "retry_on_failure": True,
            "grace_period": 60,  # Extra time before removing expired rules
        },
    },
    
    # ==========================================================================
    # NETWORK MANAGER CONFIGURATION (DNS Enforcement)
    # ==========================================================================
    "network_manager": {
        "enabled": True,
        "auto_configure_dns": True,  # Set system DNS to 127.0.0.1
        "monitor_interval": 30,      # Check for DNS drift every N seconds
        "backup_path": "dns_backup.json",
        
        # Adapter settings
        "adapters": {
            "include_virtual": False,
            "include_vpn": True,
            "exclude_patterns": ["VMware*", "VirtualBox*", "Hyper-V*"]
        },
    },
    
    # ==========================================================================
    # SECURITY CONFIGURATION (DoH/DoT Blocking)
    # ==========================================================================
    "security": {
        "enabled": True,
        "block_doh": True,   # Block DNS over HTTPS
        "block_dot": True,   # Block DNS over TLS (port 853)
        "doh_providers_update_url": None,  # Optional: URL to fetch DoH provider list
        
        # Bypass detection (monitor for attempts to bypass DNS Proxy)
        "bypass_detection": {
            "enabled": True,
            "alert_on_direct_ip": True,
            "alert_on_doh_attempt": True,
            "log_level": "WARNING",
        },
    },
    
    # ==========================================================================
    # PACKET SNIFFER CONFIGURATION (Bypass Detection Only)
    # ==========================================================================
    "packet_capture": {
        "enabled": False,  # Disabled by default (DNS Proxy handles everything)
        "mode": "bypass_detection_only",  # bypass_detection_only | full
        "engine": "scapy",
        "filter": "tcp and dst port 443",  # Only monitor HTTPS for bypass detection
        "buffer_size": 4096,
        "packet_limit": 0,
        "interfaces": [],
        "snaplen": 1500,
    },
    
    # Logging configuration
    "logging": {
        "level": "INFO",
        "file": "agent.log",
        "max_size": 10485760,  # 10MB
        "backup_count": 5,
        "log_to_console": True,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        
        "sender": {
            "enabled": True,
            "batch_size": 100,
            "max_queue_size": 1000,
            "send_interval": 2,
            "failures_before_warn": 3,
        }
    },
    
    # Heartbeat configuration
    "heartbeat": {
        "enabled": True,
        "interval": 20,
        "timeout": 10,
        "retry_interval": 5,
        "max_failures": 3
    },
    
    # General configuration
    "general": {
        "agent_name": "",
        "startup_delay": 0,
        "check_admin": True,
        "debug": False,
    }
}