"""
Unit Tests for Cleanup and Profile Manager
===========================================
Tests for:
1. ProfileManager - backup/restore functionality
2. DNSFirewall - remove_all_rules and rule management
3. SecurityManager - enable/disable lifecycle
4. cleanup_agent.py - cleanup functions

Run with:
    pytest test_cleanup.py -v
    python -m pytest test_cleanup.py -v --tb=short
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

# Add agent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.profile_manager import (
    ProfileManager,
    SystemProfile,
    DNSAdapterProfile,
    FirewallProfile,
    get_profile_manager,
    backup_system_profile,
    restore_system_profile,
)


class TestDNSAdapterProfile(unittest.TestCase):
    """Tests for DNSAdapterProfile dataclass."""
    
    def test_create_dhcp_profile(self):
        """Test creating a DHCP adapter profile."""
        profile = DNSAdapterProfile(
            adapter_name="Ethernet",
            ipv4_source="dhcp",
            ipv6_source="dhcp"
        )
        
        self.assertEqual(profile.adapter_name, "Ethernet")
        self.assertEqual(profile.ipv4_source, "dhcp")
        self.assertEqual(profile.ipv6_source, "dhcp")
        self.assertEqual(profile.ipv4_dns, [])
        self.assertEqual(profile.ipv6_dns, [])
    
    def test_create_static_profile(self):
        """Test creating a static DNS adapter profile."""
        profile = DNSAdapterProfile(
            adapter_name="Wi-Fi",
            ipv4_dns=["8.8.8.8", "8.8.4.4"],
            ipv4_source="static",
            ipv6_dns=["2001:4860:4860::8888"],
            ipv6_source="static"
        )
        
        self.assertEqual(profile.ipv4_dns, ["8.8.8.8", "8.8.4.4"])
        self.assertEqual(profile.ipv4_source, "static")


class TestFirewallProfile(unittest.TestCase):
    """Tests for FirewallProfile dataclass."""
    
    def test_default_profile(self):
        """Test default firewall profile."""
        profile = FirewallProfile()
        
        self.assertTrue(profile.domain_enabled)
        self.assertTrue(profile.private_enabled)
        self.assertTrue(profile.public_enabled)
        self.assertEqual(profile.created_rules, [])
    
    def test_track_rules(self):
        """Test tracking created rules."""
        profile = FirewallProfile()
        profile.created_rules.append("DNS_Proxy_Allow_Test")
        profile.created_rules.append("DNS_Proxy_Block_Test")
        
        self.assertEqual(len(profile.created_rules), 2)
        self.assertIn("DNS_Proxy_Allow_Test", profile.created_rules)


class TestSystemProfile(unittest.TestCase):
    """Tests for SystemProfile dataclass."""
    
    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        original = SystemProfile(
            created_at="2025-01-02T10:00:00",
            hostname="test-pc",
            notes="Test backup"
        )
        original.dns_adapters["Ethernet"] = DNSAdapterProfile(
            adapter_name="Ethernet",
            ipv4_dns=["8.8.8.8"],
            ipv4_source="static"
        )
        original.firewall.created_rules = ["Rule1", "Rule2"]
        
        # Convert to dict
        data = original.to_dict()
        
        # Verify dict structure
        self.assertEqual(data["hostname"], "test-pc")
        self.assertIn("Ethernet", data["dns_adapters"])
        self.assertEqual(data["firewall"]["created_rules"], ["Rule1", "Rule2"])
        
        # Convert back
        restored = SystemProfile.from_dict(data)
        
        self.assertEqual(restored.hostname, original.hostname)
        self.assertEqual(restored.dns_adapters["Ethernet"].ipv4_dns, ["8.8.8.8"])
        self.assertEqual(restored.firewall.created_rules, ["Rule1", "Rule2"])


class TestProfileManager(unittest.TestCase):
    """Tests for ProfileManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.profile_dir = Path(self.temp_dir) / "profiles"
        self.manager = ProfileManager(profile_dir=self.profile_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init_creates_directory(self):
        """Test that initialization creates profile directory."""
        self.assertTrue(self.profile_dir.exists())
    
    def test_has_backup_false_initially(self):
        """Test has_backup returns False initially."""
        self.assertFalse(self.manager.has_backup())
    
    @patch.object(ProfileManager, '_get_network_adapters')
    @patch.object(ProfileManager, '_get_adapter_dns_v4')
    @patch.object(ProfileManager, '_get_adapter_dns_v6')
    @patch.object(ProfileManager, '_backup_firewall_state')
    @patch.object(ProfileManager, '_backup_hosts_file')
    def test_backup_all_creates_profile(
        self,
        mock_hosts,
        mock_fw,
        mock_v6,
        mock_v4,
        mock_adapters
    ):
        """Test backup_all creates a profile file."""
        mock_adapters.return_value = ["Ethernet", "Wi-Fi"]
        mock_v4.return_value = (["8.8.8.8"], "static")
        mock_v6.return_value = ([], "dhcp")
        
        result = self.manager.backup_all(force=True)
        
        self.assertTrue(result)
        self.assertTrue(self.manager.has_backup())
        
        # Verify profile file exists
        profile_path = self.profile_dir / "system_profile.json"
        self.assertTrue(profile_path.exists())
    
    def test_load_profile_nonexistent(self):
        """Test loading nonexistent profile returns False."""
        result = self.manager.load_profile()
        self.assertFalse(result)
    
    def test_load_profile_existing(self):
        """Test loading existing profile."""
        # Create a profile file
        profile = SystemProfile(
            created_at="2025-01-02T10:00:00",
            hostname="test-pc"
        )
        profile_path = self.profile_dir / "system_profile.json"
        with open(profile_path, 'w') as f:
            json.dump(profile.to_dict(), f)
        
        # Load it
        result = self.manager.load_profile()
        
        self.assertTrue(result)
        loaded = self.manager.get_profile()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.hostname, "test-pc")
    
    def test_add_created_rule(self):
        """Test adding created rules to profile."""
        # First backup
        self.manager._current_profile = SystemProfile()
        
        self.manager.add_created_rule("DNS_Proxy_Test_Rule")
        
        profile = self.manager.get_profile()
        self.assertIn("DNS_Proxy_Test_Rule", profile.firewall.created_rules)
    
    def test_add_created_rules_bulk(self):
        """Test adding multiple rules at once."""
        self.manager._current_profile = SystemProfile()
        
        rules = ["Rule1", "Rule2", "Rule3"]
        self.manager.add_created_rules(rules)
        
        profile = self.manager.get_profile()
        for rule in rules:
            self.assertIn(rule, profile.firewall.created_rules)
    
    def test_ip_address_validation(self):
        """Test IP address validation helpers."""
        self.assertTrue(self.manager._is_ip_address("192.168.1.1"))
        self.assertTrue(self.manager._is_ip_address("8.8.8.8"))
        self.assertTrue(self.manager._is_ip_address("255.255.255.0"))
        
        self.assertFalse(self.manager._is_ip_address("not.an.ip"))
        self.assertFalse(self.manager._is_ip_address("256.1.1.1"))
        self.assertFalse(self.manager._is_ip_address("::1"))
    
    def test_ipv6_address_validation(self):
        """Test IPv6 address validation."""
        self.assertTrue(self.manager._is_ipv6_address("::1"))
        self.assertTrue(self.manager._is_ipv6_address("2001:4860:4860::8888"))
        self.assertTrue(self.manager._is_ipv6_address("fe80::1"))
        
        self.assertFalse(self.manager._is_ipv6_address("192.168.1.1"))
        self.assertFalse(self.manager._is_ipv6_address("not-ipv6"))


