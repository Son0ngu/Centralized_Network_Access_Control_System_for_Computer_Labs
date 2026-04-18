import asyncio
import atexit
import concurrent.futures
import ipaddress
import logging
import os
import sys
import socket
from typing import Dict, List, Optional

import aiodns
import dns.resolver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.time_utils import now

from cache.lru_cache import DNSRecord

logger = logging.getLogger("network.dns")


def _min_ttl_dnspython(answer) -> Optional[int]:
    """Extract minimum TTL from all RRsets in DNS response.
    
    When resolving A records, dnspython may follow CNAME chains automatically.
    The correct TTL for caching should be min(CNAME TTL, A TTL) to respect
    the entire chain's expiry policy.
    
    Args:
        answer: dnspython Answer object
        
    Returns:
        Minimum TTL from all RRsets, or answer.ttl as fallback, or None
    """
    try:
        resp = getattr(answer, "response", None)
        if resp and resp.answer:
            # Get minimum TTL from all RRsets in the answer section
            # This includes CNAME records in the chain + final A/AAAA records
            return min(rrset.ttl for rrset in resp.answer)
    except Exception:
        pass
    # Fallback to simple ttl attribute
    return getattr(answer, "ttl", None)


class OptimizedDNSResolver:
    """DNS resolver with dnspython and aiodns fallback."""
    
    def __init__(self, max_workers: int = 10, timeout: float = 10.0):
        self.max_workers = max_workers
        self.timeout = timeout
        self._shutdown = False
        
        # Configure dnspython resolver
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = timeout * 2
        
        # Respect "Machine DNS": relying on system nameservers detected by dnspython.
        logger.debug(f"Resolver initialized with system nameservers: {self.resolver.nameservers}")
        
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='DNSResolver'
        )
        
        # Register cleanup on exit
        atexit.register(self.shutdown)
    
    def resolve_domain_sync(self, domain: str) -> DNSRecord:
        """Synchronous DNS resolution with dnspython."""
        if self._shutdown:
            return self._fallback_resolve(domain)
            
        ipv4_ips = []
        cname = None
        min_ttl = None

        try:
            # Resolve A records (IPv4 only)
            try:
                answers = self.resolver.resolve(domain, 'A')
                ipv4_ips = [str(rdata) for rdata in answers]
                ttl_value = _min_ttl_dnspython(answers)
                if ttl_value is not None:
                    min_ttl = ttl_value if min_ttl is None else min(min_ttl, ttl_value)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                pass

            # Resolve CNAME if no A records
            if not ipv4_ips:
                try:
                    answers = self.resolver.resolve(domain, 'CNAME')
                    if answers:
                        cname = str(answers[0].target).rstrip('.')
                        ttl_value = _min_ttl_dnspython(answers)
                        if ttl_value is not None:
                            min_ttl = ttl_value if min_ttl is None else min(min_ttl, ttl_value)
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                    pass

            if not ipv4_ips and not cname:
                return self._fallback_resolve(domain)

        except Exception as e:
            logger.debug(f"DNS resolution error for {domain}: {e}")
            return self._fallback_resolve(domain)

        final_ttl = min_ttl if min_ttl is not None else 300

        return DNSRecord(
            ipv4=tuple(ipv4_ips),
            cname=cname,
            ttl=final_ttl,
            resolved_at=now()
        )
    
    async def resolve_domain_async(self, domain: str) -> DNSRecord:
        """Asynchronous DNS resolution with aiodns."""
        if self._shutdown:
            return await self._async_fallback_resolve(domain)
            
        ipv4_ips = []
        cname = None
        min_ttl = None  # Initialize as None to capture actual TTL from DNS response
        
        try:
            # Parallel async resolution
            tasks = [
                self._query_aiodns(domain, 'A'),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process A records
            if not isinstance(results[0], Exception) and results[0]:
                ipv4_ips = [r.host for r in results[0]]
                # Safe TTL extraction with getattr (some versions/types may lack .ttl)
                ttl_value = getattr(results[0][0], 'ttl', None)
                if ttl_value is not None:
                    min_ttl = ttl_value if min_ttl is None else min(min_ttl, ttl_value)
            
            # Try CNAME if no direct records
            if not ipv4_ips:
                cname_result = await self._query_aiodns(domain, 'CNAME')
                if not isinstance(cname_result, Exception) and cname_result:
                    cname = str(cname_result[0].cname).rstrip('.')
                    # Safe TTL extraction from CNAME response
                    ttl_value = getattr(cname_result[0], 'ttl', None)
                    if ttl_value is not None:
                        min_ttl = ttl_value if min_ttl is None else min(min_ttl, ttl_value)
        
        except Exception as e:
            logger.debug(f"Async DNS resolution error for {domain}: {e}")
            return await self._async_fallback_resolve(domain)
        
        # Use default TTL of 300 only if no actual TTL was obtained from DNS
        final_ttl = min_ttl if min_ttl is not None else 300
        
        return DNSRecord(
            ipv4=tuple(ipv4_ips),
            cname=cname,
            ttl=final_ttl,
            resolved_at=now()
        )
    
    async def _query_aiodns(self, domain: str, record_type: str):
        """Safe async DNS query with timeout using running loop.
        
        Creates aiodns resolver per-call with the current running loop
        to avoid 'attached to a different loop' errors.
        """
        try:
            resolver = aiodns.DNSResolver(
                loop=asyncio.get_running_loop(),
                timeout=self.timeout
            )
            return await asyncio.wait_for(
                resolver.query(domain, record_type),
                timeout=self.timeout
            )
        except Exception:
            return None
    
    def resolve_multiple_parallel(self, domains: List[str]) -> Dict[str, DNSRecord]:
        """Resolve multiple domains in parallel using thread pool with chunking."""
        if not domains or self._shutdown:
            return {}
        
        logger.info(f"Parallel DNS resolution for {len(domains)} domains")
        start_time = now()
        
        results = {}
        CHUNK_SIZE = 20
        wait_timeout = self.timeout * 4  # Timeout per chunk
        
        # Process in chunks to avoid overloading weak systems
        for i in range(0, len(domains), CHUNK_SIZE):
            chunk = domains[i:i + CHUNK_SIZE]
            
            future_to_domain = {
                self.executor.submit(self.resolve_domain_sync, domain): domain
                for domain in chunk
            }
            
            try:
                for future in concurrent.futures.as_completed(future_to_domain, timeout=wait_timeout):
                    domain = future_to_domain[future]
                    try:
                        results[domain] = future.result()
                    except Exception as e:
                        logger.warning(f"DNS resolution thread failed for {domain}: {e}")
                        results[domain] = self._fallback_resolve(domain)
            except concurrent.futures.TimeoutError:
                 logger.error(f"DNS Chunk resolution timed out after {wait_timeout}s")
                 pass
            
            # Brief pause between chunks to let CPU/IO breathe
            if i + CHUNK_SIZE < len(domains):
                import time
                time.sleep(0.5)
        
        duration = now() - start_time
        logger.info(f"Parallel DNS resolution completed in {duration:.2f}s ({len(results)}/{len(domains)} domains)")
        
        # Fill missing domains with fallback 
        # (If timeout happened, we don't want to leave holes or return partial dict if view expects all)
        for domain in domains:
            if domain not in results:
                results[domain] = self._fallback_resolve(domain)
        
        return results
    
    async def resolve_multiple_async(self, domains: List[str]) -> Dict[str, DNSRecord]:
        """Resolve multiple domains asynchronously."""
        if not domains or self._shutdown:
            return {}
        
        logger.info(f"Async DNS resolution for {len(domains)} domains")
        start_time = now()
        
        # Create async tasks for all domains
        tasks = [self.resolve_domain_async(domain) for domain in domains]
        
        # Execute all tasks concurrently
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        results = {}
        for domain, result in zip(domains, results_list):
            if isinstance(result, Exception):
                logger.warning(f"Async DNS resolution failed for {domain}: {result}")
                results[domain] = self._fallback_resolve(domain)
            else:
                results[domain] = result
        
        duration = now() - start_time
        logger.info(f"Async DNS resolution completed in {duration:.2f}s ({len(results)}/{len(domains)} domains)")
        
        return results
    
    def _fallback_resolve(self, domain: str) -> DNSRecord:
        """Fallback to standard socket resolution."""
        if self._is_ip_address(domain):
            try:
                ip_obj = ipaddress.ip_address(domain)
                if ip_obj.version == 4:
                    return DNSRecord(
                        ipv4=(domain,), cname=None, ttl=300, resolved_at=now()
                    )
                else:
                    return DNSRecord(
                        ipv4=(), cname=None, ttl=300, resolved_at=now()
                    )
            except:
                pass
        
        ipv4_ips = []
        
        # IPv4 resolution
        try:
            ipv4_results = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
            ipv4_ips = list(set(res[4][0] for res in ipv4_results))
        except socket.gaierror:
            pass
        
        return DNSRecord(
            ipv4=tuple(sorted(ipv4_ips)),
            cname=None,
            ttl=300,
            resolved_at=now()
        )
    
    async def _async_fallback_resolve(self, domain: str) -> DNSRecord:
        """Fallback to socket resolution in executor for async context."""
        if self._shutdown:
            return self._fallback_resolve(domain)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._fallback_resolve, domain)
    
    def _is_ip_address(self, address: str) -> bool:
        try:
            ipaddress.ip_address(address)
            return True
        except ValueError:
            return False
    
    def shutdown(self):
        if self._shutdown:
            return
            
        self._shutdown = True
        self.executor.shutdown(wait=True)
        logger.debug("DNS resolver thread pool shutdown")