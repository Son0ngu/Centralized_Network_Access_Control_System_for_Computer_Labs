import logging
import subprocess
from typing import Dict, Optional

from .provider import FirewallProvider, get_write_provider
from .utils import FirewallUtils

logger = logging.getLogger("firewall.policy")

class PolicyManager:
    
    def __init__(self, write_provider: Optional[FirewallProvider] = None):
        self._original_policies: Dict[str, str] = {}
        self.default_deny_enabled = False
        self._write_provider = write_provider or get_write_provider()
    
    def get_current_policy(self) -> Dict[str, str]:
        # Get current firewall policy for all profiles.
        try:
            result = FirewallUtils.run_netsh_command(
                ["advfirewall", "show", "allprofiles"]
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to get firewall policy: {result.stderr}")
                return {}
            
            policies = {}
            current_profile = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                if "Domain Profile Settings:" in line:
                    current_profile = "domain"
                elif "Private Profile Settings:" in line:
                    current_profile = "private"
                elif "Public Profile Settings:" in line:
                    current_profile = "public"
                elif current_profile and "Outbound connections:" in line:
                    action = "block" if "block" in line.lower() else "allow"
                    policies[current_profile] = action
            
            return policies
            
        except Exception as e:
            logger.error(f"Error getting current firewall policy: {e}")
            return {}
    
    def backup_current_policy(self):
        try:
            self._original_policies = self.get_current_policy()
            logger.debug(f"Backed up original policies: {self._original_policies}")
        except Exception as e:
            logger.warning(f"Failed to backup current policy: {e}")
            self._original_policies = {}
    
    def enable_default_deny(self) -> bool:
        try:
            logger.info("Enabling Windows Firewall Default Deny policy...")
            
            current_policies = self.get_current_policy()
            logger.debug(f"Current firewall policies: {current_policies}")
            
            profiles = ["domain", "private", "public"]
            success_count = 0
            
            for profile in profiles:
                if current_policies.get(profile) == "block":
                    logger.info(f"{profile.title()} profile already set to block outbound")
                    success_count += 1
                    continue
                
                if self._write_provider.set_profile_outbound_policy(profile, "block"):
                    logger.info(f"{profile.title()} profile set to Default Deny")
                    success_count += 1
                else:
                    logger.error(f"Failed to set {profile.title()} profile")
            
            if success_count >= 1:
                if self.verify_default_deny():
                    self.default_deny_enabled = True
                    logger.info("Default Deny policy enabled successfully")
                    return True
                else:
                    logger.warning("Policy set but verification failed - proceeding anyway")
                    self.default_deny_enabled = True
                    return True
            else:
                logger.error("Failed to set any firewall profiles")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling Default Deny policy: {e}")
            return False
    
    def verify_default_deny(self) -> bool:
        try:
            result = FirewallUtils.run_netsh_command(
                ["advfirewall", "show", "allprofiles"]
            )
            
            if result.returncode != 0:
                logger.warning(f"Could not verify firewall policy: {result.stderr}")
                return False
            
            output = result.stdout.lower()
            
            # Check for block indicators
            profiles_verified = 0
            lines = output.split('\n')
            current_profile = None
            
            for line in lines:
                line_lower = line.strip().lower()
                
                # Detect profile headers
                if any(x in line_lower for x in ['domain profile', 'private profile', 'public profile']):
                    current_profile = line.strip()
                
                elif current_profile and any(x in line_lower for x in ['outbound connections', 'firewall policy']):
                    if 'block' in line_lower:
                        profiles_verified += 1
            
            if profiles_verified == 0:
                if 'blockoutbound' in output or output.count('block') >= 2:
                    profiles_verified = 1
            
            return profiles_verified >= 1
            
        except Exception as e:
            logger.warning(f"Error verifying Default Deny policy: {e}")
            return False
    
    def restore_original_policy(self) -> bool:
        try:
            if not self._original_policies:
                logger.info("No original policy to restore, using defaults")
                return self.restore_default_policy()
            
            logger.info("Restoring original firewall policy...")
            success_count = 0
            
            for profile, action in self._original_policies.items():
                if self._write_provider.set_profile_outbound_policy(profile, action):
                    logger.info(f"{profile.title()} profile restored to {action} outbound")
                    success_count += 1
                else:
                    logger.error(f"Failed to restore {profile.title()} profile")
            
            if success_count > 0:
                self.default_deny_enabled = False
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error restoring original policy: {e}")
            return False
    
    def restore_default_policy(self) -> bool:
        try:
            logger.info("Restoring Windows Firewall to default policy...")
            
            profiles = ["domain", "private", "public"]
            success_count = 0
            
            for profile in profiles:
                if self._write_provider.set_profile_outbound_policy(profile, "allow"):
                    logger.info(f"{profile.title()} profile restored to default")
                    success_count += 1
                else:
                    logger.error(f"Failed to restore {profile.title()} profile")
            
            if success_count > 0:
                self.default_deny_enabled = False
            
            return success_count == len(profiles)
            
        except Exception as e:
            logger.error(f"Error restoring default policy: {e}")
            return False

    def restore_policies(self, policies: Dict[str, str]) -> bool:
        """Restore explicit profile outbound policies from a snapshot."""
        try:
            success_count = 0
            for profile, action in (policies or {}).items():
                if action not in ("allow", "block"):
                    continue
                if self._write_provider.set_profile_outbound_policy(profile, action):
                    logger.debug("Restored %s profile to %s", profile, action)
                    success_count += 1
                else:
                    logger.warning("Failed to restore %s profile", profile)
            if success_count > 0:
                self.default_deny_enabled = False
            return success_count > 0
        except Exception as e:
            logger.error(f"Error restoring explicit policies: {e}")
            return False