class TestDNSFirewallRemoveAllRules(unittest.TestCase):
    """Tests for DNSFirewall.remove_all_rules method."""
    
    def test_remove_all_rules_exists(self):
        """Test that remove_all_rules method exists."""
        from dns_proxy.security.dns_firewall import DNSFirewall
        
        firewall = DNSFirewall()
        self.assertTrue(hasattr(firewall, 'remove_all_rules'))
        self.assertTrue(callable(firewall.remove_all_rules))
    
    @patch('subprocess.run')
    def test_remove_all_rules_calls_remove_rules(self, mock_run):
        """Test remove_all_rules is alias for remove_rules."""
        from dns_proxy.security.dns_firewall import DNSFirewall
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        firewall = DNSFirewall()
        firewall._rules_created = ["Rule1_UDP", "Rule1_TCP"]
        
        result = firewall.remove_all_rules()
        
        # Should return same as remove_rules
        self.assertIsInstance(result, int)
    
    @patch('subprocess.run')
    def test_get_status_method_exists(self, mock_run):
        """Test get_status method returns proper dict."""
        from dns_proxy.security.dns_firewall import DNSFirewall
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        firewall = DNSFirewall()
        status = firewall.get_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn("active", status)
        self.assertIn("total_rules", status)
        self.assertIn("upstream_resolvers", status)
        self.assertIn("proxy_address", status)


