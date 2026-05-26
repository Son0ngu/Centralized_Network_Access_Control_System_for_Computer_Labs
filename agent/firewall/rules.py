import logging
import threading
from typing import Optional, Set

from shared.time_utils import now, now_iso, sleep
from .provider import FirewallProvider, get_default_provider
from .utils import FirewallUtils

logger = logging.getLogger("firewall.rules")

class RulesManager:

    def __init__(
        self,
        rule_prefix: str = "FirewallController",
        provider: Optional[FirewallProvider] = None,
    ):
        self.rule_prefix = rule_prefix
        self.allowed_ips: Set[str] = set()
        self._rule_lock = threading.Lock()
        # The provider is the *read* side — listing/counting rules. Writes
        # still go through netsh below because they need elevation and
        # idempotent name semantics we already debugged. Injected for tests
        # and to let the agent prefer NetSecurity when available.
        self._provider: FirewallProvider = provider or get_default_provider()
        logger.info("RulesManager using firewall provider: %s", self._provider.name)
    
    def create_self_allow_rules(self, program_path: str) -> bool:
        """Create allow rules for the agent's own exe.

        Rationale: when Default Deny is enabled, the agent must still reach the
        control server (HTTPS / TCP 443) and resolve domains via its own
        dnspython/aiodns stack (DNS / UDP 53 + TCP 53 fallback). Whitelisting
        by program path is bulletproof against server IP rotation (Render.com
        load balancer, CDN), unlike `remoteip=` rules.

        Rules are created with deterministic names and re-created idempotently
        (delete-then-add) so agent restarts don't accumulate duplicates.
        """
        if not program_path:
            logger.error("Self-allow rules skipped: no program path provided")
            return False

        rules = [
            ("HTTPS", "tcp", "443"),
            ("DNS_UDP", "udp", "53"),
            ("DNS_TCP", "tcp", "53"),
        ]

        success = True
        for tag, protocol, remoteport in rules:
            rule_name = f"{self.rule_prefix}_SelfAllow_{tag}"

            # Idempotent: remove any stale rule with the same name first.
            # netsh returns non-zero if no match - that's expected on first run.
            FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "delete", "rule",
                f"name={rule_name}",
            ])

            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=out",
                "action=allow",
                f"program={program_path}",
                f"protocol={protocol}",
                f"remoteport={remoteport}",
                "enable=yes",
                "profile=any",
                f"description=Allow SAINT agent outbound {tag} ({now_iso()})",
            ])

            if result.returncode == 0:
                logger.info(f"Self-allow rule created: {rule_name} ({protocol}/{remoteport})")
            else:
                logger.error(
                    f"Failed to create self-allow rule {rule_name}: "
                    f"{result.stderr.strip() or '(no stderr)'}"
                )
                success = False

        return success

    def create_allow_rule(self, ip: str) -> bool:
        try:
            if not FirewallUtils.is_valid_ip(ip):
                logger.warning(f"Invalid IP: {ip}")
                return False

            if ip in self.allowed_ips:
                logger.debug(f"Allow rule already exists for {ip}")
                return True

            timestamp = int(now())
            sanitized_ip = ip.replace('.', '_')
            rule_name = f"{self.rule_prefix}_Allow_{sanitized_ip}_{timestamp}"
            
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=out",
                "action=allow",
                f"remoteip={ip}",
                "protocol=any",
                "enable=yes",
                "profile=any",
                f"description=ALLOW rule for whitelisted IP {ip} (Created: {now_iso()})"
            ])
            
            if result.returncode == 0:
                self.allowed_ips.add(ip)
                logger.debug(f"Created allow rule for {ip}")
                return True
            else:
                logger.error(f"Failed to create allow rule for {ip}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception creating allow rule for {ip}: {e}")
            return False
    
    def remove_allow_rule(self, ip: str) -> bool:
        try:
            if ip not in self.allowed_ips:
                logger.debug(f"No allow rule exists for {ip}")
                return True
            
            rule_pattern = f"_{ip.replace('.', '_')}_"
            
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule",
                "name=all", "verbose"
            ])
            
            if result.returncode != 0:
                logger.error("Failed to list rules")
                return False
            
            rule_names_to_delete = []
            lines = result.stdout.split('\n')
            
            for line in lines:
                if line.strip().startswith("Rule Name:"):
                    rule_name = line.strip()[10:].strip()
                    if (rule_name.startswith(self.rule_prefix) and
                        "_Allow_" in rule_name and
                        rule_pattern in rule_name):
                        rule_names_to_delete.append(rule_name)
            
            success = True
            for rule_name in rule_names_to_delete:
                result = FirewallUtils.run_netsh_command([
                    "advfirewall", "firewall", "delete", "rule",
                    f"name={rule_name}"
                ])
                
                if result.returncode == 0:
                    logger.debug(f"Removed allow rule: {rule_name}")
                else:
                    logger.warning(f"Failed to remove rule {rule_name}: {result.stderr}")
                    success = False
            
            if success:
                self.allowed_ips.discard(ip)
            
            return success
                
        except Exception as e:
            logger.error(f"Error removing allow rule for {ip}: {e}")
            return False
    
    def create_allow_rules_batch(self, ips: Set[str]) -> bool:
        try:
            logger.info(f"Creating ALLOW rules for {len(ips)} IPs...")
            
            success_count = 0
            error_count = 0
            
            with self._rule_lock:
                for ip in sorted(ips):
                    try:
                        if self.create_allow_rule(ip):
                            success_count += 1
                        else:
                            error_count += 1
                        
                        # Small delay for stability
                        sleep(0.02)
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Exception creating allow rule for {ip}: {e}")
            
            logger.info(f"Allow rules creation completed: {success_count} success, {error_count} errors")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error creating allow rules batch: {e}")
            return False
    
    def clear_all_rules(self) -> bool:
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all"
            ], timeout=60)
            
            if result.returncode != 0:
                logger.error(f"Failed to list rules: {result.stderr.strip()}")
                return False
            
            # Find our rules
            rule_names = []
            lines = result.stdout.split('\n')
            
            for line in lines:
                if line.strip().startswith("Rule Name:"):
                    rule_name = line.strip()[10:].strip()
                    if rule_name.startswith(self.rule_prefix):
                        rule_names.append(rule_name)
            
            if not rule_names:
                logger.info(f"No rules with prefix '{self.rule_prefix}' to clear")
                return True
            
            logger.info(f"Found {len(rule_names)} rules to clear")
            
            success = True
            for rule_name in rule_names:
                result = FirewallUtils.run_netsh_command([
                    "advfirewall", "firewall", "delete", "rule",
                    f"name={rule_name}"
                ])
                
                if result.returncode == 0:
                    logger.debug(f"Removed rule: {rule_name}")
                else:
                    logger.warning(f"Failed to remove rule {rule_name}: {result.stderr.strip()}")
                    success = False
            
            if success:
                self.allowed_ips.clear()
                logger.info(f"Cleared {len(rule_names)} rules successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Error clearing firewall rules: {e}")
            return False
    
    def load_existing_rules(self):
        """Re-hydrate ``allowed_ips`` from rules already present on the OS.

        Backend-agnostic now: delegates to the firewall provider's
        ``list_outbound_allow_ips`` rather than parsing ``netsh`` text inline.
        Behaviour is unchanged for English-locale Windows; non-English locales
        now also work (the netsh text parser was English-only).
        """
        try:
            logger.debug("Loading existing firewall rules via provider %s",
                         self._provider.name)
            ips = self._provider.list_outbound_allow_ips(rule_prefix=self.rule_prefix)
            self.allowed_ips.update(ips)
            logger.info("Loaded %d existing allow rules", len(self.allowed_ips))
        except Exception as e:
            logger.warning("Could not load existing firewall rules: %s", e)

    def get_rule_count(self) -> int:
        try:
            return self._provider.count_rules(rule_prefix=self.rule_prefix)
        except Exception:
            return 0