# DNS Proxy Test Suite

## Overview

Comprehensive test suite for the DNS Proxy/Sinkhole system, covering:
- Unit tests for individual components
- Integration tests for component interaction
- Failure scenario tests for error handling
- Performance tests for load testing

## Test Structure

```
dns_proxy/tests/
├── __init__.py           # Package exports
├── mocks.py              # Mock objects for testing
├── test_dns_proxy.py     # Unit tests
├── test_integration.py   # Integration tests
├── test_failures.py      # Failure scenario tests
├── test_performance.py   # Performance tests
└── run_tests.py          # Test runner
```

## Running Tests

### Run All Tests

```bash
# From agent directory
cd agent

# Using pytest (recommended)
python -m pytest dns_proxy/tests/ -v

# Using unittest
python -m unittest discover dns_proxy/tests/

# Using test runner
python -m dns_proxy.tests.run_tests
```

### Run by Category

```bash
# Unit tests only
python -m dns_proxy.tests.run_tests -c unit

# Integration tests
python -m dns_proxy.tests.run_tests -c integration

# Failure scenario tests
python -m dns_proxy.tests.run_tests -c failure

# Performance tests
python -m dns_proxy.tests.run_tests -c performance
```

### Run Specific Tests

```bash
# Run specific test class
python -m dns_proxy.tests.run_tests -t TestDNSCache -t TestFirewallSync

# Using pytest
python -m pytest dns_proxy/tests/test_dns_proxy.py::TestDNSCache -v
```

### With Coverage

```bash
# Install coverage
pip install pytest-cov

# Run with coverage
python -m pytest dns_proxy/tests/ --cov=dns_proxy --cov-report=html

# View report
open htmlcov/index.html
```

## Test Categories

### Unit Tests (`test_dns_proxy.py`)

Tests individual components in isolation:

| Test Class | Component | Coverage |
|------------|-----------|----------|
| `TestDNSCache` | DNS Cache | Set, get, expiry, eviction |
| `TestUpstreamResolver` | Upstream Resolver | Resolution, timeout, failover |
| `TestDNSQueryHandler` | Query Handler | Whitelist check, blocking |
| `TestFirewallSync` | Firewall Sync | Rule add/remove |
| `TestNetworkManager` | Network Manager | Adapter detection, DNS set |
| `TestSecurityManager` | Security Manager | DoH blocking, levels |
| `TestEnhancedFirewallSync` | Enhanced Firewall | Profile binding |
| `TestTTLCleanupManager` | TTL Cleanup | Grace period, batch cleanup |
| `TestDNSProxyOrchestrator` | Orchestrator | Component coordination |
| `TestStartupSequence` | Startup | Preflight checks |
| `TestMigrationHelper` | Migration | State transitions |
| `TestStatusReporter` | Status | Health reporting |

### Integration Tests (`test_integration.py`)

Tests component interactions:

| Test Class | Scope |
|------------|-------|
| `TestDNSProxyIntegration` | Full system integration |
| `TestDNSQueryFlow` | Complete query flow |
| `TestFirewallRuleLifecycle` | Rule creation/cleanup |
| `TestNetworkConfiguration` | DNS configuration |
| `TestMigrationFlow` | Migration process |
| `TestStatusReporting` | Health monitoring |

### Failure Tests (`test_failures.py`)

Tests error handling and recovery:

| Test Class | Scenarios |
|------------|-----------|
| `TestDNSResolutionFailures` | Server failures, timeout |
| `TestFirewallFailures` | Rule failures, no admin |
| `TestNetworkConfigurationFailures` | Adapter not found |
| `TestWhitelistFailures` | Empty whitelist, sync failure |
| `TestStartupFailures` | Port in use, no admin |
| `TestOrchestratorFailures` | Component crashes |
| `TestMigrationFailures` | Rollback scenarios |
| `TestRecoveryScenarios` | Graceful degradation |

### Performance Tests (`test_performance.py`)

Tests system performance:

| Test Class | Metrics |
|------------|---------|
| `TestCachePerformance` | Insert/lookup ops/s |
| `TestWhitelistPerformance` | Domain check ops/s |
| `TestFirewallPerformance` | Rule ops/s |
| `TestEndToEndPerformance` | Full flow latency |
| `TestLatencyPerformance` | p50/p95/p99 latency |

## Mock Objects

Available mocks in `mocks.py`:

```python
from dns_proxy.tests.mocks import (
    MockDNSResolver,      # Mock DNS resolver
    MockDNSResponse,      # Mock DNS response
    MockWhitelistState,   # Mock whitelist
    MockFirewallManager,  # Mock firewall
    MockNetworkManager,   # Mock network
    MockNetworkAdapter,   # Mock adapter
    MockUDPServer,        # Mock UDP server
    MockSubprocess,       # Mock subprocess
    MockTime,             # Mock time
)

# Test fixtures
from dns_proxy.tests.mocks import (
    create_test_whitelist,  # Typical whitelist
    create_test_resolver,   # Typical resolver
    create_test_adapters,   # Typical adapters
)
```

### Usage Example

```python
import unittest
from dns_proxy.tests.mocks import (
    MockWhitelistState,
    MockFirewallManager,
    MockDNSResolver,
)

class TestMyComponent(unittest.TestCase):
    def setUp(self):
        self.whitelist = MockWhitelistState(
            allowed_domains=["example.com"],
            allowed_patterns=["*.google.com"],
        )
        self.firewall = MockFirewallManager()
        self.resolver = MockDNSResolver()
    
    def test_allowed_domain(self):
        # Test with mocks
        self.assertTrue(self.whitelist.is_domain_allowed("example.com"))
        
        response = self.resolver.resolve("example.com")
        self.assertTrue(response.success)
        
        for ip in response.ips:
            self.assertTrue(self.firewall.add_rule(ip, 300))
```

## Writing New Tests

### Template for Success Tests

```python
class TestMyComponent(unittest.TestCase):
    """Tests for MyComponent."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize mocks and component
        pass
    
    def test_basic_operation(self):
        """Test basic operation succeeds."""
        # Arrange
        # Act
        # Assert
        pass
```

### Template for Failure Tests

```python
class TestMyComponentFailures(unittest.TestCase):
    """Failure tests for MyComponent."""
    
    def test_handles_error_gracefully(self):
        """Test error is handled without crash."""
        # Set up failure condition
        # Execute operation
        # Verify graceful handling
        pass
```

## Test Requirements

```
pytest>=7.0.0
pytest-cov>=4.0.0
unittest-mock>=3.8
```

## CI Integration

Add to GitHub Actions:

```yaml
- name: Run DNS Proxy Tests
  run: |
    python -m pytest dns_proxy/tests/ -v --tb=short
```

## Performance Baselines

Expected performance on typical hardware:

| Operation | Target | Unit |
|-----------|--------|------|
| Cache insert | >1000 | ops/s |
| Cache lookup | >5000 | ops/s |
| Whitelist check | >10000 | ops/s |
| Pattern match | >1000 | ops/s |
| Full query flow | <1ms | latency |
| Concurrent queries | >500 | qps |
