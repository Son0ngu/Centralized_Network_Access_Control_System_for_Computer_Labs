"""
DNS Firewall
-------------
Controls DNS traffic at the firewall level.
Ensures DNS queries only go through our proxy and registered upstream resolvers.

Key Rules:
1. Allow DNS (port 53) ONLY to 127.0.0.1 (our proxy)
2. Allow DNS to registered upstream resolvers (for the proxy itself)
3. Block all other DNS traffic
4. Block DNS over non-standard ports

This prevents:
- Direct DNS queries bypassing our proxy
- DNS exfiltration over non-standard ports
- Rogue DNS resolvers
"""

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("dns_proxy.security.dns_firewall")


@dataclass
class DNSFirewallRule:
    """DNS firewall rule."""
    name: str
    action: str  # "allow" or "block"
    direction: str  # "in" or "out"
    remote_ip: str
    remote_port: int = 53
    protocol: str = "any"  # "tcp", "udp", or "any"
    description: str = ""
    enabled: bool = True


@dataclass
class DNSFirewallConfig:
    """DNS firewall configuration."""
    # Our DNS proxy address
    proxy_address_ipv4: str = "127.0.0.1"
    proxy_address_ipv6: str = "::1"
    
    # Registered upstream resolvers (allowed for proxy to query)
    upstream_resolvers: List[str] = field(default_factory=lambda: [
        "8.8.8.8",
        "8.8.4.4",
        "1.1.1.1",
        "1.0.0.1",
    ])
    
    # Additional allowed DNS servers (e.g., corporate DNS)
    additional_allowed: List[str] = field(default_factory=list)
    
    # Block DNS on non-standard ports
    block_nonstandard_ports: bool = True
    
    # Include IPv6 rules
    include_ipv6: bool = True
    
    # Enable strict mode (block before allow)
    strict_mode: bool = True


@dataclass
class FirewallResult:
    """Result of firewall operation."""
    success: bool
    rules_created: int = 0
    rules_deleted: int = 0
    errors: List[str] = field(default_factory=list)


