"""
Mock Objects for DNS Proxy Testing
-----------------------------------
Provides mock implementations of external dependencies
for isolated testing.
"""

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("dns_proxy.tests.mocks")


# =============================================================================
# DNS Related Mocks
# =============================================================================

@dataclass
class MockDNSQuery:
    """Mock DNS query for testing."""
    domain: str
    query_type: str = "A"
    query_class: str = "IN"
    transaction_id: int = 0x1234
    source_ip: str = "127.0.0.1"
    source_port: int = 12345


@dataclass
class MockDNSResponse:
    """Mock DNS response for testing."""
    domain: str
    ips: List[str]
    ttl: int = 300
    success: bool = True
    error: Optional[str] = None
    response_time_ms: float = 10.0
    source: str = "mock"
    
    def to_wire(self) -> bytes:
        """Generate mock DNS wire format response."""
        # Simplified mock - not real DNS format
        return b'\x00' * 12 + self.domain.encode() + b'\x00\x00\x01\x00\x01'


class MockDNSResolver:
    """Mock DNS resolver for testing."""
    
    def __init__(
        self,
        responses: Dict[str, MockDNSResponse] = None,
        default_ips: List[str] = None,
        fail_domains: List[str] = None,
        latency_ms: float = 0,
    ):
        self._responses = responses or {}
        self._default_ips = default_ips or ["93.184.216.34"]
        self._fail_domains = set(fail_domains or [])
        self._latency_ms = latency_ms
        self._query_count = 0
        self._query_log: List[str] = []
    
    def resolve(self, domain: str) -> MockDNSResponse:
        """Resolve a domain to mock response."""
        self._query_count += 1
        self._query_log.append(domain)
        
        # Simulate latency
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000)
        
        # Check for forced failures
        if domain in self._fail_domains:
            return MockDNSResponse(
                domain=domain,
                ips=[],
                success=False,
                error="NXDOMAIN",
            )
        
        # Check predefined responses
        if domain in self._responses:
            return self._responses[domain]
        
        # Return default response
        return MockDNSResponse(
            domain=domain,
            ips=self._default_ips,
            ttl=300,
            success=True,
        )
    
    def add_response(self, domain: str, response: MockDNSResponse) -> None:
        """Add a predefined response for a domain."""
        self._responses[domain] = response
    
    def add_failure(self, domain: str) -> None:
        """Add a domain that will fail resolution."""
        self._fail_domains.add(domain)
    
    def get_query_count(self) -> int:
        """Get total number of queries."""
        return self._query_count
    
    def get_query_log(self) -> List[str]:
        """Get log of all queried domains."""
        return list(self._query_log)
    
    def reset_stats(self) -> None:
        """Reset query statistics."""
        self._query_count = 0
        self._query_log.clear()


# =============================================================================
# Whitelist Mocks
# =============================================================================

