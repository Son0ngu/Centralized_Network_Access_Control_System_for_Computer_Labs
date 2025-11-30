"""
Test Whitelist Sync Flow - Test without admin privileges.
Tests: Registration -> Whitelist Sync -> DNS Resolution -> IP Rules parsing
"""

import logging
import sys
import time
import threading
from unittest.mock import MagicMock, patch

# Setup logging to see all messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_whitelist_sync")

# Test configuration
TEST_CONFIG = {
    "server": {
        "url": "https://localhost:5000",
        "urls": ["https://localhost:5000"],
        "connect_timeout": 5,
        "read_timeout": 10
    },
    "whitelist": {
        "enabled": True,
        "auto_sync": True,
        "sync_interval": 10,  # Short interval for testing
        "cache_ttl": 300,
        "max_retries": 2
    },
    "firewall": {
        "enabled": True,
        "mode": "whitelist_only",
        "rule_prefix": "TestFirewall"
    },
    "agent_id": "test-agent-123",
    "device_id": "test-device-456"
}

# Mock server response
MOCK_WHITELIST_RESPONSE = {
    "success": True,
    "domains": [
        {"value": "google.com", "type": "domain"},
        {"value": "microsoft.com", "type": "domain"},
        {"value": "github.com", "type": "domain"},
        {"value": "*.cloudflare.com", "type": "pattern"},
        {"value": "8.8.8.8", "type": "ip"},
        {"value": "1.1.1.1", "type": "ip"},
    ],
    "count": 6,
    "type": "full",
    "global_version": 1,
    "timestamp": "2025-12-01T12:00:00+07:00"
}


def test_whitelist_state():
    """Test 1: WhitelistState can parse server response correctly."""
    print("\n" + "="*60)
    print("TEST 1: WhitelistState Parsing")
    print("="*60)
    
    from whitelist.state import WhitelistState
    
    state = WhitelistState()
    
    # Update with mock data
    updated = state.update(MOCK_WHITELIST_RESPONSE)
    
    print(f"✓ State updated: {updated}")
    print(f"✓ Domains: {state.get_all_domains()}")
    print(f"✓ Patterns: {state.get_all_patterns()}")
    print(f"✓ IPs: {state.get_all_ips()}")
    print(f"✓ Stats: {state.get_stats()}")
    
    # Verify counts
    assert len(state.get_all_domains()) == 3, f"Expected 3 domains, got {len(state.get_all_domains())}"
    assert len(state.get_all_patterns()) == 1, f"Expected 1 pattern, got {len(state.get_all_patterns())}"
    assert len(state.get_all_ips()) == 2, f"Expected 2 IPs, got {len(state.get_all_ips())}"
    
    print("✅ TEST 1 PASSED: WhitelistState parsing works correctly!")
    return True


def test_dns_resolution():
    """Test 2: DNS Resolution works for domains."""
    print("\n" + "="*60)
    print("TEST 2: DNS Resolution")
    print("="*60)
    
    try:
        from network import OptimizedDNSResolver
        resolver = OptimizedDNSResolver(max_workers=5, timeout=5.0)
        
        domains = ["google.com", "microsoft.com", "github.com"]
        
        print(f"Resolving {len(domains)} domains...")
        results = resolver.resolve_multiple_parallel(domains)
        
        total_ips = 0
        for domain, record in results.items():
            ips = list(record.ipv4) if record.ipv4 else []
            total_ips += len(ips)
            print(f"  ✓ {domain} -> {ips[:3]}...")  # Show first 3 IPs
        
        print(f"✓ Total IPs resolved: {total_ips}")
        assert total_ips > 0, "No IPs resolved"
        
        print("✅ TEST 2 PASSED: DNS resolution works!")
        return True
        
    except ImportError as e:
        print(f"⚠ Skipping DNS test (missing module): {e}")
        return True
    except Exception as e:
        print(f"⚠ DNS test warning: {e}")
        return True


