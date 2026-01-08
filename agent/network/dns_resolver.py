import asyncio
import atexit
import concurrent.futures
import ipaddress
import logging
import os
import sys
import socket
from typing import Dict, List

import aiodns
import dns.resolver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.time_utils import now

from cache.lru_cache import DNSRecord

logger = logging.getLogger("network.dns")

class OptimizedDNSResolver:
    """DNS resolver with dnspython and aiodns."""
    
    def __init__(self, max_workers: int = 20, timeout: float = 5.0):
        self.max_workers = max_workers
        self.timeout = timeout
        self._shutdown = False

        # Create a dedicated event loop for this resolver instance
        # to avoid "no current event loop" errors in worker threads if async methods are used.
        self._loop = asyncio.new_event_loop()
        # Do NOT set global event loop here as it may break the main thread (GUI)
        # asyncio.set_event_loop(self._loop) 
        
        # Configure dnspython resolver
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = timeout * 2
        
        # preserve system nameservers and append public ones as fallback
        # this ensures we resolve to the same IPs as the browser/OS (CDNs, GeoDNS)
        current_nameservers = list(self.resolver.nameservers)
        public_nameservers = [
            '1.1.1.1',   # Cloudflare
            '8.8.8.8',   # Google
            '1.0.0.1',   # Cloudflare
            '8.8.4.4',   # Google
        ]
        
        for ns in public_nameservers:
            if ns not in current_nameservers:
                current_nameservers.append(ns)
        
        self.resolver.nameservers = current_nameservers
        
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='DNSResolver'
        )
        
        # Async DNS resolver bound to this loop (used only if async paths are needed)
        self.aiodns_resolver = aiodns.DNSResolver(loop=self._loop)
        self.aiodns_resolver.timeout = timeout
        
        # Register cleanup on exit
        atexit.register(self.shutdown)
    
    def resolve_domain_sync(self, domain: str) -> DNSRecord:
        """Synchronous DNS resolution with dnspython."""
        if self._shutdown:
            return self._fallback_resolve(domain)
            
        ipv4_ips = []
        ipv6_ips = []
        cname = None
        min_ttl = 300
        
        try:
            # Resolve A records (IPv4)
            try:
                answers = self.resolver.resolve(domain, 'A')
                ipv4_ips = [str(rdata) for rdata in answers]
                min_ttl = min(min_ttl, answers.ttl)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                pass
            
            # Resolve AAAA records (IPv6)
            try:
                answers = self.resolver.resolve(domain, 'AAAA')
                ipv6_ips = [str(rdata) for rdata in answers]
                min_ttl = min(min_ttl, answers.ttl)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                pass
            
            # Resolve CNAME if no direct records
            if not ipv4_ips and not ipv6_ips:
                try:
                    answers = self.resolver.resolve(domain, 'CNAME')
                    if answers:
                        cname = str(answers[0].target).rstrip('.')
                        min_ttl = min(min_ttl, answers.ttl)
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                    pass
        
        except Exception as e:
            logger.debug(f"DNS resolution error for {domain}: {e}")
            return self._fallback_resolve(domain)
        
        return DNSRecord(
            ipv4=tuple(ipv4_ips),
            ipv6=tuple(ipv6_ips),
            cname=cname,
            ttl=min_ttl,
            resolved_at=now()
        )
    
    async def resolve_domain_async(self, domain: str) -> DNSRecord:
        """Asynchronous DNS resolution with aiodns."""
        if self._shutdown:
            return await self._async_fallback_resolve(domain)
            
        ipv4_ips = []
        ipv6_ips = []
        cname = None
        min_ttl = 300
        
        try:
            # Parallel async resolution
            tasks = [
                self._safe_query_async(domain, 'A'),
                self._safe_query_async(domain, 'AAAA'),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process A records
            if not isinstance(results[0], Exception) and results[0]:
                ipv4_ips = [r.host for r in results[0]]
                min_ttl = min(min_ttl, results[0][0].ttl if results[0] else 300)
            
            # Process AAAA records
            if not isinstance(results[1], Exception) and results[1]:
                ipv6_ips = [r.host for r in results[1]]
                min_ttl = min(min_ttl, results[1][0].ttl if results[1] else 300)
            
            # Try CNAME if no direct records
            if not ipv4_ips and not ipv6_ips:
                cname_result = await self._safe_query_async(domain, 'CNAME')
                if not isinstance(cname_result, Exception) and cname_result:
                    cname = str(cname_result[0].cname).rstrip('.')
        
        except Exception as e:
            logger.debug(f"Async DNS resolution error for {domain}: {e}")
            return await self._async_fallback_resolve(domain)
        
        return DNSRecord(
            ipv4=tuple(ipv4_ips),
            ipv6=tuple(ipv6_ips),
            cname=cname,
            ttl=min_ttl,
            resolved_at=now()
        )
    
    async def _safe_query_async(self, domain: str, record_type: str):
        """Safe async DNS query with timeout."""
        try:
            return await asyncio.wait_for(
                self.aiodns_resolver.query(domain, record_type),
                timeout=self.timeout
            )
        except Exception:
            return None
    
    def resolve_multiple_parallel(self, domains: List[str]) -> Dict[str, DNSRecord]:
        """Resolve multiple domains in parallel using thread pool."""
        if not domains or self._shutdown:
            return {}
        
        logger.info(f"Parallel DNS resolution for {len(domains)} domains")
        start_time = now()
        
        # Submit all tasks to thread pool
        future_to_domain = {
            self.executor.submit(self.resolve_domain_sync, domain): domain
            for domain in domains
        }
        
        results = {}
        completed = 0
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_domain, timeout=self.timeout * 2):
            domain = future_to_domain[future]
            try:
                result = future.result()
                results[domain] = result
                completed += 1
                
                if completed % 50 == 0:
                    logger.debug(f"   Progress: {completed}/{len(domains)} domains resolved")
                    
            except Exception as e:
                logger.warning(f"DNS resolution failed for {domain}: {e}")
                results[domain] = self._fallback_resolve(domain)
        
        duration = now() - start_time
        logger.info(f"Parallel DNS resolution completed in {duration:.2f}s ({len(results)}/{len(domains)} domains)")
        
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
                        ipv4=(domain,), ipv6=(), cname=None, ttl=300, resolved_at=now()
                    )
                else:
                    return DNSRecord(
                        ipv4=(), ipv6=(domain,), cname=None, ttl=300, resolved_at=now()
                    )
            except:
                pass
        
        ipv4_ips = []
        ipv6_ips = []
        
        # IPv4 resolution
        try:
            ipv4_results = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
            ipv4_ips = list(set(res[4][0] for res in ipv4_results))
        except socket.gaierror:
            pass
        
        # IPv6 resolution
        try:
            ipv6_results = socket.getaddrinfo(domain, None, socket.AF_INET6, socket.SOCK_STREAM)
            ipv6_ips = list(set(res[4][0] for res in ipv6_results))
        except socket.gaierror:
            pass
        
        return DNSRecord(
            ipv4=tuple(sorted(ipv4_ips)),
            ipv6=tuple(sorted(ipv6_ips)),
            cname=None,
            ttl=300,
            resolved_at=now()
        )
    
    async def _async_fallback_resolve(self, domain: str) -> DNSRecord:
        if self._shutdown:
            return self._fallback_resolve(domain)
        loop = asyncio.get_event_loop()
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