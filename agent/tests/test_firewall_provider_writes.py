import os
import sys


AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from firewall.application_service import FirewallApplicationService
from firewall.policy import PolicyManager
from firewall.provider import FirewallProvider
from firewall.rules import RulesManager


class FakeFirewallProvider(FirewallProvider):
    name = "fake"

    def __init__(self):
        self.created = []
        self.deleted = []
        self.deleted_prefixes = []
        self.policies = []
        self.rules = []

    @classmethod
    def available(cls):
        return True

    def list_rules(
        self,
        *,
        rule_prefix=None,
        direction=None,
        action=None,
        enabled_only=True,
    ):
        return [
            rule for rule in self.rules
            if (not rule_prefix or rule.get("rule_name", "").startswith(rule_prefix))
            and (not direction or rule.get("direction") == direction)
            and (not action or rule.get("action") == action)
            and (not enabled_only or rule.get("enabled", True))
        ]

    def get_policy_status(self):
        return {"outbound_default_block": False, "profile_name": "Private"}

    def create_or_replace_rule(
        self,
        rule_name,
        *,
        direction="out",
        action="allow",
        protocol="any",
        remote_addresses=None,
        remote_ports=None,
        program=None,
        profile="any",
        description=None,
    ):
        self.created.append({
            "rule_name": rule_name,
            "direction": direction,
            "action": action,
            "protocol": protocol,
            "remote_addresses": list(remote_addresses or []),
            "remote_ports": list(remote_ports or []),
            "program": program,
            "profile": profile,
            "description": description,
        })
        return True

    def update_rule_remote_addresses(self, rule_name, remote_addresses):
        return True

    def delete_rule(self, rule_name):
        self.deleted.append(rule_name)
        return True

    def delete_rules_by_prefix(self, rule_prefix):
        self.deleted_prefixes.append(rule_prefix)
        return 2

    def set_profile_outbound_policy(self, profile, action):
        self.policies.append((profile, action))
        return True


class FakeManager:
    def __init__(self):
        self.restored = []
        self.cleared = 0

    def restore_snapshot(self, path):
        self.restored.append(path)
        return True

    def clear_all_rules(self):
        self.cleared += 1
        return True


def test_rules_manager_delegates_writes_to_write_provider():
    read_provider = FakeFirewallProvider()
    write_provider = FakeFirewallProvider()
    manager = RulesManager(
        "SAINT",
        provider=read_provider,
        write_provider=write_provider,
    )

    assert manager.create_allow_rule("8.8.8.8") is True
    assert manager.allowed_ips == {"8.8.8.8"}
    assert write_provider.created[0]["rule_name"].startswith("SAINT_Allow_8_8_8_8_")
    assert write_provider.created[0]["remote_addresses"] == ["8.8.8.8"]

    read_provider.rules = [{
        "rule_name": write_provider.created[0]["rule_name"],
        "direction": "out",
        "action": "allow",
        "enabled": True,
        "remote_addresses": ["8.8.8.8"],
    }]
    assert manager.remove_allow_rule("8.8.8.8") is True
    assert write_provider.deleted == [write_provider.created[0]["rule_name"]]
    assert manager.allowed_ips == set()

    assert manager.clear_all_rules() is True
    assert write_provider.deleted_prefixes == ["SAINT"]


def test_policy_manager_delegates_profile_writes_to_provider():
    provider = FakeFirewallProvider()
    manager = PolicyManager(write_provider=provider)

    assert manager.restore_policies({"domain": "allow", "public": "block"}) is True

    assert provider.policies == [("domain", "allow"), ("public", "block")]


def test_firewall_application_service_uses_running_manager_when_supplied():
    manager = FakeManager()
    service = FirewallApplicationService(rule_prefix="SAINT", manager=manager)

    assert service.restore_firewall_snapshot("profiles/test.json") is True
    assert service.clear_saint_rules() is True

    assert manager.restored == ["profiles/test.json"]
    assert manager.cleared == 1
