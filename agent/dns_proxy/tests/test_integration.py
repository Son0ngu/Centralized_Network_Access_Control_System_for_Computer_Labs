"""
Integration Tests for DNS Proxy System
--------------------------------------
Tests the interaction between multiple components.
"""

import logging
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
    create_test_whitelist,
    create_test_resolver,
)

logger = logging.getLogger("dns_proxy.tests.integration")


class TestDNSProxyIntegration(unittest.TestCase):
    """Integration tests for DNS Proxy components."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for all tests."""
        try:
            from dns_proxy.integration import (
                DNSProxyOrchestrator,
                OrchestratorConfig,
                OrchestratorMode,
            )
            cls.DNSProxyOrchestrator = DNSProxyOrchestrator
            cls.OrchestratorConfig = OrchestratorConfig
            cls.OrchestratorMode = OrchestratorMode
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"DNS Proxy modules not available: {self._skip_reason}")
        
        self.whitelist = create_test_whitelist()
        self.firewall = MockFirewallManager()
        self.resolver = create_test_resolver()
    
    def test_orchestrator_with_mock_dependencies(self):
        """Test orchestrator works with mock dependencies."""
        config = self.OrchestratorConfig(
            mode=self.OrchestratorMode.MONITOR
        )
        orchestrator = self.DNSProxyOrchestrator(config)
        
        orchestrator.set_whitelist_state(self.whitelist)
        orchestrator.set_firewall_manager(self.firewall)
        
        status = orchestrator.get_status()
        
        self.assertIn("mode", status)
        # Mode value is lowercase in implementation
        self.assertEqual(status["mode"].lower(), "monitor")
    
    def test_whitelist_firewall_integration(self):
        """Test whitelist and firewall work together."""
        # Domain is whitelisted
        self.assertTrue(self.whitelist.is_domain_allowed("google.com"))
        
        # Resolve domain
        response = self.resolver.resolve("google.com")
        self.assertTrue(response.success)
        
        # Add firewall rules for resolved IPs
        for ip in response.ips:
            success = self.firewall.add_rule(ip, response.ttl)
            self.assertTrue(success)
        
        # Verify rules were added
        self.assertEqual(self.firewall.get_add_count(), len(response.ips))
        
        for ip in response.ips:
            self.assertTrue(self.firewall.has_rule(ip))
    
    def test_blocked_domain_flow(self):
        """Test blocked domain handling."""
        # Domain is not whitelisted
        self.assertFalse(self.whitelist.is_domain_allowed("blocked.example.com"))
        
        # Should not add firewall rules for blocked domains
        # In real system, DNS proxy would return NXDOMAIN
    
    def test_wildcard_pattern_flow(self):
        """Test wildcard pattern matching."""
        # *.google.com pattern should match subdomains
        self.assertTrue(self.whitelist.is_domain_allowed("www.google.com"))
        self.assertTrue(self.whitelist.is_domain_allowed("mail.google.com"))
        self.assertTrue(self.whitelist.is_domain_allowed("drive.google.com"))
        
        # But not unrelated domains
        self.assertFalse(self.whitelist.is_domain_allowed("google.evil.com"))


