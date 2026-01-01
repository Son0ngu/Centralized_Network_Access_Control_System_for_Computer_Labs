"""
DNS Proxy Tests - __init__.py
-----------------------------
Test suite package for DNS Proxy module.

Test Modules:
- test_dns_proxy: Unit tests for individual components
- test_integration: Integration tests for component interaction
- test_failures: Failure scenario tests
- test_performance: Performance and load tests

Usage:
    # Run all tests
    python -m pytest dns_proxy/tests/
    
    # Run specific test module
    python -m pytest dns_proxy/tests/test_failures.py
    
    # Run with coverage
    python -m pytest dns_proxy/tests/ --cov=dns_proxy
"""

# Import mocks for test utilities
from .mocks import (
    MockDNSQuery,
    MockDNSResponse,
    MockDNSResolver,
    MockWhitelistState,
    MockFirewallManager,
    MockFirewallRule,
    MockNetworkAdapter,
    MockNetworkManager,
    MockUDPServer,
    MockSubprocess,
    MockCompletedProcess,
    MockTime,
    create_test_whitelist,
    create_test_resolver,
    create_test_adapters,
)

# Import main test classes
from .test_dns_proxy import (
    # Unit test classes
    TestDNSCache,
    TestDNSCacheFailures,
    TestUpstreamResolver,
    TestUpstreamResolverFailures,
    TestDNSQueryHandler,
    TestDNSQueryHandlerFailures,
    TestFirewallSync,
    TestFirewallSyncFailures,
    TestNetworkManager,
    TestNetworkManagerFailures,
    TestSecurityManager,
    TestSecurityManagerFailures,
    TestEnhancedFirewallSync,
    TestTTLCleanupManager,
    TestTTLCleanupFailures,
    TestDNSProxyOrchestrator,
    TestStartupSequence,
    TestStartupSequenceFailures,
    TestMigrationHelper,
    TestMigrationHelperFailures,
    TestStatusReporter,
    TestEndToEndSuccess,
    TestEndToEndFailures,
    TestPerformance,
    run_all_tests,
)

# Import integration tests
from .test_integration import (
    TestDNSProxyIntegration,
    TestDNSQueryFlow,
    TestFirewallRuleLifecycle,
    TestNetworkConfiguration,
    TestMigrationFlow,
    TestStatusReporting,
)

# Import failure tests
from .test_failures import (
    TestDNSResolutionFailures,
    TestFirewallFailures,
    TestNetworkConfigurationFailures,
    TestWhitelistFailures,
    TestStartupFailures,
    TestOrchestratorFailures,
    TestMigrationFailures,
    TestRecoveryScenarios,
)

# Import performance tests
from .test_performance import (
    TestCachePerformance,
    TestWhitelistPerformance,
    TestFirewallPerformance,
    TestEndToEndPerformance,
    TestMemoryPerformance,
    TestLatencyPerformance,
    PerformanceReport,
)

__all__ = [
    # Mocks
    "MockDNSQuery",
    "MockDNSResponse",
    "MockDNSResolver",
    "MockWhitelistState",
    "MockFirewallManager",
    "MockFirewallRule",
    "MockNetworkAdapter",
    "MockNetworkManager",
    "MockUDPServer",
    "MockSubprocess",
    "MockCompletedProcess",
    "MockTime",
    "create_test_whitelist",
    "create_test_resolver",
    "create_test_adapters",
    
    # Unit Tests - Success
    "TestDNSCache",
    "TestUpstreamResolver",
    "TestDNSQueryHandler",
    "TestFirewallSync",
    "TestNetworkManager",
    "TestSecurityManager",
    "TestEnhancedFirewallSync",
    "TestTTLCleanupManager",
    "TestDNSProxyOrchestrator",
    "TestStartupSequence",
    "TestMigrationHelper",
    "TestStatusReporter",
    "TestEndToEndSuccess",
    "TestPerformance",
    
    # Unit Tests - Failures
    "TestDNSCacheFailures",
    "TestUpstreamResolverFailures",
    "TestDNSQueryHandlerFailures",
    "TestFirewallSyncFailures",
    "TestNetworkManagerFailures",
    "TestSecurityManagerFailures",
    "TestTTLCleanupFailures",
    "TestStartupSequenceFailures",
    "TestMigrationHelperFailures",
    "TestEndToEndFailures",
    
    # Integration Tests
    "TestDNSProxyIntegration",
    "TestDNSQueryFlow",
    "TestFirewallRuleLifecycle",
    "TestNetworkConfiguration",
    "TestMigrationFlow",
    "TestStatusReporting",
    
    # Failure Scenario Tests
    "TestDNSResolutionFailures",
    "TestFirewallFailures",
    "TestNetworkConfigurationFailures",
    "TestWhitelistFailures",
    "TestStartupFailures",
    "TestOrchestratorFailures",
    "TestMigrationFailures",
    "TestRecoveryScenarios",
    
    # Performance Tests
    "TestCachePerformance",
    "TestWhitelistPerformance",
    "TestFirewallPerformance",
    "TestEndToEndPerformance",
    "TestMemoryPerformance",
    "TestLatencyPerformance",
    "PerformanceReport",
    
    # Runner
    "run_all_tests",
]
