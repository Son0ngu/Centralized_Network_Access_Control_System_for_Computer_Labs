"""Netsh-backed implementation of :class:`FirewallProvider`.

Wraps the existing text-parsing code path that lived inline in
``RulesManager._load_existing_rules`` / ``get_rule_count`` and in
``gui_qt/views/firewall.py``. The parsing logic stays the same; we just
funnel every caller through one place so the next refactor (e.g. swapping in
the PowerShell backend) is a single import change.

Caveats:
- Output of ``netsh advfirewall firewall show rule`` is English-only.
  On non-English Windows installs the keys (``Rule Name:``,
  ``Direction:``…) are localised and parsing silently returns nothing.
  Prefer :class:`NetSecurityFirewallProvider` when available.
- ``netsh`` returns multiple ``Rule Name:`` blocks separated by blank lines.
  A trailing newline matters; we flush the current block on EOF too.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from .provider import (
    FirewallPolicyStatus,
    FirewallProvider,
    FirewallRule,
    _normalize_action,
    _normalize_direction,
    _split_csv,
)
from .utils import FirewallUtils

logger = logging.getLogger("firewall.netsh_provider")


_KEY_MAP = {
    "rule name": "rule_name",
    "direction": "direction",
    "action": "action",
    "enabled": "enabled",
    "protocol": "protocol",
    "profiles": "profile",
    "program": "program",
    "remoteip": "remote_addresses",
    "remoteport": "remote_ports",
}


def _flush(block: Dict[str, str]) -> Optional[FirewallRule]:
    """Convert a raw key/value block from netsh into a FirewallRule dict.

    Returns None for empty blocks (multiple blank lines between rules).
    """
    if not block:
        return None
    rule: FirewallRule = {
        "rule_name": block.get("rule_name", ""),
        "direction": _normalize_direction(block.get("direction")) or "",
        "action": _normalize_action(block.get("action")) or "",
        "enabled": (block.get("enabled", "").strip().lower() in ("yes", "true")),
        "protocol": (block.get("protocol") or "").strip().lower(),
        "profile": (block.get("profile") or "").strip(),
        "program": (block.get("program") or "").strip() or None,
        "remote_addresses": _split_csv(block.get("remote_addresses")),
        "remote_ports": _split_csv(block.get("remote_ports")),
    }
    return rule


class NetshFirewallProvider(FirewallProvider):
    """Reads firewall state by parsing ``netsh advfirewall`` text output."""

    name = "netsh"

    @classmethod
    def available(cls) -> bool:
        # netsh ships with every Windows install we target; assume yes.
        # On non-Windows hosts (CI/Linux tests) the subprocess call below
        # will fail and callers get an empty list — that's acceptable.
        return True

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_rules(
        self,
        *,
        rule_prefix: Optional[str] = None,
        direction: Optional[str] = None,
        action: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[FirewallRule]:
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all", "verbose",
            ])
        except Exception as exc:
            logger.debug("netsh list_rules failed: %s", exc)
            return []

        if result.returncode != 0:
            logger.debug("netsh list_rules non-zero rc=%s", result.returncode)
            return []

        rules: List[FirewallRule] = []
        current: Dict[str, str] = {}
        want_direction = _normalize_direction(direction)
        want_action = _normalize_action(action)

        for raw_line in result.stdout.split("\n"):
            line = raw_line.strip()
            if not line:
                flushed = _flush(current)
                current = {}
                if flushed and _accepts(flushed, rule_prefix, want_direction,
                                        want_action, enabled_only):
                    rules.append(flushed)
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            mapped = _KEY_MAP.get(key.strip().lower())
            if not mapped:
                continue
            # netsh repeats some keys on multi-line values; last-write-wins is OK
            # because our consumers don't rely on the legacy multi-line cases.
            current[mapped] = value.strip()

        # Trailing block (no terminating blank line on the last entry)
        flushed = _flush(current)
        if flushed and _accepts(flushed, rule_prefix, want_direction,
                                want_action, enabled_only):
            rules.append(flushed)

        return rules

    def list_outbound_allow_ips(self, *, rule_prefix: str) -> Set[str]:
        """Faster path: avoid building full FirewallRule dicts for every row.

        Mirrors the old streaming parser in ``RulesManager._load_existing_rules``
        — we only need IPs that pass the (out, allow, prefix-match) filter,
        so we short-circuit as soon as we see a different action/direction.
        """
        ips: Set[str] = set()
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all", "verbose",
            ])
        except Exception as exc:
            logger.debug("netsh list_outbound_allow_ips failed: %s", exc)
            return ips
        if result.returncode != 0:
            return ips

        current_rule: Optional[str] = None
        current_dir: Optional[str] = None
        current_act: Optional[str] = None

        for raw_line in result.stdout.split("\n"):
            line = raw_line.strip()
            if not line:
                current_rule = None
                current_dir = None
                current_act = None
                continue
            lower = line.lower()
            if lower.startswith("rule name:"):
                name = line.split(":", 1)[1].strip()
                current_rule = name if name.startswith(rule_prefix) else None
                current_dir = None
                current_act = None
                continue
            if not current_rule:
                continue
            if lower.startswith("direction:"):
                current_dir = line.split(":", 1)[1].strip().lower()
            elif lower.startswith("action:"):
                current_act = line.split(":", 1)[1].strip().lower()
            elif lower.startswith("remoteip:") and current_dir == "out" and current_act == "allow":
                for chunk in _split_csv(line.split(":", 1)[1]):
                    if chunk.lower() == "any":
                        continue
                    if FirewallUtils.is_valid_ip(chunk):
                        ips.add(chunk)
        return ips

    def count_rules(self, *, rule_prefix: Optional[str] = None) -> int:
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "firewall", "show", "rule", "name=all",
            ])
        except Exception:
            return 0
        if result.returncode != 0:
            return 0
        count = 0
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("rule name:"):
                name = stripped.split(":", 1)[1].strip()
                if not rule_prefix or name.startswith(rule_prefix):
                    count += 1
        return count

    def get_policy_status(self) -> FirewallPolicyStatus:
        status: FirewallPolicyStatus = {
            "outbound_default_block": False,
            "profile_name": "",
        }
        try:
            result = FirewallUtils.run_netsh_command([
                "advfirewall", "show", "currentprofile",
            ])
        except Exception as exc:
            logger.debug("netsh get_policy_status failed: %s", exc)
            return status
        if result.returncode != 0:
            return status
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if lower.endswith("profile settings:"):
                # e.g. "Public Profile Settings:" → "Public"
                status["profile_name"] = line.split(" Profile", 1)[0].strip()
            elif "outbound" in lower and "block" in lower:
                status["outbound_default_block"] = True
            elif "outbound" in lower and "allow" in lower:
                status["outbound_default_block"] = False
        return status


def _accepts(
    rule: FirewallRule,
    rule_prefix: Optional[str],
    want_direction: Optional[str],
    want_action: Optional[str],
    enabled_only: bool,
) -> bool:
    """Apply list_rules filters to a parsed rule. Kept module-level for tests."""
    if rule_prefix and not rule.get("rule_name", "").startswith(rule_prefix):
        return False
    if want_direction and rule.get("direction") != want_direction:
        return False
    if want_action and rule.get("action") != want_action:
        return False
    if enabled_only and not rule.get("enabled"):
        return False
    return True


__all__ = ["NetshFirewallProvider"]