class TestSecurityManagerDisable(unittest.TestCase):
    """Tests for SecurityManager.disable method."""
    
    @patch('dns_proxy.security.security_manager.EnhancedDoHBlocker')
    @patch('dns_proxy.security.security_manager.DNSFirewall')
    @patch('dns_proxy.security.security_manager.ProviderUpdater')
    def test_disable_calls_remove_all_rules(
        self,
        mock_updater,
        mock_firewall_cls,
        mock_blocker
    ):
        """Test that disable() calls remove_all_rules on DNSFirewall."""
        from dns_proxy.security.security_manager import (
            SecurityManager,
            SecurityConfig,
            SecurityLevel
        )
        
        # Mock the firewall
        mock_firewall = MagicMock()
        mock_firewall.apply_rules.return_value = True
        mock_firewall_cls.return_value = mock_firewall
        
        # Create manager and enable
        config = SecurityConfig(level=SecurityLevel.STANDARD)
        manager = SecurityManager(config)
        
        # Manually set components
        manager._enabled = True
        manager._dns_firewall = mock_firewall
        
        # Disable
        result = manager.disable()
        
        # Should call remove_all_rules
        mock_firewall.remove_all_rules.assert_called_once()
        self.assertTrue(result)


class TestCleanupAgentFunctions(unittest.TestCase):
    """Tests for cleanup_agent.py functions."""
    
    def test_colors_class_exists(self):
        """Test Colors class has all needed attributes."""
        import cleanup_agent
        
        self.assertTrue(hasattr(cleanup_agent, 'Colors'))
        self.assertTrue(hasattr(cleanup_agent.Colors, 'RED'))
        self.assertTrue(hasattr(cleanup_agent.Colors, 'GREEN'))
        self.assertTrue(hasattr(cleanup_agent.Colors, 'RESET'))
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test run_command on successful execution."""
        import cleanup_agent
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr=""
        )
        
        success, output = cleanup_agent.run_command(["echo", "test"])
        
        self.assertTrue(success)
        self.assertEqual(output, "Success")
    
    @patch('subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test run_command on failed execution."""
        import cleanup_agent
        
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred"
        )
        
        success, output = cleanup_agent.run_command(["bad", "command"])
        
        self.assertFalse(success)
        self.assertEqual(output, "Error occurred")
    
    @patch('subprocess.run')
    def test_run_command_timeout(self, mock_run):
        """Test run_command handles timeout."""
        import subprocess
        import cleanup_agent
        
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)
        
        success, output = cleanup_agent.run_command(["slow", "command"])
        
        self.assertFalse(success)
        self.assertEqual(output, "Command timed out")
    
    @patch('ctypes.windll.shell32.IsUserAnAdmin')
    def test_is_admin_true(self, mock_admin):
        """Test is_admin returns True when admin."""
        import cleanup_agent
        
        mock_admin.return_value = 1
        
        result = cleanup_agent.is_admin()
        self.assertTrue(result)
    
    @patch('ctypes.windll.shell32.IsUserAnAdmin')
    def test_is_admin_false(self, mock_admin):
        """Test is_admin returns False when not admin."""
        import cleanup_agent
        
        mock_admin.return_value = 0
        
        result = cleanup_agent.is_admin()
        self.assertFalse(result)


