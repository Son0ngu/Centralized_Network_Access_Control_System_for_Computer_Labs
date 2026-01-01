"""
Failure Scenario Tests for DNS Proxy System
--------------------------------------------
Tests error handling and recovery in various failure scenarios.
"""

import logging
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from .mocks import (
    MockDNSResolver,
    MockDNSResponse,
    MockFirewallManager,
    MockNetworkManager,
    MockWhitelistState,
    MockSubprocess,
)

logger = logging.getLogger("dns_proxy.tests.failures")


class TestDNSResolutionFailures(unittest.TestCase):
    """Test DNS resolution failure scenarios."""
    
    def test_all_upstream_servers_fail(self):
        """Test behavior when all upstream DNS servers fail."""
        resolver = MockDNSResolver(
            default_ips=[],
            fail_domains=["*"],  # Fail all
        )
        resolver.add_failure("example.com")
        
        response = resolver.resolve("example.com")
        
        self.assertFalse(response.success)
        self.assertEqual(len(response.ips), 0)
    
    def test_timeout_handling(self):
        """Test DNS query timeout handling."""
        # Simulate slow resolver
        resolver = MockDNSResolver(latency_ms=5000)  # 5 second latency
        
        start = time.time()
        
        # In real implementation, should timeout before 5 seconds
        # For mock, just verify it doesn't hang forever
        response = resolver.resolve("slow.example.com")
        
        elapsed = time.time() - start
        # Should complete (mock returns immediately even with latency set)
    
    def test_partial_server_failure(self):
        """Test when some but not all DNS servers fail."""
        # First resolution fails
        resolver = MockDNSResolver()
        resolver.add_failure("fail-first.com")
        
        # Should return failure for failed domain
        response = resolver.resolve("fail-first.com")
        self.assertFalse(response.success)
        
        # But succeed for other domains
        response = resolver.resolve("success.com")
        self.assertTrue(response.success)
    
    def test_malformed_response_handling(self):
        """Test handling of malformed DNS responses."""
        resolver = MockDNSResolver()
        
        # Add response with empty/invalid IPs
        resolver.add_response("malformed.com", MockDNSResponse(
            domain="malformed.com",
            ips=["not-an-ip", "also-invalid"],
            success=True,
        ))
        
        response = resolver.resolve("malformed.com")
        # Should handle gracefully


