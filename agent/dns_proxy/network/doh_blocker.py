"""
DoH/DoT Blocker
---------------
Blocks DNS over HTTPS (DoH) and DNS over TLS (DoT) to prevent DNS bypass.
Uses Windows Firewall rules to block connections to known DoH/DoT servers.
"""

import ipaddress
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("dns_proxy.network.doh_blocker")


@dataclass
class DoHProvider:
    """Known DoH/DoT provider."""
    name: str
    ipv4_addresses: List[str] = field(default_factory=list)
    ipv6_addresses: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    
    @property
    def all_ips(self) -> List[str]:
        return self.ipv4_addresses + self.ipv6_addresses


# Known DoH/DoT providers and their IPs
# Updated as of 2024-12
DOH_PROVIDERS: List[DoHProvider] = [
    DoHProvider(
        name="Google",
        ipv4_addresses=["8.8.8.8", "8.8.4.4"],
        ipv6_addresses=["2001:4860:4860::8888", "2001:4860:4860::8844"],
        domains=["dns.google", "dns.google.com"],
    ),
    DoHProvider(
        name="Cloudflare",
        ipv4_addresses=["1.1.1.1", "1.0.0.1"],
        ipv6_addresses=["2606:4700:4700::1111", "2606:4700:4700::1001"],
        domains=["cloudflare-dns.com", "one.one.one.one"],
    ),
    DoHProvider(
        name="Cloudflare Malware",
        ipv4_addresses=["1.1.1.2", "1.0.0.2"],
        ipv6_addresses=["2606:4700:4700::1112", "2606:4700:4700::1002"],
        domains=["security.cloudflare-dns.com"],
    ),
    DoHProvider(
        name="Cloudflare Family",
        ipv4_addresses=["1.1.1.3", "1.0.0.3"],
        ipv6_addresses=["2606:4700:4700::1113", "2606:4700:4700::1003"],
        domains=["family.cloudflare-dns.com"],
    ),
    DoHProvider(
        name="Quad9",
        ipv4_addresses=["9.9.9.9", "149.112.112.112", "9.9.9.10", "149.112.112.10"],
        ipv6_addresses=["2620:fe::fe", "2620:fe::9", "2620:fe::10", "2620:fe::fe:10"],
        domains=["dns.quad9.net"],
    ),
    DoHProvider(
        name="OpenDNS",
        ipv4_addresses=["208.67.222.222", "208.67.220.220", "208.67.222.123", "208.67.220.123"],
        ipv6_addresses=["2620:119:35::35", "2620:119:53::53"],
        domains=["doh.opendns.com", "doh.familyshield.opendns.com"],
    ),
    DoHProvider(
        name="AdGuard",
        ipv4_addresses=["94.140.14.14", "94.140.15.15", "94.140.14.15", "94.140.15.16"],
        ipv6_addresses=["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"],
        domains=["dns.adguard.com", "dns-family.adguard.com"],
    ),
    DoHProvider(
        name="NextDNS",
        ipv4_addresses=["45.90.28.0", "45.90.30.0"],
        ipv6_addresses=["2a07:a8c0::", "2a07:a8c1::"],
        domains=["dns.nextdns.io"],
    ),
    DoHProvider(
        name="CleanBrowsing",
        ipv4_addresses=["185.228.168.168", "185.228.169.168", "185.228.168.10", "185.228.169.11"],
        ipv6_addresses=["2a0d:2a00:1::", "2a0d:2a00:2::"],
        domains=["doh.cleanbrowsing.org"],
    ),
    DoHProvider(
        name="Comodo",
        ipv4_addresses=["8.26.56.26", "8.20.247.20"],
        ipv6_addresses=[],
        domains=["doh.familyshield.opendns.com"],
    ),
    DoHProvider(
        name="DNS.SB",
        ipv4_addresses=["185.222.222.222", "45.11.45.11"],
        ipv6_addresses=["2a09::", "2a11::"],
        domains=["doh.dns.sb", "doh.sb"],
    ),
    DoHProvider(
        name="Mozilla",
        ipv4_addresses=[],  # Uses Cloudflare
        ipv6_addresses=[],
        domains=["mozilla.cloudflare-dns.com"],
    ),
]

# DoT port
DOT_PORT = 853


@dataclass
class BlockRule:
    """Firewall block rule."""
    name: str
    ips: List[str]
    port: int
    protocol: str = "TCP"
    direction: str = "out"
    success: bool = False
    error: Optional[str] = None


@dataclass
class BlockerResult:
    """Result of blocking operation."""
    success: bool
    rules_created: int = 0
    rules_failed: int = 0
    ips_blocked: int = 0
    errors: List[str] = field(default_factory=list)


