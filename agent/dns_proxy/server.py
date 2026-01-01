"""
DNS Proxy Server
-----------------
UDP/TCP DNS server listening on 127.0.0.1:53.
Receives DNS queries and delegates to DNSQueryHandler.
"""

import logging
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Tuple

from .config import DNSProxyConfig, DNSServerConfig
from .handler import DNSQueryHandler

logger = logging.getLogger("dns_proxy.server")


@dataclass
class ServerStats:
    """Server statistics."""
    udp_queries: int = 0
    tcp_queries: int = 0
    udp_errors: int = 0
    tcp_errors: int = 0
    active_connections: int = 0


class UDPHandler:
    """
    UDP DNS handler.
    Handles DNS queries over UDP (standard DNS).
    """
    
    def __init__(
        self,
        config: DNSServerConfig,
        query_handler: DNSQueryHandler,
        stats: ServerStats
    ):
        self.config = config
        self.query_handler = query_handler
        self.stats = stats
        
        self._socket: Optional[socket.socket] = None
        self._socket_v6: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_v6: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(
            max_workers=config.max_workers,
            thread_name_prefix="dns_udp"
        )
    
    def start(self) -> None:
        """Start UDP handler."""
        self._running = True
        
        # IPv4 socket
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.config.listen_ip, self.config.port))
            self._socket.settimeout(1.0)  # For graceful shutdown
            
            self._thread = threading.Thread(
                target=self._listen_loop,
                args=(self._socket, "IPv4"),
                name="dns_udp_ipv4"
            )
            self._thread.daemon = True
            self._thread.start()
            
            logger.info(f"UDP DNS listening on {self.config.listen_ip}:{self.config.port}")
        except Exception as e:
            logger.error(f"Failed to start UDP IPv4 server: {e}")
            raise
        
        # IPv6 socket (optional)
        if self.config.ipv6_listen_ip:
            try:
                self._socket_v6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                self._socket_v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Only bind to IPv6, not dual-stack
                self._socket_v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                self._socket_v6.bind((self.config.ipv6_listen_ip, self.config.port))
                self._socket_v6.settimeout(1.0)
                
                self._thread_v6 = threading.Thread(
                    target=self._listen_loop,
                    args=(self._socket_v6, "IPv6"),
                    name="dns_udp_ipv6"
                )
                self._thread_v6.daemon = True
                self._thread_v6.start()
                
                logger.info(f"UDP DNS listening on [{self.config.ipv6_listen_ip}]:{self.config.port}")
            except Exception as e:
                logger.warning(f"Failed to start UDP IPv6 server (non-fatal): {e}")
    
    def _listen_loop(self, sock: socket.socket, version: str) -> None:
        """Main UDP listen loop."""
        logger.debug(f"UDP {version} listen loop started")
        
        while self._running:
            try:
                # Receive query
                data, addr = sock.recvfrom(self.config.buffer_size)
                
                # Submit to thread pool
                self._executor.submit(self._handle_query, sock, data, addr)
                
            except socket.timeout:
                continue
            except OSError as e:
                if self._running:
                    logger.error(f"UDP {version} socket error: {e}")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"UDP {version} error: {e}", exc_info=True)
    
    def _handle_query(
        self,
        sock: socket.socket,
        query_data: bytes,
        client_addr: Tuple[str, int]
    ) -> None:
        """Handle single UDP query."""
        try:
            self.stats.udp_queries += 1
            
            result = self.query_handler.handle_query(query_data)
            
            if result.response_data:
                sock.sendto(result.response_data, client_addr)
                
        except Exception as e:
            self.stats.udp_errors += 1
            logger.error(f"Error handling UDP query from {client_addr}: {e}")
    
    def stop(self) -> None:
        """Stop UDP handler."""
        self._running = False
        
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
        
        if self._socket_v6:
            try:
                self._socket_v6.close()
            except:
                pass
        
        # Fast shutdown - don't wait for pending queries
        self._executor.shutdown(wait=False, cancel_futures=True)
        
        logger.info("UDP DNS server stopped")


