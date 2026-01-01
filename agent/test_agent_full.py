"""
Agent Unit Tests
================
Kiểm tra các chức năng chính của Agent hoạt động đúng:
1. DNS Proxy Server - Khởi động và xử lý query
2. Whitelist - Kiểm tra domain allowed/blocked
3. Firewall Rules - Cleanup hoạt động
4. Network Configuration - DNS enforcer
5. Config Validation - Cấu hình hợp lệ

Chạy:
    python test_agent_full.py          # Chạy tất cả tests
    python test_agent_full.py -v       # Verbose mode
    python test_agent_full.py -k dns   # Chỉ test DNS

Yêu cầu:
    - Chạy với quyền Administrator để test DNS/Firewall
    - dnspython package (pip install dnspython)

Author: Firewall Controller Team
"""

import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix import path for firewall.manager which uses 'agent.shared.time_utils'
# Create module aliases so imports work correctly
try:
    from shared import time_utils
    from utils import ip_detector, error_handler, validators
    
    # Create fake 'agent' package structure
    import types
    agent_module = types.ModuleType('agent')
    agent_module.shared = types.ModuleType('agent.shared')
    agent_module.shared.time_utils = time_utils
    agent_module.utils = types.ModuleType('agent.utils')
    agent_module.utils.ip_detector = ip_detector
    agent_module.utils.error_handler = error_handler
    agent_module.utils.validators = validators
    
    sys.modules['agent'] = agent_module
    sys.modules['agent.shared'] = agent_module.shared
    sys.modules['agent.shared.time_utils'] = time_utils
    sys.modules['agent.utils'] = agent_module.utils
    sys.modules['agent.utils.ip_detector'] = ip_detector
    sys.modules['agent.utils.error_handler'] = error_handler
    sys.modules['agent.utils.validators'] = validators
except ImportError as e:
    print(f"Warning: Could not set up module aliases: {e}")

# Colors for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        return False


# ============================================================
# TEST 1: Configuration Tests
# ============================================================
class TestConfiguration(unittest.TestCase):
    """Test configuration loading and validation."""
    
    def test_config_file_exists(self):
        """Test that config file exists."""
        config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
        self.assertTrue(
            os.path.exists(config_path),
            f"Config file not found: {config_path}"
        )
    
    def test_config_json_valid(self):
        """Test that config file is valid JSON."""
        config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config = json.load(f)
                    self.assertIsInstance(config, dict)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in config file: {e}")
    
    def test_config_has_required_sections(self):
        """Test that config has required sections."""
        config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Only check sections that are always required
            # firewall section is optional (can use defaults)
            required_sections = ["server", "whitelist", "heartbeat"]
            for section in required_sections:
                self.assertIn(
                    section, config,
                    f"Missing required config section: {section}"
                )
    
    def test_server_url_configured(self):
        """Test that server URL is configured."""
        config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            server = config.get("server", {})
            has_url = bool(server.get("url")) or bool(server.get("urls"))
            
            self.assertTrue(
                has_url,
                "Server URL not configured in config"
            )