class DoHBlocker:
    """
    Blocks DoH (DNS over HTTPS) and DoT (DNS over TLS) connections.
    
    Methods:
    - Block by IP address (recommended)
    - Uses Windows Firewall rules
    - Supports IPv4 and IPv6
    """
    
    # Firewall rule name prefix
    RULE_PREFIX = "DNS_Proxy_Block_"
    
    # Ports to block
    DOH_PORT = 443  # HTTPS
    DOT_PORT = 853  # DNS over TLS
    
    def __init__(self, block_doh: bool = True, block_dot: bool = True):
        self._block_doh = block_doh
        self._block_dot = block_dot
        self._blocked_ips: Set[str] = set()
        self._rules_created: List[str] = []
        
        logger.info(
            f"DoH Blocker initialized (DoH: {block_doh}, DoT: {block_dot})"
        )
    
    def block_all_providers(self, include_ipv6: bool = True) -> BlockerResult:
        """
        Block all known DoH/DoT providers.
        
        Args:
            include_ipv6: Whether to include IPv6 addresses
            
        Returns:
            BlockerResult with operation details
        """
        result = BlockerResult(success=True)
        
        # Collect all IPs
        ipv4_ips: Set[str] = set()
        ipv6_ips: Set[str] = set()
        
        for provider in DOH_PROVIDERS:
            ipv4_ips.update(provider.ipv4_addresses)
            if include_ipv6:
                ipv6_ips.update(provider.ipv6_addresses)
        
        logger.info(
            f"Blocking {len(ipv4_ips)} IPv4 and {len(ipv6_ips)} IPv6 DoH/DoT addresses"
        )
        
        # Block DoH (port 443)
        if self._block_doh:
            if ipv4_ips:
                rule_result = self._create_block_rule(
                    name=f"{self.RULE_PREFIX}DoH_IPv4",
                    ips=list(ipv4_ips),
                    port=self.DOH_PORT,
                    description="Block DNS over HTTPS (IPv4)"
                )
                if rule_result.success:
                    result.rules_created += 1
                else:
                    result.rules_failed += 1
                    result.errors.append(rule_result.error)
            
            if ipv6_ips:
                rule_result = self._create_block_rule(
                    name=f"{self.RULE_PREFIX}DoH_IPv6",
                    ips=list(ipv6_ips),
                    port=self.DOH_PORT,
                    description="Block DNS over HTTPS (IPv6)"
                )
                if rule_result.success:
                    result.rules_created += 1
                else:
                    result.rules_failed += 1
                    result.errors.append(rule_result.error)
        
        # Block DoT (port 853)
        if self._block_dot:
            if ipv4_ips:
                rule_result = self._create_block_rule(
                    name=f"{self.RULE_PREFIX}DoT_IPv4",
                    ips=list(ipv4_ips),
                    port=self.DOT_PORT,
                    description="Block DNS over TLS (IPv4)"
                )
                if rule_result.success:
                    result.rules_created += 1
                else:
                    result.rules_failed += 1
                    result.errors.append(rule_result.error)
            
            if ipv6_ips:
                rule_result = self._create_block_rule(
                    name=f"{self.RULE_PREFIX}DoT_IPv6",
                    ips=list(ipv6_ips),
                    port=self.DOT_PORT,
                    description="Block DNS over TLS (IPv6)"
                )
                if rule_result.success:
                    result.rules_created += 1
                else:
                    result.rules_failed += 1
                    result.errors.append(rule_result.error)
        
        # Block generic DoT to any IP (port 853)
        if self._block_dot:
            rule_result = self._create_block_rule(
                name=f"{self.RULE_PREFIX}DoT_All",
                ips=["any"],
                port=self.DOT_PORT,
                description="Block all DNS over TLS (port 853)"
            )
            if rule_result.success:
                result.rules_created += 1
            else:
                result.rules_failed += 1
                result.errors.append(rule_result.error)
        
        self._blocked_ips = ipv4_ips | ipv6_ips
        result.ips_blocked = len(self._blocked_ips)
        result.success = result.rules_failed == 0
        
        if result.success:
            logger.info(
                f"DoH/DoT blocking complete: {result.rules_created} rules, "
                f"{result.ips_blocked} IPs blocked"
            )
        else:
            logger.warning(
                f"DoH/DoT blocking had errors: {result.rules_failed} failed"
            )
        
        return result
    
    def _create_block_rule(
        self,
        name: str,
        ips: List[str],
        port: int,
        description: str = ""
    ) -> BlockRule:
        """Create a Windows Firewall block rule."""
        rule = BlockRule(name=name, ips=ips, port=port)
        
        try:
            # First, delete existing rule if any
            self._delete_rule(name)
            
            # Build IP list for netsh
            if ips == ["any"]:
                remote_ip = "any"
            else:
                remote_ip = ",".join(ips)
            
            # Create the rule
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={name}",
                "dir=out",
                "action=block",
                f"remoteip={remote_ip}",
                f"remoteport={port}",
                "protocol=tcp",
                "enable=yes",
            ]
            
            if description:
                # Note: netsh doesn't support description directly
                pass
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                rule.success = True
                self._rules_created.append(name)
                logger.debug(f"Created firewall rule: {name}")
            else:
                rule.success = False
                rule.error = result.stderr.strip() or "Unknown error"
                logger.error(f"Failed to create rule {name}: {rule.error}")
            
        except subprocess.TimeoutExpired:
            rule.success = False
            rule.error = "Command timed out"
        except Exception as e:
            rule.success = False
            rule.error = str(e)
            logger.error(f"Error creating rule {name}: {e}")
        
        return rule
    
    def _delete_rule(self, name: str) -> bool:
        """Delete a firewall rule by name."""
        try:
            cmd = [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f"name={name}"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.debug(f"Error deleting rule {name}: {e}")
            return False
    
    def remove_all_rules(self) -> int:
        """
        Remove all DoH/DoT block rules created by this blocker.
        
        Returns:
            Number of rules removed
        """
        removed = 0
        
        # Remove known created rules
        for name in self._rules_created.copy():
            if self._delete_rule(name):
                removed += 1
                self._rules_created.remove(name)
        
        # Also try to remove standard rule names
        standard_rules = [
            f"{self.RULE_PREFIX}DoH_IPv4",
            f"{self.RULE_PREFIX}DoH_IPv6",
            f"{self.RULE_PREFIX}DoT_IPv4",
            f"{self.RULE_PREFIX}DoT_IPv6",
            f"{self.RULE_PREFIX}DoT_All",
        ]
        
        for name in standard_rules:
            if self._delete_rule(name):
                removed += 1
        
        self._blocked_ips.clear()
        
        logger.info(f"Removed {removed} DoH/DoT block rules")
        return removed
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is in the blocked list."""
        return ip in self._blocked_ips
    
    def get_blocked_ips(self) -> Set[str]:
        """Get set of blocked IPs."""
        return self._blocked_ips.copy()
    
    def get_providers(self) -> List[DoHProvider]:
        """Get list of known DoH providers."""
        return DOH_PROVIDERS.copy()
    
    def add_custom_ips(self, ips: List[str], name: str = "Custom") -> BlockerResult:
        """
        Add custom IPs to block for DoH/DoT.
        
        Args:
            ips: List of IP addresses to block
            name: Rule name suffix
            
        Returns:
            BlockerResult
        """
        result = BlockerResult(success=True)
        
        # Validate IPs
        valid_ips = []
        for ip in ips:
            try:
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                result.errors.append(f"Invalid IP: {ip}")
        
        if not valid_ips:
            result.success = False
            return result
        
        # Create rules
        if self._block_doh:
            rule = self._create_block_rule(
                name=f"{self.RULE_PREFIX}{name}_DoH",
                ips=valid_ips,
                port=self.DOH_PORT,
            )
            if rule.success:
                result.rules_created += 1
            else:
                result.rules_failed += 1
        
        if self._block_dot:
            rule = self._create_block_rule(
                name=f"{self.RULE_PREFIX}{name}_DoT",
                ips=valid_ips,
                port=self.DOT_PORT,
            )
            if rule.success:
                result.rules_created += 1
            else:
                result.rules_failed += 1
        
        self._blocked_ips.update(valid_ips)
        result.ips_blocked = len(valid_ips)
        result.success = result.rules_failed == 0
        
        return result
    
    def check_rules_exist(self) -> Dict[str, bool]:
        """
        Check which DoH/DoT block rules exist.
        
        Returns:
            Dict mapping rule name to existence status
        """
        rules = {}
        
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            output = result.stdout
            
            rule_names = [
                f"{self.RULE_PREFIX}DoH_IPv4",
                f"{self.RULE_PREFIX}DoH_IPv6",
                f"{self.RULE_PREFIX}DoT_IPv4",
                f"{self.RULE_PREFIX}DoT_IPv6",
                f"{self.RULE_PREFIX}DoT_All",
            ]
            
            for name in rule_names:
                rules[name] = name in output
            
        except Exception as e:
            logger.error(f"Error checking rules: {e}")
        
        return rules
    
    def get_stats(self) -> Dict:
        """Get blocker statistics."""
        return {
            "block_doh": self._block_doh,
            "block_dot": self._block_dot,
            "ips_blocked": len(self._blocked_ips),
            "rules_created": len(self._rules_created),
            "known_providers": len(DOH_PROVIDERS),
        }
