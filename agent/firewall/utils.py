import ipaddress
import logging
import socket
import subprocess
from typing import Set

from agent.utils.ip_detector import check_admin_privileges, get_local_ip

logger = logging.getLogger("firewall.utils")


class FirewallUtils:

    @staticmethod
    def is_valid_ipv4(ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            return isinstance(addr, ipaddress.IPv4Address)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def get_essential_ips() -> Set[str]:
        essential: Set[str] = set()
        
        # Localhost
        essential.update(["127.0.0.1", "::1"])
        
        # Common DNS servers
        essential.update([
            # Google
            "8.8.8.8", "8.8.4.4",
            "2001:4860:4860::8888", "2001:4860:4860::8844",
            # Cloudflare
            "1.1.1.1", "1.0.0.1",
            "2606:4700:4700::1111", "2606:4700:4700::1001",
            # OpenDNS
            "208.67.222.222", "208.67.220.220",
            "2620:119:35::35", "2620:119:53::53",
            # Quad9
            "9.9.9.9", "149.112.112.112",
            "2620:fe::fe", "2620:fe::9"
        ])
        
        # Try to detect local IPv4 via shared IPDetector
        try:
            local_ip = get_local_ip()
            if local_ip:
                essential.add(local_ip)
                if '.' in local_ip:
                    gateway_ip = '.'.join(local_ip.split('.')[:-1]) + '.1'
                    essential.add(gateway_ip)
                    logger.debug(f"Detected local IPv4 network: {local_ip}, gateway: {gateway_ip}")
        except Exception as e:
            logger.debug(f"Could not detect local IPv4 network: {e}")
        
        # Try to detect local IPv6 address
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s6:
                s6.connect(("2001:4860:4860::8888", 80))
                local_ip6 = s6.getsockname()[0]
                essential.add(local_ip6)
                logger.debug(f"Detected local IPv6 address: {local_ip6}")
        except Exception as e:
            logger.debug(f"Could not detect local IPv6 network: {e}")
        
        return essential
    
    @staticmethod
    def has_admin_privileges() -> bool:
        """Check if the application is running with administrator privileges."""
        try:
            return check_admin_privileges()
        except Exception as e:
            logger.error(f"Error checking admin privileges: {e}")
            return False
    
    @staticmethod
    def run_netsh_command(args: list, timeout: int = 30) -> subprocess.CompletedProcess:
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
        if ports is None:
            ports = [80, 443, 53]
        
        try:
            addr = ipaddress.ip_address(ip)
            family = socket.AF_INET6 if isinstance(addr, ipaddress.IPv6Address) else socket.AF_INET
        except ValueError:
            logger.debug(f"Connectivity test skipped - invalid IP: {ip}")
            return False
        
        try:
            for port in ports:
                try:
                    with socket.socket(family, socket.SOCK_STREAM) as sock:
                        sock.settimeout(timeout)
                        if family == socket.AF_INET6:
                            result = sock.connect_ex((ip, port, 0, 0))
                        else:
                            result = sock.connect_ex((ip, port))
                        if result == 0:
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.debug(f"Connectivity test failed for {ip}: {e}")
            return False