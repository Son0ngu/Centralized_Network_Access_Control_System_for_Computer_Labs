import logging
import threading
from typing import Set

from shared.time_utils import now, now_iso, sleep
from .utils import FirewallUtils

logger = logging.getLogger("firewall.rules")

class RulesManager:
    
    def __init__(self, rule_prefix: str = "FirewallController"):
        self.rule_prefix = rule_prefix
        self.allowed_ips: Set[str] = set()
        self._rule_lock = threading.Lock()
    
    def create_allow_rule(self, ip: str) -> bool:
        try:
            if not FirewallUtils.is_valid_ip(ip):
                logger.warning(f"Invalid IP: {ip}")
                return False
            
            if ip in self.allowed_ips:
                logger.debug(f"Allow rule already exists for {ip}")
                return True
            
            timestamp = int(now())
            sanitized_ip = ip.replace('.', '_').replace(':', '_')
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
            
            rule_pattern = f"_{ip.replace('.', '_').replace(':', '_')}_"
            
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
        try:
            logger.debug("Loading existing firewall rules...")
            
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all"
            ], timeout=60)
            
            if result.returncode != 0:
                logger.warning(f"Could not list rules: {result.stderr.strip()}")
                return
            
            current_rule = None
            current_action = None
            current_direction = None
            lines = result.stdout.split('\n')
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("Rule Name:"):
                    current_rule = line[10:].strip()
                    current_action = None
                    current_direction = None
                    
                    if not current_rule.startswith(self.rule_prefix):
                        current_rule = None
                        continue
                
                elif current_rule:
                    if line.startswith("Direction:"):
                        current_direction = line[10:].strip().lower()
                    
                    elif line.startswith("Action:"):
                        current_action = line[7:].strip().lower()
                    
                    elif line.startswith("RemoteIP:") and current_action == "allow" and current_direction == "out":
                        ip_part = line[9:].strip()
                        
                        if ip_part and ip_part.lower() != "any":
                            ip_parts = ip_part.split(',')
                            for part in ip_parts:
                                part = part.strip()
                                if FirewallUtils.is_valid_ip(part):
                                    self.allowed_ips.add(part)
            
            logger.info(f"Loaded {len(self.allowed_ips)} existing allow rules")
            
        except Exception as e:
            logger.warning(f"Could not load existing firewall rules: {e}")
    
    def get_rule_count(self) -> int:
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all"
            ])
            
            if result.returncode != 0:
                return 0
            
            count = 0
            for line in result.stdout.split('\n'):
                if line.strip().startswith("Rule Name:"):
                    rule_name = line.strip()[10:].strip()
                    if rule_name.startswith(self.rule_prefix):
                        count += 1
            
            return count
            
        except Exception:
            return 0