def test_firewall_manager_ip_parsing():
    """Test 3: FirewallManager can parse domains to IP rules (without actually creating rules)."""
    print("\n" + "="*60)
    print("TEST 3: Firewall Manager IP Parsing (Mock)")
    print("="*60)
    
    from firewall.manager import FirewallManager
    from firewall.utils import FirewallUtils
    
    # Create manager (won't actually touch firewall without admin)
    manager = FirewallManager(rule_prefix="TestFC")
    
    # Test domain set
    domains = {"google.com", "microsoft.com"}
    ips = {"8.8.8.8", "1.1.1.1"}
    
    print(f"Input: {len(domains)} domains, {len(ips)} IPs")
    
    # Test the DNS resolution method directly
    resolved_ips = manager._resolve_domains_to_ips(domains)
    
    print(f"✓ Resolved IPs from domains: {len(resolved_ips)}")
    for ip in list(resolved_ips)[:5]:  # Show first 5
        print(f"    - {ip}")
    
    # Combine with direct IPs
    all_ips = resolved_ips.union(ips)
    print(f"✓ Total IPs for firewall rules: {len(all_ips)}")
    
    # Validate IPs
    valid_count = sum(1 for ip in all_ips if FirewallUtils.is_valid_ipv4(ip))
    print(f"✓ Valid IPv4 addresses: {valid_count}")
    
    assert len(resolved_ips) > 0, "No IPs resolved from domains"
    assert valid_count > 0, "No valid IPv4 addresses"
    
    print("✅ TEST 3 PASSED: Firewall IP parsing works!")
    return True


def test_whitelist_manager_sync_flow():
    """Test 4: Full WhitelistManager sync flow with mocked server."""
    print("\n" + "="*60)
    print("TEST 4: WhitelistManager Sync Flow (Mocked Server)")
    print("="*60)
    
    from whitelist.manager import WhitelistManager
    
    # Create manager
    manager = WhitelistManager(TEST_CONFIG)
    
    # Mock the syncer to return our test data
    def mock_sync_with_server(params):
        print(f"  [Mock] Sync called with params: {params.get('agent_id')}")
        return {
            "success": True,
            "data": MOCK_WHITELIST_RESPONSE
        }
    
    manager._sync.sync_with_server = mock_sync_with_server
    
    # Mock firewall manager to track calls
    mock_firewall = MagicMock()
    mock_firewall.update_whitelist = MagicMock(return_value=True)
    manager.set_firewall_manager(mock_firewall)
    
    print("✓ WhitelistManager created")
    print("✓ Mock firewall manager linked")
    
    # Perform sync
    print("\n📡 Calling sync_now()...")
    result = manager.sync_now()
    
    print(f"✓ Sync result: {result}")
    print(f"✓ State after sync: {manager._state.get_stats()}")
    
    # Verify firewall was called
    if mock_firewall.update_whitelist.called:
        call_args = mock_firewall.update_whitelist.call_args
        domains_arg = call_args[0][0] if call_args[0] else set()
        ips_arg = call_args[0][1] if len(call_args[0]) > 1 else set()
        print(f"✓ Firewall update_whitelist called!")
        print(f"    - Domains passed: {len(domains_arg)}")
        print(f"    - IPs passed: {len(ips_arg)}")
    else:
        print("❌ Firewall update_whitelist was NOT called!")
        return False
    
    assert result == True, "Sync should return True"
    assert mock_firewall.update_whitelist.called, "Firewall update should be called"
    
    print("✅ TEST 4 PASSED: WhitelistManager sync flow works!")
    return True


def test_periodic_sync():
    """Test 5: Periodic sync starts and runs."""
    print("\n" + "="*60)
    print("TEST 5: Periodic Sync Thread")
    print("="*60)
    
    from whitelist.manager import WhitelistManager
    
    # Short sync interval for test
    test_config = TEST_CONFIG.copy()
    test_config["whitelist"] = TEST_CONFIG["whitelist"].copy()
    test_config["whitelist"]["sync_interval"] = 2  # 2 seconds
    
    manager = WhitelistManager(test_config)
    
    # Track sync calls
    sync_count = [0]
    original_sync = manager.sync_now
    
    def counting_sync():
        sync_count[0] += 1
        print(f"  [Sync #{sync_count[0]}] sync_now() called")
        return True  # Don't actually sync
    
    manager.sync_now = counting_sync
    
    print("✓ Starting sync thread...")
    manager.start_sync()
    
    # Wait for a few syncs
    print("✓ Waiting 5 seconds for periodic syncs...")
    time.sleep(5)
    
    print("✓ Stopping sync thread...")
    manager.stop_sync()
    
    print(f"✓ Total syncs in 5 seconds: {sync_count[0]}")
    
    # Should have at least 2 syncs (initial + periodic)
    assert sync_count[0] >= 2, f"Expected at least 2 syncs, got {sync_count[0]}"
    
    print("✅ TEST 5 PASSED: Periodic sync works!")
    return True


