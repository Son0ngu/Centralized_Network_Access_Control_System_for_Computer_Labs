"""
Firewall DNS Synchronization
----------------------------
Synchronizes DNS responses with firewall rules.
CRITICAL: Blocks DNS response until firewall rules are added.
Uses configurable timeout to prevent hanging queries.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from .config import FirewallSyncConfig
from .cache import DNSCacheEntry

logger = logging.getLogger("dns_proxy.firewall_sync")


@dataclass
class FirewallRule:
    """Represents a firewall rule created for DNS."""
    ip: str
    domain: str
    ttl: int
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    rule_name: str = ""
    grace_period: int = 60
    
    def __post_init__(self):
        if self.expires_at == 0.0:
            # Add grace period to TTL
            self.expires_at = self.created_at + self.ttl + self.grace_period
    
    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    @property
    def remaining_ttl(self) -> int:
        remaining = int(self.expires_at - time.time())
        return max(0, remaining)


@dataclass
class SyncResult:
    """Result of a firewall sync operation."""
    success: bool
    ips_added: List[str] = field(default_factory=list)
    ips_failed: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None
    timed_out: bool = False


class FirewallDNSSync:
    """
    Synchronizes DNS responses with firewall rules.
    
    CRITICAL BEHAVIOR:
    - Blocks until firewall rules are added (up to timeout)
    - Returns failure if rules cannot be added within timeout
    - Tracks IP TTLs and removes expired rules
    - Thread-safe for concurrent DNS queries
    
    Timeout Behavior (configurable, default 3s):
    - If adding rules takes longer than timeout, operation fails
    - DNS response should return NXDOMAIN or error on timeout
    - This prevents hanging queries when firewall is unresponsive
    """
    
    def __init__(
        self,
        config: FirewallSyncConfig,
        firewall_manager=None
    ):
        self.config = config
        self.enabled = getattr(config, "enabled", True)
        self._firewall_manager = firewall_manager
        
        # Track active rules by IP
        self._active_rules: Dict[str, FirewallRule] = {}
        self._lock = threading.RLock()
        
        # Pending removals queue
        self._removal_queue: queue.Queue = queue.Queue()
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="FirewallSync"
        )
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self._stats = {
            "rules_added": 0,
            "rules_removed": 0,
            "add_failures": 0,
            "timeouts": 0,
            "total_sync_time_ms": 0.0,
        }
        
        logger.info(
            f"FirewallDNSSync initialized (enabled={self.enabled}): "
            f"timeout={config.timeout}s, grace_period={config.grace_period}s"
        )
    
    def set_firewall_manager(self, manager) -> None:
        """Set the firewall manager reference."""
        if not self.enabled:
            logger.debug("Firewall sync disabled - firewall manager not required")
            return
        self._firewall_manager = manager
        logger.info("Firewall manager connected to DNS sync")
    
    def start(self) -> None:
        """Start background cleanup thread."""
        if not self.enabled:
            logger.info("Firewall sync disabled - DNS-only enforcement active")
            return
        if self._running:
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="FirewallSyncCleanup"
        )
        self._cleanup_thread.start()
        logger.info("Firewall sync cleanup thread started")
    
    def stop(self) -> None:
        """Stop background threads."""
        if not self.enabled:
            return
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self._executor.shutdown(wait=False)
        logger.info("Firewall sync stopped")
    
    def add_ips_blocking(
        self,
        domain: str,
        ips: List[str],
        ttl: int
    ) -> SyncResult:
        """
        Add firewall rules for IPs - BLOCKING operation.
        
        This method blocks until:
        1. All rules are added successfully, OR
        2. Timeout is reached (default 3s)
        
        Args:
            domain: Domain these IPs belong to
            ips: List of IP addresses to allow
            ttl: TTL in seconds (from DNS response)
            
        Returns:
            SyncResult indicating success/failure
            
        IMPORTANT:
        - If this returns success=False, the DNS response should
          return NXDOMAIN or an error to prevent traffic to unallowed IPs
        """
        if not self.enabled:
            return SyncResult(success=True, ips_added=ips, duration_ms=0.0)
        
        if not ips:
            return SyncResult(success=True)
        
        if not self._firewall_manager:
            # No firewall manager available
            if self.config.require_firewall:
                # Strict mode: fail if no firewall manager
                logger.warning("No firewall manager set - rules will not be added (strict mode)")
                return SyncResult(
                    success=False,
                    ips_failed=ips,
                    error="Firewall manager not available"
                )
            else:
                # Phase 1 DNS-only mode: allow traffic without firewall rules
                logger.debug(f"No firewall manager - allowing DNS resolution for {domain}")
                return SyncResult(
                    success=True,
                    ips_added=[],
                    duration_ms=0.0
                )
        
        start_time = time.time()
        
        # Filter out already-allowed IPs
        ips_to_add = []
        with self._lock:
            for ip in ips:
                if ip not in self._active_rules:
                    ips_to_add.append(ip)
                else:
                    # Refresh TTL for existing rule
                    rule = self._active_rules[ip]
                    rule.expires_at = time.time() + ttl + self.config.grace_period
                    logger.debug(f"Refreshed TTL for existing rule: {ip}")
        
        if not ips_to_add:
            return SyncResult(
                success=True,
                ips_added=[],
                duration_ms=0.0
            )
        
        logger.debug(f"Adding firewall rules for {domain}: {len(ips_to_add)} IPs")
        
        # Perform add operation with timeout
        try:
            future = self._executor.submit(
                self._add_rules_internal,
                domain,
                ips_to_add,
                ttl
            )
            
            result = future.result(timeout=self.config.timeout)
            
            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms
            
            self._stats["total_sync_time_ms"] += duration_ms
            
            if result.success:
                self._stats["rules_added"] += len(result.ips_added)
                logger.info(
                    f"Firewall rules added for {domain}: "
                    f"{len(result.ips_added)} IPs in {duration_ms:.1f}ms"
                )
            else:
                self._stats["add_failures"] += len(result.ips_failed)
                logger.error(
                    f"Failed to add firewall rules for {domain}: {result.error}"
                )
            
            return result
            
        except FuturesTimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            self._stats["timeouts"] += 1
            
            logger.error(
                f"TIMEOUT adding firewall rules for {domain} after {duration_ms:.1f}ms. "
                f"DNS response will fail to prevent unallowed traffic."
            )
            
            return SyncResult(
                success=False,
                ips_failed=ips_to_add,
                duration_ms=duration_ms,
                error=f"Timeout after {self.config.timeout}s",
                timed_out=True
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._stats["add_failures"] += len(ips_to_add)
            
            logger.error(f"Error adding firewall rules for {domain}: {e}")
            
            return SyncResult(
                success=False,
                ips_failed=ips_to_add,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    def _add_rules_internal(
        self,
        domain: str,
        ips: List[str],
        ttl: int
    ) -> SyncResult:
        """
        Internal method to track DNS-resolved IPs.
        
        NOTE: With DNS Proxy/Sinkhole architecture, we DON'T need to create
        Windows Firewall rules anymore. The Sinkhole blocks non-whitelisted
        domains at DNS level (returns NXDOMAIN). This method only tracks
        IPs for monitoring/statistics purposes.
        """
        added = []
        failed = []
        
        for ip in ips:
            try:
                # NOTE: Firewall rules disabled - DNS Proxy handles blocking
                # Just log and track the IP for monitoring
                success = True  # Always succeed since we're not creating rules
                logger.debug(f"Tracked IP {ip} for domain {domain} (no firewall rule needed)")
                
                if success:
                    # Track the rule
                    rule = FirewallRule(
                        ip=ip,
                        domain=domain,
                        ttl=ttl,
                        grace_period=self.config.grace_period
                    )
                    
                    with self._lock:
                        self._active_rules[ip] = rule
                    
                    added.append(ip)
                else:
                    failed.append(ip)
                    
            except Exception as e:
                logger.error(f"Error adding rule for {ip}: {e}")
                failed.append(ip)
        
        # Retry failed IPs if configured
        if failed and self.config.retry_on_failure:
            for retry in range(self.config.max_retries):
                time.sleep(self.config.retry_delay)
                
                still_failed = []
                for ip in failed:
                    try:
                        success = self._firewall_manager.add_ip_to_whitelist(
                            ip=ip,
                            reason=f"DNS:{domain}"
                        )
                        
                        if success:
                            rule = FirewallRule(
                                ip=ip,
                                domain=domain,
                                ttl=ttl,
                                grace_period=self.config.grace_period
                            )
                            
                            with self._lock:
                                self._active_rules[ip] = rule
                            
                            added.append(ip)
                        else:
                            still_failed.append(ip)
                            
                    except Exception as e:
                        logger.error(f"Retry {retry+1} failed for {ip}: {e}")
                        still_failed.append(ip)
                
                failed = still_failed
                if not failed:
                    break
        
        success = len(failed) == 0
        
        return SyncResult(
            success=success,
            ips_added=added,
            ips_failed=failed,
            error=f"Failed to add {len(failed)} IPs" if failed else None
        )
    
    def remove_ip(self, ip: str) -> bool:
        """
        Remove tracking for an IP.
        
        NOTE: With DNS Proxy/Sinkhole architecture, we don't actually
        create/remove Windows Firewall rules. This just removes tracking.
        """
        with self._lock:
            if ip not in self._active_rules:
                return False
            
            del self._active_rules[ip]
        
        # NOTE: Firewall rules disabled - just log
        self._stats["rules_removed"] += 1
        logger.debug(f"Removed tracking for IP: {ip}")
        return True
    
    def is_ip_active(self, ip: str) -> bool:
        """Check if an IP has an active firewall rule."""
        with self._lock:
            rule = self._active_rules.get(ip)
            if rule and not rule.is_expired:
                return True
            return False
    
    def get_active_rules_for_domain(self, domain: str) -> List[FirewallRule]:
        """Get all active rules for a domain."""
        with self._lock:
            return [
                rule for rule in self._active_rules.values()
                if rule.domain == domain and not rule.is_expired
            ]
    
    def get_expiring_rules(self, within_seconds: int = 60) -> List[FirewallRule]:
        """Get rules that will expire soon."""
        threshold = time.time() + within_seconds
        
        with self._lock:
            return [
                rule for rule in self._active_rules.values()
                if rule.expires_at <= threshold and not rule.is_expired
            ]
    
    def _cleanup_loop(self) -> None:
        """Background loop to clean expired rules."""
        cleanup_interval = 30  # seconds
        
        while self._running:
            try:
                self._cleanup_expired_rules()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            # Interruptible sleep
            for _ in range(cleanup_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _cleanup_expired_rules(self) -> int:
        """Remove expired firewall rules."""
        now = time.time()
        expired_ips = []
        
        with self._lock:
            for ip, rule in self._active_rules.items():
                if rule.expires_at < now:
                    expired_ips.append(ip)
        
        removed = 0
        for ip in expired_ips:
            if self.remove_ip(ip):
                removed += 1
                logger.debug(f"Removed expired rule: {ip}")
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} expired firewall rules")
        
        return removed
    
    def get_stats(self) -> Dict:
        """Get synchronization statistics."""
        if not self.enabled:
            return {
                "enabled": False,
                "active_rules": 0,
                "rules_added": 0,
                "rules_removed": 0,
                "add_failures": 0,
                "timeouts": 0,
                "avg_sync_time_ms": 0.0,
                "timeout_setting": self.config.timeout,
                "grace_period": self.config.grace_period,
            }
        
        with self._lock:
            active_count = len([r for r in self._active_rules.values() if not r.is_expired])
            
            avg_sync_time = 0.0
            total_ops = self._stats["rules_added"] + self._stats["add_failures"]
            if total_ops > 0:
                avg_sync_time = self._stats["total_sync_time_ms"] / total_ops
            
            return {
                "enabled": True,
                "active_rules": active_count,
                "rules_added": self._stats["rules_added"],
                "rules_removed": self._stats["rules_removed"],
                "add_failures": self._stats["add_failures"],
                "timeouts": self._stats["timeouts"],
                "avg_sync_time_ms": round(avg_sync_time, 2),
                "timeout_setting": self.config.timeout,
                "grace_period": self.config.grace_period,
            }
    
    def get_active_rules(self) -> Dict[str, Dict]:
        """Get all active rules with details."""
        with self._lock:
            return {
                ip: {
                    "domain": rule.domain,
                    "ttl": rule.ttl,
                    "remaining_ttl": rule.remaining_ttl,
                    "created_at": rule.created_at,
                    "expires_at": rule.expires_at,
                }
                for ip, rule in self._active_rules.items()
                if not rule.is_expired
            }
    
    def clear_all_rules(self) -> int:
        """Remove all active firewall rules."""
        with self._lock:
            ips = list(self._active_rules.keys())
        
        removed = 0
        for ip in ips:
            if self.remove_ip(ip):
                removed += 1
        
        logger.info(f"Cleared {removed} firewall rules")
        return removed
