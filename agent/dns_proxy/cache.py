"""
DNS Cache Module
----------------
Thread-safe DNS cache with TTL management.
Respects min-TTL to prevent too-frequent firewall rule removal.
Supports negative caching for NXDOMAIN responses.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .config import CacheConfig

logger = logging.getLogger("dns_proxy.cache")


@dataclass
class DNSCacheEntry:
    """Single DNS cache entry with TTL tracking (IPv4 only)."""
    domain: str
    
    # Record data (IPv4 only)
    ipv4_addresses: Tuple[str, ...] = field(default_factory=tuple)
    cname: Optional[str] = None
    
    # TTL management
    original_ttl: int = 300         # TTL from upstream
    effective_ttl: int = 300        # TTL after min/max adjustment
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    
    # Metadata
    is_negative: bool = False       # True for NXDOMAIN/blocked
    blocked: bool = False           # True if domain was blocked by whitelist
    source: str = "upstream"        # "upstream", "cache", "blocked"
    hit_count: int = 0
    last_accessed: float = 0.0
    
    # Firewall tracking
    firewall_rules_added: bool = False
    firewall_rule_ids: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + self.effective_ttl
        if self.last_accessed == 0.0:
            self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at
    
    @property
    def remaining_ttl(self) -> int:
        """Get remaining TTL in seconds."""
        remaining = int(self.expires_at - time.time())
        return max(0, remaining)
    
    @property
    def all_ips(self) -> Set[str]:
        """Get all IP addresses (IPv4 only)."""
        return set(self.ipv4_addresses)
    
    def touch(self) -> None:
        """Update last accessed time and hit count."""
        self.last_accessed = time.time()
        self.hit_count += 1


class DNSCache:
    """
    Thread-safe DNS cache with intelligent TTL management.
    
    Features:
    - Min-TTL enforcement to prevent too-frequent rule removal
    - Max-TTL cap to ensure eventual refresh
    - Negative caching for blocked/NXDOMAIN responses
    - LRU eviction when max entries reached
    - Background cleanup of expired entries
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        
        # Main cache storage
        self._cache: Dict[str, DNSCacheEntry] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "inserts": 0,
            "evictions": 0,
            "expirations": 0,
        }
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info(f"DNS Cache initialized: max_entries={self.config.max_entries}, "
                   f"min_ttl={self.config.min_ttl}s, max_ttl={self.config.max_ttl}s")
    
    def start(self) -> None:
        """Start background cleanup thread."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="DNSCacheCleanup"
        )
        self._cleanup_thread.start()
        logger.info("DNS Cache cleanup thread started")
    
    def stop(self) -> None:
        """Stop background cleanup thread."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("DNS Cache stopped")
    
    def get(self, domain: str) -> Optional[DNSCacheEntry]:
        """
        Get cached entry for domain.
        
        Args:
            domain: Domain name to lookup
            
        Returns:
            DNSCacheEntry if found and not expired, None otherwise
        """
        domain = domain.lower().strip()
        
        with self._lock:
            entry = self._cache.get(domain)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if entry.is_expired:
                # Remove expired entry
                del self._cache[domain]
                self._stats["misses"] += 1
                self._stats["expirations"] += 1
                logger.debug(f"Cache expired: {domain}")
                return None
            
            # Update access stats
            entry.touch()
            self._stats["hits"] += 1
            
            logger.debug(f"Cache hit: {domain} (remaining TTL: {entry.remaining_ttl}s)")
            return entry
    
    def set(
        self,
        domain: str,
        ipv4_addresses: List[str] = None,
        cname: str = None,
        ttl: int = 300,
        is_negative: bool = False,
        blocked: bool = False,
        source: str = "upstream"
    ) -> DNSCacheEntry:
        """
        Add or update cache entry with TTL enforcement (IPv4 only).
        
        Args:
            domain: Domain name
            ipv4_addresses: List of IPv4 addresses
            cname: CNAME record if any
            ttl: TTL from upstream (will be adjusted to min/max)
            is_negative: True if NXDOMAIN response
            blocked: True if blocked by whitelist
            source: Source of the record
            
        Returns:
            Created/updated cache entry
        """
        domain = domain.lower().strip()
        
        # Apply TTL bounds
        original_ttl = ttl
        
        if is_negative or blocked:
            # Use negative TTL for blocked/NXDOMAIN
            effective_ttl = self.config.negative_ttl
        else:
            # Enforce min/max TTL
            effective_ttl = max(self.config.min_ttl, min(ttl, self.config.max_ttl))
        
        if effective_ttl != original_ttl:
            logger.debug(f"TTL adjusted for {domain}: {original_ttl} → {effective_ttl}")
        
        now = time.time()
        
        entry = DNSCacheEntry(
            domain=domain,
            ipv4_addresses=tuple(ipv4_addresses or []),
            cname=cname,
            original_ttl=original_ttl,
            effective_ttl=effective_ttl,
            created_at=now,
            expires_at=now + effective_ttl,
            is_negative=is_negative,
            blocked=blocked,
            source=source,
        )
        
        with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self.config.max_entries:
                self._evict_lru()
            
            self._cache[domain] = entry
            self._stats["inserts"] += 1
        
        log_level = logging.DEBUG
        if blocked:
            log_level = logging.INFO
            
        logger.log(log_level, 
            f"Cache set: {domain} → {len(entry.all_ips)} IPs, "
            f"TTL={effective_ttl}s, blocked={blocked}"
        )
        
        return entry
    
    def set_blocked(self, domain: str) -> DNSCacheEntry:
        """Shorthand for caching a blocked domain."""
        return self.set(
            domain=domain,
            is_negative=True,
            blocked=True,
            source="blocked"
        )
    
    def remove(self, domain: str) -> bool:
        """
        Remove entry from cache.
        
        Args:
            domain: Domain to remove
            
        Returns:
            True if entry was removed, False if not found
        """
        domain = domain.lower().strip()
        
        with self._lock:
            if domain in self._cache:
                del self._cache[domain]
                logger.debug(f"Cache removed: {domain}")
                return True
            return False
    
    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
            return count
    
    def get_expiring_entries(self, within_seconds: int = 60) -> List[DNSCacheEntry]:
        """
        Get entries that will expire soon.
        
        Args:
            within_seconds: Threshold in seconds
            
        Returns:
            List of entries expiring within the threshold
        """
        threshold = time.time() + within_seconds
        
        with self._lock:
            return [
                entry for entry in self._cache.values()
                if entry.expires_at <= threshold and not entry.is_expired
            ]
    
    def get_entries_by_ip(self, ip: str) -> List[DNSCacheEntry]:
        """Get all cache entries that contain a specific IP."""
        with self._lock:
            return [
                entry for entry in self._cache.values()
                if ip in entry.all_ips
            ]
    
    def mark_firewall_added(self, domain: str, rule_ids: List[str] = None) -> bool:
        """Mark that firewall rules have been added for this domain."""
        domain = domain.lower().strip()
        
        with self._lock:
            entry = self._cache.get(domain)
            if entry:
                entry.firewall_rules_added = True
                if rule_ids:
                    entry.firewall_rule_ids = rule_ids
                return True
            return False
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
            
            return {
                "entries": len(self._cache),
                "max_entries": self.config.max_entries,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_percent": round(hit_rate, 2),
                "inserts": self._stats["inserts"],
                "evictions": self._stats["evictions"],
                "expirations": self._stats["expirations"],
                "min_ttl": self.config.min_ttl,
                "max_ttl": self.config.max_ttl,
                "negative_ttl": self.config.negative_ttl,
            }
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find LRU entry
        lru_domain = min(
            self._cache.keys(),
            key=lambda d: self._cache[d].last_accessed
        )
        
        del self._cache[lru_domain]
        self._stats["evictions"] += 1
        logger.debug(f"Cache evicted (LRU): {lru_domain}")
    
    def _cleanup_loop(self) -> None:
        """Background loop to clean expired entries."""
        while self._running:
            try:
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
            
            # Interruptible sleep
            for _ in range(self.config.cleanup_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _cleanup_expired(self) -> int:
        """Remove all expired entries."""
        now = time.time()
        expired_domains = []
        
        with self._lock:
            for domain, entry in self._cache.items():
                if entry.expires_at < now:
                    expired_domains.append(domain)
            
            for domain in expired_domains:
                del self._cache[domain]
                self._stats["expirations"] += 1
        
        if expired_domains:
            logger.debug(f"Cleanup removed {len(expired_domains)} expired entries")
        
        return len(expired_domains)
    
    def __len__(self) -> int:
        """Return number of cached entries."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, domain: str) -> bool:
        """Check if domain is in cache (and not expired)."""
        return self.get(domain) is not None
