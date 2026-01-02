"""
Profile Manager - Backup and Restore System Settings
=====================================================
Saves and restores DNS and firewall settings before/after agent operation.

Features:
- Save DNS configuration per adapter
- Save firewall policy state
- Atomic restore on shutdown/cleanup
- JSON-based profile storage

Usage:
    manager = ProfileManager()
    
    # Before starting agent
    manager.backup_all()
    
    # When stopping agent
    manager.restore_all()
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("utils.profile_manager")

# Default profile directory
DEFAULT_PROFILE_DIR = Path.home() / ".firewall_agent" / "profiles"


@dataclass
class DNSAdapterProfile:
    """DNS configuration for a single network adapter."""
    adapter_name: str
    ipv4_dns: List[str] = field(default_factory=list)
    ipv4_source: str = "dhcp"  # dhcp, static
    ipv6_dns: List[str] = field(default_factory=list)
    ipv6_source: str = "dhcp"
    interface_index: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class FirewallProfile:
    """Windows Firewall profile state."""
    domain_enabled: bool = True
    private_enabled: bool = True
    public_enabled: bool = True
    # Our rules to track for cleanup
    created_rules: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemProfile:
    """Complete system profile backup."""
    version: str = "1.0"
    created_at: str = ""
    hostname: str = ""
    dns_adapters: Dict[str, DNSAdapterProfile] = field(default_factory=dict)
    firewall: FirewallProfile = field(default_factory=FirewallProfile)
    hosts_file_backup: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "hostname": self.hostname,
            "dns_adapters": {
                name: asdict(adapter) 
                for name, adapter in self.dns_adapters.items()
            },
            "firewall": asdict(self.firewall),
            "hosts_file_backup": self.hosts_file_backup,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SystemProfile":
        """Create from dictionary."""
        profile = cls(
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
            hostname=data.get("hostname", ""),
            notes=data.get("notes", ""),
            hosts_file_backup=data.get("hosts_file_backup"),
        )
        
        # Restore DNS adapters
        for name, adapter_data in data.get("dns_adapters", {}).items():
            profile.dns_adapters[name] = DNSAdapterProfile(**adapter_data)
        
        # Restore firewall profile
        fw_data = data.get("firewall", {})
        profile.firewall = FirewallProfile(**fw_data)
        
        return profile


class ProfileManager:
    """
    Manages backup and restore of system settings.
    
    Ensures the system can be restored to its original state
    after the agent modifies DNS and firewall settings.
    """
    
    PROFILE_FILENAME = "system_profile.json"
    HOSTS_BACKUP_FILENAME = "hosts.backup"
    
    def __init__(self, profile_dir: Path = None):
        self._profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_profile: Optional[SystemProfile] = None
        self._profile_path = self._profile_dir / self.PROFILE_FILENAME
        self._hosts_backup_path = self._profile_dir / self.HOSTS_BACKUP_FILENAME
        
        logger.info(f"Profile Manager initialized (dir: {self._profile_dir})")
    
    # ========================================
    # PUBLIC API
    # ========================================
    
    def backup_all(self, force: bool = False) -> bool:
        """
        Backup all system settings before agent starts.
        
        Args:
            force: Overwrite existing backup if True
            
        Returns:
            True if backup successful
        """
        # Check for existing backup
        if self._profile_path.exists() and not force:
            logger.info("Existing profile found, loading instead of creating new")
            return self.load_profile()
        
        try:
            import socket
            
            profile = SystemProfile(
                created_at=datetime.now().isoformat(),
                hostname=socket.gethostname(),
            )
            
            # Backup DNS settings
            self._backup_dns_settings(profile)
            
            # Backup firewall state
            self._backup_firewall_state(profile)
            
            # Backup hosts file
            self._backup_hosts_file(profile)
            
            # Save profile
            self._current_profile = profile
            self._save_profile()
            
            logger.info(f"System profile backed up: {len(profile.dns_adapters)} adapters")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup system profile: {e}")
            return False
    
    def restore_all(self) -> Tuple[bool, List[str]]:
        """
        Restore all system settings to backed up state.
        
        Returns:
            Tuple of (success, list of errors/warnings)
        """
        errors: List[str] = []
        
        # Load profile if not loaded
        if not self._current_profile:
            if not self.load_profile():
                return False, ["No profile to restore from"]
        
        profile = self._current_profile
        
        # Restore in reverse order of changes
        
        # 1. Remove agent firewall rules
        try:
            self._cleanup_agent_firewall_rules()
        except Exception as e:
            errors.append(f"Firewall cleanup error: {e}")
        
        # 2. Restore hosts file
        try:
            self._restore_hosts_file()
        except Exception as e:
            errors.append(f"Hosts file restore error: {e}")
        
        # 3. Restore DNS settings
        for adapter_name, adapter_profile in profile.dns_adapters.items():
            try:
                self._restore_adapter_dns(adapter_profile)
            except Exception as e:
                errors.append(f"DNS restore error ({adapter_name}): {e}")
        
        # 4. Flush DNS cache
        self._flush_dns_cache()
        
        # Cleanup profile after successful restore
        if not errors:
            self._cleanup_profile_files()
            logger.info("System restored successfully")
        else:
            logger.warning(f"Restore completed with {len(errors)} errors")
        
        return len(errors) == 0, errors
    
    def load_profile(self) -> bool:
        """Load existing profile from disk."""
        if not self._profile_path.exists():
            logger.info("No saved profile found")
            return False
        
        try:
            with open(self._profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._current_profile = SystemProfile.from_dict(data)
            logger.info(f"Profile loaded: {self._current_profile.hostname} @ {self._current_profile.created_at}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return False
    
    def has_backup(self) -> bool:
        """Check if a backup exists."""
        return self._profile_path.exists()
    
    def get_profile(self) -> Optional[SystemProfile]:
        """Get current profile."""
        return self._current_profile
    
    def add_created_rule(self, rule_name: str) -> None:
        """Track a firewall rule created by agent."""
        if self._current_profile and rule_name not in self._current_profile.firewall.created_rules:
            self._current_profile.firewall.created_rules.append(rule_name)
            self._save_profile()
    
    def add_created_rules(self, rule_names: List[str]) -> None:
        """Track multiple firewall rules."""
        if self._current_profile:
            for name in rule_names:
                if name not in self._current_profile.firewall.created_rules:
                    self._current_profile.firewall.created_rules.append(name)
            self._save_profile()
    
    # ========================================
    # PRIVATE METHODS - BACKUP
    # ========================================
    
    def _backup_dns_settings(self, profile: SystemProfile) -> None:
        """Backup DNS settings for all adapters."""
        adapters = self._get_network_adapters()
        
        for adapter_name in adapters:
            try:
                # Get IPv4 DNS
                ipv4_dns, ipv4_source = self._get_adapter_dns_v4(adapter_name)
                
                # Get IPv6 DNS
                ipv6_dns, ipv6_source = self._get_adapter_dns_v6(adapter_name)
                
                adapter_profile = DNSAdapterProfile(
                    adapter_name=adapter_name,
                    ipv4_dns=ipv4_dns,
                    ipv4_source=ipv4_source,
                    ipv6_dns=ipv6_dns,
                    ipv6_source=ipv6_source,
                )
                
                profile.dns_adapters[adapter_name] = adapter_profile
                logger.debug(f"Backed up DNS for {adapter_name}: {ipv4_dns}")
                
            except Exception as e:
                logger.warning(f"Failed to backup DNS for {adapter_name}: {e}")
    
    def _get_network_adapters(self) -> List[str]:
        """Get list of network adapter names."""
        adapters = []
        
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 4:
                        # Get adapter name (last part, may contain spaces)
                        name_start = line.find(parts[3])
                        if name_start > 0:
                            adapter_name = line[name_start:].strip()
                            if 'loopback' not in adapter_name.lower():
                                adapters.append(adapter_name)
        except Exception as e:
            logger.error(f"Error getting adapters: {e}")
        
        return adapters
    
    def _get_adapter_dns_v4(self, adapter_name: str) -> Tuple[List[str], str]:
        """Get IPv4 DNS servers for an adapter."""
        dns_servers = []
        source = "dhcp"
        
        try:
            result = subprocess.run(
                ["netsh", "interface", "ipv4", "show", "dnsservers", f"name={adapter_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # Check if DHCP or static
                if "dhcp" in output.lower() or "configured through dhcp" in output.lower():
                    source = "dhcp"
                else:
                    source = "static"
                
                # Extract DNS servers
                for line in output.split('\n'):
                    line = line.strip()
                    # Look for IP addresses
                    if line and not line.startswith('Configuration'):
                        parts = line.split()
                        for part in parts:
                            if self._is_ip_address(part):
                                dns_servers.append(part)
                                
        except Exception as e:
            logger.warning(f"Error getting IPv4 DNS for {adapter_name}: {e}")
        
        return dns_servers, source
    
    def _get_adapter_dns_v6(self, adapter_name: str) -> Tuple[List[str], str]:
        """Get IPv6 DNS servers for an adapter."""
        dns_servers = []
        source = "dhcp"
        
        try:
            result = subprocess.run(
                ["netsh", "interface", "ipv6", "show", "dnsservers", f"name={adapter_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                if "dhcp" in output.lower():
                    source = "dhcp"
                else:
                    source = "static"
                    # Extract IPv6 addresses
                    for line in output.split('\n'):
                        line = line.strip()
                        if ':' in line and not line.startswith('Configuration'):
                            parts = line.split()
                            for part in parts:
                                if ':' in part and self._is_ipv6_address(part):
                                    dns_servers.append(part)
                                    
        except Exception as e:
            logger.debug(f"Error getting IPv6 DNS for {adapter_name}: {e}")
        
        return dns_servers, source
    
    def _backup_firewall_state(self, profile: SystemProfile) -> None:
        """Backup firewall profile state."""
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                profile.firewall.domain_enabled = "domain profile" in output and "on" in output
                profile.firewall.private_enabled = "private profile" in output and "on" in output
                profile.firewall.public_enabled = "public profile" in output and "on" in output
                
        except Exception as e:
            logger.warning(f"Error backing up firewall state: {e}")
    
    def _backup_hosts_file(self, profile: SystemProfile) -> None:
        """Backup hosts file if it will be modified."""
        hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
        
        if hosts_path.exists():
            try:
                with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Save to backup file
                with open(self._hosts_backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                profile.hosts_file_backup = str(self._hosts_backup_path)
                logger.debug("Hosts file backed up")
                
            except Exception as e:
                logger.warning(f"Error backing up hosts file: {e}")
    
    # ========================================
    # PRIVATE METHODS - RESTORE
    # ========================================
    
    def _restore_adapter_dns(self, adapter: DNSAdapterProfile) -> None:
        """Restore DNS settings for a single adapter."""
        adapter_name = adapter.adapter_name
        
        # Restore IPv4
        if adapter.ipv4_source == "dhcp":
            # Reset to DHCP
            subprocess.run(
                ["netsh", "interface", "ipv4", "set", "dnsservers",
                 f"name={adapter_name}", "source=dhcp"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            logger.debug(f"Reset IPv4 DNS to DHCP for {adapter_name}")
        elif adapter.ipv4_dns:
            # Set static DNS
            for i, dns in enumerate(adapter.ipv4_dns):
                cmd = [
                    "netsh", "interface", "ipv4",
                    "add" if i > 0 else "set", "dnsservers",
                    f"name={adapter_name}",
                    f"address={dns}",
                ]
                if i == 0:
                    cmd.extend(["source=static", "validate=no"])
                else:
                    cmd.append("validate=no")
                
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            logger.debug(f"Restored static IPv4 DNS for {adapter_name}: {adapter.ipv4_dns}")
        
        # Restore IPv6
        if adapter.ipv6_source == "dhcp":
            subprocess.run(
                ["netsh", "interface", "ipv6", "set", "dnsservers",
                 f"name={adapter_name}", "source=dhcp"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
    
    def _cleanup_agent_firewall_rules(self) -> None:
        """Remove all firewall rules created by the agent."""
        # Rule prefixes used by agent
        prefixes = [
            "DNS_Proxy_",
            "FirewallController",
            "FC_",
            "DoH_Block_",
            "DoT_Block_",
        ]
        
        try:
            # Get all rules
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                rules_to_delete = set()
                
                # Find rules matching our prefixes
                for line in result.stdout.split('\n'):
                    if line.startswith("Rule Name:"):
                        rule_name = line.replace("Rule Name:", "").strip()
                        for prefix in prefixes:
                            if rule_name.startswith(prefix):
                                rules_to_delete.add(rule_name)
                                break
                
                # Also add tracked rules from profile
                if self._current_profile:
                    for rule in self._current_profile.firewall.created_rules:
                        rules_to_delete.add(rule)
                
                # Delete rules
                for rule_name in rules_to_delete:
                    subprocess.run(
                        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                        capture_output=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                
                if rules_to_delete:
                    logger.info(f"Removed {len(rules_to_delete)} firewall rules")
                    
        except Exception as e:
            logger.error(f"Error cleaning up firewall rules: {e}")
            raise
    
    def _restore_hosts_file(self) -> None:
        """Restore original hosts file."""
        if not self._hosts_backup_path.exists():
            return
        
        hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
        
        try:
            # Read backup
            with open(self._hosts_backup_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Write to hosts file
            with open(hosts_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            logger.info("Hosts file restored")
            
        except PermissionError:
            logger.warning("Cannot restore hosts file - need Administrator privileges")
        except Exception as e:
            logger.error(f"Error restoring hosts file: {e}")
    
    def _flush_dns_cache(self) -> None:
        """Flush DNS resolver cache."""
        try:
            subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            logger.debug("DNS cache flushed")
        except Exception as e:
            logger.warning(f"Error flushing DNS cache: {e}")
    
    # ========================================
    # PRIVATE HELPERS
    # ========================================
    
    def _save_profile(self) -> None:
        """Save current profile to disk."""
        if not self._current_profile:
            return
        
        try:
            with open(self._profile_path, 'w', encoding='utf-8') as f:
                json.dump(self._current_profile.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")
    
    def _cleanup_profile_files(self) -> None:
        """Remove profile files after successful restore."""
        try:
            if self._profile_path.exists():
                self._profile_path.unlink()
            if self._hosts_backup_path.exists():
                self._hosts_backup_path.unlink()
        except Exception as e:
            logger.warning(f"Error cleaning up profile files: {e}")
    
    def _is_ip_address(self, s: str) -> bool:
        """Check if string is an IPv4 address."""
        parts = s.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    def _is_ipv6_address(self, s: str) -> bool:
        """Check if string looks like an IPv6 address."""
        # Simple check - contains colons and valid hex
        if ':' not in s:
            return False
        parts = s.split(':')
        try:
            for part in parts:
                if part and not all(c in '0123456789abcdefABCDEF' for c in part):
                    return False
            return True
        except:
            return False


# Singleton instance
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get or create the singleton profile manager."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


def backup_system_profile() -> bool:
    """Convenience function to backup system profile."""
    return get_profile_manager().backup_all()


def restore_system_profile() -> Tuple[bool, List[str]]:
    """Convenience function to restore system profile."""
    return get_profile_manager().restore_all()