# ============================================================
# TEST 2: Whitelist State Tests
# ============================================================
class TestWhitelistState(unittest.TestCase):
    """Test whitelist state management."""
    
    def setUp(self):
        """Set up test fixtures."""
        from whitelist.state import WhitelistState
        self.state = WhitelistState()
    
    def test_initial_state_empty(self):
        """Test that initial state is empty."""
        stats = self.state.get_stats()
        # API uses "domains_count" not "domain_count"
        self.assertEqual(stats["domains_count"], 0)
        self.assertEqual(stats["patterns_count"], 0)
        self.assertEqual(stats["ips_count"], 0)
    
    def test_update_with_domains(self):
        """Test updating whitelist with domains."""
        data = {
            "domains": [
                {"value": "google.com", "type": "domain"},
                {"value": "facebook.com", "type": "domain"},
            ]
        }
        
        result = self.state.update(data)
        self.assertTrue(result, "Update should return True for new data")
        
        stats = self.state.get_stats()
        self.assertEqual(stats["domains_count"], 2)
    
    def test_update_with_patterns(self):
        """Test updating whitelist with wildcard patterns."""
        data = {
            "domains": [
                {"value": "*.google.com", "type": "pattern"},
                {"value": "*.microsoft.com", "type": "pattern"},
            ]
        }
        
        result = self.state.update(data)
        self.assertTrue(result)
        
        stats = self.state.get_stats()
        self.assertEqual(stats["patterns_count"], 2)
    
    def test_update_with_ips(self):
        """Test updating whitelist with IP addresses."""
        data = {
            "domains": [
                {"value": "8.8.8.8", "type": "ip"},
            ],
            "ips": ["1.1.1.1", "1.0.0.1"]
        }
        
        result = self.state.update(data)
        self.assertTrue(result)
        
        stats = self.state.get_stats()
        self.assertEqual(stats["ips_count"], 3)
    
    def test_is_domain_allowed_direct_match(self):
        """Test direct domain matching."""
        self.state.update({
            "domains": [{"value": "google.com", "type": "domain"}]
        })
        
        self.assertTrue(self.state.is_domain_allowed("google.com"))
        self.assertTrue(self.state.is_domain_allowed("GOOGLE.COM"))  # Case insensitive
        self.assertFalse(self.state.is_domain_allowed("facebook.com"))
    
    def test_is_domain_allowed_subdomain(self):
        """Test subdomain matching."""
        self.state.update({
            "domains": [{"value": "google.com", "type": "domain"}]
        })
        
        # Subdomain of allowed domain should be allowed
        self.assertTrue(self.state.is_domain_allowed("www.google.com"))
        self.assertTrue(self.state.is_domain_allowed("mail.google.com"))
        self.assertTrue(self.state.is_domain_allowed("a.b.c.google.com"))
    
    def test_is_ip_allowed(self):
        """Test IP address matching."""
        self.state.update({
            "ips": ["8.8.8.8", "8.8.4.4"]
        })
        
        self.assertTrue(self.state.is_ip_allowed("8.8.8.8"))
        self.assertTrue(self.state.is_ip_allowed("8.8.4.4"))
        self.assertFalse(self.state.is_ip_allowed("1.1.1.1"))
    
    def test_duplicate_update_returns_false(self):
        """Test that duplicate update returns False."""
        data = {"domains": [{"value": "google.com", "type": "domain"}]}
        
        self.state.update(data)
        result = self.state.update(data)  # Same data again
        
        self.assertFalse(result, "Duplicate update should return False")
    
    def test_clear_state(self):
        """Test clearing whitelist state."""
        self.state.update({
            "domains": [{"value": "google.com", "type": "domain"}]
        })
        
        self.state.clear()
        
        stats = self.state.get_stats()
        self.assertEqual(stats["domains_count"], 0)


# ============================================================
# TEST 3: DNS Proxy Configuration Tests
# ============================================================
class TestDNSProxyConfig(unittest.TestCase):
    """Test DNS Proxy configuration."""
    
    def test_default_config(self):
        """Test default DNS proxy configuration."""
        from dns_proxy.config import DNSProxyConfig, DEFAULT_DNS_PROXY_CONFIG
        
        config = DEFAULT_DNS_PROXY_CONFIG
        self.assertTrue(config.enabled)
        self.assertIsNotNone(config.server)
        self.assertIsNotNone(config.cache)
        self.assertIsNotNone(config.firewall_sync)
    
    def test_server_config(self):
        """Test DNS server configuration."""
        from dns_proxy.config import DNSServerConfig
        
        server_config = DNSServerConfig(
            bind_address="127.0.0.1",
            port=53,
            enable_tcp=True,
        )
        
        self.assertEqual(server_config.bind_address, "127.0.0.1")
        self.assertEqual(server_config.port, 53)
        self.assertTrue(server_config.enable_tcp)
    
    def test_cache_config(self):
        """Test DNS cache configuration."""
        from dns_proxy.config import CacheConfig
        
        cache_config = CacheConfig()
        self.assertTrue(cache_config.enabled)
        self.assertGreater(cache_config.max_entries, 0)
        self.assertGreater(cache_config.min_ttl, 0)
        self.assertGreater(cache_config.max_ttl, cache_config.min_ttl)
    
    def test_upstream_resolver_config(self):
        """Test upstream resolver configuration."""
        from dns_proxy.config import UpstreamResolverConfig
        
        resolver = UpstreamResolverConfig(
            address="8.8.8.8",
            port=53,
            priority=1,
            enabled=True
        )
        
        self.assertEqual(resolver.address, "8.8.8.8")
        self.assertEqual(resolver.port, 53)
        self.assertTrue(resolver.enabled)


