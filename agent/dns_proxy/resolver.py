"""
Upstream DNS Resolver
---------------------
Handles forwarding DNS queries to upstream resolvers with failover support.
Uses dnspython for DNS operations.
"""

import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import dns.message
import dns.query
import dns.rdatatype
import dns.resolver
import dns.exception

from .config import DNSProxyConfig, UpstreamResolverConfig

logger = logging.getLogger("dns_proxy.resolver")


@dataclass
class ResolverHealth:
    """Health status for an upstream resolver."""
    address: str
    port: int
    is_healthy: bool = True
    last_check: float = 0.0
    consecutive_failures: int = 0
    total_queries: int = 0
    total_failures: int = 0
    avg_response_time_ms: float = 0.0
    
    @property
    def failure_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.total_failures / self.total_queries * 100


@dataclass
class DNSResult:
    """Result of a DNS resolution (IPv4 only)."""
    success: bool
    domain: str
    ipv4_addresses: List[str]
    cname: Optional[str] = None
    ttl: int = 300
    response_time_ms: float = 0.0
    resolver_used: str = ""
    error: Optional[str] = None
    raw_response: Optional[dns.message.Message] = None
    
    @property
    def all_ips(self) -> List[str]:
        return self.ipv4_addresses
    
    @property
    def is_nxdomain(self) -> bool:
        if self.raw_response:
            return self.raw_response.rcode() == dns.rcode.NXDOMAIN
        return False


