"""
Enhanced DoH/DoT Blocker
-------------------------
Multi-layer blocking strategy for DNS over HTTPS (DoH) and DNS over TLS (DoT).

Blocking Methods:
1. IP-based firewall rules (known DoH server IPs)
2. Hosts file blocking (DoH domains -> 0.0.0.0)
3. Port 853 (DoT) global block
4. SNI-pattern documentation (for advanced firewalls)

NOTE: Windows Firewall doesn't support SNI inspection natively.
For SNI-based blocking, use third-party solutions like:
- Windows Filtering Platform (WFP) custom driver
- Third-party firewall with DPI (Deep Packet Inspection)
- Proxy with TLS inspection

This module implements what's possible with native Windows tools.
"""

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("dns_proxy.security.doh_blocker")


@dataclass
class DoHProviderEntry:
    """DoH/DoT provider entry with detailed info."""
    name: str
    domains: List[str] = field(default_factory=list)
    ipv4_addresses: List[str] = field(default_factory=list)
    ipv6_addresses: List[str] = field(default_factory=list)
    sni_patterns: List[str] = field(default_factory=list)  # For documentation/advanced FW
    category: str = "public"  # public, browser, os, enterprise
    priority: int = 1  # 1=critical, 2=common, 3=less common
    last_updated: Optional[str] = None
    
    @property
    def all_ips(self) -> List[str]:
        return self.ipv4_addresses + self.ipv6_addresses