# ============================================================
# TEST 4: DNS Cache Tests
# ============================================================
class TestDNSCache(unittest.TestCase):
    """Test DNS caching functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        from dns_proxy.cache import DNSCache
        from dns_proxy.config import CacheConfig
        
        config = CacheConfig(
            enabled=True,
            max_entries=100,
            min_ttl=60,
            max_ttl=3600,
        )
        self.cache = DNSCache(config)
    
    def test_cache_set_and_get(self):
        """Test setting and getting from cache."""
        # Use set() method instead of put()
        entry = self.cache.set(
            domain="google.com",
            ipv4_addresses=["142.250.185.46"],
            ttl=300,
        )
        
        self.assertIsNotNone(entry)
        
        result = self.cache.get("google.com")
        self.assertIsNotNone(result)
        self.assertEqual(result.domain, "google.com")
        self.assertIn("142.250.185.46", result.all_ips)
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get("nonexistent.com")
        self.assertIsNone(result)
    
    def test_cache_case_insensitive(self):
        """Test cache is case insensitive."""
        # Cache should normalize to lowercase
        self.cache.set(
            domain="GOOGLE.COM",
            ipv4_addresses=["142.250.185.46"],
            ttl=300,
        )
        
        # Should find with different case
        result = self.cache.get("google.com")
        self.assertIsNotNone(result)
    
    def test_cache_stats(self):
        """Test cache statistics."""
        self.cache.set(
            domain="google.com",
            ipv4_addresses=["142.250.185.46"],
            ttl=300,
        )
        
        self.cache.get("google.com")  # Hit
        self.cache.get("facebook.com")  # Miss
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        # API uses "entries" not "size"
        self.assertEqual(stats["entries"], 1)


# ============================================================
# TEST 5: Network Manager Tests (Mock)
# ============================================================
class TestNetworkManagerMock(unittest.TestCase):
    """Test Network Manager with mocks (no admin required)."""
    
    def test_network_mode_enum(self):
        """Test NetworkMode enum values."""
        from dns_proxy.network.network_manager import NetworkMode
        
        self.assertEqual(NetworkMode.DISABLED.value, "disabled")
        self.assertEqual(NetworkMode.MONITOR.value, "monitor")
        self.assertEqual(NetworkMode.ACTIVE.value, "active")
    
    def test_network_config_defaults(self):
        """Test NetworkConfig default values."""
        from dns_proxy.network.network_manager import NetworkConfig, NetworkMode
        
        config = NetworkConfig()
        self.assertEqual(config.mode, NetworkMode.MONITOR)
        self.assertTrue(config.configure_ipv4)
        self.assertTrue(config.block_doh)
        self.assertTrue(config.block_dot)
    
    def test_doh_providers_list(self):
        """Test that DoH providers list is populated."""
        from dns_proxy.network.doh_blocker import DOH_PROVIDERS
        
        self.assertGreater(len(DOH_PROVIDERS), 0)
        
        # Check Google is in the list
        google = next((p for p in DOH_PROVIDERS if p.name == "Google"), None)
        self.assertIsNotNone(google)
        self.assertIn("8.8.8.8", google.ipv4_addresses)
        self.assertIn("8.8.4.4", google.ipv4_addresses)
    
    def test_dns_enforcer_modes(self):
        """Test DNSEnforcer mode enum."""
        from dns_proxy.network.dns_enforcer import EnforcementMode
        
        self.assertEqual(EnforcementMode.DISABLED.value, "disabled")
        self.assertEqual(EnforcementMode.MONITOR.value, "monitor")
        self.assertEqual(EnforcementMode.ENFORCE.value, "enforce")


# ============================================================
# TEST 6: Firewall Manager Tests (Skip if import fails)
# ============================================================
class TestFirewallManager(unittest.TestCase):
    """Test Firewall Manager functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Check if FirewallManager can be imported."""
        try:
            # Fix import path issue
            import sys
            if 'agent.shared.time_utils' not in sys.modules:
                # Alias the module
                from shared import time_utils
                sys.modules['agent.shared.time_utils'] = time_utils
        except Exception:
            pass
    
    def test_firewall_manager_init(self):
        """Test FirewallManager initialization."""
        try:
            from firewall.manager import FirewallManager
        except ModuleNotFoundError as e:
            self.skipTest(f"FirewallManager import failed: {e}")
        
        manager = FirewallManager(rule_prefix="TEST_FC")
        
        self.assertEqual(manager.rule_prefix, "TEST_FC")
        self.assertFalse(manager.default_deny_enabled)
    
    def test_firewall_status(self):
        """Test getting firewall status."""
        try:
            from firewall.manager import FirewallManager
        except ModuleNotFoundError as e:
            self.skipTest(f"FirewallManager import failed: {e}")
        
        manager = FirewallManager()
        status = manager.get_status()
        
        self.assertIn("mode", status)
        self.assertIn("firewall_rules_enabled", status)
        self.assertEqual(status["mode"], "dns_proxy")
    
    def test_legacy_api_noop(self):
        """Test that legacy API methods are no-op."""
        try:
            from firewall.manager import FirewallManager
        except ModuleNotFoundError as e:
            self.skipTest(f"FirewallManager import failed: {e}")
        
        manager = FirewallManager()
        
        # These should return True but not actually do anything
        result = manager.add_ip_to_whitelist("1.2.3.4")
        self.assertTrue(result)
        
        result = manager.remove_ip_from_whitelist("1.2.3.4")
        self.assertTrue(result)


# ============================================================
# TEST 7: Token Manager Tests
# ============================================================
class TestTokenManager(unittest.TestCase):
    """Test Token Manager functionality."""
    
    def test_token_manager_init(self):
        """Test TokenManager initialization."""
        from core.token_manager import TokenManager
        
        config = {
            "server": {
                "url": "http://localhost:5000"
            },
            "auth": {
                "access_token": "",
                "refresh_token": ""
            }
        }
        
        manager = TokenManager(config)
        # API uses has_valid_token not has_valid_tokens
        self.assertFalse(manager.has_valid_token)
    
    def test_set_tokens(self):
        """Test setting tokens."""
        from core.token_manager import TokenManager
        
        config = {"server": {"url": "http://localhost:5000"}, "auth": {}}
        manager = TokenManager(config)
        
        manager.set_tokens(
            access_token="test_access_token",
            refresh_token="test_refresh_token"
        )
        
        self.assertEqual(manager.access_token, "test_access_token")
        self.assertEqual(manager.refresh_token, "test_refresh_token")
    
    def test_auth_header(self):
        """Test getting auth header."""
        from core.token_manager import TokenManager
        
        config = {"server": {"url": "http://localhost:5000"}, "auth": {}}
        manager = TokenManager(config)
        
        manager.set_tokens(
            access_token="test_token",
            refresh_token="refresh"
        )
        
        header = manager.get_auth_header()
        self.assertIn("Authorization", header)
        self.assertTrue(header["Authorization"].startswith("Bearer "))


# ============================================================
# TEST 8: DNS Proxy Server Tests (Requires Admin)
# ============================================================
@unittest.skipUnless(is_admin(), "Requires administrator privileges")
@unittest.skipUnless(is_port_available(53), "Port 53 is in use")
class TestDNSProxyServer(unittest.TestCase):
    """Test DNS Proxy Server (requires admin and port 53 available)."""
    
    def setUp(self):
        """Set up test fixtures."""
        from dns_proxy.server import DNSProxyServer
        from dns_proxy.config import DNSProxyConfig, DNSServerConfig
        
        # DNSServerConfig doesn't have enable_udp parameter
        # UDP is always enabled, only TCP is optional
        server_config = DNSServerConfig(
            bind_address="127.0.0.1",
            port=53,
            enable_tcp=True,
        )
        
        config = DNSProxyConfig(
            enabled=True,
            server=server_config,
        )
        
        self.server = DNSProxyServer(config=config)
        self.server_started = False
    
    def tearDown(self):
        """Clean up after tests."""
        if self.server_started:
            try:
                self.server.stop()
            except:
                pass
    
    def test_server_start_stop(self):
        """Test starting and stopping DNS server."""
        try:
            self.server.start()
            self.server_started = True
            time.sleep(0.5)
            
            # Check server is running via get_stats() method
            stats = self.server.get_stats()
            # If we got stats without error, server is running
            self.assertIsNotNone(stats)
            
        except Exception as e:
            if "Port 53 in use" in str(e):
                self.skipTest("Port 53 is already in use")
            raise
    
    def test_dns_query(self):
        """Test DNS query through proxy."""
        try:
            import dns.resolver
        except ImportError:
            self.skipTest("dnspython not installed")
        
        try:
            self.server.start()
            self.server_started = True
            time.sleep(1)
            
            # Configure resolver to use local proxy
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['127.0.0.1']
            resolver.timeout = 5
            
            # Query should work (google.com should be resolvable)
            answers = resolver.resolve('google.com', 'A')
            ips = [str(r) for r in answers]
            
            self.assertGreater(len(ips), 0)
            
        except Exception as e:
            if "Port 53 in use" in str(e):
                self.skipTest("Port 53 is already in use")
            raise


# ============================================================
# TEST 9: Integration Tests (Requires Admin)
# ============================================================
@unittest.skipUnless(is_admin(), "Requires administrator privileges")
class TestIntegration(unittest.TestCase):
    """Integration tests for agent components."""
    
    def test_whitelist_with_dns_handler(self):
        """Test whitelist integration with DNS handler."""
        from dns_proxy.handler import DNSQueryHandler
        from dns_proxy.config import DNSProxyConfig
        from whitelist.state import WhitelistState
        
        # Set up whitelist
        whitelist = WhitelistState()
        whitelist.update({
            "domains": [
                {"value": "google.com", "type": "domain"},
                {"value": "*.microsoft.com", "type": "pattern"},
            ]
        })
        
        # Create handler with whitelist
        config = DNSProxyConfig()
        handler = DNSQueryHandler(
            config=config,
            whitelist_state=whitelist,
        )
        
        # Test allowed domains (should not block)
        self.assertTrue(whitelist.is_domain_allowed("google.com"))
        self.assertTrue(whitelist.is_domain_allowed("www.microsoft.com"))
        
        # Test blocked domain
        self.assertFalse(whitelist.is_domain_allowed("facebook.com"))


# ============================================================
# TEST 10: Utility Tests
# ============================================================
class TestUtilities(unittest.TestCase):
    """Test utility functions."""
    
    def test_time_utils(self):
        """Test time utilities."""
        from shared.time_utils import now, now_iso
        
        timestamp = now()
        self.assertIsInstance(timestamp, float)
        self.assertGreater(timestamp, 0)
        
        iso_time = now_iso()
        self.assertIsInstance(iso_time, str)
        self.assertIn("T", iso_time)  # ISO format has T separator
    
    def test_ip_detector(self):
        """Test IP detector utility."""
        from utils.ip_detector import get_local_ip
        
        ip = get_local_ip()
        self.assertIsNotNone(ip)
        # Should be either a valid IP or fallback
        self.assertTrue(
            ip == "127.0.0.1" or "." in ip,
            f"Invalid IP format: {ip}"
        )
    
    def test_os_info(self):
        """Test OS info utility."""
        from shared.os_info import get_os_details
        
        os_info = get_os_details()
        self.assertIsInstance(os_info, dict)
        # API returns platform/name/version, not os_name/os_version
        self.assertIn("platform", os_info)
        self.assertIn("name", os_info)


# ============================================================
# TEST RUNNER
# ============================================================
class ColoredTestResult(unittest.TextTestResult):
    """Custom test result with colored output."""
    
    def addSuccess(self, test):
        super().addSuccess(test)
        if self.showAll:
            self.stream.write(f"{Colors.GREEN}PASS{Colors.RESET}\n")
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.showAll:
            self.stream.write(f"{Colors.RED}FAIL{Colors.RESET}\n")
    
    def addError(self, test, err):
        super().addError(test, err)
        if self.showAll:
            self.stream.write(f"{Colors.RED}ERROR{Colors.RESET}\n")
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.showAll:
            self.stream.write(f"{Colors.YELLOW}SKIP{Colors.RESET} ({reason})\n")


class ColoredTestRunner(unittest.TextTestRunner):
    """Custom test runner with colored output."""
    resultclass = ColoredTestResult


def print_header():
    """Print test header."""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║          FIREWALL AGENT - UNIT TESTS                          ║
║          Kiểm tra chức năng Agent                             ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def print_system_info():
    """Print system information."""
    print(f"{Colors.BLUE}System Information:{Colors.RESET}")
    print(f"  Administrator: {Colors.GREEN if is_admin() else Colors.RED}{'Yes' if is_admin() else 'No'}{Colors.RESET}")
    print(f"  Port 53 Available: {Colors.GREEN if is_port_available(53) else Colors.YELLOW}{'Yes' if is_port_available(53) else 'No (in use)'}{Colors.RESET}")
    
    try:
        import dns.resolver
        print(f"  dnspython: {Colors.GREEN}Installed{Colors.RESET}")
    except ImportError:
        print(f"  dnspython: {Colors.YELLOW}Not installed (some tests will skip){Colors.RESET}")
    
    print()


def main():
    """Main test runner."""
    print_header()
    print_system_info()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestConfiguration,
        TestWhitelistState,
        TestDNSProxyConfig,
        TestDNSCache,
        TestNetworkManagerMock,
        TestFirewallManager,
        TestTokenManager,
        TestDNSProxyServer,
        TestIntegration,
        TestUtilities,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    print(f"{Colors.BLUE}Running tests...{Colors.RESET}\n")
    
    runner = ColoredTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped
    
    print(f"""
{Colors.BOLD}TEST SUMMARY:{Colors.RESET}
  Total:   {total}
  Passed:  {Colors.GREEN}{passed}{Colors.RESET}
  Failed:  {Colors.RED if failures > 0 else Colors.GREEN}{failures}{Colors.RESET}
  Errors:  {Colors.RED if errors > 0 else Colors.GREEN}{errors}{Colors.RESET}
  Skipped: {Colors.YELLOW}{skipped}{Colors.RESET}