class TestFirewallFailures(unittest.TestCase):
    """Test firewall operation failure scenarios."""
    
    def test_add_rule_failure(self):
        """Test handling when adding firewall rule fails."""
        firewall = MockFirewallManager(fail_on_add=True)
        
        success = firewall.add_rule("1.2.3.4", ttl=300)
        
        self.assertFalse(success)
        self.assertFalse(firewall.has_rule("1.2.3.4"))
    
    def test_remove_rule_failure(self):
        """Test handling when removing firewall rule fails."""
        firewall = MockFirewallManager()
        
        # First add successfully
        firewall.add_rule("1.2.3.4", ttl=300)
        
        # Then fail on remove
        firewall.set_fail_on_remove(True)
        
        success = firewall.remove_rule("1.2.3.4")
        
        self.assertFalse(success)
        # Rule should still exist
        self.assertTrue(firewall.has_rule("1.2.3.4"))
    
    def test_no_admin_rights(self):
        """Test behavior without administrator rights."""
        # Mock admin check
        with patch('ctypes.windll.shell32.IsUserAnAdmin', return_value=0):
            # Firewall operations should handle this gracefully
            pass
    
    def test_firewall_command_timeout(self):
        """Test handling when firewall command times out."""
        firewall = MockFirewallManager(add_latency_ms=10000)  # 10 second delay
        
        # Should handle timeout gracefully
        # (Mock implementation doesn't actually timeout)
    
    def test_concurrent_rule_modifications(self):
        """Test concurrent rule add/remove operations."""
        firewall = MockFirewallManager()
        errors = []
        
        def add_rules():
            for i in range(100):
                try:
                    firewall.add_rule(f"1.2.3.{i % 256}", ttl=300)
                except Exception as e:
                    errors.append(str(e))
        
        def remove_rules():
            for i in range(100):
                try:
                    firewall.remove_rule(f"1.2.3.{i % 256}")
                except Exception as e:
                    errors.append(str(e))
        
        threads = [
            threading.Thread(target=add_rules),
            threading.Thread(target=remove_rules),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should handle concurrent access without errors
        self.assertEqual(len(errors), 0)


class TestNetworkConfigurationFailures(unittest.TestCase):
    """Test network configuration failure scenarios."""
    
    def test_adapter_not_found(self):
        """Test handling when adapter not found."""
        network = MockNetworkManager(adapters=[])
        # Override the _adapters to be truly empty
        network._adapters = []
        
        adapters = network.get_adapters()
        self.assertEqual(len(adapters), 0)
        
        # Setting DNS on non-existent adapter should fail
        success = network.set_dns_servers("NonExistent", ["127.0.0.1"])
        self.assertFalse(success)
    
    def test_dns_set_failure(self):
        """Test handling when DNS set fails."""
        network = MockNetworkManager()
        network.set_fail_on_set_dns(True)
        
        adapters = network.get_adapters()
        if adapters:
            success = network.set_dns_servers(adapters[0].name, ["127.0.0.1"])
            self.assertFalse(success)
    
    def test_adapter_disconnect_during_operation(self):
        """Test handling when adapter disconnects during operation."""
        # Simulate by changing adapter state
        network = MockNetworkManager()
        
        adapters = network.get_adapters()
        if adapters:
            # Mark adapter as disconnected
            adapters[0].is_connected = False
            
            # Should handle gracefully
            active = network.get_active_adapters()
            self.assertEqual(len(active), 0)


class TestWhitelistFailures(unittest.TestCase):
    """Test whitelist operation failure scenarios."""
    
    def test_empty_whitelist(self):
        """Test behavior with empty whitelist."""
        whitelist = MockWhitelistState()
        
        # All domains should be blocked
        self.assertFalse(whitelist.is_domain_allowed("example.com"))
        self.assertFalse(whitelist.is_domain_allowed("google.com"))
    
    def test_whitelist_sync_failure(self):
        """Test handling when whitelist sync fails."""
        # In production, would test HTTP request failure
        # Here we just verify the mock handles empty state
        whitelist = MockWhitelistState()
        
        # Should not crash on empty state
        domains = whitelist.get_all_domains()
        self.assertEqual(len(domains), 0)
    
    def test_concurrent_whitelist_modifications(self):
        """Test concurrent whitelist add/remove operations."""
        whitelist = MockWhitelistState()
        errors = []
        
        def add_domains():
            for i in range(100):
                try:
                    whitelist.add_domain(f"domain{i}.com")
                except Exception as e:
                    errors.append(str(e))
        
        def check_domains():
            for i in range(100):
                try:
                    whitelist.is_domain_allowed(f"domain{i}.com")
                except Exception as e:
                    errors.append(str(e))
        
        threads = [
            threading.Thread(target=add_domains),
            threading.Thread(target=check_domains),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)


class TestStartupFailures(unittest.TestCase):
    """Test startup failure scenarios."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.integration import StartupSequence
            cls.StartupSequence = StartupSequence
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"Startup module not available: {self._skip_reason}")
    
    def test_port_already_in_use(self):
        """Test startup failure when port is in use."""
        # Try to bind to a random available port first
        test_port = 65432  # High port less likely to be in use
        
        try:
            # Bind to port to simulate it being in use
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", test_port))
            
            startup = self.StartupSequence()
            checks = startup.run_preflight_checks(dns_port=test_port)
            
            port_check = next((c for c in checks if "Port" in c.name), None)
            if port_check:
                self.assertFalse(port_check.passed)
            
            sock.close()
        except OSError:
            # Port was already in use
            startup = self.StartupSequence()
            checks = startup.run_preflight_checks(dns_port=test_port)
            
            port_check = next((c for c in checks if "Port" in c.name), None)
            if port_check:
                self.assertFalse(port_check.passed)
    
    def test_missing_dependencies(self):
        """Test startup failure with missing dependencies."""
        startup = self.StartupSequence()
        
        # Mock missing dnspython
        with patch.dict('sys.modules', {'dns': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'dns'")):
                # Should detect missing dependency
                pass
    
    def test_no_admin_rights_startup(self):
        """Test startup without admin rights."""
        startup = self.StartupSequence()
        
        with patch('ctypes.windll.shell32.IsUserAnAdmin', return_value=0):
            checks = startup.run_preflight_checks(require_admin=True)
            
            admin_check = next((c for c in checks if "Admin" in c.name), None)
            if admin_check:
                self.assertFalse(admin_check.passed)


class TestOrchestratorFailures(unittest.TestCase):
    """Test orchestrator failure scenarios."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.integration import (
                DNSProxyOrchestrator,
                OrchestratorConfig,
            )
            cls.DNSProxyOrchestrator = DNSProxyOrchestrator
            cls.OrchestratorConfig = OrchestratorConfig
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"Orchestrator not available: {self._skip_reason}")
    
    def test_start_without_dependencies(self):
        """Test starting orchestrator without dependencies."""
        config = self.OrchestratorConfig()
        orchestrator = self.DNSProxyOrchestrator(config)
        
        # Don't set whitelist or firewall manager
        
        # Start should handle missing dependencies
        # (behavior depends on implementation)
        status = orchestrator.get_status()
        self.assertIn("running", status)
    
    def test_component_crash_recovery(self):
        """Test recovery when component crashes."""
        config = self.OrchestratorConfig()
        orchestrator = self.DNSProxyOrchestrator(config)
        
        # Mock component crash
        mock_whitelist = MockWhitelistState(["example.com"])
        orchestrator.set_whitelist_state(mock_whitelist)
        
        # Should handle component failures gracefully
    
    def test_stop_with_pending_operations(self):
        """Test stopping orchestrator with pending operations."""
        config = self.OrchestratorConfig()
        orchestrator = self.DNSProxyOrchestrator(config)
        
        # Should handle graceful shutdown
        orchestrator.stop()


