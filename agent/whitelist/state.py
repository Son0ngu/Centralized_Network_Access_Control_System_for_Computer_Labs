"""
Whitelist State - State management for whitelist data.
Vietnam ONLY - Clean implementation.
"""

import hashlib
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Set

# Fix: Add now_server_compatible to import
from shared.time_utils import now, now_iso, now_server_compatible

logger = logging.getLogger("whitelist.state")


class WhitelistState:
    """
    Thread-safe whitelist state management.
    """
    
    def __init__(self):
        """Initialize whitelist state."""
        self._lock = threading.RLock()
        self._domains: Set[str] = set()
        self._patterns: Set[str] = set()
        self._ips: Set[str] = set()
        self._last_updated: Optional[float] = None
        self._version: str = ""
        self._checksum: str = ""
        self._metadata: Dict[str, Any] = {}
    
    def update(self, data: Dict) -> bool:
        """
        Update whitelist state from server data.
        
        Args:
            data: Whitelist data from server
            
        Returns:
            True if state was updated, False otherwise
        """
        with self._lock:
            try:
                # Extract domains
                new_domains = set()
                new_patterns = set()
                new_ips = set()
                
                for item in data.get("domains", []):
                    if isinstance(item, str):
                        domain = item.lower().strip()
                    elif isinstance(item, dict):
                        domain = item.get("domain", "").lower().strip()
                    else:
                        continue
                    
                    if domain:
                        if "*" in domain or "?" in domain:
                            new_patterns.add(domain)
                        else:
                            new_domains.add(domain)
                
                # Extract IPs
                for ip in data.get("ips", []):
                    if isinstance(ip, str):
                        new_ips.add(ip.strip())
                
                # Check if changed
                if (new_domains == self._domains and 
                    new_patterns == self._patterns and 
                    new_ips == self._ips):
                    return False
                
                # Update state
                self._domains = new_domains
                self._patterns = new_patterns
                self._ips = new_ips
                self._last_updated = now()
                self._version = data.get("version", "")
                self._checksum = self._calculate_checksum()
                self._metadata = data.get("metadata", {})
                
                logger.info(
                    f"Whitelist updated: {len(self._domains)} domains, "
                    f"{len(self._patterns)} patterns, {len(self._ips)} IPs"
                )
                return True
                
            except Exception as e:
                logger.error(f"Failed to update whitelist state: {e}")
                return False
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum of current state."""
        data = json.dumps({
            "domains": sorted(self._domains),
            "patterns": sorted(self._patterns),
            "ips": sorted(self._ips)
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()
    
    def is_domain_allowed(self, domain: str) -> bool:
        """
        Check if domain is in whitelist.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain is allowed
        """
        with self._lock:
            domain = domain.lower().strip()
            
            # Direct match
            if domain in self._domains:
                return True
            
            # Pattern match
            import fnmatch
            for pattern in self._patterns:
                if fnmatch.fnmatch(domain, pattern):
                    return True
            
            # Subdomain match
            parts = domain.split(".")
            for i in range(len(parts)):
                parent = ".".join(parts[i:])
                if parent in self._domains:
                    return True
            
            return False
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is in whitelist."""
        with self._lock:
            return ip in self._ips
    
    def get_stats(self) -> Dict:
        """Get whitelist statistics."""
        with self._lock:
            return {
                "domains_count": len(self._domains),
                "patterns_count": len(self._patterns),
                "ips_count": len(self._ips),
                "last_updated": now_server_compatible(self._last_updated) if self._last_updated else None,
                "version": self._version,
                "checksum": self._checksum
            }
    
    def get_all_domains(self) -> Set[str]:
        """Get all domains."""
        with self._lock:
            return self._domains.copy()
    
    def get_all_patterns(self) -> Set[str]:
        """Get all patterns."""
        with self._lock:
            return self._patterns.copy()
    
    def get_all_ips(self) -> Set[str]:
        """Get all IPs."""
        with self._lock:
            return self._ips.copy()
    
    def clear(self) -> None:
        """Clear all whitelist data."""
        with self._lock:
            self._domains.clear()
            self._patterns.clear()
            self._ips.clear()
            self._last_updated = None
            self._version = ""
            self._checksum = ""
            self._metadata.clear()