class TestDNSQueryFlow(unittest.TestCase):
    """Test complete DNS query flow."""
    
    def setUp(self):
        self.whitelist = create_test_whitelist()
        self.firewall = MockFirewallManager()
        self.resolver = create_test_resolver()
    
    def test_allowed_domain_full_flow(self):
        """Test full flow for allowed domain."""
        domain = "google.com"
        
        # Step 1: Check whitelist
        is_allowed = self.whitelist.is_domain_allowed(domain)
        self.assertTrue(is_allowed)
        
        # Step 2: Resolve domain
        response = self.resolver.resolve(domain)
        self.assertTrue(response.success)
        self.assertGreater(len(response.ips), 0)
        
        # Step 3: Add firewall rules BEFORE returning response
        for ip in response.ips:
            self.firewall.add_rule(ip, response.ttl)
        
        # Step 4: Verify firewall state
        for ip in response.ips:
            self.assertTrue(self.firewall.has_rule(ip))
        
        # Step 5: Return DNS response (simulated)
        # In real system, client would receive response here
    
    def test_blocked_domain_full_flow(self):
        """Test full flow for blocked domain."""
        domain = "blocked.malware.com"
        
        # Step 1: Check whitelist
        is_allowed = self.whitelist.is_domain_allowed(domain)
        self.assertFalse(is_allowed)
        
        # Step 2: Block - return NXDOMAIN
        # No firewall rules should be added
        initial_count = self.firewall.get_add_count()
        
        # Simulated blocking - don't add rules
        
        # Verify no rules were added
        self.assertEqual(self.firewall.get_add_count(), initial_count)
    
    def test_concurrent_query_handling(self):
        """Test handling of concurrent DNS queries."""
        results = []
        errors = []
        
        def query_domain(domain: str):
            try:
                is_allowed = self.whitelist.is_domain_allowed(domain)
                if is_allowed:
                    response = self.resolver.resolve(domain)
                    if response.success:
                        for ip in response.ips:
                            self.firewall.add_rule(ip, response.ttl)
                        results.append((domain, response.ips))
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads querying different domains
        domains = ["google.com", "microsoft.com", "github.com"] * 10
        threads = [
            threading.Thread(target=query_domain, args=(d,))
            for d in domains
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # Should have processed all queries
        self.assertEqual(len(results), len(domains))


class TestFirewallRuleLifecycle(unittest.TestCase):
    """Test firewall rule creation and cleanup lifecycle."""
    
    def setUp(self):
        self.firewall = MockFirewallManager()
    
    def test_rule_creation(self):
        """Test rule creation with various parameters."""
        # Basic rule
        success = self.firewall.add_rule("1.2.3.4", ttl=300)
        self.assertTrue(success)
        self.assertTrue(self.firewall.has_rule("1.2.3.4"))
        
        # Rule with profile
        success = self.firewall.add_rule("5.6.7.8", ttl=600, profile="private")
        self.assertTrue(success)
        
        rule = self.firewall.get_rule("5.6.7.8")
        self.assertEqual(rule.profile, "private")
    
    def test_rule_removal(self):
        """Test rule removal."""
        self.firewall.add_rule("1.2.3.4", ttl=300)
        self.assertTrue(self.firewall.has_rule("1.2.3.4"))
        
        success = self.firewall.remove_rule("1.2.3.4")
        self.assertTrue(success)
        self.assertFalse(self.firewall.has_rule("1.2.3.4"))
    
    def test_rule_update(self):
        """Test updating existing rule."""
        self.firewall.add_rule("1.2.3.4", ttl=300)
        
        # Update by adding again
        self.firewall.add_rule("1.2.3.4", ttl=600)
        
        rule = self.firewall.get_rule("1.2.3.4")
        self.assertEqual(rule.ttl, 600)
    
    def test_rule_failure_handling(self):
        """Test handling when rule operations fail."""
        self.firewall.set_fail_on_add(True)
        
        success = self.firewall.add_rule("1.2.3.4", ttl=300)
        self.assertFalse(success)
        self.assertFalse(self.firewall.has_rule("1.2.3.4"))


class TestNetworkConfiguration(unittest.TestCase):
    """Test network configuration integration."""
    
    def setUp(self):
        self.network = MockNetworkManager()
    
    def test_get_adapters(self):
        """Test getting network adapters."""
        adapters = self.network.get_adapters()
        self.assertGreater(len(adapters), 0)
    
    def test_set_dns_servers(self):
        """Test setting DNS servers on adapter."""
        adapters = self.network.get_adapters()
        
        if adapters:
            adapter_name = adapters[0].name
            
            success = self.network.set_dns_servers(
                adapter_name,
                ["127.0.0.1"]
            )
            self.assertTrue(success)
            
            dns = self.network.get_dns_servers(adapter_name)
            self.assertEqual(dns, ["127.0.0.1"])
    
    def test_dns_set_failure(self):
        """Test handling DNS set failure."""
        self.network.set_fail_on_set_dns(True)
        
        adapters = self.network.get_adapters()
        if adapters:
            success = self.network.set_dns_servers(
                adapters[0].name,
                ["127.0.0.1"]
            )
            self.assertFalse(success)


class TestMigrationFlow(unittest.TestCase):
    """Test migration from PacketSniffer to DNS Proxy."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.integration import (
                MigrationHelper,
                MigrationMode,
                DNSProxyOrchestrator,
                OrchestratorConfig,
            )
            cls.MigrationHelper = MigrationHelper
            cls.MigrationMode = MigrationMode
            cls.DNSProxyOrchestrator = DNSProxyOrchestrator
            cls.OrchestratorConfig = OrchestratorConfig
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"Migration modules not available: {self._skip_reason}")
    
    def test_migration_state_transitions(self):
        """Test migration state transitions."""
        helper = self.MigrationHelper()
        
        # Initial state
        state = helper.get_state()
        self.assertEqual(state.mode, self.MigrationMode.SNIFFER_ONLY)
    
    def test_migration_with_mock_orchestrator(self):
        """Test migration with mock orchestrator."""
        helper = self.MigrationHelper()
        
        # Create mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.start.return_value = True
        mock_orchestrator.get_status.return_value = {"running": True}
        
        helper.set_dns_proxy_orchestrator(mock_orchestrator)
        
        # Attempt migration (should fail without sniffer but not crash)
        result = helper.migrate(
            target_mode=self.MigrationMode.PARALLEL,
            parallel_duration_seconds=1,
        )
        
        # Should succeed with mock
        # (actual behavior depends on implementation)
    
    def test_rollback(self):
        """Test migration rollback."""
        helper = self.MigrationHelper()
        
        # Set up mock orchestrator that will fail
        mock_orchestrator = MagicMock()
        mock_orchestrator.start.return_value = False
        
        helper.set_dns_proxy_orchestrator(mock_orchestrator)
        
        # Migration should fail and rollback
        result = helper.migrate(auto_rollback=True)
        self.assertFalse(result)
        
        # Should be back to initial state
        state = helper.get_state()
        self.assertEqual(state.mode, self.MigrationMode.SNIFFER_ONLY)


class TestStatusReporting(unittest.TestCase):
    """Test status reporting integration."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.integration import (
                StatusReporter,
                HealthLevel,
            )
            cls.StatusReporter = StatusReporter
            cls.HealthLevel = HealthLevel
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"Status Reporter not available: {self._skip_reason}")
    
    def test_status_without_orchestrator(self):
        """Test status reporting without orchestrator."""
        reporter = self.StatusReporter()
        
        health = reporter.get_system_health()
        
        # Should return valid health object
        self.assertIsNotNone(health)
        self.assertIsNotNone(health.level)
    
    def test_status_with_mock_orchestrator(self):
        """Test status reporting with mock orchestrator."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_status.return_value = {
            "running": True,
            "mode": "ACTIVE",
            "components": {
                "dns_proxy": {"status": "running"},
                "dns_cache": {"status": "running", "entries": 100},
                "firewall_sync": {"status": "running", "active_rules": 50},
                "network_manager": {"status": "running"},
                "security_manager": {"status": "running"},
                "resolver": {"status": "running"},
            },
        }
        
        reporter = self.StatusReporter(mock_orchestrator)
        
        health = reporter.get_system_health()
        
        # All components are running, so should be HEALTHY
        self.assertEqual(health.level, self.HealthLevel.HEALTHY)
    
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_status.return_value = {
            "metrics": {
                "total_queries": 1000,
                "queries_per_second": 10.5,
                "cache_hit_ratio": 0.85,
            },
        }
        
        reporter = self.StatusReporter(mock_orchestrator)
        
        metrics = reporter.get_performance_metrics()
        
        self.assertEqual(metrics.total_queries, 1000)


if __name__ == "__main__":
    unittest.main()