# Comprehensive DoH/DoT provider database
# Updated: 2024-12
DOH_PROVIDERS_DATABASE: List[DoHProviderEntry] = [
    # === CRITICAL: Browser built-in DoH ===
    DoHProviderEntry(
        name="Cloudflare",
        domains=[
            "cloudflare-dns.com",
            "one.one.one.one",
            "1dot1dot1dot1.cloudflare-dns.com",
        ],
        ipv4_addresses=["1.1.1.1", "1.0.0.1"],
        ipv6_addresses=["2606:4700:4700::1111", "2606:4700:4700::1001"],
        sni_patterns=["*.cloudflare-dns.com", "one.one.one.one"],
        category="browser",
        priority=1,
    ),
    DoHProviderEntry(
        name="Cloudflare Malware",
        domains=["security.cloudflare-dns.com"],
        ipv4_addresses=["1.1.1.2", "1.0.0.2"],
        ipv6_addresses=["2606:4700:4700::1112", "2606:4700:4700::1002"],
        sni_patterns=["security.cloudflare-dns.com"],
        category="browser",
        priority=1,
    ),
    DoHProviderEntry(
        name="Cloudflare Family",
        domains=["family.cloudflare-dns.com"],
        ipv4_addresses=["1.1.1.3", "1.0.0.3"],
        ipv6_addresses=["2606:4700:4700::1113", "2606:4700:4700::1003"],
        sni_patterns=["family.cloudflare-dns.com"],
        category="browser",
        priority=1,
    ),
    DoHProviderEntry(
        name="Google",
        domains=["dns.google", "dns.google.com", "8888.google"],
        ipv4_addresses=["8.8.8.8", "8.8.4.4"],
        ipv6_addresses=["2001:4860:4860::8888", "2001:4860:4860::8844"],
        sni_patterns=["dns.google", "dns.google.com"],
        category="browser",
        priority=1,
    ),
    DoHProviderEntry(
        name="Mozilla/Cloudflare",
        domains=["mozilla.cloudflare-dns.com"],
        ipv4_addresses=[],  # Uses Cloudflare IPs
        ipv6_addresses=[],
        sni_patterns=["mozilla.cloudflare-dns.com"],
        category="browser",
        priority=1,
    ),
    
    # === PUBLIC DNS with DoH ===
    DoHProviderEntry(
        name="Quad9",
        domains=["dns.quad9.net", "dns9.quad9.net", "dns10.quad9.net"],
        ipv4_addresses=["9.9.9.9", "149.112.112.112", "9.9.9.10", "149.112.112.10"],
        ipv6_addresses=["2620:fe::fe", "2620:fe::9", "2620:fe::10", "2620:fe::fe:10"],
        sni_patterns=["*.quad9.net"],
        category="public",
        priority=1,
    ),
    DoHProviderEntry(
        name="OpenDNS",
        domains=["doh.opendns.com", "doh.familyshield.opendns.com"],
        ipv4_addresses=["208.67.222.222", "208.67.220.220", "208.67.222.123", "208.67.220.123"],
        ipv6_addresses=["2620:119:35::35", "2620:119:53::53"],
        sni_patterns=["doh.opendns.com", "*.opendns.com"],
        category="public",
        priority=1,
    ),
    DoHProviderEntry(
        name="AdGuard",
        domains=["dns.adguard.com", "dns-family.adguard.com", "dns-unfiltered.adguard.com"],
        ipv4_addresses=["94.140.14.14", "94.140.15.15", "94.140.14.15", "94.140.15.16"],
        ipv6_addresses=["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"],
        sni_patterns=["*.adguard.com", "*.adguard-dns.com"],
        category="public",
        priority=1,
    ),
    DoHProviderEntry(
        name="NextDNS",
        domains=["dns.nextdns.io", "firefox.dns.nextdns.io", "chrome.dns.nextdns.io"],
        ipv4_addresses=["45.90.28.0", "45.90.30.0"],
        ipv6_addresses=["2a07:a8c0::", "2a07:a8c1::"],
        sni_patterns=["*.nextdns.io"],
        category="public",
        priority=1,
    ),
    DoHProviderEntry(
        name="CleanBrowsing",
        domains=["doh.cleanbrowsing.org", "family-filter-dns.cleanbrowsing.org"],
        ipv4_addresses=["185.228.168.168", "185.228.169.168", "185.228.168.10", "185.228.169.11"],
        ipv6_addresses=["2a0d:2a00:1::", "2a0d:2a00:2::"],
        sni_patterns=["*.cleanbrowsing.org"],
        category="public",
        priority=2,
    ),
    DoHProviderEntry(
        name="DNS.SB",
        domains=["doh.dns.sb", "doh.sb"],
        ipv4_addresses=["185.222.222.222", "45.11.45.11"],
        ipv6_addresses=["2a09::", "2a11::"],
        sni_patterns=["*.dns.sb"],
        category="public",
        priority=2,
    ),
    DoHProviderEntry(
        name="Mullvad",
        domains=["dns.mullvad.net", "adblock.dns.mullvad.net"],
        ipv4_addresses=["194.242.2.2", "193.19.108.2"],
        ipv6_addresses=["2a07:e340::2"],
        sni_patterns=["*.mullvad.net"],
        category="public",
        priority=2,
    ),
    DoHProviderEntry(
        name="Control D",
        domains=["freedns.controld.com", "dns.controld.com"],
        ipv4_addresses=["76.76.2.0", "76.76.10.0"],
        ipv6_addresses=["2606:1a40::", "2606:1a40:1::"],
        sni_patterns=["*.controld.com"],
        category="public",
        priority=2,
    ),
    
    # === LESS COMMON ===
    DoHProviderEntry(
        name="LibreDNS",
        domains=["doh.libredns.gr"],
        ipv4_addresses=["116.202.176.26"],
        ipv6_addresses=[],
        sni_patterns=["*.libredns.gr"],
        category="public",
        priority=3,
    ),
    DoHProviderEntry(
        name="AhaDNS",
        domains=["doh.la.ahadns.net", "doh.nl.ahadns.net"],
        ipv4_addresses=["185.213.26.187", "5.2.75.75"],
        ipv6_addresses=["2a0d:5600:33:3::3", "2a04:52c0:101:75::75"],
        sni_patterns=["*.ahadns.net"],
        category="public",
        priority=3,
    ),
    
    # === OS BUILT-IN DoH ===
    DoHProviderEntry(
        name="Windows 11 DoH",
        domains=["dns.msftncsi.com"],  # Microsoft connectivity check
        ipv4_addresses=[],  # Uses Cloudflare/Google/Quad9
        ipv6_addresses=[],
        sni_patterns=[],
        category="os",
        priority=1,
    ),
]