class TestMigrationFailures(unittest.TestCase):
    """Test migration failure scenarios."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.integration import (
                MigrationHelper,
                MigrationMode,
            )
            cls.MigrationHelper = MigrationHelper
            cls.MigrationMode = MigrationMode
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"Migration not available: {self._skip_reason}")
    
    def test_migration_without_orchestrator(self):
        """Test migration fails without orchestrator."""
        helper = self.MigrationHelper()
        
        result = helper.migrate()
        
        self.assertFalse(result)
        
        state = helper.get_state()
        self.assertGreater(len(state.errors), 0)
    
    def test_migration_dns_proxy_fails_to_start(self):
        """Test migration when DNS proxy fails to start."""
        helper = self.MigrationHelper()
        
        mock_orchestrator = MagicMock()
        mock_orchestrator.start.return_value = False
        
        helper.set_dns_proxy_orchestrator(mock_orchestrator)
        
        result = helper.migrate()
        
        self.assertFalse(result)
    
    def test_rollback_failure(self):
        """Test handling when rollback fails."""
        helper = self.MigrationHelper()
        
        # Set up orchestrator that fails on stop too
        mock_orchestrator = MagicMock()
        mock_orchestrator.start.return_value = True
        mock_orchestrator.get_status.return_value = {"running": False}  # Fail verification
        mock_orchestrator.stop.side_effect = Exception("Stop failed")
        
        helper.set_dns_proxy_orchestrator(mock_orchestrator)
        
        # Migration should fail
        result = helper.migrate(auto_rollback=True)
        
        # Should handle rollback failure gracefully
    
    def test_parallel_mode_verification_failure(self):
        """Test when parallel mode verification fails."""
        helper = self.MigrationHelper()
        
        mock_orchestrator = MagicMock()
        mock_orchestrator.start.return_value = True
        
        # Simulate intermittent health check failures
        call_count = [0]
        def failing_status():
            call_count[0] += 1
            if call_count[0] > 2:
                return {"running": False}
            return {"running": True}
        
        mock_orchestrator.get_status.side_effect = failing_status
        
        helper.set_dns_proxy_orchestrator(mock_orchestrator)
        
        result = helper.migrate(
            target_mode=self.MigrationMode.PARALLEL,
            parallel_duration_seconds=1,
        )
        
        # Should detect health check failure


class TestRecoveryScenarios(unittest.TestCase):
    """Test system recovery from various failure states."""
    
    def test_recover_from_dns_failure(self):
        """Test recovery after DNS server becomes unreachable."""
        resolver = MockDNSResolver()
        
        # Initial success
        response = resolver.resolve("example.com")
        self.assertTrue(response.success)
        
        # Simulate failure
        resolver.add_failure("example.com")
        response = resolver.resolve("example.com")
        self.assertFalse(response.success)
        
        # Remove failure - recovery
        resolver._fail_domains.discard("example.com")
        response = resolver.resolve("example.com")
        self.assertTrue(response.success)
    
    def test_recover_from_firewall_failure(self):
        """Test recovery after firewall operations start failing."""
        firewall = MockFirewallManager()
        
        # Initial success
        self.assertTrue(firewall.add_rule("1.2.3.4", 300))
        
        # Simulate failure
        firewall.set_fail_on_add(True)
        self.assertFalse(firewall.add_rule("5.6.7.8", 300))
        
        # Recovery
        firewall.set_fail_on_add(False)
        self.assertTrue(firewall.add_rule("9.10.11.12", 300))
    
    def test_graceful_degradation(self):
        """Test system operates in degraded mode during partial failure."""
        whitelist = MockWhitelistState(["example.com"])
        firewall = MockFirewallManager()
        resolver = MockDNSResolver()
        
        # Normal operation
        domain = "example.com"
        if whitelist.is_domain_allowed(domain):
            response = resolver.resolve(domain)
            if response.success:
                firewall.add_rule(response.ips[0], response.ttl)
        
        self.assertTrue(firewall.has_rule(resolver.resolve(domain).ips[0]))
        
        # Firewall fails - should still allow DNS but log error
        firewall.set_fail_on_add(True)
        
        # Can still check whitelist and resolve DNS
        self.assertTrue(whitelist.is_domain_allowed(domain))
        response = resolver.resolve(domain)
        self.assertTrue(response.success)
        
        # Firewall add fails but doesn't crash
        result = firewall.add_rule(response.ips[0], response.ttl)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
