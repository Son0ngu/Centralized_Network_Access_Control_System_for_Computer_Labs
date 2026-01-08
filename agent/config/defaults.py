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
        "auto_sync_firewall": True,
        "resolve_ips_on_startup": True,
        "ip_cache_ttl": 300,
        "ip_refresh_interval": 300,
    },
    
    # Firewall configuration
    "firewall": {
        "enabled": False,
        "mode": "monitor",  # monitor, blacklist, whitelist_only
        "default_policy": "allow",
        "backup": {
            "enabled": True,
            "path": "profiles/backup.wfw",
            "restore_on_startup": False
        }
    },
    
    # Packet Capture configuration
    "capture": {
        "engine": "scapy",
        "filter": "outbound and (tcp.DstPort == 80 or tcp.DstPort == 443)",
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
    
    # Firewall configuration
    "firewall": {
        "enabled": True,
        "mode": "whitelist_only",
        "rule_prefix": "FirewallController",
        "cleanup_on_exit": True,
        "create_allow_rules": True,
        "create_default_block": True,
        "allow_essential_ips": True,
        "allow_private_networks": False,
        "rule_priority_offset": 100,
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