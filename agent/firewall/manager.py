"""
Firewall Manager - Main class for Windows Firewall management.
Vietnam ONLY - Modular implementation using Default Deny policy.
"""

import logging
from typing import Dict, List, Optional, Set

from shared.time_utils import now_iso
from .policy import PolicyManager
from .rules import RulesManager
from .utils import FirewallUtils

logger = logging.getLogger("firewall.manager")


class FirewallManager:
    """
    Simplified Firewall Manager using Windows Default Deny Policy.
    NO BLOCK RULES - Only ALLOW rules + Default Deny Policy.
    """
    
    def __init__(self, rule_prefix: str = "FirewallController"):
        """Initialize the firewall manager with Default Deny approach."""
        self.rule_prefix = rule_prefix
        
        # Initialize sub-managers
        self.policy_manager = PolicyManager()
        self.rules_manager = RulesManager(rule_prefix)
        
        # State tracking
        self.essential_ips: Set[str] = set()
        self.whitelist_mode_active = False
        
        # Check admin privileges
        if not FirewallUtils.has_admin_privileges():
            logger.warning("⚠ Firewall operations require administrator privileges")
        
        # Load existing rules and backup policy
        try:
            self.rules_manager.load_existing_rules()
            self.policy_manager.backup_current_policy()
            
            # Check if Default Deny is already active
            if self.policy_manager.verify_default_deny():
                self.policy_manager.default_deny_enabled = True
                if self.rules_manager.allowed_ips:
                    self.whitelist_mode_active = True
                    logger.info("Detected existing whitelist-only firewall mode")
            
            logger.info(f"✅ FirewallManager initialized with prefix: {self.rule_prefix}")
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
    
    # ========================================
    # MAIN WHITELIST SETUP
    # ========================================
    
    def setup_whitelist_firewall(self, whitelisted_ips: Set[str], essential_ips: Set[str] = None) -> bool:
        """Setup whitelist-based firewall using Windows Default Deny policy."""
        try:
            logger.info("🔒 Setting up whitelist firewall with DEFAULT DENY policy...")
            
            if not whitelisted_ips:
                logger.error("❌ No whitelisted IPs provided")
                return False
            
            # Get essential IPs if not provided
            if essential_ips is None:
                essential_ips = FirewallUtils.get_essential_ips()
            
            # Filter IPv4 only
            whitelisted_ips_v4 = {ip for ip in whitelisted_ips if FirewallUtils.is_valid_ipv4(ip)}
            essential_ips_v4 = {ip for ip in essential_ips if FirewallUtils.is_valid_ipv4(ip)}
            
            all_allowed_ips = whitelisted_ips_v4.union(essential_ips_v4)
            
            logger.info(f"📋 Total IPv4 IPs to allow: {len(all_allowed_ips)}")
            
            # Step 1: Enable Default Deny policy
            if not self.policy_manager.enable_default_deny():
                logger.error("❌ Failed to enable Default Deny policy")
                return False
            
            # Step 2: Create allow rules
            success = self.rules_manager.create_allow_rules_batch(all_allowed_ips)
            
            if success:
                self.whitelist_mode_active = True
                self.essential_ips = essential_ips_v4
                
                logger.info("✅ Whitelist firewall with Default Deny setup completed!")
                logger.info("🔒 Windows Firewall Policy: DENY all outbound by default")
                logger.info(f"📝 Created {len(all_allowed_ips)} ALLOW rules for whitelisted traffic")
                
                return True
            else:
                logger.error("❌ Failed to create allow rules")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up whitelist firewall: {e}")
            return False
    
    # ========================================
    # DYNAMIC IP MANAGEMENT
    # ========================================
    
    def add_ip_to_whitelist(self, ip: str, reason: str = "dynamic_addition") -> bool:
        """Add IP to whitelist dynamically."""
        try:
            if not FirewallUtils.is_valid_ipv4(ip):
                logger.warning(f"Invalid IPv4: {ip}")
                return False
            
            if ip in self.allowed_ips:
                logger.debug(f"IP {ip} already in whitelist")
                return True
            
            success = self.rules_manager.create_allow_rule(ip)
            
            if success:
                logger.info(f"✓ Added {ip} to whitelist ({reason})")
            else:
                logger.error(f"✗ Failed to add {ip} to whitelist")
            
            return success
                
        except Exception as e:
            logger.error(f"Error adding IP to whitelist: {e}")
            return False
    
    def remove_ip_from_whitelist(self, ip: str) -> bool:
        """Remove IP from whitelist."""
        try:
            if ip not in self.allowed_ips:
                logger.debug(f"IP {ip} not in whitelist")
                return True
            
            success = self.rules_manager.remove_allow_rule(ip)
            
            if success:
                logger.info(f"✓ Removed {ip} from whitelist")
            else:
                logger.error(f"✗ Failed to remove {ip} from whitelist")
            
            return success
                
        except Exception as e:
            logger.error(f"Error removing IP from whitelist: {e}")
            return False
    
    def sync_whitelist_changes(self, old_ips: Set[str], new_ips: Set[str]) -> bool:
        """Sync whitelist changes."""
        try:
            added_ips = new_ips - old_ips
            removed_ips = old_ips - new_ips
            
            if not added_ips and not removed_ips:
                logger.debug("No IP changes to sync")
                return True
            
            logger.info(f"🔄 Syncing: +{len(added_ips)} IPs, -{len(removed_ips)} IPs")
            
            success_count = 0
            error_count = 0
            
            # Add new IPs
            for ip in added_ips:
                if self.add_ip_to_whitelist(ip, "sync_update"):
                    success_count += 1
                else:
                    error_count += 1
            
            # Remove old IPs
            for ip in removed_ips:
                if self.remove_ip_from_whitelist(ip):
                    success_count += 1
                else:
                    error_count += 1
            
            logger.info(f"🔄 Sync completed: {success_count} changes, {error_count} errors")
            return error_count == 0
            
        except Exception as e:
            logger.error(f"Error syncing whitelist: {e}")
            return False
    
    # ========================================
    # CLEANUP
    # ========================================
    
    def cleanup_whitelist_firewall(self) -> bool:
        """Clean up whitelist firewall and restore original policy."""
        try:
            logger.info("🧹 Cleaning up whitelist firewall...")
            
            # Step 1: Remove all our allow rules
            rules_success = self.rules_manager.clear_all_rules()
            
            # Step 2: Restore original Windows Firewall policy
            if self.policy_manager.restore_original_policy():
                logger.info("✓ Windows Firewall policy restored to original state")
            else:
                logger.warning("⚠ Failed to restore original policy, using defaults")
                self.policy_manager.restore_default_policy()
            
            # Step 3: Clear state
            self.essential_ips.clear()
            self.whitelist_mode_active = False
            
            logger.info("✅ Whitelist firewall cleanup completed")
            return rules_success
            
        except Exception as e:
            logger.error(f"Error cleaning up whitelist firewall: {e}")
            return False
    
    def clear_all_rules(self) -> bool:
        """Remove all firewall rules created by this manager."""
        return self.rules_manager.clear_all_rules()
    
    def cleanup_all_rules(self) -> bool:
        """Complete cleanup for whitelist-only mode (legacy compatibility)."""
        try:
            logger.info("🧹 Performing complete firewall cleanup...")
            
            # Step 1: Remove all our allow rules
            rules_success = self.rules_manager.clear_all_rules()
            
            # Step 2: Restore original firewall policy
            policy_success = self.policy_manager.restore_original_policy()
            
            # Step 3: Clear all state
            self.essential_ips.clear()
            self.whitelist_mode_active = False
            
            success = rules_success and policy_success
            
            if success:
                logger.info("✅ Complete firewall cleanup successful")
            else:
                logger.warning("⚠ Some cleanup operations failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in complete cleanup: {e}")
            return False
    
    # ========================================
    # PROPERTIES (DELEGATED)
    # ========================================
    
    @property
    def allowed_ips(self) -> Set[str]:
        """Get allowed IPs from rules manager."""
        return self.rules_manager.allowed_ips
    
    @property
    def default_deny_enabled(self) -> bool:
        """Check if default deny is enabled."""
        return self.policy_manager.default_deny_enabled
    
    # ========================================
    # STATUS & MONITORING
    # ========================================
    
    def get_whitelist_status(self) -> Dict:
        """Get current status of whitelist-only firewall mode."""
        return {
            "whitelist_mode_active": self.whitelist_mode_active,
            "default_deny_enabled": self.default_deny_enabled,
            "allowed_ips_count": len(self.allowed_ips),
            "essential_ips_count": len(self.essential_ips),
            "total_allowed": len(self.allowed_ips) + len(self.essential_ips),
            "rule_prefix": self.rule_prefix,
            "approach": "default_deny_with_allow_rules",
            "status_timestamp": now_iso()
        }
    
    def get_firewall_policy_status(self) -> Dict:
        """Get current Windows Firewall policy status."""
        try:
            policies = self.policy_manager.get_current_policy()
            
            return {
                "default_deny_active": self.default_deny_enabled,
                "profiles": policies,
                "whitelist_mode_active": self.whitelist_mode_active,
                "allowed_ips_count": len(self.allowed_ips),
                "checked_at": now_iso()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "checked_at": now_iso()
            }
    
    def validate_firewall_state(self) -> Dict:
        """Validate current firewall state."""
        try:
            logger.info("🔍 Validating firewall state...")
            
            validation_result = {
                "whitelist_mode_active": self.whitelist_mode_active,
                "default_deny_enabled": self.default_deny_enabled,
                "total_allowed_ips": len(self.allowed_ips),
                "policy_verified": False,
                "issues": [],
                "validated_at": now_iso()
            }
            
            # Check policy state
            if self.whitelist_mode_active:
                policy_verified = self.policy_manager.verify_default_deny()
                validation_result["policy_verified"] = policy_verified
                
                if not policy_verified:
                    validation_result["issues"].append("Default Deny policy may not be active")
            
            # Check for missing essential IPs
            if not self.essential_ips:
                validation_result["issues"].append("No essential IPs configured")
            
            logger.info(f"🔍 Validation complete: {len(validation_result['issues'])} issues found")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating firewall state: {e}")
            return {"error": str(e), "validated_at": now_iso()}
    
    def test_whitelist_connectivity(self, sample_ips: List[str]) -> Dict[str, bool]:
        """Test connectivity to sample whitelisted IPs."""
        try:
            logger.info(f"🔌 Testing connectivity to {len(sample_ips)} sample IPs...")
            
            results = {}
            for ip in sample_ips[:5]:  # Test max 5 IPs
                results[ip] = FirewallUtils.test_ip_connectivity(ip)
            
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"🔌 Connectivity test: {success_count}/{len(results)} IPs accessible")
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing connectivity: {e}")
            return {}
    
    # ========================================
    # LEGACY COMPATIBILITY
    # ========================================
    
    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked (not in whitelist when Default Deny is active)."""
        if self.whitelist_mode_active and self.default_deny_enabled:
            return ip not in self.allowed_ips and ip not in self.essential_ips
        return False
    
    def get_blocked_ips(self) -> List[str]:
        """Get blocked IPs (in Default Deny mode, all non-whitelisted IPs are blocked)."""
        if self.whitelist_mode_active and self.default_deny_enabled:
            return ["ALL_NON_WHITELISTED_IPS"]
        return []
    
    def block_ip(self, ip: str, domain: Optional[str] = None) -> bool:
        """Legacy: In Default Deny mode, blocking means removing from whitelist."""
        if self.whitelist_mode_active:
            return self.remove_ip_from_whitelist(ip)
        logger.info(f"Default Deny not active - cannot block {ip}")
        return False
    
    def unblock_ip(self, ip: str) -> bool:
        """Legacy: In Default Deny mode, unblocking means adding to whitelist."""
        if self.whitelist_mode_active:
            return self.add_ip_to_whitelist(ip, "unblock_request")
        logger.info(f"Default Deny not active - cannot unblock {ip}")
        return False
    
    # Internal policy methods for compatibility
    def _restore_original_policy(self) -> bool:
        """Wrapper for policy manager."""
        return self.policy_manager.restore_original_policy()
    
    def _restore_default_policy(self) -> bool:
        """Wrapper for policy manager."""
        return self.policy_manager.restore_default_policy()
    
    # ========================================
    # WHITELIST UPDATE (CALLED BY WhitelistManager)
    # ========================================
    
    def update_whitelist(self, domains: set, ips: set) -> bool:
        """
        Update firewall rules based on whitelist data.
        Called by WhitelistManager after sync.
        
        Args:
            domains: Set of whitelisted domains (need DNS resolution)
            ips: Set of whitelisted IPs
            
        Returns:
            True if update successful
        """
        try:
            logger.info(f"🔄 Updating firewall whitelist: {len(domains)} domains, {len(ips)} IPs")
            
            # Get current allowed IPs
            old_ips = self.allowed_ips.copy()
            
            # Collect all IPs to whitelist
            new_ips: Set[str] = set()
            
            # Add direct IPs from whitelist
            for ip in ips:
                if FirewallUtils.is_valid_ipv4(ip):
                    new_ips.add(ip)
            
            # Resolve domains to IPs
            resolved_ips = self._resolve_domains_to_ips(domains)
            new_ips.update(resolved_ips)
            
            logger.info(f"📋 Total IPs after resolution: {len(new_ips)} ({len(resolved_ips)} from DNS)")
            
            # If no IPs, don't update (safety)
            if not new_ips:
                logger.warning("⚠ No valid IPs to whitelist, keeping current rules")
                return False
            
            # Setup whitelist firewall if not already active
            if not self.whitelist_mode_active:
                return self.setup_whitelist_firewall(new_ips)
            
            # Sync changes
            return self.sync_whitelist_changes(old_ips, new_ips)
            
        except Exception as e:
            logger.error(f"Error updating whitelist: {e}")
            return False
    
    def _resolve_domains_to_ips(self, domains: set) -> Set[str]:
        """
        Resolve domains to IP addresses.
        
        Args:
            domains: Set of domain names
            
        Returns:
            Set of resolved IPv4 addresses
        """
        resolved_ips: Set[str] = set()
        
        if not domains:
            return resolved_ips
        
        try:
            # Try to use OptimizedDNSResolver if available
            try:
                from network import OptimizedDNSResolver
                resolver = OptimizedDNSResolver(max_workers=10, timeout=5.0)
                
                # Resolve in parallel
                results = resolver.resolve_multiple_parallel(list(domains))
                
                for domain, record in results.items():
                    if record.ipv4:
                        for ip in record.ipv4:
                            if FirewallUtils.is_valid_ipv4(ip):
                                resolved_ips.add(ip)
                                
                logger.info(f"✓ Resolved {len(domains)} domains -> {len(resolved_ips)} IPs (optimized)")
                
            except ImportError:
                # Fallback to simple socket resolution
                import socket
                
                for domain in domains:
                    try:
                        # Get all addresses
                        results = socket.getaddrinfo(domain, None, socket.AF_INET)
                        for result in results:
                            ip = result[4][0]
                            if FirewallUtils.is_valid_ipv4(ip):
                                resolved_ips.add(ip)
                    except socket.gaierror:
                        logger.debug(f"Could not resolve: {domain}")
                    except Exception as e:
                        logger.debug(f"Error resolving {domain}: {e}")
                
                logger.info(f"✓ Resolved {len(domains)} domains -> {len(resolved_ips)} IPs (socket)")
                
        except Exception as e:
            logger.error(f"Error in DNS resolution: {e}")
        
        return resolved_ips
    
    def enable_whitelist_mode(self, server_urls: List[str] = None, whitelist_ips: Set[str] = None, whitelist_domains: Set[str] = None) -> bool:
        """
        Enable whitelist-only mode with Default Deny policy.
        Should be called during agent startup if firewall.mode == "whitelist_only".
        
        IMPORTANT: This adds allow rules for server URLs and essential IPs
        BEFORE enabling Default Deny to prevent blocking server connections.
        
        Args:
            server_urls: List of server URLs to allow (will resolve to IPs)
            whitelist_ips: Set of whitelisted IPs from server sync
            whitelist_domains: Set of domains to resolve to IPs
        
        Returns:
            True if enabled successfully
        """
        try:
            if self.whitelist_mode_active and self.default_deny_enabled:
                logger.info("Whitelist mode already active")
                return True
            
            logger.info("🔒 Enabling whitelist-only mode...")
            
            # Step 1: Collect all IPs to allow BEFORE enabling Default Deny
            all_allowed_ips = set()
            
            # 1a. Add essential IPs (DNS, localhost, gateway)
            essential_ips = FirewallUtils.get_essential_ips()
            all_allowed_ips.update(essential_ips)
            self.essential_ips = essential_ips
            logger.info(f"📝 Essential IPs: {len(essential_ips)}")
            
            # 1b. Resolve server URLs to IPs
            if server_urls:
                server_ips = self._resolve_server_urls(server_urls)
                all_allowed_ips.update(server_ips)
                logger.info(f"📝 Server IPs resolved: {len(server_ips)} - {server_ips}")
            
            # 1c. Add direct whitelist IPs from server sync
            if whitelist_ips:
                # Filter IPv4 only
                whitelist_ipv4 = {ip for ip in whitelist_ips if FirewallUtils.is_valid_ipv4(ip)}
                all_allowed_ips.update(whitelist_ipv4)
                logger.info(f"📝 Whitelist direct IPs: {len(whitelist_ipv4)}")
            
            # 1d. Resolve whitelist domains to IPs
            if whitelist_domains:
                logger.info(f"📝 Resolving {len(whitelist_domains)} whitelist domains...")
                domain_ips = self._resolve_domains_to_ips(whitelist_domains)
                all_allowed_ips.update(domain_ips)
                logger.info(f"📝 Whitelist domains resolved to: {len(domain_ips)} IPs")
            
            logger.info(f"📋 Total IPs to allow: {len(all_allowed_ips)}")
            
            # Step 2: Create allow rules FIRST (before Default Deny)
            logger.info("Step 2: Creating ALLOW rules before enabling Default Deny...")
            for ip in all_allowed_ips:
                self.rules_manager.create_allow_rule(ip)
            
            # Step 3: NOW enable Default Deny policy (after rules are created)
            logger.info("Step 3: Enabling Default Deny policy...")
            if not self.policy_manager.enable_default_deny():
                logger.error("❌ Failed to enable Default Deny policy")
                return False
            
            self.whitelist_mode_active = True
            
            logger.info("✅ Whitelist-only mode enabled successfully")
            logger.info(f"📝 Total ALLOW rules created: {len(all_allowed_ips)}")
            logger.info("🔒 Default Deny policy is now active")
            
            return True
            
        except Exception as e:
            logger.error(f"Error enabling whitelist mode: {e}")
            return False
    
    def _resolve_domains_to_ips(self, domains: Set[str]) -> Set[str]:
        """Resolve domain names to IP addresses."""
        import socket
        
        ips = set()
        for domain in domains:
            try:
                # Skip wildcards - they can't be resolved directly
                if '*' in domain or '?' in domain:
                    # For wildcards, try to resolve base domain
                    base_domain = domain.replace('*.', '').replace('*', '')
                    if base_domain:
                        domain = base_domain
                    else:
                        continue
                
                # Remove protocol if present
                domain = domain.replace('http://', '').replace('https://', '')
                domain = domain.split('/')[0]  # Remove path
                domain = domain.split(':')[0]  # Remove port
                
                if not domain:
                    continue
                
                # Try to resolve
                try:
                    ip = socket.gethostbyname(domain)
                    ips.add(ip)
                    logger.debug(f"Resolved {domain} -> {ip}")
                except socket.gaierror:
                    # Try to get all IPs
                    try:
                        _, _, ip_list = socket.gethostbyname_ex(domain)
                        for ip in ip_list:
                            ips.add(ip)
                            logger.debug(f"Resolved {domain} -> {ip}")
                    except:
                        logger.debug(f"Could not resolve domain: {domain}")
            except Exception as e:
                logger.debug(f"Error resolving {domain}: {e}")
        
        return ips
    
    def _resolve_server_urls(self, urls: List[str]) -> Set[str]:
        """Resolve server URLs to IP addresses."""
        import socket
        from urllib.parse import urlparse
        
        ips = set()
        for url in urls:
            try:
                parsed = urlparse(url)
                hostname = parsed.hostname
                if hostname:
                    # Resolve hostname to IP
                    try:
                        ip = socket.gethostbyname(hostname)
                        ips.add(ip)
                        logger.debug(f"Resolved {hostname} -> {ip}")
                    except socket.gaierror:
                        # Try to get all IPs
                        try:
                            _, _, ip_list = socket.gethostbyname_ex(hostname)
                            for ip in ip_list:
                                ips.add(ip)
                        except:
                            logger.warning(f"Could not resolve {hostname}")
            except Exception as e:
                logger.warning(f"Error resolving {url}: {e}")
        
        return ips