class DNSFirewall:
    """
    Controls DNS traffic at the Windows Firewall level.
    
    Strategy (order matters):
    1. Allow loopback DNS (127.0.0.1:53, [::1]:53)
    2. Allow upstream resolvers for proxy (configurable list)
    3. Block all other DNS (port 53)
    4. Optionally block DNS on common bypass ports
    
    Usage:
        config = DNSFirewallConfig(
            upstream_resolvers=["8.8.8.8", "1.1.1.1"]
        )
        firewall = DNSFirewall(config)
        
        # Apply rules
        result = firewall.apply_rules()
        
        # Check status
        status = firewall.check_rules()
        
        # Remove rules
        firewall.remove_rules()
    """
    
    RULE_PREFIX = "DNS_Proxy_DNSControl_"
    
    # DNS port
    DNS_PORT = 53
    
    # Common DNS bypass ports to block
    BYPASS_PORTS = [
        5353,   # mDNS
        5355,   # LLMNR
        # Don't block 443/853 here - handled by DoH blocker
    ]
    
    def __init__(self, config: DNSFirewallConfig = None):
        self._config = config or DNSFirewallConfig()
        self._rules_created: List[str] = []
        self._active = False
        
        logger.info(
            f"DNS Firewall initialized with {len(self._config.upstream_resolvers)} "
            f"upstream resolvers"
        )
    
    def apply_rules(self) -> FirewallResult:
        """
        Apply DNS firewall rules.
        
        Rule priority (Windows processes top-down):
        1. Allow rules (specific) - processed first due to lower priority
        2. Block rules (general) - catch-all
        
        Returns:
            FirewallResult with operation details
        """
        result = FirewallResult(success=True)
        
        # First, remove any existing rules
        self.remove_rules()
        
        try:
            # === ALLOW RULES ===
            
            # 1. Allow DNS to loopback (our proxy)
            result.rules_created += self._create_allow_rule(
                name=f"{self.RULE_PREFIX}Allow_Loopback",
                remote_ip="127.0.0.1",
                description="Allow DNS to local proxy"
            )
            
            if self._config.include_ipv6:
                result.rules_created += self._create_allow_rule(
                    name=f"{self.RULE_PREFIX}Allow_Loopback_IPv6",
                    remote_ip="::1",
                    description="Allow DNS to local proxy (IPv6)"
                )
            
            # 2. Allow DNS to upstream resolvers (for proxy itself)
            for i, resolver in enumerate(self._config.upstream_resolvers):
                result.rules_created += self._create_allow_rule(
                    name=f"{self.RULE_PREFIX}Allow_Upstream_{i}",
                    remote_ip=resolver,
                    description=f"Allow DNS to upstream resolver {resolver}"
                )
            
            # 3. Allow additional DNS servers
            for i, server in enumerate(self._config.additional_allowed):
                result.rules_created += self._create_allow_rule(
                    name=f"{self.RULE_PREFIX}Allow_Additional_{i}",
                    remote_ip=server,
                    description=f"Allow DNS to additional server {server}"
                )
            
            # === BLOCK RULES ===
            
            # 4. Block all other DNS (catch-all)
            result.rules_created += self._create_block_rule(
                name=f"{self.RULE_PREFIX}Block_All_DNS",
                remote_ip="any",
                remote_port=self.DNS_PORT,
                description="Block all other DNS traffic"
            )
            
            # 5. Block DNS on bypass ports (optional)
            if self._config.block_nonstandard_ports:
                for port in self.BYPASS_PORTS:
                    result.rules_created += self._create_block_rule(
                        name=f"{self.RULE_PREFIX}Block_Port_{port}",
                        remote_ip="any",
                        remote_port=port,
                        description=f"Block DNS bypass on port {port}"
                    )
            
            self._active = True
            logger.info(f"DNS Firewall rules applied: {result.rules_created} rules")
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Failed to apply DNS firewall rules: {e}")
        
        return result
    
    def _create_allow_rule(
        self,
        name: str,
        remote_ip: str,
        description: str = ""
    ) -> int:
        """Create an allow rule for DNS traffic."""
        return self._create_rule(
            name=name,
            action="allow",
            remote_ip=remote_ip,
            remote_port=self.DNS_PORT,
            description=description
        )
    
    def _create_block_rule(
        self,
        name: str,
        remote_ip: str,
        remote_port: int,
        description: str = ""
    ) -> int:
        """Create a block rule for DNS traffic."""
        return self._create_rule(
            name=name,
            action="block",
            remote_ip=remote_ip,
            remote_port=remote_port,
            description=description
        )
    
    def _create_rule(
        self,
        name: str,
        action: str,
        remote_ip: str,
        remote_port: int,
        description: str = ""
    ) -> int:
        """Create a Windows Firewall rule."""
        rules_created = 0
        
        # Create for both UDP and TCP
        for protocol in ["udp", "tcp"]:
            rule_name = f"{name}_{protocol.upper()}"
            
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=out",
                f"action={action}",
                f"protocol={protocol}",
                f"remoteport={remote_port}",
                "enable=yes",
            ]
            
            if remote_ip and remote_ip != "any":
                cmd.append(f"remoteip={remote_ip}")
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    rules_created += 1
                    self._rules_created.append(rule_name)
                    logger.debug(f"Created rule: {rule_name}")
                else:
                    logger.warning(f"Failed to create rule {rule_name}: {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Error creating rule {rule_name}: {e}")
        
        return rules_created
    
    def remove_rules(self) -> int:
        """Remove all DNS firewall rules."""
        removed = 0
        
        # Remove known rules
        for rule_name in self._rules_created.copy():
            if self._delete_rule(rule_name):
                removed += 1
                self._rules_created.remove(rule_name)
        
        # Also try to remove by prefix pattern
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            for line in result.stdout.split("\n"):
                if "Rule Name:" in line and self.RULE_PREFIX in line:
                    # Extract rule name
                    rule_name = line.split(":", 1)[1].strip()
                    if self._delete_rule(rule_name):
                        removed += 1
                        
        except Exception as e:
            logger.error(f"Error removing rules: {e}")
        
        self._active = False
        logger.info(f"DNS Firewall rules removed: {removed}")
        
        return removed
    
    def _delete_rule(self, name: str) -> bool:
        """Delete a firewall rule by name."""
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except:
            return False
    
    def check_rules(self) -> Dict:
        """
        Check current DNS firewall rule status.
        
        Returns:
            Dict with rule status information
        """
        status = {
            "active": self._active,
            "rules_count": 0,
            "allow_rules": [],
            "block_rules": [],
            "missing_rules": [],
        }
        
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            output = result.stdout
            
            # Check expected rules
            expected_rules = [
                f"{self.RULE_PREFIX}Allow_Loopback",
                f"{self.RULE_PREFIX}Block_All_DNS",
            ]
            
            for resolver in self._config.upstream_resolvers:
                expected_rules.append(f"{self.RULE_PREFIX}Allow_Upstream")
            
            for rule_base in expected_rules:
                # Check both UDP and TCP variants
                for protocol in ["UDP", "TCP"]:
                    rule_name = f"{rule_base}_{protocol}"
                    if rule_name in output or rule_base in output:
                        status["rules_count"] += 1
                        if "Allow" in rule_base:
                            status["allow_rules"].append(rule_name)
                        else:
                            status["block_rules"].append(rule_name)
                    elif rule_base in output:
                        pass  # Base name found
                    else:
                        status["missing_rules"].append(rule_name)
                        
        except Exception as e:
            logger.error(f"Error checking rules: {e}")
            status["error"] = str(e)
        
        return status
    
    def update_upstream_resolvers(self, resolvers: List[str]) -> FirewallResult:
        """
        Update the list of allowed upstream resolvers.
        
        Args:
            resolvers: New list of upstream DNS resolvers
            
        Returns:
            FirewallResult
        """
        self._config.upstream_resolvers = resolvers.copy()
        return self.apply_rules()  # Reapply with new list
    
    def add_upstream_resolver(self, resolver: str) -> FirewallResult:
        """Add an upstream resolver to the allowed list."""
        if resolver not in self._config.upstream_resolvers:
            self._config.upstream_resolvers.append(resolver)
            return self.apply_rules()
        return FirewallResult(success=True)
    
    def remove_upstream_resolver(self, resolver: str) -> FirewallResult:
        """Remove an upstream resolver from the allowed list."""
        if resolver in self._config.upstream_resolvers:
            self._config.upstream_resolvers.remove(resolver)
            return self.apply_rules()
        return FirewallResult(success=True)
    
    def get_allowed_resolvers(self) -> List[str]:
        """Get list of currently allowed upstream resolvers."""
        return (
            [self._config.proxy_address_ipv4] +
            ([self._config.proxy_address_ipv6] if self._config.include_ipv6 else []) +
            self._config.upstream_resolvers +
            self._config.additional_allowed
        )
    
    def is_resolver_allowed(self, ip: str) -> bool:
        """Check if a resolver IP is allowed."""
        return ip in self.get_allowed_resolvers()
    
    def get_stats(self) -> Dict:
        """Get firewall statistics."""
        return {
            "active": self._active,
            "rules_created": len(self._rules_created),
            "upstream_resolvers": len(self._config.upstream_resolvers),
            "additional_allowed": len(self._config.additional_allowed),
            "block_nonstandard_ports": self._config.block_nonstandard_ports,
            "include_ipv6": self._config.include_ipv6,
        }
    
    @property
    def config(self) -> DNSFirewallConfig:
        return self._config
    
    @property
    def is_active(self) -> bool:
        return self._active
