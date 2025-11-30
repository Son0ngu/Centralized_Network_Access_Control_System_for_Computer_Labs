"""
LRU Cache - Least Recently Used cache implementation.
Vietnam ONLY - Clean implementation.
"""

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from shared.time_utils import now, is_cache_valid

logger = logging.getLogger("cache.lru_cache")


@dataclass
class DNSRecord:
    """DNS resolution result."""
    ipv4: Tuple[str, ...]
    ipv6: Tuple[str, ...]
    cname: Optional[str]
    ttl: int
    resolved_at: float


@dataclass
class CacheValue:
    """Generic cache value with metadata."""
    value: Any
    created_at: float
    ttl: float


class LRUCache:
    """
    Thread-safe LRU Cache with TTL support.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        """
        Initialize LRU Cache.
        
        Args:
            max_size: Maximum number of items in cache
            default_ttl: Default time-to-live in seconds
        """
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._ttls: Dict[str, float] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            timestamp = self._timestamps.get(key, 0)
            ttl = self._ttls.get(key, self._default_ttl)
            
            if not is_cache_valid(timestamp, ttl):
                self._remove(key)
                self._misses += 1
                return None
            
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set item in cache."""
        with self._lock:
            if key in self._cache:
                self._remove(key)
            
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)
            
            self._cache[key] = value
            self._timestamps[key] = now()
            self._ttls[key] = ttl if ttl is not None else self._default_ttl
    
    def _remove(self, key: str) -> None:
        """Remove item from cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
        self._ttls.pop(key, None)
    
    def delete(self, key: str) -> bool:
        """Delete item from cache."""
        with self._lock:
            if key in self._cache:
                self._remove(key)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._ttls.clear()
    
    def cleanup_expired(self) -> int:
        """Remove all expired items."""
        with self._lock:
            expired_keys = []
            for key in list(self._cache.keys()):
                timestamp = self._timestamps.get(key, 0)
                ttl = self._ttls.get(key, self._default_ttl)
                if not is_cache_valid(timestamp, ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove(key)
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2)
            }
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


# Alias for backward compatibility
HighPerformanceLRUCache = LRUCache