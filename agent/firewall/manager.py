"""
Firewall Manager - Simplified for DNS Proxy Architecture
---------------------------------------------------------
With DNS Proxy/Sinkhole architecture, whitelist enforcement is handled
at DNS level. This manager is now OPTIONAL and only used for:
1. Cleanup of any leftover rules on shutdown
2. Legacy compatibility

NOTE: Firewall rules are NOT created during normal operation.
DNS Proxy returns NXDOMAIN for blocked domains, preventing connections.
"""

import logging
from typing import Dict, List, Set

from agent.shared.time_utils import now_iso
from .policy import PolicyManager
from .rules import RulesManager
from .utils import FirewallUtils

logger = logging.getLogger("firewall.manager")


class FirewallManager:
    """
    Simplified Firewall Manager for DNS Proxy Architecture.
    
    Primary whitelist enforcement is done by DNS Proxy (Sinkhole).
    This class is kept for:
    - Cleanup on shutdown
    - Legacy API compatibility
    - Manual rule management if needed
    """
    
    def __init__(self, rule_prefix: str = "FirewallController"):
        self.rule_prefix = rule_prefix
        
        # Initialize sub-managers
        self.policy_manager = PolicyManager()
        self.rules_manager = RulesManager(rule_prefix)
        
        # State tracking (mostly unused with DNS Proxy)
        self.essential_ips: Set[str] = set()
        self.whitelist_mode_active = False
        
        # Check admin privileges
        if not FirewallUtils.has_admin_privileges():
            logger.warning("Firewall operations require administrator privileges")
        
        # Load existing rules for cleanup purposes
        try:
            self.rules_manager.load_existing_rules()
            self.policy_manager.backup_current_policy()
            logger.info(f"FirewallManager initialized (DNS Proxy mode - rules disabled)")
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    # ========================================
    # CLEANUP METHODS (Still needed)
    # ========================================
    
    def cleanup_all_rules(self) -> bool:
        """Remove all firewall rules created by this manager."""
        try:
            logger.info("Cleaning up all firewall rules...")
            
            # Remove all our rules
            rules_success = self.rules_manager.clear_all_rules()
            
            # Restore original firewall policy
            policy_success = self.policy_manager.restore_original_policy()
            
            # Clear state
            self.essential_ips.clear()
            self.whitelist_mode_active = False
            
            success = rules_success and policy_success
            
            if success:
                logger.info("Firewall cleanup completed")
            else:
                logger.warning("Some cleanup operations failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            return False
    
    def clear_all_rules(self) -> bool:
        """Remove all firewall rules created by this manager."""
        return self.rules_manager.clear_all_rules()
    
    # Alias for compatibility
    cleanup_whitelist_firewall = cleanup_all_rules

    # ========================================
    # PROPERTIES (For status/monitoring)
    # ========================================
    
    @property
    def allowed_ips(self) -> Set[str]:
        """Get allowed IPs from rules manager."""
        return self.rules_manager.allowed_ips
    
    @property
    def default_deny_enabled(self) -> bool:
        """Check if default deny is enabled (always False with DNS Proxy)."""
        return False  # DNS Proxy handles blocking, not firewall policy

    # ========================================
    # STATUS METHODS
    # ========================================
    
    def get_status(self) -> Dict:
        """Get firewall manager status."""
        return {
            "mode": "dns_proxy",
            "firewall_rules_enabled": False,
            "allowed_ips_count": len(self.allowed_ips),
            "rule_prefix": self.rule_prefix,
            "note": "DNS Proxy handles whitelist enforcement",
            "status_timestamp": now_iso()
        }
    
    # Alias for compatibility
    get_whitelist_status = get_status
    get_firewall_policy_status = get_status

    # ========================================
    # LEGACY API (No-op for compatibility)
    # ========================================
    
    def add_ip_to_whitelist(self, ip: str, reason: str = "dynamic_addition") -> bool:
        """
        Legacy: Add IP to whitelist.
        NOTE: With DNS Proxy, this is a no-op. DNS Proxy handles all blocking.
        """
        logger.debug(f"add_ip_to_whitelist called for {ip} - no-op (DNS Proxy mode)")
        return True  # Always succeed since DNS Proxy handles it
    
    def remove_ip_from_whitelist(self, ip: str) -> bool:
        """
        Legacy: Remove IP from whitelist.
        NOTE: With DNS Proxy, this is a no-op. DNS Proxy handles all blocking.
        """
        logger.debug(f"remove_ip_from_whitelist called for {ip} - no-op (DNS Proxy mode)")
        return True  # Always succeed
    
    def update_whitelist(self, domains: set, ips: set) -> bool:
        """
        Legacy: Update firewall whitelist.
        NOTE: With DNS Proxy, this is a no-op. DNS Proxy handles all blocking.
        """
        logger.debug(f"update_whitelist called - no-op (DNS Proxy mode)")
        return True
    
    def sync_whitelist_changes(self, old_ips: Set[str], new_ips: Set[str]) -> bool:
        """
        Legacy: Sync whitelist changes.
        NOTE: With DNS Proxy, this is a no-op.
        """
        logger.debug(f"sync_whitelist_changes called - no-op (DNS Proxy mode)")
        return True
    
    def is_blocked(self, ip: str) -> bool:
        """Legacy: Check if IP is blocked. Always False with DNS Proxy."""
        return False
    
    def get_blocked_ips(self) -> List[str]:
        """Legacy: Get blocked IPs. Returns empty with DNS Proxy."""
        return []
    
    def block_ip(self, ip: str, domain: str = None) -> bool:
        """Legacy: Block IP. No-op with DNS Proxy."""
        return True
    
    def unblock_ip(self, ip: str) -> bool:
        """Legacy: Unblock IP. No-op with DNS Proxy."""
        return True
    
    def validate_firewall_state(self) -> Dict:
        """Validate firewall state."""
        return {
            "mode": "dns_proxy",
            "dns_proxy_active": True,
            "firewall_rules_needed": False,
            "issues": [],
            "validated_at": now_iso()
        }
    
    def test_whitelist_connectivity(self, sample_ips: List[str]) -> Dict[str, bool]:
        """Test connectivity to IPs."""
        results = {}
        for ip in sample_ips[:5]:
            try:
                results[ip] = FirewallUtils.test_ip_connectivity(ip)
            except:
                results[ip] = False
        return results
    
    # Internal methods for compatibility
    def _restore_original_policy(self) -> bool:
        return self.policy_manager.restore_original_policy()
    
    def _restore_default_policy(self) -> bool:
        return self.policy_manager.restore_default_policy()