class TestCleanupWithProfile(unittest.TestCase):
    """Tests for profile-based cleanup."""
    
    def test_profile_manager_available_flag(self):
        """Test PROFILE_MANAGER_AVAILABLE is set correctly."""
        import cleanup_agent
        self.assertTrue(hasattr(cleanup_agent, 'PROFILE_MANAGER_AVAILABLE'))
    
    @patch('cleanup_agent.get_profile_manager')
    @patch('builtins.print')  # Mock print to avoid encoding issues
    def test_cleanup_with_profile_no_backup(self, mock_print, mock_get_manager):
        """Test cleanup_with_profile when no backup exists."""
        import cleanup_agent
        
        if not cleanup_agent.PROFILE_MANAGER_AVAILABLE:
            self.skipTest("Profile manager not available")
        
        mock_manager = MagicMock()
        mock_manager.has_backup.return_value = False
        mock_get_manager.return_value = mock_manager
        
        success, errors = cleanup_agent.cleanup_with_profile()
        
        self.assertFalse(success)
        self.assertIn("No profile backup found", errors)
    
    @patch('cleanup_agent.get_profile_manager')
    @patch('builtins.print')  # Mock print to avoid encoding issues
    def test_cleanup_with_profile_success(self, mock_print, mock_get_manager):
        """Test cleanup_with_profile success case."""
        import cleanup_agent
        
        if not cleanup_agent.PROFILE_MANAGER_AVAILABLE:
            self.skipTest("Profile manager not available")
        
        mock_manager = MagicMock()
        mock_manager.has_backup.return_value = True
        mock_manager.restore_all.return_value = (True, [])
        mock_get_manager.return_value = mock_manager
        
        success, errors = cleanup_agent.cleanup_with_profile()
        
        self.assertTrue(success)
        self.assertEqual(errors, [])
        mock_manager.restore_all.assert_called_once()


class TestUpstreamResolverFirewallIntegration(unittest.TestCase):
    """
    Integration tests for upstream resolver and firewall interaction.
    
    These tests verify that:
    1. Allow rules are created for upstream resolvers
    2. Allow rules are processed before block rules
    3. Upstream resolvers can be reached after rules are applied
    """
    
    @patch('subprocess.run')
    def test_allow_rules_created_for_upstreams(self, mock_run):
        """Test that allow rules are created for each upstream resolver."""
        from dns_proxy.security.dns_firewall import DNSFirewall, DNSFirewallConfig
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        config = DNSFirewallConfig(
            upstream_resolvers=["8.8.8.8", "1.1.1.1", "208.67.222.222"]
        )
        firewall = DNSFirewall(config)
        
        result = firewall.apply_rules()
        
        self.assertTrue(result.success)
        
        # Check that netsh was called to create rules for each upstream
        calls = [str(call) for call in mock_run.call_args_list]
        
        # Should have allow rules for upstreams
        self.assertTrue(
            any("8.8.8.8" in str(call) for call in calls),
            "Should create allow rule for 8.8.8.8"
        )
        self.assertTrue(
            any("1.1.1.1" in str(call) for call in calls),
            "Should create allow rule for 1.1.1.1"
        )
    
    @patch('subprocess.run')
    def test_loopback_allow_rule_created(self, mock_run):
        """Test that loopback (127.0.0.1) allow rule is created."""
        from dns_proxy.security.dns_firewall import DNSFirewall
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        firewall = DNSFirewall()
        result = firewall.apply_rules()
        
        # Check for loopback rule
        calls = [str(call) for call in mock_run.call_args_list]
        self.assertTrue(
            any("127.0.0.1" in str(call) for call in calls),
            "Should create allow rule for 127.0.0.1"
        )
    
    @patch('subprocess.run')
    def test_block_all_rule_created(self, mock_run):
        """Test that block-all DNS rule is created."""
        from dns_proxy.security.dns_firewall import DNSFirewall
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        firewall = DNSFirewall()
        result = firewall.apply_rules()
        
        # Check for block rule
        calls = [str(call) for call in mock_run.call_args_list]
        self.assertTrue(
            any("block" in str(call).lower() for call in calls),
            "Should create block rule"
        )


class TestRestoreHostsFile(unittest.TestCase):
    """Tests for hosts file restoration."""
    
    @patch('builtins.print')  # Mock print to avoid encoding issues
    def test_restore_hosts_file_no_backup(self, mock_print):
        """Test restore_hosts_file when no backup exists."""
        import cleanup_agent
        
        # Should return True (nothing to restore)
        result = cleanup_agent.restore_hosts_file()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
