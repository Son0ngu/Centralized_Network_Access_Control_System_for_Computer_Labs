"""
Firewall Utilities - Helper functions and validation.
Vietnam ONLY - Clean implementation.
"""

import ipaddress
import logging
import socket
import subprocess
from typing import Set

logger = logging.getLogger("firewall.utils")


class FirewallUtils:
    """Utility functions for firewall operations."""
    
    @staticmethod
    def is_valid_ipv4(ip: str) -> bool:
        """Check if string is a valid IPv4 address."""
        try:
            addr = ipaddress.ip_address(ip)
            return isinstance(addr, ipaddress.IPv4Address)
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Check if string is a valid IP address (IPv4 or IPv6)."""
        try:
            ipaddress.ip_address(ip)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def get_essential_ips() -> Set[str]:
        """Get essential IPs - IPv4 only for firewall compatibility."""
        essential = set()
        
        # IPv4 localhost
        essential.add("127.0.0.1")
        
        # Common DNS servers (IPv4 only)
        essential.update([
            "8.8.8.8", "8.8.4.4",              # Google DNS
            "1.1.1.1", "1.0.0.1",              # Cloudflare DNS
            "208.67.222.222", "208.67.220.220", # OpenDNS
            "9.9.9.9", "149.112.112.112"       # Quad9 DNS
        ])
        
        # Try to detect local network
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                essential.add(local_ip)
                
                # Add gateway
                gateway_ip = '.'.join(local_ip.split('.')[:-1]) + '.1'
                essential.add(gateway_ip)
                
                logger.debug(f"Detected local network: {local_ip}, gateway: {gateway_ip}")
        except Exception as e:
            logger.debug(f"Could not detect local network: {e}")
        
        return essential
    
    @staticmethod
    def has_admin_privileges() -> bool:
        """Check if the application is running with administrator privileges."""
        try:
            command = ["netsh", "advfirewall", "show", "currentprofile"]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error checking admin privileges: {e}")
            return False
    
    @staticmethod
    def run_netsh_command(args: list, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run netsh command with standard settings."""
        command = ["netsh"] + args
        
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    
    @staticmethod
    def test_ip_connectivity(ip: str, ports: list = None, timeout: int = 3) -> bool:
        """Test connectivity to an IP address."""
        if ports is None:
            ports = [80, 443, 53]
        
        try:
            for port in ports:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(timeout)
                        result = sock.connect_ex((ip, port))
                        if result == 0:
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.debug(f"Connectivity test failed for {ip}: {e}")
            return False