"""
Test Runner for DNS Proxy Module
---------------------------------
Run all tests with detailed reporting.

Usage:
    python -m dns_proxy.tests.run_tests
    
    # Or from agent directory:
    python dns_proxy/tests/run_tests.py
"""

import logging
import sys
import time
import unittest
from io import StringIO
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dns_proxy.tests.runner")


class TestResult:
    """Result of a test run."""
    
    def __init__(self, name: str, passed: bool, duration: float, error: str = None):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.error = error


class TestReport:
    """Generate test report."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time: float = 0
        self.end_time: float = 0
    
    def add_result(self, result: TestResult):
        """Add test result."""
        self.results.append(result)
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    def generate_summary(self) -> str:
        """Generate summary text."""
        lines = [
            "",
            "=" * 70,
            "DNS PROXY TEST SUMMARY",
            "=" * 70,
            "",
            f"Total Tests:  {self.total}",
            f"Passed:       {self.passed} ({100*self.passed/max(1,self.total):.1f}%)",
            f"Failed:       {self.failed} ({100*self.failed/max(1,self.total):.1f}%)",
            f"Duration:     {self.duration:.2f}s",
            "",
        ]
        
        if self.failed > 0:
            lines.append("FAILED TESTS:")
            lines.append("-" * 40)
            for r in self.results:
                if not r.passed:
                    lines.append(f"  ✗ {r.name}")
                    if r.error:
                        lines.append(f"    Error: {r.error[:100]}")
            lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


def discover_and_run_tests(
    pattern: str = "test*.py",
    verbosity: int = 2
) -> Tuple[unittest.TestResult, TestReport]:
    """
    Discover and run all tests.
    
    Args:
        pattern: Test file pattern
        verbosity: Output verbosity (0-2)
        
    Returns:
        Tuple of (unittest result, report)
    """
    report = TestReport()
    report.start_time = time.time()
    
    # Discover tests
    loader = unittest.TestLoader()
    
    try:
        suite = loader.discover(
            start_dir='.',
            pattern=pattern,
            top_level_dir=None
        )
    except Exception as e:
        logger.error(f"Failed to discover tests: {e}")
        # Try importing directly
        suite = unittest.TestSuite()
        
        try:
            from . import test_dns_proxy
            suite.addTests(loader.loadTestsFromModule(test_dns_proxy))
        except ImportError:
            pass
        
        try:
            from . import test_integration
            suite.addTests(loader.loadTestsFromModule(test_integration))
        except ImportError:
            pass
        
        try:
            from . import test_failures
            suite.addTests(loader.loadTestsFromModule(test_failures))
        except ImportError:
            pass
        
        try:
            from . import test_performance
            suite.addTests(loader.loadTestsFromModule(test_performance))
        except ImportError:
            pass
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    report.end_time = time.time()
    
    # Process results
    for test, error in result.failures + result.errors:
        report.add_result(TestResult(
            name=str(test),
            passed=False,
            duration=0,
            error=error[:200] if error else None
        ))
    
    # Add passed tests
    for test in result.successes if hasattr(result, 'successes') else []:
        report.add_result(TestResult(
            name=str(test),
            passed=True,
            duration=0
        ))
    
    # If we don't have successes attribute, estimate from totals
    if not hasattr(result, 'successes'):
        passed_count = result.testsRun - len(result.failures) - len(result.errors)
        for i in range(passed_count):
            report.add_result(TestResult(
                name=f"test_{i}",
                passed=True,
                duration=0
            ))
    
    return result, report


def run_specific_tests(
    test_names: List[str],
    verbosity: int = 2
) -> Tuple[unittest.TestResult, TestReport]:
    """
    Run specific test classes or methods.
    
    Args:
        test_names: List of test class or method names
        verbosity: Output verbosity
        
    Returns:
        Tuple of (result, report)
    """
    report = TestReport()
    report.start_time = time.time()
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Import test modules
    test_modules = {
        'test_dns_proxy': None,
        'test_integration': None,
        'test_failures': None,
        'test_performance': None,
    }
    
    try:
        from . import test_dns_proxy
        test_modules['test_dns_proxy'] = test_dns_proxy
    except ImportError:
        pass
    
    try:
        from . import test_integration
        test_modules['test_integration'] = test_integration
    except ImportError:
        pass
    
    try:
        from . import test_failures
        test_modules['test_failures'] = test_failures
    except ImportError:
        pass
    
    try:
        from . import test_performance
        test_modules['test_performance'] = test_performance
    except ImportError:
        pass
    
    # Find and add requested tests
    for name in test_names:
        found = False
        
        for module_name, module in test_modules.items():
            if module is None:
                continue
            
            if hasattr(module, name):
                test_class = getattr(module, name)
                if isinstance(test_class, type) and issubclass(test_class, unittest.TestCase):
                    suite.addTests(loader.loadTestsFromTestCase(test_class))
                    found = True
                    break
        
        if not found:
            logger.warning(f"Test not found: {name}")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    report.end_time = time.time()
    
    return result, report


def run_category(category: str, verbosity: int = 2) -> Tuple[unittest.TestResult, TestReport]:
    """
    Run tests by category.
    
    Categories:
    - unit: Unit tests
    - integration: Integration tests
    - failure: Failure scenario tests
    - performance: Performance tests
    - all: All tests
    
    Args:
        category: Test category
        verbosity: Output verbosity
        
    Returns:
        Tuple of (result, report)
    """
    categories = {
        'unit': [
            'TestDNSCache', 'TestDNSCacheFailures',
            'TestUpstreamResolver', 'TestUpstreamResolverFailures',
            'TestDNSQueryHandler', 'TestDNSQueryHandlerFailures',
            'TestFirewallSync', 'TestFirewallSyncFailures',
            'TestNetworkManager', 'TestNetworkManagerFailures',
            'TestSecurityManager', 'TestSecurityManagerFailures',
            'TestEnhancedFirewallSync',
            'TestTTLCleanupManager', 'TestTTLCleanupFailures',
        ],
        'integration': [
            'TestDNSProxyIntegration',
            'TestDNSQueryFlow',
            'TestFirewallRuleLifecycle',
            'TestNetworkConfiguration',
            'TestMigrationFlow',
            'TestStatusReporting',
        ],
        'failure': [
            'TestDNSResolutionFailures',
            'TestFirewallFailures',
            'TestNetworkConfigurationFailures',
            'TestWhitelistFailures',
            'TestStartupFailures',
            'TestOrchestratorFailures',
            'TestMigrationFailures',
            'TestRecoveryScenarios',
        ],
        'performance': [
            'TestCachePerformance',
            'TestWhitelistPerformance',
            'TestFirewallPerformance',
            'TestEndToEndPerformance',
            'TestMemoryPerformance',
            'TestLatencyPerformance',
        ],
    }
    
    if category == 'all':
        return discover_and_run_tests(verbosity=verbosity)
    
    if category not in categories:
        logger.error(f"Unknown category: {category}")
        logger.info(f"Available categories: {', '.join(categories.keys())}")
        return None, None
    
    return run_specific_tests(categories[category], verbosity=verbosity)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='DNS Proxy Test Runner')
    parser.add_argument(
        '-c', '--category',
        choices=['unit', 'integration', 'failure', 'performance', 'all'],
        default='all',
        help='Test category to run'
    )
    parser.add_argument(
        '-v', '--verbosity',
        type=int,
        choices=[0, 1, 2],
        default=2,
        help='Output verbosity'
    )
    parser.add_argument(
        '-t', '--test',
        action='append',
        help='Specific test class to run (can be repeated)'
    )
    
    args = parser.parse_args()
    
    print()
    print("=" * 70)
    print("DNS PROXY TEST SUITE")
    print("=" * 70)
    print()
    
    if args.test:
        result, report = run_specific_tests(args.test, args.verbosity)
    else:
        result, report = run_category(args.category, args.verbosity)
    
    if report:
        print(report.generate_summary())
    
    # Exit with appropriate code
    if result and (result.failures or result.errors):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