class TCPHandler:
    """
    TCP DNS handler.
    Handles DNS queries over TCP (for large responses).
    """
    
    def __init__(
        self,
        config: DNSServerConfig,
        query_handler: DNSQueryHandler,
        stats: ServerStats
    ):
        self.config = config
        self.query_handler = query_handler
        self.stats = stats
        
        self._socket: Optional[socket.socket] = None
        self._socket_v6: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_v6: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(
            max_workers=config.max_workers,
            thread_name_prefix="dns_tcp"
        )
    
    def start(self) -> None:
        """Start TCP handler."""
        self._running = True
        
        # IPv4 socket
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.config.listen_ip, self.config.port))
            self._socket.listen(self.config.tcp_backlog)
            self._socket.settimeout(1.0)
            
            self._thread = threading.Thread(
                target=self._accept_loop,
                args=(self._socket, "IPv4"),
                name="dns_tcp_ipv4"
            )
            self._thread.daemon = True
            self._thread.start()
            
            logger.info(f"TCP DNS listening on {self.config.listen_ip}:{self.config.port}")
        except Exception as e:
            logger.error(f"Failed to start TCP IPv4 server: {e}")
            raise
        
        # IPv6 socket (optional)
        if self.config.ipv6_listen_ip:
            try:
                self._socket_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                self._socket_v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket_v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                self._socket_v6.bind((self.config.ipv6_listen_ip, self.config.port))
                self._socket_v6.listen(self.config.tcp_backlog)
                self._socket_v6.settimeout(1.0)
                
                self._thread_v6 = threading.Thread(
                    target=self._accept_loop,
                    args=(self._socket_v6, "IPv6"),
                    name="dns_tcp_ipv6"
                )
                self._thread_v6.daemon = True
                self._thread_v6.start()
                
                logger.info(f"TCP DNS listening on [{self.config.ipv6_listen_ip}]:{self.config.port}")
            except Exception as e:
                logger.warning(f"Failed to start TCP IPv6 server (non-fatal): {e}")
    
    def _accept_loop(self, sock: socket.socket, version: str) -> None:
        """Accept incoming TCP connections."""
        logger.debug(f"TCP {version} accept loop started")
        
        while self._running:
            try:
                conn, addr = sock.accept()
                self.stats.active_connections += 1
                self._executor.submit(self._handle_connection, conn, addr)
                
            except socket.timeout:
                continue
            except OSError as e:
                if self._running:
                    logger.error(f"TCP {version} accept error: {e}")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"TCP {version} error: {e}", exc_info=True)
    
    def _handle_connection(
        self,
        conn: socket.socket,
        client_addr: Tuple[str, int]
    ) -> None:
        """Handle TCP connection."""
        try:
            conn.settimeout(self.config.connection_timeout)
            
            while self._running:
                # TCP DNS has 2-byte length prefix
                length_data = self._recv_exact(conn, 2)
                if not length_data:
                    break
                
                query_length = struct.unpack("!H", length_data)[0]
                
                if query_length > self.config.buffer_size:
                    logger.warning(f"TCP query too large from {client_addr}: {query_length}")
                    break
                
                query_data = self._recv_exact(conn, query_length)
                if not query_data:
                    break
                
                self.stats.tcp_queries += 1
                
                # Handle query
                result = self.query_handler.handle_query(query_data)
                
                if result.response_data:
                    # Send response with length prefix
                    response_length = struct.pack("!H", len(result.response_data))
                    conn.sendall(response_length + result.response_data)
                    
        except socket.timeout:
            pass
        except Exception as e:
            self.stats.tcp_errors += 1
            logger.debug(f"TCP connection error from {client_addr}: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
            self.stats.active_connections -= 1
    
    def _recv_exact(self, conn: socket.socket, n: int) -> Optional[bytes]:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def stop(self) -> None:
        """Stop TCP handler."""
        self._running = False
        
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
        
        if self._socket_v6:
            try:
                self._socket_v6.close()
            except:
                pass
        
        # Fast shutdown - don't wait for pending queries
        self._executor.shutdown(wait=False, cancel_futures=True)
        
        logger.info("TCP DNS server stopped")


class DNSProxyServer:
    """
    Main DNS Proxy Server.
    Coordinates UDP and TCP handlers.
    
    Usage:
        config = DNSProxyConfig()
        server = DNSProxyServer(config)
        
        # Connect to whitelist
        server.query_handler.set_whitelist_state(whitelist_state)
        
        # Start serving
        server.start()
        
        # ... 
        
        server.stop()
    """
    
    def __init__(self, config: DNSProxyConfig = None):
        self.config = config or DNSProxyConfig()
        
        self._stats = ServerStats()
        self._query_handler = DNSQueryHandler(self.config)
        
        self._udp_handler = UDPHandler(
            self.config.server,
            self._query_handler,
            self._stats
        )
        
        self._tcp_handler = TCPHandler(
            self.config.server,
            self._query_handler,
            self._stats
        )
        
        self._running = False
        
        logger.info("DNS Proxy Server initialized")
    
    @property
    def query_handler(self) -> DNSQueryHandler:
        """Get query handler for configuration."""
        return self._query_handler
    
    def start(self) -> None:
        """Start DNS proxy server."""
        if self._running:
            logger.warning("DNS Proxy Server already running")
            return
        
        logger.info("Starting DNS Proxy Server...")
        
        # Start handler components
        self._query_handler.start()
        
        # Start UDP handler
        self._udp_handler.start()
        
        # Start TCP handler (optional based on config)
        if self.config.server.enable_tcp:
            self._tcp_handler.start()
        
        self._running = True
        
        logger.info(
            f"DNS Proxy Server started on "
            f"{self.config.server.listen_ip}:{self.config.server.port}"
        )
    
    def stop(self) -> None:
        """Stop DNS proxy server."""
        if not self._running:
            return
        
        logger.info("Stopping DNS Proxy Server...")
        
        self._running = False
        
        self._udp_handler.stop()
        self._tcp_handler.stop()
        self._query_handler.stop()
        
        logger.info("DNS Proxy Server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def get_stats(self) -> dict:
        """Get server statistics."""
        handler_stats = self._query_handler.get_stats()
        
        return {
            "server": {
                "running": self._running,
                "udp_queries": self._stats.udp_queries,
                "tcp_queries": self._stats.tcp_queries,
                "udp_errors": self._stats.udp_errors,
                "tcp_errors": self._stats.tcp_errors,
                "active_tcp_connections": self._stats.active_connections,
            },
            **handler_stats
        }


def check_admin_rights() -> bool:
    """Check if running with admin rights (required for port 53)."""
    import ctypes
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def check_port_available(port: int = 53, host: str = "127.0.0.1") -> Tuple[bool, str]:
    """
    Check if DNS port is available.
    
    Returns:
        Tuple of (available, message)
    """
    import subprocess
    
    # Try to detect what's using port 53
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.split("\n"):
            if f":{port}" in line and ("LISTENING" in line or "UDP" in line):
                # Found something on port 53
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    
                    # Get process name
                    proc_result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if "svchost.exe" in proc_result.stdout:
                        return False, (
                            f"Port {port} is in use by Windows DNS Client service. "
                            f"Run 'net stop dnscache' as admin to disable it."
                        )
                    
                    return False, f"Port {port} is in use by PID {pid}. Check with 'netstat -ano | findstr :{port}'"
    except Exception as e:
        logger.debug(f"Error checking port: {e}")
    
    # Try to bind directly
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host, port))
        sock.close()
        return True, "Port available"
    except PermissionError:
        return False, "Admin rights required to bind to port 53"
    except OSError as e:
        if e.errno == 10048:  # WSAEADDRINUSE
            return False, f"Port {port} is already in use"
        return False, str(e)