class MockWhitelistState:
    """Mock whitelist state for testing."""
    
    def __init__(
        self,
        allowed_domains: List[str] = None,
        allowed_ips: List[str] = None,
        allowed_patterns: List[str] = None,
    ):
        self._domains: Set[str] = set(allowed_domains or [])
        self._ips: Set[str] = set(allowed_ips or [])
        self._patterns: Set[str] = set(allowed_patterns or [])
        self._check_count = 0
        self._lock = threading.Lock()
    
    def is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is allowed."""
        with self._lock:
            self._check_count += 1
            
            # Exact match
            if domain in self._domains:
                return True
            
            # Pattern match (wildcard)
            for pattern in self._patterns:
                if pattern.startswith("*."):
                    suffix = pattern[2:]
                    if domain.endswith(suffix) or domain == suffix:
                        return True
                    if domain.endswith("." + suffix):
                        return True
            
            return False
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        with self._lock:
            self._check_count += 1
            return ip in self._ips
    
    def add_domain(self, domain: str) -> None:
        """Add a domain to whitelist."""
        with self._lock:
            self._domains.add(domain)
    
    def add_ip(self, ip: str) -> None:
        """Add an IP to whitelist."""
        with self._lock:
            self._ips.add(ip)
    
    def add_pattern(self, pattern: str) -> None:
        """Add a pattern to whitelist."""
        with self._lock:
            self._patterns.add(pattern)
    
    def remove_domain(self, domain: str) -> None:
        """Remove a domain from whitelist."""
        with self._lock:
            self._domains.discard(domain)
    
    def get_all_domains(self) -> Set[str]:
        """Get all whitelisted domains."""
        with self._lock:
            return self._domains.copy()
    
    def get_all_ips(self) -> Set[str]:
        """Get all whitelisted IPs."""
        with self._lock:
            return self._ips.copy()
    
    def get_all_patterns(self) -> Set[str]:
        """Get all whitelist patterns."""
        with self._lock:
            return self._patterns.copy()
    
    def get_check_count(self) -> int:
        """Get number of checks performed."""
        return self._check_count
    
    def clear(self) -> None:
        """Clear all whitelist entries."""
        with self._lock:
            self._domains.clear()
            self._ips.clear()
            self._patterns.clear()


# =============================================================================
# Firewall Mocks
# =============================================================================

@dataclass
class MockFirewallRule:
    """Mock firewall rule."""
    ip: str
    ttl: int
    created_at: float
    profile: str = "all"
    interface: Optional[str] = None
    name: str = ""
    
    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl


class MockFirewallManager:
    """Mock firewall manager for testing."""
    
    def __init__(
        self,
        fail_on_add: bool = False,
        fail_on_remove: bool = False,
        add_latency_ms: float = 0,
    ):
        self._rules: Dict[str, MockFirewallRule] = {}
        self._add_count = 0
        self._remove_count = 0
        self._fail_on_add = fail_on_add
        self._fail_on_remove = fail_on_remove
        self._add_latency_ms = add_latency_ms
        self._lock = threading.Lock()
        self._operation_log: List[Dict] = []
    
    def add_rule(
        self,
        ip: str,
        ttl: int = 300,
        profile: str = "all",
        interface: str = None,
    ) -> bool:
        """Add a firewall rule."""
        with self._lock:
            # Simulate latency
            if self._add_latency_ms > 0:
                time.sleep(self._add_latency_ms / 1000)
            
            self._operation_log.append({
                "operation": "add",
                "ip": ip,
                "ttl": ttl,
                "timestamp": time.time(),
            })
            
            if self._fail_on_add:
                return False
            
            rule = MockFirewallRule(
                ip=ip,
                ttl=ttl,
                created_at=time.time(),
                profile=profile,
                interface=interface,
                name=f"DNS_Whitelist_{ip}",
            )
            self._rules[ip] = rule
            self._add_count += 1
            return True
    
    def remove_rule(self, ip: str) -> bool:
        """Remove a firewall rule."""
        with self._lock:
            self._operation_log.append({
                "operation": "remove",
                "ip": ip,
                "timestamp": time.time(),
            })
            
            if self._fail_on_remove:
                return False
            
            if ip in self._rules:
                del self._rules[ip]
                self._remove_count += 1
                return True
            return False
    
    def has_rule(self, ip: str) -> bool:
        """Check if rule exists for IP."""
        with self._lock:
            return ip in self._rules
    
    def get_rule(self, ip: str) -> Optional[MockFirewallRule]:
        """Get rule for IP."""
        with self._lock:
            return self._rules.get(ip)
    
    def get_all_rules(self) -> Dict[str, MockFirewallRule]:
        """Get all rules."""
        with self._lock:
            return self._rules.copy()
    
    def get_add_count(self) -> int:
        """Get number of add operations."""
        return self._add_count
    
    def get_remove_count(self) -> int:
        """Get number of remove operations."""
        return self._remove_count
    
    def get_operation_log(self) -> List[Dict]:
        """Get operation log."""
        with self._lock:
            return list(self._operation_log)
    
    def set_fail_on_add(self, fail: bool) -> None:
        """Set whether add operations should fail."""
        self._fail_on_add = fail
    
    def set_fail_on_remove(self, fail: bool) -> None:
        """Set whether remove operations should fail."""
        self._fail_on_remove = fail
    
    def clear(self) -> None:
        """Clear all rules."""
        with self._lock:
            self._rules.clear()
            self._operation_log.clear()


# =============================================================================
# Network Mocks
# =============================================================================

@dataclass
class MockNetworkAdapter:
    """Mock network adapter."""
    name: str
    description: str
    index: int
    mac_address: str = "00:11:22:33:44:55"
    ipv4_addresses: List[str] = field(default_factory=lambda: ["192.168.1.100"])
    ipv6_addresses: List[str] = field(default_factory=list)
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8"])
    is_up: bool = True
    is_connected: bool = True
    has_gateway: bool = True


class MockNetworkManager:
    """Mock network manager for testing."""
    
    def __init__(self, adapters: List[MockNetworkAdapter] = None):
        self._adapters = adapters or [
            MockNetworkAdapter(
                name="Ethernet",
                description="Intel Ethernet Connection",
                index=1,
            ),
        ]
        self._dns_overrides: Dict[str, List[str]] = {}
        self._fail_on_set_dns = False
    
    def get_adapters(self) -> List[MockNetworkAdapter]:
        """Get all network adapters."""
        return list(self._adapters)
    
    def get_active_adapters(self) -> List[MockNetworkAdapter]:
        """Get active (up and connected) adapters."""
        return [a for a in self._adapters if a.is_up and a.is_connected]
    
    def set_dns_servers(self, adapter_name: str, dns_servers: List[str]) -> bool:
        """Set DNS servers for adapter."""
        if self._fail_on_set_dns:
            return False
        
        self._dns_overrides[adapter_name] = dns_servers
        
        for adapter in self._adapters:
            if adapter.name == adapter_name:
                adapter.dns_servers = dns_servers
                return True
        return False
    
    def get_dns_servers(self, adapter_name: str) -> List[str]:
        """Get DNS servers for adapter."""
        if adapter_name in self._dns_overrides:
            return self._dns_overrides[adapter_name]
        
        for adapter in self._adapters:
            if adapter.name == adapter_name:
                return adapter.dns_servers
        return []
    
    def set_fail_on_set_dns(self, fail: bool) -> None:
        """Set whether set_dns operations should fail."""
        self._fail_on_set_dns = fail


# =============================================================================
# UDP Server Mock
# =============================================================================

class MockUDPServer:
    """Mock UDP server for testing DNS proxy."""
    
    def __init__(self, bind_address: str = "127.0.0.1", port: int = 0):
        self._bind_address = bind_address
        self._port = port
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._received_packets: List[Tuple[bytes, Tuple[str, int]]] = []
        self._response_handler: Optional[Callable] = None
        self._lock = threading.Lock()
    
    def start(self) -> int:
        """Start the mock server. Returns bound port."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self._bind_address, self._port))
        self._socket.settimeout(0.5)
        
        # Get actual bound port
        self._port = self._socket.getsockname()[1]
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        
        return self._port
    
    def stop(self) -> None:
        """Stop the mock server."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._socket:
            self._socket.close()
    
    def _run(self) -> None:
        """Server main loop."""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                with self._lock:
                    self._received_packets.append((data, addr))
                
                if self._response_handler:
                    response = self._response_handler(data, addr)
                    if response:
                        self._socket.sendto(response, addr)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Mock server error: {e}")
    
    def set_response_handler(
        self,
        handler: Callable[[bytes, Tuple[str, int]], Optional[bytes]]
    ) -> None:
        """Set custom response handler."""
        self._response_handler = handler
    
    def get_received_packets(self) -> List[Tuple[bytes, Tuple[str, int]]]:
        """Get all received packets."""
        with self._lock:
            return list(self._received_packets)
    
    def clear_received(self) -> None:
        """Clear received packets."""
        with self._lock:
            self._received_packets.clear()
    
    @property
    def port(self) -> int:
        """Get bound port."""
        return self._port


# =============================================================================
# Subprocess Mock
# =============================================================================

class MockSubprocess:
    """Mock subprocess for testing firewall commands."""
    
    def __init__(self):
        self._commands: List[List[str]] = []
        self._return_codes: Dict[str, int] = {}
        self._outputs: Dict[str, str] = {}
        self._fail_patterns: List[str] = []
    
    def run(self, cmd: List[str], **kwargs) -> 'MockCompletedProcess':
        """Mock subprocess.run."""
        self._commands.append(cmd)
        
        cmd_str = " ".join(cmd)
        
        # Check for failure patterns
        for pattern in self._fail_patterns:
            if pattern in cmd_str:
                return MockCompletedProcess(
                    returncode=1,
                    stdout="",
                    stderr=f"Error: {pattern}",
                )
        
        # Check for custom return code
        for key, code in self._return_codes.items():
            if key in cmd_str:
                return MockCompletedProcess(
                    returncode=code,
                    stdout=self._outputs.get(key, ""),
                    stderr="" if code == 0 else "Error",
                )
        
        # Default success
        return MockCompletedProcess(
            returncode=0,
            stdout="Ok.",
            stderr="",
        )
    
    def add_failure_pattern(self, pattern: str) -> None:
        """Add pattern that causes failure."""
        self._fail_patterns.append(pattern)
    
    def set_return_code(self, pattern: str, code: int) -> None:
        """Set return code for command pattern."""
        self._return_codes[pattern] = code
    
    def set_output(self, pattern: str, output: str) -> None:
        """Set output for command pattern."""
        self._outputs[pattern] = output
    
    def get_commands(self) -> List[List[str]]:
        """Get all executed commands."""
        return list(self._commands)
    
    def clear(self) -> None:
        """Clear recorded commands."""
        self._commands.clear()


@dataclass
class MockCompletedProcess:
    """Mock completed process result."""
    returncode: int
    stdout: str
    stderr: str
    
    @property
    def args(self) -> List[str]:
        return []


# =============================================================================
# Time Mock
# =============================================================================

class MockTime:
    """Mock time for testing TTL and expiry."""
    
    def __init__(self, start_time: float = None):
        self._current_time = start_time or time.time()
        self._real_time = time
    
    def time(self) -> float:
        """Get current mock time."""
        return self._current_time
    
    def advance(self, seconds: float) -> None:
        """Advance mock time by seconds."""
        self._current_time += seconds
    
    def set_time(self, timestamp: float) -> None:
        """Set mock time to specific timestamp."""
        self._current_time = timestamp
    
    def sleep(self, seconds: float) -> None:
        """Mock sleep - just advances time."""
        self.advance(seconds)


# =============================================================================
# Test Fixtures
# =============================================================================

def create_test_whitelist() -> MockWhitelistState:
    """Create a typical whitelist for testing."""
    return MockWhitelistState(
        allowed_domains=[
            "google.com",
            "microsoft.com",
            "github.com",
        ],
        allowed_patterns=[
            "*.google.com",
            "*.microsoft.com",
            "*.github.io",
        ],
        allowed_ips=[
            "8.8.8.8",
            "8.8.4.4",
            "1.1.1.1",
        ],
    )


def create_test_resolver() -> MockDNSResolver:
    """Create a typical DNS resolver for testing."""
    resolver = MockDNSResolver()
    
    resolver.add_response("google.com", MockDNSResponse(
        domain="google.com",
        ips=["142.250.185.78", "142.250.185.79"],
        ttl=300,
    ))
    
    resolver.add_response("microsoft.com", MockDNSResponse(
        domain="microsoft.com",
        ips=["20.70.246.20"],
        ttl=1800,
    ))
    
    resolver.add_failure("blocked.malware.com")
    
    return resolver


def create_test_adapters() -> List[MockNetworkAdapter]:
    """Create typical network adapters for testing."""
    return [
        MockNetworkAdapter(
            name="Ethernet",
            description="Intel I219-V",
            index=1,
            ipv4_addresses=["192.168.1.100"],
            ipv6_addresses=["fe80::1"],
            dns_servers=["192.168.1.1"],
            is_up=True,
            is_connected=True,
            has_gateway=True,
        ),
        MockNetworkAdapter(
            name="Wi-Fi",
            description="Intel Wireless-AC 9260",
            index=2,
            ipv4_addresses=["192.168.1.101"],
            dns_servers=["192.168.1.1"],
            is_up=False,
            is_connected=False,
            has_gateway=False,
        ),
    ]