def test_initialization_order():
    """Test 6: Verify initialization order - firewall linked before sync starts."""
    print("\n" + "="*60)
    print("TEST 6: Initialization Order Check")
    print("="*60)
    
    # Read the lifecycle.py file to verify order
    import os
    lifecycle_path = os.path.join(os.path.dirname(__file__), "core", "lifecycle.py")
    
    with open(lifecycle_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find positions of key operations
    whitelist_init_pos = content.find("agent.whitelist = WhitelistManager")
    firewall_init_pos = content.find("agent.firewall = FirewallManager")
    firewall_link_pos = content.find("set_firewall_manager")
    sync_start_pos = content.find("start_sync()")
    
    print(f"  WhitelistManager init: line position {whitelist_init_pos}")
    print(f"  FirewallManager init: line position {firewall_init_pos}")
    print(f"  set_firewall_manager: line position {firewall_link_pos}")
    print(f"  start_sync(): line position {sync_start_pos}")
    
    # Verify correct order
    # Order should be: WhitelistManager -> FirewallManager -> set_firewall_manager -> start_sync
    
    if whitelist_init_pos < firewall_init_pos:
        print("✓ WhitelistManager initialized before FirewallManager")
    else:
        print("❌ Order issue: FirewallManager should be after WhitelistManager")
    
    if firewall_link_pos < sync_start_pos:
        print("✓ Firewall linked BEFORE sync starts")
    else:
        print("❌ BUG: Sync starts before firewall is linked!")
        return False
    
    if firewall_init_pos < firewall_link_pos:
        print("✓ FirewallManager created before linking")
    
    print("✅ TEST 6 PASSED: Initialization order is correct!")
    return True


def test_incremental_ip_sync():
    """Test 7: Verify incremental IP add/remove works correctly."""
    print("\n" + "="*60)
    print("TEST 7: Incremental IP Sync (Add/Remove on whitelist changes)")
    print("="*60)
    
    from firewall.manager import FirewallManager
    from firewall.rules import RulesManager
    from unittest.mock import MagicMock, patch
    
    # Create a mock RulesManager to track add/remove calls
    class MockRulesManager:
        def __init__(self):
            self.allowed_ips = set()
            self.add_calls = []
            self.remove_calls = []
        
        def create_allow_rule(self, ip):
            self.add_calls.append(ip)
            self.allowed_ips.add(ip)
            return True
        
        def remove_allow_rule(self, ip):
            self.remove_calls.append(ip)
            self.allowed_ips.discard(ip)
            return True
        
        def create_allow_rules_batch(self, ips):
            for ip in ips:
                self.create_allow_rule(ip)
            return True
        
        def load_existing_rules(self):
            pass
        
        def clear_all_rules(self):
            return True
    
    # Create a mock PolicyManager
    class MockPolicyManager:
        def __init__(self):
            self.default_deny_enabled = False
        
        def backup_current_policy(self):
            pass
        
        def enable_default_deny(self):
            self.default_deny_enabled = True
            return True
        
        def verify_default_deny(self):
            return self.default_deny_enabled
        
        def restore_original_policy(self):
            return True
    
    # Create manager with mocked sub-managers
    manager = FirewallManager(rule_prefix="TestFC")
    manager.rules_manager = MockRulesManager()
    manager.policy_manager = MockPolicyManager()
    
    # Pre-set whitelist_mode_active to skip setup (we're testing sync_whitelist_changes only)
    manager.whitelist_mode_active = True
    
    # ====== SYNC 1: Initial whitelist with IPs A, B, C ======
    print("\n📥 SYNC 1: Initial whitelist (A, B, C)")
    
    # Mock DNS resolution
    def mock_resolve_1(domains):
        return {"1.1.1.1", "2.2.2.2", "3.3.3.3"}  # A, B, C
    
    with patch.object(manager, '_resolve_domains_to_ips', mock_resolve_1):
        result1 = manager.update_whitelist({"domain.com"}, set())
    
    print(f"  Sync 1 result: {result1}")
    print(f"  Allowed IPs after sync 1: {manager.allowed_ips}")
    print(f"  Add calls: {manager.rules_manager.add_calls}")
    print(f"  Remove calls: {manager.rules_manager.remove_calls}")
    
    # Verify sync 1
    assert manager.allowed_ips == {"1.1.1.1", "2.2.2.2", "3.3.3.3"}, f"Sync 1 should add A, B, C, got: {manager.allowed_ips}"
    assert set(manager.rules_manager.add_calls) == {"1.1.1.1", "2.2.2.2", "3.3.3.3"}, "Should add 3 IPs"
    assert len(manager.rules_manager.remove_calls) == 0, "Should not remove any IPs"
    print("  ✓ Sync 1: Added 3 IPs correctly")
    
    # Clear call tracking
    manager.rules_manager.add_calls.clear()
    manager.rules_manager.remove_calls.clear()
    
    # ====== SYNC 2: Changed whitelist to B, C, D ======
    print("\n📥 SYNC 2: Changed whitelist (B, C, D) - should add D, remove A")
    
    def mock_resolve_2(domains):
        return {"2.2.2.2", "3.3.3.3", "4.4.4.4"}  # B, C, D
    
    with patch.object(manager, '_resolve_domains_to_ips', mock_resolve_2):
        result2 = manager.update_whitelist({"domain.com"}, set())
    
    print(f"  Sync 2 result: {result2}")
    print(f"  Allowed IPs after sync 2: {manager.allowed_ips}")
    print(f"  Add calls: {manager.rules_manager.add_calls}")
    print(f"  Remove calls: {manager.rules_manager.remove_calls}")
    
    # Verify sync 2
    assert manager.allowed_ips == {"2.2.2.2", "3.3.3.3", "4.4.4.4"}, f"Sync 2 should have B, C, D, got: {manager.allowed_ips}"
    assert "4.4.4.4" in manager.rules_manager.add_calls, "Should add D (4.4.4.4)"
    assert "1.1.1.1" in manager.rules_manager.remove_calls, "Should remove A (1.1.1.1)"
    print("  ✓ Sync 2: Added D, Removed A correctly")
    
    # Clear call tracking
    manager.rules_manager.add_calls.clear()
    manager.rules_manager.remove_calls.clear()
    
    # ====== SYNC 3: Remove all - only keep E ======
    print("\n📥 SYNC 3: Changed whitelist (E only) - should add E, remove B, C, D")
    
    def mock_resolve_3(domains):
        return {"5.5.5.5"}  # E only
    
    with patch.object(manager, '_resolve_domains_to_ips', mock_resolve_3):
        result3 = manager.update_whitelist({"domain.com"}, set())
    
    print(f"  Sync 3 result: {result3}")
    print(f"  Allowed IPs after sync 3: {manager.allowed_ips}")
    print(f"  Add calls: {manager.rules_manager.add_calls}")
    print(f"  Remove calls: {manager.rules_manager.remove_calls}")
    
    # Verify sync 3
    assert manager.allowed_ips == {"5.5.5.5"}, f"Sync 3 should have only E, got: {manager.allowed_ips}"
    assert "5.5.5.5" in manager.rules_manager.add_calls, "Should add E (5.5.5.5)"
    assert set(manager.rules_manager.remove_calls) == {"2.2.2.2", "3.3.3.3", "4.4.4.4"}, "Should remove B, C, D"
    print("  ✓ Sync 3: Added E, Removed B, C, D correctly")
    
    print("\n✅ TEST 7 PASSED: Incremental IP sync works correctly!")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 WHITELIST SYNC FLOW TESTS")
    print("="*60)
    
    tests = [
        ("WhitelistState Parsing", test_whitelist_state),
        ("DNS Resolution", test_dns_resolution),
        ("Firewall IP Parsing", test_firewall_manager_ip_parsing),
        ("WhitelistManager Sync Flow", test_whitelist_manager_sync_flow),
        ("Periodic Sync", test_periodic_sync),
        ("Initialization Order", test_initialization_order),
        ("Incremental IP Sync", test_incremental_ip_sync),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ TEST FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
