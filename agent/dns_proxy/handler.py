"""
DNS Query Handler
-----------------
Handles DNS query processing with whitelist checking.
Integrates cache, upstream resolver, and firewall sync.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import dns.message
import dns.rcode
import dns.rdatatype
import dns.rrset
import dns.name
import dns.rdataclass

from .config import DNSProxyConfig
from .cache import DNSCache, DNSCacheEntry
from .resolver import UpstreamResolver, DNSResult
from .firewall_sync import FirewallDNSSync, SyncResult

logger = logging.getLogger("dns_proxy.handler")


@dataclass
class QueryResult:
    """Result of DNS query handling."""
    success: bool
    response_data: bytes
    domain: str
    action: str  # "allowed", "blocked", "cached", "error"
    ips: List[str]
    ttl: int
    processing_time_ms: float
    cache_hit: bool = False
    firewall_synced: bool = False
    error: Optional[str] = None


class DNSQueryHandler:
    """
    Handles DNS queries with whitelist checking and firewall synchronization.
    
    Flow:
    1. Parse incoming DNS query
    2. Check whitelist for domain
    3. If blocked → return NXDOMAIN
    4. If allowed:
       a. Check cache → return if hit
       b. Query upstream resolver
       c. Add firewall rules (BLOCKING)
       d. Cache response
       e. Return response
    
    CRITICAL: Step 4c blocks until firewall rules are added (or timeout).
    This ensures traffic only flows after firewall allows it.
    """
    
    def __init__(
        self,
        config: DNSProxyConfig,
        whitelist_state=None,
        cache: DNSCache = None,
        upstream_resolver: UpstreamResolver = None,
        firewall_sync: FirewallDNSSync = None
    ):
        self.config = config
        self._whitelist_state = whitelist_state
        self._firewall_sync_enabled = getattr(config.firewall_sync, "enabled", True)

        # Initialize components if not provided
        self._cache = cache or DNSCache(config.cache)
        self._upstream = upstream_resolver or UpstreamResolver(config)
        if self._firewall_sync_enabled:
            self._firewall_sync = firewall_sync or FirewallDNSSync(config.firewall_sync)
        else:
            self._firewall_sync = None
            logger.info("Firewall sync disabled - DNS-only sinkhole mode active")
        
        # Statistics
        self._stats = {
            "total_queries": 0,
            "allowed": 0,
            "blocked": 0,
            "cache_hits": 0,
            "upstream_queries": 0,
            "firewall_syncs": 0,
            "errors": 0,
        }
        
        # Essential domains that bypass whitelist check
        # These are required for agent operation (server connection, DNS, etc.)
        self._essential_domains: set = set()
        
        logger.info("DNS Query Handler initialized")
    
    def set_whitelist_state(self, whitelist_state) -> None:
        """Set whitelist state reference."""
        self._whitelist_state = whitelist_state
        logger.info("Whitelist state connected to handler")
    
    def set_firewall_manager(self, firewall_manager) -> None:
        """Set firewall manager for sync."""
        if not self._firewall_sync_enabled or not self._firewall_sync:
            logger.debug("Firewall sync disabled - firewall manager not attached")
            return
        self._firewall_sync.set_firewall_manager(firewall_manager)
    
    def set_firewall_sync(self, firewall_sync) -> None:
        """Set firewall sync instance."""
        if not self._firewall_sync_enabled:
            logger.info("Firewall sync disabled - provided instance ignored")
            return
        self._firewall_sync = firewall_sync
        logger.info("Firewall sync connected to handler")
    
    def add_essential_domain(self, domain: str) -> None:
        """
        Add an essential domain that bypasses whitelist check.
        Used for server URLs that agent needs to connect to.
        """
        domain = domain.lower().strip().rstrip('.')
        self._essential_domains.add(domain)
        logger.info(f"Added essential domain: {domain}")
    
    def add_essential_domains(self, domains: list) -> None:
        """Add multiple essential domains."""
        for domain in domains:
            self.add_essential_domain(domain)
    
    def handle_query(self, query_data: bytes) -> QueryResult:
        """
        Handle a DNS query.
        
        Args:
            query_data: Raw DNS query bytes
            
        Returns:
            QueryResult with response and metadata
        """
        start_time = time.time()
        self._stats["total_queries"] += 1
        
        try:
            # Parse DNS query
            query = dns.message.from_wire(query_data)
            
            if not query.question:
                return self._error_result(
                    query_data, "No question in query", start_time
                )
            
            # Get domain from question
            question = query.question[0]
            domain = str(question.name).rstrip(".")
            qtype = dns.rdatatype.to_text(question.rdtype)
            
            if self.config.log_queries:
                logger.debug(f"Query: {domain} ({qtype})")
            
            # Check whitelist
            if not self._is_domain_allowed(domain):
                self._stats["blocked"] += 1
                
                if self.config.log_blocked:
                    logger.info(f"BLOCKED: {domain}")
                
                # Cache the blocked response
                self._cache.set_blocked(domain)
                
                # Build NXDOMAIN response
                response = self._build_nxdomain_response(query)
                
                return QueryResult(
                    success=True,
                    response_data=response.to_wire(),
                    domain=domain,
                    action="blocked",
                    ips=[],
                    ttl=self.config.cache.negative_ttl,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    cache_hit=False,
                    firewall_synced=False
                )
            
            # Domain is allowed - check cache first
            cached_entry = self._cache.get(domain)
            
            if cached_entry and not cached_entry.blocked:
                self._stats["cache_hits"] += 1
                self._stats["allowed"] += 1
                
                # Build response from cache
                response = self._build_response_from_cache(query, cached_entry)
                
                return QueryResult(
                    success=True,
                    response_data=response.to_wire(),
                    domain=domain,
                    action="cached",
                    ips=list(cached_entry.all_ips),
                    ttl=cached_entry.remaining_ttl,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    cache_hit=True,
                    firewall_synced=cached_entry.firewall_rules_added
                )
            
            # Query upstream resolver
            self._stats["upstream_queries"] += 1
            
            dns_result = self._upstream.resolve(domain)
            
            if not dns_result.success:
                if dns_result.is_nxdomain:
                    # Legitimate NXDOMAIN from upstream
                    self._cache.set(
                        domain=domain,
                        is_negative=True,
                        source="upstream"
                    )
                    
                    response = self._build_nxdomain_response(query)
                    
                    return QueryResult(
                        success=True,
                        response_data=response.to_wire(),
                        domain=domain,
                        action="nxdomain",
                        ips=[],
                        ttl=self.config.cache.negative_ttl,
                        processing_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    # Upstream error
                    return self._error_result(
                        query_data, dns_result.error, start_time
                    )
            
            # Got valid response - add firewall rules BEFORE returning
            all_ips = dns_result.all_ips
            
            sync_result = SyncResult(success=True)
            
            if all_ips and self._firewall_sync_enabled and self._firewall_sync:

                self._stats["firewall_syncs"] += 1
                
                sync_result = self._firewall_sync.add_ips_blocking(
                    domain=domain,
                    ips=all_ips,
                    ttl=dns_result.ttl
                )
                
                if not sync_result.success:
                    # CRITICAL: Firewall sync failed
                    # Return error to prevent traffic to unallowed IPs
                    
                    if sync_result.timed_out:
                        logger.error(
                            f"Firewall sync TIMEOUT for {domain} - "
                            f"returning SERVFAIL to prevent unallowed traffic"
                        )
                    
                    return self._servfail_result(query, domain, start_time)
            
            # Cache the successful response
            cache_entry = self._cache.set(
                domain=domain,
                ipv4_addresses=dns_result.ipv4_addresses,
                ipv6_addresses=dns_result.ipv6_addresses,
                cname=dns_result.cname,
                ttl=dns_result.ttl,
                source="upstream"
            )
            
            # Mark firewall rules as added
            self._cache.mark_firewall_added(domain)
            
            self._stats["allowed"] += 1
            
            # Build response
            response = self._build_response(
                query,
                dns_result.ipv4_addresses,
                dns_result.ipv6_addresses,
                dns_result.ttl
            )
            
            return QueryResult(
                success=True,
                response_data=response.to_wire(),
                domain=domain,
                action="allowed",
                ips=all_ips,
                ttl=dns_result.ttl,
                processing_time_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                firewall_synced=True
            )
            
        except Exception as e:
            logger.error(f"Error handling query: {e}", exc_info=True)
            self._stats["errors"] += 1
            return self._error_result(query_data, str(e), start_time)
    
    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is in whitelist or essential domains."""
        domain_lower = domain.lower().strip().rstrip('.')
        
        # 1. Check essential domains first (bypass whitelist)
        # These are required for agent operation (server connection, etc.)
        if self._is_essential_domain(domain_lower):
            logger.debug(f"Essential domain allowed: {domain}")
            return True
        
        # 2. No whitelist configured - allow all (for testing)
        if not self._whitelist_state:
            logger.warning("No whitelist configured - allowing all domains")
            return True
        
        # 3. Whitelist empty - allow all to prevent blocking everything
        stats = self._whitelist_state.get_stats()
        if stats.get("domains_count", 0) == 0 and stats.get("patterns_count", 0) == 0:
            logger.warning("Whitelist is empty (not synced?) - allowing all domains")
            return True
        
        # 4. Check whitelist
        return self._whitelist_state.is_domain_allowed(domain)
    
    def _is_essential_domain(self, domain: str) -> bool:
        """Check if domain is in essential domains list."""
        # Direct match
        if domain in self._essential_domains:
            return True
        
        # Subdomain match (e.g., api.server.com matches server.com)
        parts = domain.split('.')
        for i in range(len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._essential_domains:
                return True
        
        return False
    
    def _build_nxdomain_response(self, query: dns.message.Message) -> dns.message.Message:
        """Build NXDOMAIN response for blocked domain."""
        response = dns.message.make_response(query)
        response.set_rcode(dns.rcode.NXDOMAIN)
        return response
    
    def _build_response(
        self,
        query: dns.message.Message,
        ipv4_addresses: List[str],
        ipv6_addresses: List[str],
        ttl: int
    ) -> dns.message.Message:
        """Build DNS response with A/AAAA records."""
        response = dns.message.make_response(query)
        response.set_rcode(dns.rcode.NOERROR)
        
        question = query.question[0]
        qname = question.name
        
        # Add A records
        if ipv4_addresses:
            rrset = dns.rrset.RRset(qname, dns.rdataclass.IN, dns.rdatatype.A)
            for ip in ipv4_addresses:
                rdata = dns.rdata.from_text(
                    dns.rdataclass.IN,
                    dns.rdatatype.A,
                    ip
                )
                rrset.add(rdata, ttl)
            response.answer.append(rrset)
        
        # Add AAAA records
        if ipv6_addresses:
            rrset = dns.rrset.RRset(qname, dns.rdataclass.IN, dns.rdatatype.AAAA)
            for ip in ipv6_addresses:
                rdata = dns.rdata.from_text(
                    dns.rdataclass.IN,
                    dns.rdatatype.AAAA,
                    ip
                )
                rrset.add(rdata, ttl)
            response.answer.append(rrset)
        
        return response
    
    def _build_response_from_cache(
        self,
        query: dns.message.Message,
        entry: DNSCacheEntry
    ) -> dns.message.Message:
        """Build DNS response from cached entry."""
        return self._build_response(
            query,
            list(entry.ipv4_addresses),
            list(entry.ipv6_addresses),
            entry.remaining_ttl
        )
    
    def _servfail_result(
        self,
        query: dns.message.Message,
        domain: str,
        start_time: float
    ) -> QueryResult:
        """Build SERVFAIL response for firewall sync failure."""
        response = dns.message.make_response(query)
        response.set_rcode(dns.rcode.SERVFAIL)
        
        self._stats["errors"] += 1
        
        return QueryResult(
            success=False,
            response_data=response.to_wire(),
            domain=domain,
            action="error",
            ips=[],
            ttl=0,
            processing_time_ms=(time.time() - start_time) * 1000,
            error="Firewall sync failed"
        )
    
    def _error_result(
        self,
        query_data: bytes,
        error: str,
        start_time: float
    ) -> QueryResult:
        """Build error result."""
        # Try to build SERVFAIL response
        try:
            query = dns.message.from_wire(query_data)
            response = dns.message.make_response(query)
            response.set_rcode(dns.rcode.SERVFAIL)
            response_data = response.to_wire()
            domain = str(query.question[0].name).rstrip(".") if query.question else "unknown"
        except:
            # Can't parse query - return minimal error response
            response_data = b""
            domain = "unknown"
        
        return QueryResult(
            success=False,
            response_data=response_data,
            domain=domain,
            action="error",
            ips=[],
            ttl=0,
            processing_time_ms=(time.time() - start_time) * 1000,
            error=error
        )
    
    def start(self) -> None:
        """Start handler components."""
        self._cache.start()
        self._upstream.start()
        if self._firewall_sync:
            self._firewall_sync.start()
        logger.info("DNS Query Handler started")
    
    def stop(self) -> None:
        """Stop handler components."""
        self._cache.stop()
        self._upstream.stop()
        if self._firewall_sync:
            self._firewall_sync.stop()
        logger.info("DNS Query Handler stopped")
    
    def get_stats(self) -> Dict:
        """Get handler statistics."""
        cache_stats = self._cache.get_stats()
        resolver_health = self._upstream.get_health_status()
        firewall_stats = (
            self._firewall_sync.get_stats()
            if self._firewall_sync
            else {
                "enabled": False,
                "active_rules": 0,
                "rules_added": 0,
                "rules_removed": 0,
                "add_failures": 0,
                "timeouts": 0,
                "avg_sync_time_ms": 0.0,
            }
        )
        
        return {
            "handler": {
                **self._stats,
                "block_rate_percent": round(
                    self._stats["blocked"] / max(1, self._stats["total_queries"]) * 100, 2
                ),
            },
            "cache": cache_stats,
            "resolvers": resolver_health,
            "firewall_sync": firewall_stats,
        }
    
    @property
    def cache(self) -> DNSCache:
        """Get cache instance."""
        return self._cache
    
    @property
    def upstream_resolver(self) -> UpstreamResolver:
        """Get upstream resolver instance."""
        return self._upstream
    
    @property
    def firewall_sync(self) -> FirewallDNSSync:
        """Get firewall sync instance."""
        return self._firewall_sync