class UpstreamResolver:
    """
    Upstream DNS resolver with health checking and failover.
    
    Features:
    - Multiple upstream resolvers with priority
    - Automatic failover on failure
    - Health tracking and recovery
    - UDP with TCP fallback for large responses
    """
    
    # Health check settings
    HEALTH_CHECK_DOMAIN = "dns.google"
    HEALTH_CHECK_INTERVAL = 30  # seconds
    MAX_CONSECUTIVE_FAILURES = 3
    RECOVERY_WAIT_TIME = 60  # seconds
    
    def __init__(self, config: DNSProxyConfig):
        self.config = config
        
        # Build resolver list sorted by priority
        self._resolvers: List[UpstreamResolverConfig] = sorted(
            [r for r in config.upstream_resolvers if r.enabled],
            key=lambda r: r.priority
        )
        
        if not self._resolvers:
            raise ValueError("No upstream resolvers configured")
        
        # Health tracking per resolver
        self._health: Dict[str, ResolverHealth] = {}
        for resolver in self._resolvers:
            key = f"{resolver.address}:{resolver.port}"
            self._health[key] = ResolverHealth(
                address=resolver.address,
                port=resolver.port,
                last_check=time.time()
            )
        
        # Current primary resolver index
        self._current_index = 0
        self._lock = threading.RLock()
        
        # Health check thread
        self._health_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info(f"Upstream resolver initialized with {len(self._resolvers)} resolvers")
    
    def start(self) -> None:
        """Start health checking thread."""
        if self._running:
            return
        
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="UpstreamHealthCheck"
        )
        self._health_thread.start()
        logger.info("Upstream resolver health check started")
    
    def stop(self) -> None:
        """Stop health checking."""
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=2)  # Reduced for faster shutdown
        logger.info("Upstream resolver stopped")
    
    def resolve(self, domain: str, query_types: List[str] = None) -> DNSResult:
        """
        Resolve domain using upstream resolvers with failover.
        
        Args:
            domain: Domain name to resolve
            query_types: List of record types to query (default: ["A", "AAAA"])
            
        Returns:
            DNSResult with resolution results
        """
        if query_types is None:
            query_types = ["A", "AAAA"]
        
        domain = domain.lower().strip().rstrip(".")
        
        # Try each healthy resolver in order
        last_error = None
        tried_resolvers = []
        
        for attempt in range(len(self._resolvers)):
            resolver = self._get_next_resolver()
            if resolver is None:
                break
            
            key = f"{resolver.address}:{resolver.port}"
            tried_resolvers.append(key)
            
            try:
                result = self._query_resolver(domain, resolver, query_types)
                
                if result.success:
                    # Update health on success
                    self._update_health(key, success=True, response_time=result.response_time_ms)
                    return result
                else:
                    last_error = result.error
                    self._update_health(key, success=False)
                    
            except Exception as e:
                last_error = str(e)
                self._update_health(key, success=False)
                logger.warning(f"Resolver {key} error for {domain}: {e}")
            
            # Move to next resolver
            with self._lock:
                self._current_index = (self._current_index + 1) % len(self._resolvers)
        
        # Fallback: use system DNS configuration if all custom resolvers fail
        system_result = self._resolve_with_system(domain, query_types)
        if system_result.success:
            logger.warning(
                f"Upstream resolvers failed for {domain}; "
                f"using system resolver ({system_result.resolver_used})"
            )
            return system_result
        elif system_result.error:
            last_error = system_result.error

        # All resolvers failed
        logger.error(f"All resolvers failed for {domain}. Tried: {tried_resolvers}")
        
        return DNSResult(
            success=False,
            domain=domain,
            ipv4_addresses=[],
            error=last_error or "All upstream resolvers failed"
        )
    
    def _resolve_with_system(self, domain: str, query_types: List[str]) -> DNSResult:
        """Resolve domain using system-configured DNS servers (IPv4 only).

        This is a safety net for environments where the predefined
        upstream resolvers (e.g., 8.8.8.8) are blocked or unreachable.
        """
        ipv4_addresses: List[str] = []
        min_ttl = self.config.cache.max_ttl

        resolver = dns.resolver.Resolver(configure=True)

        # Only query A records (IPv4)
        for qtype in ["A"]:
            try:
                answers = resolver.resolve(domain, qtype, lifetime=self.config.upstream_timeout)
                rrset = answers.rrset

                if rrset and rrset.ttl < min_ttl:
                    min_ttl = rrset.ttl

                ipv4_addresses.extend([str(rdata) for rdata in answers])
            except dns.resolver.NoAnswer:
                continue
            except dns.resolver.NXDOMAIN:
                return DNSResult(
                    success=False,
                    domain=domain,
                    ipv4_addresses=[],
                    ttl=self.config.cache.negative_ttl,
                    resolver_used="system",
                    error="NXDOMAIN from system resolver"
                )
            except dns.exception.Timeout:
                logger.debug(f"System resolver timeout for {domain} ({qtype})")
                continue
            except Exception as e:
                logger.debug(f"System resolver error for {domain} ({qtype}): {e}")
                continue

        has_results = bool(ipv4_addresses)
        ttl = min_ttl if has_results else self.config.cache.negative_ttl

        return DNSResult(
            success=has_results,
            domain=domain,
            ipv4_addresses=ipv4_addresses,
            ttl=ttl,
            resolver_used="system",
            error=None if has_results else "System resolver returned no records"
        )
    
    def _query_resolver(
        self,
        domain: str,
        resolver: UpstreamResolverConfig,
        query_types: List[str]
    ) -> DNSResult:
        """Query a specific resolver (IPv4 only)."""
        start_time = time.time()
        
        ipv4_addresses = []
        cname = None
        min_ttl = 86400
        raw_response = None
        
        # Only query A records (IPv4)
        for qtype in ["A"]:
            try:
                # Build DNS query
                query = dns.message.make_query(domain, qtype)
                
                # Try UDP first
                try:
                    response = dns.query.udp(
                        query,
                        resolver.address,
                        port=resolver.port,
                        timeout=self.config.upstream_timeout
                    )
                    
                    # Check if truncated - retry with TCP
                    if response.flags & dns.flags.TC:
                        logger.debug(f"Response truncated for {domain}, retrying with TCP")
                        response = dns.query.tcp(
                            query,
                            resolver.address,
                            port=resolver.port,
                            timeout=self.config.upstream_timeout
                        )
                    
                except socket.timeout:
                    # UDP timeout - try TCP
                    response = dns.query.tcp(
                        query,
                        resolver.address,
                        port=resolver.port,
                        timeout=self.config.upstream_timeout
                    )
                
                raw_response = response
                
                # Check for NXDOMAIN
                if response.rcode() == dns.rcode.NXDOMAIN:
                    response_time = (time.time() - start_time) * 1000
                    return DNSResult(
                        success=True,  # NXDOMAIN is a valid response
                        domain=domain,
                        ipv4_addresses=[],
                        ttl=self.config.cache.negative_ttl,
                        response_time_ms=response_time,
                        resolver_used=f"{resolver.address}:{resolver.port}",
                        raw_response=response
                    )
                
                # Parse answer section (IPv4 only)
                for rrset in response.answer:
                    # Track TTL
                    if rrset.ttl < min_ttl:
                        min_ttl = rrset.ttl
                    
                    if rrset.rdtype == dns.rdatatype.A:
                        for rdata in rrset:
                            ipv4_addresses.append(str(rdata))
                    elif rrset.rdtype == dns.rdatatype.CNAME:
                        for rdata in rrset:
                            cname = str(rdata).rstrip(".")
                
            except dns.exception.Timeout:
                logger.debug(f"Timeout querying {resolver.address} for {domain} ({qtype})")
                continue
            except Exception as e:
                logger.debug(f"Error querying {resolver.address} for {domain} ({qtype}): {e}")
                continue
        
        response_time = (time.time() - start_time) * 1000
        
        # Consider success if we got at least one IPv4 address
        has_results = bool(ipv4_addresses)
        
        return DNSResult(
            success=has_results,
            domain=domain,
            ipv4_addresses=ipv4_addresses,
            cname=cname,
            ttl=min_ttl if has_results else 300,
            response_time_ms=response_time,
            resolver_used=f"{resolver.address}:{resolver.port}",
            raw_response=raw_response,
            error=None if has_results else "No records found"
        )
    
    def _get_next_resolver(self) -> Optional[UpstreamResolverConfig]:
        """Get next healthy resolver to use."""
        with self._lock:
            # Try to find a healthy resolver
            for i in range(len(self._resolvers)):
                idx = (self._current_index + i) % len(self._resolvers)
                resolver = self._resolvers[idx]
                key = f"{resolver.address}:{resolver.port}"
                health = self._health.get(key)
                
                if health and health.is_healthy:
                    return resolver
            
            # No healthy resolvers - try to use first one anyway
            # (it might have recovered)
            if self._resolvers:
                return self._resolvers[0]
            
            return None
    
    def _update_health(self, key: str, success: bool, response_time: float = 0.0) -> None:
        """Update resolver health status."""
        with self._lock:
            health = self._health.get(key)
            if not health:
                return
            
            health.total_queries += 1
            
            if success:
                health.consecutive_failures = 0
                health.is_healthy = True
                
                # Update average response time
                if health.avg_response_time_ms == 0:
                    health.avg_response_time_ms = response_time
                else:
                    # Exponential moving average
                    health.avg_response_time_ms = (
                        health.avg_response_time_ms * 0.8 + response_time * 0.2
                    )
            else:
                health.consecutive_failures += 1
                health.total_failures += 1
                
                if health.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    health.is_healthy = False
                    logger.warning(
                        f"Resolver {key} marked unhealthy after "
                        f"{health.consecutive_failures} consecutive failures"
                    )
            
            health.last_check = time.time()
    
    def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            # Interruptible sleep
            for _ in range(self.HEALTH_CHECK_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)
    
    def _perform_health_checks(self) -> None:
        """Check health of all resolvers."""
        now = time.time()
        
        with self._lock:
            for key, health in self._health.items():
                # Skip recently checked healthy resolvers
                if health.is_healthy and (now - health.last_check) < self.HEALTH_CHECK_INTERVAL:
                    continue
                
                # Check unhealthy resolvers less frequently
                if not health.is_healthy:
                    if (now - health.last_check) < self.RECOVERY_WAIT_TIME:
                        continue
        
        # Perform health check outside lock
        for resolver in self._resolvers:
            key = f"{resolver.address}:{resolver.port}"
            
            try:
                result = self._query_resolver(
                    self.HEALTH_CHECK_DOMAIN,
                    resolver,
                    ["A"]
                )
                
                self._update_health(key, success=result.success, response_time=result.response_time_ms)
                
                if result.success:
                    logger.debug(f"Health check passed: {key} ({result.response_time_ms:.1f}ms)")
                else:
                    logger.debug(f"Health check failed: {key}")
                    
            except Exception as e:
                self._update_health(key, success=False)
                logger.debug(f"Health check error for {key}: {e}")
    
    def get_health_status(self) -> Dict[str, Dict]:
        """Get health status of all resolvers."""
        with self._lock:
            return {
                key: {
                    "address": health.address,
                    "port": health.port,
                    "is_healthy": health.is_healthy,
                    "consecutive_failures": health.consecutive_failures,
                    "failure_rate_percent": round(health.failure_rate, 2),
                    "avg_response_time_ms": round(health.avg_response_time_ms, 2),
                    "total_queries": health.total_queries,
                }
                for key, health in self._health.items()
            }
    
    def get_primary_resolver(self) -> Optional[str]:
        """Get current primary resolver address."""
        with self._lock:
            if self._resolvers:
                r = self._resolvers[self._current_index]
                return f"{r.address}:{r.port}"
            return None