""")
    
    if failures == 0 and errors == 0:
        print(f"{Colors.GREEN}✓ All tests passed!{Colors.RESET}")
    else:
        print(f"{Colors.RED}✗ Some tests failed!{Colors.RESET}")
        
        if failures > 0:
            print(f"\n{Colors.RED}Failures:{Colors.RESET}")
            for test, traceback in result.failures:
                print(f"  - {test}")
        
        if errors > 0:
            print(f"\n{Colors.RED}Errors:{Colors.RESET}")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    # Save results to file
    save_results_to_file(result, total, passed, failures, errors, skipped)
    
    return 0 if (failures == 0 and errors == 0) else 1


def save_results_to_file(result, total, passed, failures, errors, skipped):
    """Save test results to file."""
    output = []
    output.append("=" * 60)
    output.append("FIREWALL AGENT - UNIT TEST RESULTS")
    output.append("=" * 60)
    output.append("")
    output.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"Admin: {'Yes' if is_admin() else 'No'}")
    output.append("")
    output.append("SUMMARY:")
    output.append(f"  Total:   {total}")
    output.append(f"  Passed:  {passed}")
    output.append(f"  Failed:  {failures}")
    output.append(f"  Errors:  {errors}")
    output.append(f"  Skipped: {skipped}")
    output.append("")
    
    if result.failures:
        output.append("FAILURES:")
        for test, traceback in result.failures:
            output.append(f"  - {test}")
            output.append(traceback)
            output.append("")
    
    if result.errors:
        output.append("ERRORS:")
        for test, traceback in result.errors:
            output.append(f"  - {test}")
            output.append(traceback)
            output.append("")
    
    if result.skipped:
        output.append("SKIPPED:")
        for test, reason in result.skipped:
            output.append(f"  - {test}: {reason}")
        output.append("")
    
    output.append("=" * 60)
    
    with open("test_agent_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    
    print(f"\n{Colors.CYAN}Results saved to: test_agent_results.txt{Colors.RESET}")


if __name__ == "__main__":
    sys.exit(main())
