"""
Whitelist Controller - Manages whitelist CRUD operations for GUI.
Vietnam ONLY - Using customtkinter.

Features:
- Add/Remove IP addresses
- Refresh whitelist display
- Integration with WhitelistManager
- Thread-safe operations
"""

import logging
import threading
import re
from typing import Callable, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("gui.whitelist_controller")


class WhitelistController:
    """
    Controller for whitelist management in GUI.
    
    Provides methods for:
    - add_ip(ip): Add IP to local list (note: server sync manages actual whitelist)
    - remove_ip(ip): Remove IP from local list
    - get_all_ips(): Get all whitelisted IPs
    - refresh(): Trigger sync and refresh data
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Callbacks for UI updates
        self._on_data_changed: List[Callable[[List[Dict]], None]] = []
        self._on_error: List[Callable[[str], None]] = []
        self._on_success: List[Callable[[str], None]] = []
        
        # Local IP list (for UI display - actual whitelist is managed by WhitelistManager)
        self._local_ips: Dict[str, Dict] = {}
        self._lock_data = threading.RLock()
        
        # Reference to Agent's whitelist manager
        self._whitelist_manager = None
        
        logger.info("WhitelistController initialized")
    
    def set_whitelist_manager(self, manager) -> None:
        """
        Set reference to WhitelistManager from Agent.
        
        Args:
            manager: WhitelistManager instance
        """
        self._whitelist_manager = manager
        
        # Register callback to be notified when sync completes (periodic sync)
        if hasattr(manager, 'on_sync_complete'):
            manager.on_sync_complete(self._on_manager_sync_complete)
        
        # First sync from current manager state (cached data)
        self._sync_from_manager()
        
        # Then trigger immediate server sync in background
        # This ensures fresh data is loaded from server right away
        self._trigger_server_sync()
        
        logger.info("WhitelistController connected to WhitelistManager")
    
    def _on_manager_sync_complete(self) -> None:
        """Called when WhitelistManager completes a sync (including periodic syncs)."""
        logger.info("Manager sync complete, updating GUI...")
        self._sync_from_manager()
    
    def _trigger_server_sync(self) -> None:
        """Trigger immediate sync with server in background."""
        if not self._whitelist_manager:
            return
            
        def do_sync():
            try:
                logger.info("Triggering immediate whitelist sync from server...")
                if hasattr(self._whitelist_manager, 'sync_now'):
                    success = self._whitelist_manager.sync_now()
                    if success:
                        # Sync complete, update UI with fresh data
                        self._sync_from_manager()
                        logger.info("Immediate whitelist sync completed")
                    else:
                        logger.warning("Immediate whitelist sync failed")
            except Exception as e:
                logger.error(f"Error in immediate sync: {e}")
        
        # Run in background thread to not block UI
        threading.Thread(target=do_sync, daemon=True, name="ImmediateWhitelistSync").start()
    
    def _sync_from_manager(self) -> None:
        """Sync local list from WhitelistManager (domains + IPs)."""
        if not self._whitelist_manager:
            return
        
        try:
            if hasattr(self._whitelist_manager, '_state'):
                state = self._whitelist_manager._state
                
                with self._lock_data:
                    # Clear ALL existing server entries (case-insensitive check)
                    self._local_ips = {k: v for k, v in self._local_ips.items() 
                                      if v.get("source", "").lower() != "server"}
                    
                    # Get domains from manager's state
                    domains = state.get_all_domains()
                    for domain in domains:
                        key = f"domain:{domain}"
                        self._local_ips[key] = {
                            "ip": domain,
                            "type": "Domain",
                            "status": "Active",
                            "source": "Server",
                        }
                    
                    # Get patterns (wildcards) from manager's state
                    patterns = state.get_all_patterns()
                    for pattern in patterns:
                        key = f"pattern:{pattern}"
                        self._local_ips[key] = {
                            "ip": pattern,
                            "type": "Pattern",
                            "status": "Active",
                            "source": "Server",
                        }
                    
                    # Get IPs from manager's state
                    ips = state.get_all_ips()
                    for ip in ips:
                        key = f"ip:{ip}"
                        self._local_ips[key] = {
                            "ip": ip,
                            "type": "IP",
                            "status": "Active",
                            "source": "Server",
                        }
                
                total = len(domains) + len(patterns) + len(ips)
                logger.info(f"Synced from manager: {len(domains)} domains, {len(patterns)} patterns, {len(ips)} IPs")
                self._notify_data_changed()
                
        except Exception as e:
            logger.error(f"Failed to sync from manager: {e}")
    
    # ========== Callbacks Registration ==========
    
    def on_data_changed(self, callback: Callable[[List[Dict]], None]) -> None:
        """Register callback for data changes."""
        if callback not in self._on_data_changed:
            self._on_data_changed.append(callback)
    
    def on_error(self, callback: Callable[[str], None]) -> None:
        """Register callback for errors."""
        if callback not in self._on_error:
            self._on_error.append(callback)
    
    def on_success(self, callback: Callable[[str], None]) -> None:
        """Register callback for success messages."""
        if callback not in self._on_success:
            self._on_success.append(callback)
    
    def _notify_data_changed(self) -> None:
        """Notify all data changed listeners."""
        data = self.get_all_ips()
        for callback in self._on_data_changed:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in data changed callback: {e}")
    
    def _notify_error(self, message: str) -> None:
        """Notify all error listeners."""
        for callback in self._on_error:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def _notify_success(self, message: str) -> None:
        """Notify all success listeners."""
        for callback in self._on_success:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error in success callback: {e}")
    
    # ========== Validation ==========
    
    @staticmethod
    def validate_ip(ip: str) -> Tuple[bool, str]:
        """
        Validate IP address format.
        
        Args:
            ip: IP address string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not ip:
            return False, "IP address cannot be empty"
        
        ip = ip.strip()
        
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        
        # IPv6 pattern (simplified)
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        
        # CIDR notation for IPv4
        cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
        
        if re.match(ipv4_pattern, ip):
            # Validate octets
            parts = ip.split(".")
            for part in parts:
                if int(part) > 255:
                    return False, f"Invalid IPv4 octet: {part}"
            return True, ""
        
        if re.match(cidr_pattern, ip):
            # Validate CIDR
            ip_part, cidr_part = ip.split("/")
            parts = ip_part.split(".")
            for part in parts:
                if int(part) > 255:
                    return False, f"Invalid IPv4 octet: {part}"
            if int(cidr_part) > 32:
                return False, f"Invalid CIDR: /{cidr_part}"
            return True, ""
        
        if re.match(ipv6_pattern, ip):
            return True, ""
        
        # Check for simplified IPv6
        if ":" in ip and not "." in ip:
            return True, ""  # Simplified check
        
        return False, f"Invalid IP format: {ip}"
    
    # ========== CRUD Operations ==========
    
    def add_ip(self, ip: str) -> bool:
        """
        Add IP address to whitelist.
        
        Args:
            ip: IP address to add
            
        Returns:
            True if successful
        """
        ip = ip.strip()
        
        # Validate
        is_valid, error = self.validate_ip(ip)
        if not is_valid:
            self._notify_error(f"Invalid IP: {error}")
            return False
        
        # Check duplicate
        with self._lock_data:
            if ip in self._local_ips:
                self._notify_error(f"IP already exists: {ip}")
                return False
        
        def add_worker():
            try:
                # Add to local list
                with self._lock_data:
                    try:
                        from shared.time_utils import now_vietnam
                        added_date = now_vietnam().strftime("%Y-%m-%d %H:%M")
                    except ImportError:
                        added_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    self._local_ips[ip] = {
                        "ip": ip,
                        "added_date": added_date,
                        "status": "Pending",
                        "source": "local"
                    }
                
                # If WhitelistManager supports adding IPs, call it
                if self._whitelist_manager:
                    if hasattr(self._whitelist_manager, 'add_ip'):
                        self._whitelist_manager.add_ip(ip)
                    elif hasattr(self._whitelist_manager, '_state'):
                        # Direct state manipulation (not recommended in production)
                        self._whitelist_manager._state._ips.add(ip)
                
                # Update status
                with self._lock_data:
                    if ip in self._local_ips:
                        self._local_ips[ip]["status"] = "Active"
                
                self._notify_data_changed()
                self._notify_success(f"IP added: {ip}")
                logger.info(f"IP added to whitelist: {ip}")
                
            except Exception as e:
                self._notify_error(f"Failed to add IP: {e}")
                logger.error(f"Failed to add IP {ip}: {e}")
        
        # Run in thread
        thread = threading.Thread(target=add_worker, daemon=True)
        thread.start()
        return True
    
    def remove_ip(self, ip: str) -> bool:
        """
        Remove IP address from whitelist.
        
        Args:
            ip: IP address to remove
            
        Returns:
            True if successful
        """
        ip = ip.strip()
        
        with self._lock_data:
            if ip not in self._local_ips:
                self._notify_error(f"IP not found: {ip}")
                return False
        
        def remove_worker():
            try:
                # Remove from local list
                with self._lock_data:
                    if ip in self._local_ips:
                        del self._local_ips[ip]
                
                # If WhitelistManager supports removing IPs, call it
                if self._whitelist_manager:
                    if hasattr(self._whitelist_manager, 'remove_ip'):
                        self._whitelist_manager.remove_ip(ip)
                    elif hasattr(self._whitelist_manager, '_state'):
                        # Direct state manipulation
                        self._whitelist_manager._state._ips.discard(ip)
                
                self._notify_data_changed()
                self._notify_success(f"IP removed: {ip}")
                logger.info(f"IP removed from whitelist: {ip}")
                
            except Exception as e:
                self._notify_error(f"Failed to remove IP: {e}")
                logger.error(f"Failed to remove IP {ip}: {e}")
        
        # Run in thread
        thread = threading.Thread(target=remove_worker, daemon=True)
        thread.start()
        return True
    
    def get_all_ips(self) -> List[Dict]:
        """
        Get all whitelisted IPs.
        
        Returns:
            List of IP dictionaries
        """
        with self._lock_data:
            return list(self._local_ips.values())
    
    def refresh(self) -> None:
        """Refresh whitelist data from manager."""
        def refresh_worker():
            try:
                # Force sync with server
                if self._whitelist_manager:
                    if hasattr(self._whitelist_manager, 'force_refresh'):
                        self._whitelist_manager.force_refresh()
                    elif hasattr(self._whitelist_manager, 'sync_now'):
                        self._whitelist_manager.sync_now()
                
                # Sync local list
                self._sync_from_manager()
                
                self._notify_success("Whitelist refreshed")
                logger.info("Whitelist refreshed")
                
            except Exception as e:
                self._notify_error(f"Refresh failed: {e}")
                logger.error(f"Whitelist refresh failed: {e}")
        
        thread = threading.Thread(target=refresh_worker, daemon=True)
        thread.start()
    
    def get_stats(self) -> Dict:
        """Get whitelist statistics."""
        with self._lock_data:
            # Count by type
            domains = sum(1 for ip in self._local_ips.values() if ip.get("type") == "Domain")
            patterns = sum(1 for ip in self._local_ips.values() if ip.get("type") == "Pattern")
            ips = sum(1 for ip in self._local_ips.values() if ip.get("type") == "IP")
            
            stats = {
                "total_ips": len(self._local_ips),
                "active": sum(1 for ip in self._local_ips.values() if ip.get("status") == "Active"),
                "pending": sum(1 for ip in self._local_ips.values() if ip.get("status") == "Pending"),
                "local": sum(1 for ip in self._local_ips.values() if ip.get("source") == "Local"),
                "server": sum(1 for ip in self._local_ips.values() if ip.get("source") == "Server"),
                "manager_domains": domains,
                "manager_ips": ips + patterns,
            }
        
        # Get stats from manager if available
        if self._whitelist_manager:
            if hasattr(self._whitelist_manager, 'get_stats'):
                manager_stats = self._whitelist_manager.get_stats()
                stats.update({
                    "sync_count": manager_stats.get("sync_count", 0),
                })
        
        return stats


# Convenience function
def get_whitelist_controller() -> WhitelistController:
    """Get WhitelistController singleton instance."""
    return WhitelistController()