@dataclass
class BlockingResult:
    """Result of blocking operation."""
    success: bool
    method: str  # "firewall", "hosts", "both"
    ips_blocked: int = 0
    domains_blocked: int = 0
    rules_created: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class EnhancedDoHBlocker:
    """
    Multi-layer DoH/DoT blocking.
    
    Layers:
    1. Firewall IP blocking (known DoH server IPs)
    2. Hosts file blocking (DoH domains -> 0.0.0.0)
    3. Port 853 global block (DoT)
    4. DNS outbound restrictions (separate module)
    
    Usage:
        blocker = EnhancedDoHBlocker()
        
        # Block all known providers
        result = blocker.block_all()
        
        # Or selectively
        result = blocker.block_by_category("browser")  # Block browser DoH only
    """
    
    RULE_PREFIX = "DNS_Proxy_Security_"
    HOSTS_MARKER_START = "# === DNS Proxy DoH Block Start ==="
    HOSTS_MARKER_END = "# === DNS Proxy DoH Block End ==="
    
    # Windows hosts file path
    HOSTS_FILE = Path(r"C:\Windows\System32\drivers\etc\hosts")
    
    # Ports
    DOH_PORT = 443
    DOT_PORT = 853
    
    def __init__(
        self,
        block_via_firewall: bool = True,
        block_via_hosts: bool = True,
        block_ipv6: bool = True,
        providers: List[DoHProviderEntry] = None
    ):
        self._block_via_firewall = block_via_firewall
        self._block_via_hosts = block_via_hosts
        self._block_ipv6 = block_ipv6
        
        self._providers = providers or DOH_PROVIDERS_DATABASE.copy()
        self._blocked_ips: Set[str] = set()
        self._blocked_domains: Set[str] = set()
        self._rules_created: List[str] = []
        self._hosts_modified = False
        
        logger.info(
            f"Enhanced DoH Blocker initialized with {len(self._providers)} providers"
        )
    
    def block_all(self, priority_max: int = 3) -> BlockingResult:
        """
        Block all providers up to specified priority.
        
        Args:
            priority_max: Maximum priority level to block (1=critical only, 3=all)
            
        Returns:
            BlockingResult with details
        """
        providers = [p for p in self._providers if p.priority <= priority_max]
        return self._block_providers(providers)
    
    def block_by_category(self, category: str) -> BlockingResult:
        """Block providers by category."""
        providers = [p for p in self._providers if p.category == category]
        return self._block_providers(providers)
    
    def block_critical(self) -> BlockingResult:
        """Block only critical (priority 1) providers."""
        return self.block_all(priority_max=1)
    
    def _block_providers(self, providers: List[DoHProviderEntry]) -> BlockingResult:
        """Block specified providers."""
        result = BlockingResult(success=True, method="both")
        
        # Collect all IPs and domains
        ipv4_ips: Set[str] = set()
        ipv6_ips: Set[str] = set()
        domains: Set[str] = set()
        
        for provider in providers:
            ipv4_ips.update(provider.ipv4_addresses)
            if self._block_ipv6:
                ipv6_ips.update(provider.ipv6_addresses)
            domains.update(provider.domains)
        
        logger.info(
            f"Blocking {len(providers)} providers: "
            f"{len(ipv4_ips)} IPv4, {len(ipv6_ips)} IPv6, {len(domains)} domains"
        )
        
        # Layer 1: Firewall IP blocking
        if self._block_via_firewall:
            fw_result = self._apply_firewall_rules(ipv4_ips, ipv6_ips)
            result.ips_blocked = len(ipv4_ips) + len(ipv6_ips)
            result.rules_created = fw_result["rules_created"]
            result.errors.extend(fw_result.get("errors", []))
        
        # Layer 2: Hosts file blocking
        if self._block_via_hosts:
            hosts_result = self._apply_hosts_blocking(domains)
            result.domains_blocked = len(domains)
            result.errors.extend(hosts_result.get("errors", []))
            if hosts_result.get("warnings"):
                result.warnings.extend(hosts_result["warnings"])
        
        # Layer 3: Block DoT port globally
        dot_result = self._block_dot_globally()
        result.rules_created += dot_result.get("rules_created", 0)
        result.errors.extend(dot_result.get("errors", []))
        
        self._blocked_ips = ipv4_ips | ipv6_ips
        self._blocked_domains = domains
        
        result.success = len(result.errors) == 0
        
        return result
    
    def _apply_firewall_rules(
        self,
        ipv4_ips: Set[str],
        ipv6_ips: Set[str]
    ) -> Dict:
        """Apply firewall rules to block DoH IPs."""
        result = {"rules_created": 0, "errors": []}
        
        # Delete existing rules first
        self._delete_firewall_rules()
        
        # Block IPv4 DoH (port 443)
        if ipv4_ips:
            try:
                self._create_firewall_rule(
                    name=f"{self.RULE_PREFIX}DoH_IPv4",
                    ips=list(ipv4_ips),
                    port=self.DOH_PORT,
                    protocol="tcp"
                )
                result["rules_created"] += 1
            except Exception as e:
                result["errors"].append(f"IPv4 DoH rule: {e}")
        
        # Block IPv6 DoH (port 443)
        if ipv6_ips:
            try:
                self._create_firewall_rule(
                    name=f"{self.RULE_PREFIX}DoH_IPv6",
                    ips=list(ipv6_ips),
                    port=self.DOH_PORT,
                    protocol="tcp"
                )
                result["rules_created"] += 1
            except Exception as e:
                result["errors"].append(f"IPv6 DoH rule: {e}")
        
        return result
    
    def _create_firewall_rule(
        self,
        name: str,
        ips: List[str],
        port: int,
        protocol: str = "tcp"
    ) -> None:
        """Create a Windows Firewall block rule."""
        remote_ip = ",".join(ips) if ips else "any"
        
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={name}",
            "dir=out",
            "action=block",
            f"remoteip={remote_ip}",
            f"remoteport={port}",
            f"protocol={protocol}",
            "enable=yes",
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "Unknown error")
        
        self._rules_created.append(name)
        logger.debug(f"Created firewall rule: {name}")
    
    def _block_dot_globally(self) -> Dict:
        """Block all DoT traffic (port 853)."""
        result = {"rules_created": 0, "errors": []}
        
        try:
            self._create_firewall_rule(
                name=f"{self.RULE_PREFIX}DoT_All",
                ips=[],  # All destinations
                port=self.DOT_PORT,
                protocol="tcp"
            )
            result["rules_created"] += 1
            logger.info("DoT (port 853) blocked globally")
        except Exception as e:
            result["errors"].append(f"DoT global block: {e}")
        
        return result
    
    def _apply_hosts_blocking(self, domains: Set[str]) -> Dict:
        """
        Block domains via hosts file.
        
        Maps DoH domains to 0.0.0.0 to prevent resolution.
        """
        result = {"errors": [], "warnings": []}
        
        if not domains:
            return result
        
        try:
            # Read current hosts file
            if not self.HOSTS_FILE.exists():
                result["errors"].append("Hosts file not found")
                return result
            
            hosts_content = self.HOSTS_FILE.read_text(encoding="utf-8", errors="ignore")
            
            # Remove existing DNS Proxy entries
            hosts_content = self._remove_hosts_entries(hosts_content)
            
            # Build new entries
            new_entries = [
                "",
                self.HOSTS_MARKER_START,
                f"# Added by DNS Proxy at {datetime.now().isoformat()}",
                "# Block DoH/DoT domains to prevent DNS bypass",
                "",
            ]
            
            for domain in sorted(domains):
                new_entries.append(f"0.0.0.0 {domain}")
                new_entries.append(f"::0 {domain}")  # IPv6 block
            
            new_entries.extend([
                "",
                self.HOSTS_MARKER_END,
                "",
            ])
            
            # Backup hosts file
            backup_path = self.HOSTS_FILE.with_suffix(".bak")
            shutil.copy2(self.HOSTS_FILE, backup_path)
            
            # Write updated hosts file
            new_content = hosts_content.rstrip() + "\n" + "\n".join(new_entries)
            self.HOSTS_FILE.write_text(new_content, encoding="utf-8")
            
            self._hosts_modified = True
            logger.info(f"Hosts file updated with {len(domains)} DoH domain blocks")
            
            # Flush DNS cache
            subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
        except PermissionError:
            result["errors"].append(
                "Permission denied: Run as Administrator to modify hosts file"
            )
        except Exception as e:
            result["errors"].append(f"Hosts file error: {e}")
        
        return result
    
    def _remove_hosts_entries(self, content: str) -> str:
        """Remove DNS Proxy entries from hosts content."""
        lines = content.split("\n")
        new_lines = []
        in_block = False
        
        for line in lines:
            if self.HOSTS_MARKER_START in line:
                in_block = True
                continue
            elif self.HOSTS_MARKER_END in line:
                in_block = False
                continue
            
            if not in_block:
                new_lines.append(line)
        
        return "\n".join(new_lines)
    
    def _delete_firewall_rules(self) -> int:
        """Delete all DNS Proxy security rules."""
        deleted = 0
        
        # Get list of rules
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            for rule_name in self._rules_created.copy():
                if rule_name in result.stdout:
                    del_result = subprocess.run(
                        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                        capture_output=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if del_result.returncode == 0:
                        deleted += 1
                        self._rules_created.remove(rule_name)
            
            # Also try standard names
            standard_rules = [
                f"{self.RULE_PREFIX}DoH_IPv4",
                f"{self.RULE_PREFIX}DoH_IPv6",
                f"{self.RULE_PREFIX}DoT_All",
            ]
            
            for rule_name in standard_rules:
                subprocess.run(
                    ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                    capture_output=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
        except Exception as e:
            logger.error(f"Error deleting firewall rules: {e}")
        
        return deleted
    
    def restore_hosts_file(self) -> bool:
        """Restore hosts file by removing DNS Proxy entries."""
        try:
            if not self.HOSTS_FILE.exists():
                return False
            
            content = self.HOSTS_FILE.read_text(encoding="utf-8", errors="ignore")
            new_content = self._remove_hosts_entries(content)
            self.HOSTS_FILE.write_text(new_content, encoding="utf-8")
            
            self._hosts_modified = False
            logger.info("Hosts file restored")
            
            # Flush DNS cache
            subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore hosts file: {e}")
            return False
    
    def remove_all_blocks(self) -> Dict:
        """Remove all blocking rules and restore hosts."""
        result = {
            "firewall_rules_removed": 0,
            "hosts_restored": False,
            "errors": [],
        }
        
        # Remove firewall rules
        result["firewall_rules_removed"] = self._delete_firewall_rules()
        
        # Restore hosts file
        result["hosts_restored"] = self.restore_hosts_file()
        
        self._blocked_ips.clear()
        self._blocked_domains.clear()
        
        return result
    
    def get_providers(self) -> List[DoHProviderEntry]:
        """Get list of known providers."""
        return self._providers.copy()
    
    def add_provider(self, provider: DoHProviderEntry) -> None:
        """Add a custom provider to block."""
        self._providers.append(provider)
    
    def get_sni_patterns(self) -> List[Dict]:
        """
        Get SNI patterns for all providers.
        
        This is for documentation/advanced firewall integration.
        Windows Firewall doesn't support SNI blocking natively.
        
        Returns:
            List of dicts with provider name and SNI patterns
        """
        patterns = []
        for provider in self._providers:
            if provider.sni_patterns:
                patterns.append({
                    "provider": provider.name,
                    "sni_patterns": provider.sni_patterns,
                    "domains": provider.domains,
                })
        return patterns
    
    def export_blocklist(self, format: str = "json") -> str:
        """
        Export blocklist in various formats.
        
        Formats:
        - json: Full provider database
        - hosts: Hosts file format
        - ips: Plain IP list
        - domains: Plain domain list
        """
        if format == "json":
            import json
            return json.dumps(
                [
                    {
                        "name": p.name,
                        "domains": p.domains,
                        "ipv4": p.ipv4_addresses,
                        "ipv6": p.ipv6_addresses,
                        "sni": p.sni_patterns,
                        "category": p.category,
                        "priority": p.priority,
                    }
                    for p in self._providers
                ],
                indent=2
            )
        elif format == "hosts":
            lines = []
            for p in self._providers:
                for d in p.domains:
                    lines.append(f"0.0.0.0 {d}")
            return "\n".join(lines)
        elif format == "ips":
            ips = set()
            for p in self._providers:
                ips.update(p.ipv4_addresses)
                ips.update(p.ipv6_addresses)
            return "\n".join(sorted(ips))
        elif format == "domains":
            domains = set()
            for p in self._providers:
                domains.update(p.domains)
            return "\n".join(sorted(domains))
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def get_stats(self) -> Dict:
        """Get blocker statistics."""
        return {
            "providers_count": len(self._providers),
            "blocked_ips": len(self._blocked_ips),
            "blocked_domains": len(self._blocked_domains),
            "firewall_rules": len(self._rules_created),
            "hosts_modified": self._hosts_modified,
            "block_via_firewall": self._block_via_firewall,
            "block_via_hosts": self._block_via_hosts,
            "block_ipv6": self._block_ipv6,
        }

    # =========================================================
    # Convenience methods for security_manager.py compatibility
    # =========================================================
    
    def block_by_firewall(self) -> BlockingResult:
        """
        Block all DoH/DoT providers using Windows Firewall.
        This is a convenience method for security_manager.py.
        """
        # Temporarily disable hosts blocking and block via firewall only
        original_hosts = self._block_via_hosts
        self._block_via_hosts = False
        try:
            result = self.block_all(priority_max=3)
        finally:
            self._block_via_hosts = original_hosts
        return result
    
    def block_by_hosts_file(self) -> BlockingResult:
        """
        Block all DoH domains using hosts file.
        This is a convenience method for security_manager.py.
        """
        # Collect all domains from providers
        domains: set = set()
        for provider in self._providers:
            domains.update(provider.domains)
        
        # Apply hosts blocking
        hosts_result = self._apply_hosts_blocking(domains)
        
        return BlockingResult(
            success=hosts_result.get("success", False),
            method="hosts",
            domains_blocked=hosts_result.get("count", 0),
        )
    
    def block_dot_port(self) -> BlockingResult:
        """
        Block DoT port 853 globally.
        This is a convenience method for security_manager.py.
        """
        dot_result = self._block_dot_globally()
        return BlockingResult(
            success=dot_result.get("success", False),
            method="dot",
        )
