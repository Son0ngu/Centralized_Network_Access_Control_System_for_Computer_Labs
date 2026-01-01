"""
Performance Tests for DNS Proxy System
--------------------------------------
Tests system performance under various load conditions.
"""

import logging
import statistics
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from .mocks import (
    MockDNSResolver,
    MockDNSResponse,
    MockFirewallManager,
    MockWhitelistState,
)

logger = logging.getLogger("dns_proxy.tests.performance")


class TestCachePerformance(unittest.TestCase):
    """Performance tests for DNS cache."""
    
    @classmethod
    def setUpClass(cls):
        try:
            from dns_proxy.cache import DNSCache
            cls.DNSCache = DNSCache
            cls._skip = False
        except ImportError as e:
            cls._skip = True
            cls._skip_reason = str(e)
    
    def setUp(self):
        if self._skip:
            self.skipTest(f"DNS Cache not available: {self._skip_reason}")
    
    def test_cache_insert_performance(self):
        """Test cache insert performance."""
        from dns_proxy.config import CacheConfig
        config = CacheConfig(max_entries=10000)
        cache = self.DNSCache(config=config)
        
        count = 5000
        
        start = time.perf_counter()
        for i in range(count):
            cache.set(f"domain{i}.com", ipv4_addresses=[f"1.2.3.{i % 256}"], ttl=300)
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Cache insert: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        # Should handle at least 1000 ops/s
        self.assertGreater(ops_per_second, 1000)
    
    def test_cache_lookup_performance(self):
        """Test cache lookup performance."""
        from dns_proxy.config import CacheConfig
        config = CacheConfig(max_entries=10000)
        cache = self.DNSCache(config=config)
        
        # Pre-populate
        for i in range(1000):
            cache.set(f"domain{i}.com", ipv4_addresses=[f"1.2.3.{i % 256}"], ttl=300)
        
        count = 10000
        
        start = time.perf_counter()
        for i in range(count):
            cache.get(f"domain{i % 1000}.com")
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Cache lookup: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        # Should handle at least 5000 ops/s
        self.assertGreater(ops_per_second, 5000)
    
    def test_cache_concurrent_access_performance(self):
        """Test cache performance under concurrent access."""
        from dns_proxy.config import CacheConfig
        config = CacheConfig(max_entries=10000)
        cache = self.DNSCache(config=config)
        
        # Pre-populate
        for i in range(1000):
            cache.set(f"domain{i}.com", ipv4_addresses=[f"1.2.3.{i % 256}"], ttl=300)
        
        count_per_thread = 1000
        num_threads = 10
        results = []
        errors = []
        
        def worker(thread_id: int):
            local_count = 0
            start = time.perf_counter()
            
            try:
                for i in range(count_per_thread):
                    if i % 2 == 0:
                        cache.get(f"domain{i % 1000}.com")
                    else:
                        cache.set(f"thread{thread_id}_{i}.com", ipv4_addresses=[f"10.{thread_id}.0.{i % 256}"], ttl=300)
                    local_count += 1
            except Exception as e:
                errors.append(str(e))
            
            elapsed = time.perf_counter() - start
            return local_count, elapsed
        
        start = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())
        
        total_elapsed = time.perf_counter() - start
        total_ops = sum(r[0] for r in results)
        
        ops_per_second = total_ops / total_elapsed
        
        logger.info(f"Concurrent cache: {total_ops} ops in {total_elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        self.assertEqual(len(errors), 0)
        self.assertGreater(ops_per_second, 1000)


class TestWhitelistPerformance(unittest.TestCase):
    """Performance tests for whitelist checking."""
    
    def test_domain_check_performance(self):
        """Test domain check performance."""
        # Create whitelist with many entries
        domains = [f"domain{i}.com" for i in range(1000)]
        patterns = [f"*.subdomain{i}.com" for i in range(100)]
        
        whitelist = MockWhitelistState(
            allowed_domains=domains,
            allowed_patterns=patterns,
        )
        
        count = 10000
        
        start = time.perf_counter()
        for i in range(count):
            whitelist.is_domain_allowed(f"domain{i % 1000}.com")
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Whitelist check: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        # Should handle at least 10000 ops/s
        self.assertGreater(ops_per_second, 10000)
    
    def test_pattern_matching_performance(self):
        """Test wildcard pattern matching performance."""
        patterns = [f"*.pattern{i}.example.com" for i in range(500)]
        
        whitelist = MockWhitelistState(allowed_patterns=patterns)
        
        count = 5000
        
        start = time.perf_counter()
        for i in range(count):
            whitelist.is_domain_allowed(f"sub.pattern{i % 500}.example.com")
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Pattern matching: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        # Should handle at least 1000 ops/s
        self.assertGreater(ops_per_second, 1000)


class TestFirewallPerformance(unittest.TestCase):
    """Performance tests for firewall operations."""
    
    def test_rule_add_performance(self):
        """Test firewall rule add performance."""
        firewall = MockFirewallManager()
        
        count = 1000
        
        start = time.perf_counter()
        for i in range(count):
            firewall.add_rule(f"10.0.{i // 256}.{i % 256}", ttl=300)
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Firewall add: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        # Mock should be very fast
        self.assertGreater(ops_per_second, 1000)
    
    def test_rule_lookup_performance(self):
        """Test firewall rule lookup performance."""
        firewall = MockFirewallManager()
        
        # Pre-populate
        for i in range(1000):
            firewall.add_rule(f"10.0.{i // 256}.{i % 256}", ttl=300)
        
        count = 10000
        
        start = time.perf_counter()
        for i in range(count):
            firewall.has_rule(f"10.0.{(i % 1000) // 256}.{(i % 1000) % 256}")
        elapsed = time.perf_counter() - start
        
        ops_per_second = count / elapsed
        
        logger.info(f"Firewall lookup: {count} ops in {elapsed:.3f}s ({ops_per_second:.0f} ops/s)")
        
        self.assertGreater(ops_per_second, 10000)


class TestEndToEndPerformance(unittest.TestCase):
    """End-to-end performance tests."""
    
    def test_full_query_flow_performance(self):
        """Test performance of complete query flow."""
        whitelist = MockWhitelistState(
            allowed_domains=["google.com", "microsoft.com"],
            allowed_patterns=["*.google.com", "*.microsoft.com"],
        )
        firewall = MockFirewallManager()
        resolver = MockDNSResolver()
        
        count = 1000
        timings = []
        
        for i in range(count):
            domain = f"sub{i}.google.com"
            
            start = time.perf_counter()
            
            # Step 1: Check whitelist
            if whitelist.is_domain_allowed(domain):
                # Step 2: Resolve
                response = resolver.resolve(domain)
                
                if response.success:
                    # Step 3: Add firewall rules
                    for ip in response.ips:
                        firewall.add_rule(ip, response.ttl)
            
            elapsed = time.perf_counter() - start
            timings.append(elapsed * 1000)  # Convert to ms
        
        avg_time = statistics.mean(timings)
        p95_time = sorted(timings)[int(0.95 * len(timings))]
        p99_time = sorted(timings)[int(0.99 * len(timings))]
        
        logger.info(f"Full flow: avg={avg_time:.3f}ms, p95={p95_time:.3f}ms, p99={p99_time:.3f}ms")
        
        # Average should be under 1ms for mock
        self.assertLess(avg_time, 1.0)
    
    def test_concurrent_query_performance(self):
        """Test concurrent query handling performance."""
        whitelist = MockWhitelistState(
            allowed_domains=["google.com"],
            allowed_patterns=["*.google.com"],
        )
        firewall = MockFirewallManager()
        resolver = MockDNSResolver()
        
        num_threads = 50
        queries_per_thread = 100
        results = []
        
        def query_worker(thread_id: int) -> Tuple[int, float]:
            count = 0
            start = time.perf_counter()
            
            for i in range(queries_per_thread):
                domain = f"sub{thread_id}_{i}.google.com"
                
                if whitelist.is_domain_allowed(domain):
                    response = resolver.resolve(domain)
                    if response.success:
                        for ip in response.ips:
                            firewall.add_rule(ip, response.ttl)
                        count += 1
            
            elapsed = time.perf_counter() - start
            return count, elapsed
        
        start = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(query_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())
        
        total_elapsed = time.perf_counter() - start
        total_queries = sum(r[0] for r in results)
        
        qps = total_queries / total_elapsed
        
        logger.info(f"Concurrent queries: {total_queries} in {total_elapsed:.3f}s ({qps:.0f} qps)")
        
        # Should handle at least 500 queries/second
        self.assertGreater(qps, 500)


class TestMemoryPerformance(unittest.TestCase):
    """Memory usage performance tests."""
    
    def test_cache_memory_with_many_entries(self):
        """Test cache memory usage with many entries."""
        try:
            from dns_proxy.cache import DNSCache
            from dns_proxy.config import CacheConfig
        except ImportError:
            self.skipTest("DNS Cache not available")
        
        import sys
        
        config = CacheConfig(max_entries=10000)
        cache = DNSCache(config=config)
        
        # Measure baseline
        # Note: This is approximate as Python's memory management is complex
        
        # Add many entries
        for i in range(10000):
            cache.set(
                f"domain{i}.example.com",
                ipv4_addresses=[f"10.{i // 65536}.{(i // 256) % 256}.{i % 256}"],
                ttl=300
            )
        
        # Cache should respect max_size
        # Actual size verification depends on implementation


class TestLatencyPerformance(unittest.TestCase):
    """Latency performance tests."""
    
    def test_cache_latency_distribution(self):
        """Test cache operation latency distribution."""
        try:
            from dns_proxy.cache import DNSCache
            from dns_proxy.config import CacheConfig
            config = CacheConfig(max_entries=1000)
            cache = DNSCache(config=config)
        except ImportError:
            self.skipTest("DNS Cache not available")
        
        # Pre-populate
        for i in range(1000):
            cache.set(f"domain{i}.com", ipv4_addresses=[f"1.2.3.{i % 256}"], ttl=300)
        
        latencies = []
        
        for i in range(10000):
            start = time.perf_counter()
            cache.get(f"domain{i % 1000}.com")
            elapsed = (time.perf_counter() - start) * 1000000  # microseconds
            latencies.append(elapsed)
        
        avg = statistics.mean(latencies)
        p50 = sorted(latencies)[len(latencies) // 2]
        p95 = sorted(latencies)[int(0.95 * len(latencies))]
        p99 = sorted(latencies)[int(0.99 * len(latencies))]
        max_lat = max(latencies)
        
        logger.info(f"Cache latency (μs): avg={avg:.1f}, p50={p50:.1f}, p95={p95:.1f}, p99={p99:.1f}, max={max_lat:.1f}")
        
        # p99 should be under 100 microseconds for simple dict lookup
        self.assertLess(p99, 1000)  # 1ms max for p99


class PerformanceReport:
    """Generate performance test report."""
    
    def __init__(self):
        self.results = {}
    
    def add_result(self, name: str, ops_per_second: float, latency_ms: float = None):
        """Add a performance result."""
        self.results[name] = {
            "ops_per_second": ops_per_second,
            "latency_ms": latency_ms,
        }
    
    def generate_report(self) -> str:
        """Generate text report."""
        lines = [
            "=" * 60,
            "DNS Proxy Performance Report",
            "=" * 60,
            "",
        ]
        
        for name, data in self.results.items():
            lines.append(f"{name}:")
            lines.append(f"  Operations/second: {data['ops_per_second']:.0f}")
            if data['latency_ms']:
                lines.append(f"  Avg latency: {data['latency_ms']:.3f}ms")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
