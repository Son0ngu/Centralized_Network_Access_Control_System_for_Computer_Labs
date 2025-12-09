"""
Whitelist Manager - Core whitelist management functionality.
Vietnam ONLY - Clean implementation.
"""

import fnmatch
import hashlib
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

from shared.time_utils import now, now_iso, now_server_compatible, sleep, cache_age

from .state import WhitelistState
from .sync import WhitelistSyncer  # Fix: Changed from WhitelistSync

logger = logging.getLogger("whitelist.manager")


class WhitelistManager:
    """
    Manages domain whitelist with server synchronization.
    Vietnam ONLY - Clean implementation.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize WhitelistManager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.whitelist_config = config.get("whitelist", {})
        self.server_config = config.get("server", {})
        
        # Core state
        self._state = WhitelistState()
        
        # Initialize syncer with proper parameters
        server_urls = self._get_server_urls()
        agent_id = config.get("agent_id", "unknown")
        self._sync = WhitelistSyncer(
            server_urls=server_urls,
            agent_id=agent_id,
            config=config,  # Pass full config for JWT auth
            connect_timeout=self.server_config.get("connect_timeout", 10),
            read_timeout=self.server_config.get("read_timeout", 30),
            max_retries=self.whitelist_config.get("max_retries", 3)
        )
        
        # Firewall integration
        self._firewall_manager = None
        
        # Callbacks for sync completion
        self._on_sync_callbacks: List[Callable[[], None]] = []
        
        # Threading
        self._lock = threading.RLock()
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Settings
        self._sync_interval = self.whitelist_config.get("sync_interval", 60)
        self._cache_ttl = self.whitelist_config.get("cache_ttl", 300)
        
        # Statistics
        self._stats = {
            "total_checks": 0,
            "allowed": 0,
            "blocked": 0,
            "sync_count": 0,
            "last_sync": None,
            "errors": 0
        }
        
        logger.info("WhitelistManager initialized")
    
    def on_sync_complete(self, callback: Callable[[], None]) -> None:
        """Register callback to be called when sync completes."""
        if callback not in self._on_sync_callbacks:
            self._on_sync_callbacks.append(callback)
    
    def _notify_sync_complete(self) -> None:
        """Notify all registered callbacks that sync is complete."""
        for callback in self._on_sync_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in sync callback: {e}")
    
    def _get_server_urls(self) -> List[str]:
        """Get list of server URLs."""
        urls = []
        
        if isinstance(self.server_config.get("urls"), list):
            urls.extend(self.server_config["urls"])
        
        if self.server_config.get("url"):
            main_url = self.server_config["url"]
            if main_url not in urls:
                urls.append(main_url)
        
        return urls or ["http://localhost:5000"]
    
    def set_firewall_manager(self, firewall_manager) -> None:
        """Set firewall manager for rule updates."""
        self._firewall_manager = firewall_manager
        logger.info("Firewall manager linked to whitelist")
    
    def start_sync(self) -> None:
        """Start background sync thread."""
        if self._running:
            logger.warning("Sync already running")
            return
        
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="WhitelistSync"
        )
        self._sync_thread.start()
        logger.info(f"Whitelist sync started (interval: {self._sync_interval}s)")
    
    def stop_sync(self) -> None:
        """Stop background sync thread."""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        logger.info("Whitelist sync stopped")
    
    def stop_periodic_updates(self) -> None:
        """Alias for stop_sync for backward compatibility."""
        self.stop_sync()
    
    def _sync_loop(self) -> None:
        """Background sync loop."""
        logger.info("🚀 Starting initial whitelist sync...")
        
        # Initial sync
        self.sync_now()
        
        while self._running:
            # Wait for next sync interval
            logger.debug(f"⏰ Next sync in {self._sync_interval} seconds...")
            for _ in range(int(self._sync_interval)):
                if not self._running:
                    break
                sleep(1)
            
            if self._running:
                logger.info(f"Periodic whitelist sync (interval: {self._sync_interval}s)")
                self.sync_now()
    
    def sync_now(self) -> bool:
        """Perform immediate sync with server."""
        try:
            agent_id = self.config.get("agent_id", "unknown")
            
            # Build sync parameters
            params = {
                "agent_id": agent_id,
                "global_version": self._state._version if hasattr(self._state, '_version') and self._state._version else None,
                "timestamp": now_iso()
            }
            
            logger.info(f"Syncing whitelist from server (agent_id: {agent_id})...")
            
            # Sync with server
            result = self._sync.sync_with_server(params)
            
            if result.get("success"):
                data = result.get("data", {})
                
                # Log server response
                domains_count = len(data.get("domains", []))
                logger.info(f"📥 Received {domains_count} entries from server")
                
                # Debug: Log first few entries
                if domains_count > 0:
                    sample = data.get("domains", [])[:3]
                    logger.debug(f"Sample entries: {sample}")
                
                # Update state
                updated = self._state.update(data)
                
                self._stats["sync_count"] += 1
                self._stats["last_sync"] = now()
                
                if updated:
                    logger.info("Whitelist state updated with new data")
                    
                    # Update firewall rules if available
                    if self._firewall_manager:
                        logger.info("🔥 Updating firewall rules...")
                        self._update_firewall_rules()
                    else:
                        logger.debug("No firewall manager linked, skipping firewall update")
                else:
                    logger.debug("No changes in whitelist data (already up to date)")
                
                # Notify callbacks (even if no changes, so GUI can refresh)
                self._notify_sync_complete()
                
                return True
            else:
                self._stats["errors"] += 1
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"Whitelist sync failed: {error_msg}")
                return False
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Sync error: {e}", exc_info=True)
            return False
    
    def is_allowed(self, domain: str, ip: Optional[str] = None) -> bool:
        """Check if domain/IP is allowed."""
        with self._lock:
            self._stats["total_checks"] += 1
            
            # Check domain
            if domain and self._state.is_domain_allowed(domain):
                self._stats["allowed"] += 1
                return True
            
            # Check IP
            if ip and self._state.is_ip_allowed(ip):
                self._stats["allowed"] += 1
                return True
            
            self._stats["blocked"] += 1
            return False
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed (delegate to state)."""
        return self._state.is_ip_allowed(ip)
    
    def _update_firewall_rules(self) -> None:
        """Update firewall rules based on whitelist."""
        if not self._firewall_manager:
            logger.debug("No firewall manager linked, skipping firewall update")
            return
        
        try:
            # Get all whitelisted domains and IPs
            domains = self._state.get_all_domains()
            patterns = self._state.get_all_patterns()
            ips = self._state.get_all_ips()
            
            # Combine domains and patterns
            all_domains = domains.union(patterns)
            
            logger.info(f"Updating firewall with {len(all_domains)} domains and {len(ips)} IPs")
            
            # Update firewall - it will resolve domains to IPs internally
            if hasattr(self._firewall_manager, 'update_whitelist'):
                success = self._firewall_manager.update_whitelist(all_domains, ips)
                if success:
                    logger.info("Firewall rules updated successfully")
                else:
                    logger.warning("Firewall update returned failure")
            else:
                logger.warning("Firewall manager doesn't support update_whitelist method")
            
        except Exception as e:
            logger.error(f"Failed to update firewall rules: {e}")
    
    def get_stats(self) -> Dict:
        """Get whitelist statistics."""
        with self._lock:
            state_stats = self._state.get_stats()
            
            return {
                **state_stats,
                "total_checks": self._stats["total_checks"],
                "allowed": self._stats["allowed"],
                "blocked": self._stats["blocked"],
                "sync_count": self._stats["sync_count"],
                "last_sync": now_server_compatible(self._stats["last_sync"]) if self._stats["last_sync"] else None,
                "errors": self._stats["errors"],
                "sync_interval": self._sync_interval,
                "running": self._running
            }
    
    def get_cache_info(self) -> Dict:
        """Get cache information."""
        with self._lock:
            last_sync = self._stats.get("last_sync")
            
            return {
                "ttl": self._cache_ttl,
                "age": cache_age(last_sync) if last_sync else None,
                "valid": last_sync and cache_age(last_sync) < self._cache_ttl,
                "last_sync": now_server_compatible(last_sync) if last_sync else None
            }
    
    def force_refresh(self) -> bool:
        """Force immediate refresh of whitelist."""
        logger.info("Forcing whitelist refresh...")
        return self.sync_now()
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.stop_sync()
        self._state.clear()
        logger.info("WhitelistManager cleaned up")