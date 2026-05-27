"""PowerShell NetSecurity-module backed :class:`FirewallProvider`.

Why this exists:

``netsh advfirewall ... show rule`` emits human-readable text that we have to
parse with key-prefix string matching (``Rule Name:``, ``Direction:`` …).
That output is *localised* — on a Vietnamese / Japanese / Spanish Windows
host the keys become ``Tên quy tắc:`` etc and the parser silently returns
zero rules. PowerShell's NetSecurity cmdlets emit structured objects that we
can serialise to JSON and consume reliably regardless of UI language.

Cmdlets used:

- ``Get-NetFirewallRule`` — header (name, direction, action, enabled, profile)
- ``Get-NetFirewallAddressFilter`` — RemoteAddress / LocalAddress
- ``Get-NetFirewallPortFilter`` — RemotePort / LocalPort, protocol
- ``Get-NetFirewallApplicationFilter`` — Program path
- ``Get-NetFirewallProfile`` — outbound default policy

We join them in a single PowerShell script so it's one process spawn per
``list_rules`` call rather than one per rule.

Tradeoffs:

- Slower than ``netsh`` for trivial reads (PowerShell startup overhead is
  ~250ms cold). Acceptable because the dashboard does at most a few reads
  per second and ``RulesManager`` only re-hydrates on startup.
- Requires the ``NetSecurity`` PowerShell module which is shipped with every
  Windows 8+ install we target. If it's missing the factory falls back to
  the netsh provider.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Iterable, List, Optional, Set

from .provider import (
    FirewallPolicyStatus,
    FirewallProvider,
    FirewallRule,
    _normalize_action,
    _normalize_direction,
)

logger = logging.getLogger("firewall.netsecurity_provider")


def _ps_quote(value) -> str:
    """Single-quote a PowerShell literal."""
    return "'" + str(value).replace("'", "''") + "'"


def _ps_array(values: Iterable) -> str:
    items = [str(v) for v in values or [] if str(v)]
    if not items:
        return "@()"
    return "@(" + ",".join(_ps_quote(item) for item in items) + ")"


def _ps_direction(value: str) -> str:
    return "Inbound" if _normalize_direction(value) == "in" else "Outbound"


def _ps_action(value: str) -> str:
    return "Block" if _normalize_action(value) == "block" else "Allow"


def _ps_profile(value: str) -> str:
    v = (value or "any").strip().lower()
    if v == "any":
        return "Any"
    mapping = {"domain": "Domain", "private": "Private", "public": "Public"}
    return mapping.get(v, value)


def _ps_protocol(value: str) -> str:
    v = (value or "any").strip().lower()
    if v == "any":
        return "Any"
    return v.upper()


# PowerShell script that emits one JSON document per call. We combine the
# four cmdlets in-process so the agent only pays the PS startup cost once.
#
# ``$Prefix`` is interpolated by Python (no PS string interpolation, to keep
# escaping simple). We always pass ``-Like`` style matching because callers
# already expect a prefix not an exact name.
_LIST_RULES_PS = r"""
$ErrorActionPreference = 'Stop'
try {
    $rules = Get-NetFirewallRule -PolicyStore ActiveStore __FILTER_NAME__ __FILTER_DIR__ __FILTER_ACT__ __FILTER_ENABLED__
} catch {
    # NetSecurity not available or no matching rules
    Write-Output '[]'
    exit 0
}
$out = foreach ($r in $rules) {
    $addr = $r | Get-NetFirewallAddressFilter
    $port = $r | Get-NetFirewallPortFilter
    $app  = $r | Get-NetFirewallApplicationFilter
    $remote = @()
    if ($addr.RemoteAddress) {
        $remote = @($addr.RemoteAddress) | ForEach-Object { "$_" }
    }
    $rports = @()
    if ($port.RemotePort) {
        $rports = @($port.RemotePort) | ForEach-Object { "$_" }
    }
    [pscustomobject]@{
        rule_name        = $r.DisplayName
        direction        = "$($r.Direction)".ToLower()
        action           = "$($r.Action)".ToLower()
        enabled          = ($r.Enabled -eq 'True' -or $r.Enabled -eq $true)
        protocol         = "$($port.Protocol)".ToLower()
        profile          = "$($r.Profile)"
        program          = $app.Program
        remote_addresses = $rports | Out-Null; $remote
        remote_ports     = $rports
    }
}
if (-not $out) { Write-Output '[]'; exit 0 }
@($out) | ConvertTo-Json -Compress -Depth 4
"""


_POLICY_STATUS_PS = r"""
$ErrorActionPreference = 'Stop'
$active = Get-NetConnectionProfile | Select-Object -First 1
$profileName = if ($active) { "$($active.NetworkCategory)" } else { 'Public' }
try {
    $fp = Get-NetFirewallProfile -Profile $profileName
} catch {
    $fp = Get-NetFirewallProfile -Profile Public
}
[pscustomobject]@{
    profile_name             = "$($fp.Name)"
    outbound_default_block   = ("$($fp.DefaultOutboundAction)".ToLower() -eq 'block')
} | ConvertTo-Json -Compress
"""


def _which_powershell() -> Optional[str]:
    """Locate a usable PowerShell binary.

    Prefer ``pwsh`` (PowerShell 7+) when present; fall back to Windows
    PowerShell 5.1 (``powershell.exe``). On non-Windows hosts both will be
    absent and we report unavailable.
    """
    for candidate in ("pwsh.exe", "pwsh", "powershell.exe", "powershell"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def _run_ps(script: str, timeout: int = 30) -> Optional[str]:
    """Run a PowerShell snippet. Returns stdout text or None on failure."""
    binary = _which_powershell()
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("PowerShell invocation failed: %s", exc)
        return None
    if result.returncode != 0:
        # PS scripts above use `try/catch` so a non-zero rc means the host
        # truly couldn't run the script — log at debug and let caller fall back.
        logger.debug("PowerShell rc=%s stderr=%s", result.returncode, result.stderr[:200])
        return None
    return result.stdout


class NetSecurityFirewallProvider(FirewallProvider):
    """NetSecurity-cmdlet backend. Robust to non-English Windows locales."""

    name = "netsecurity"

    @classmethod
    def available(cls) -> bool:
        """Probe for PowerShell + the NetSecurity module.

        We avoid spawning PS just to check — ``shutil.which`` is enough to
        decide whether to try this provider. If NetSecurity is missing at
        runtime, ``_run_ps`` returns None and we degrade silently.
        """
        if os.name != "nt":
            return False
        return _which_powershell() is not None

    def list_rules(
        self,
        *,
        rule_prefix: Optional[str] = None,
        direction: Optional[str] = None,
        action: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[FirewallRule]:
        # Build the Get-NetFirewallRule filter clauses inline. Using -Like with
        # a wildcard avoids escaping issues for prefix matches.
        filt_name = (
            f"-DisplayName '{(rule_prefix or '').replace(chr(39), chr(39) * 2)}*'"
            if rule_prefix else ""
        )
        ndir = _normalize_direction(direction)
        nact = _normalize_action(action)
        filt_dir = f"-Direction {'Inbound' if ndir == 'in' else 'Outbound'}" if ndir else ""
        filt_act = f"-Action {'Allow' if nact == 'allow' else 'Block'}" if nact else ""
        filt_enabled = "-Enabled True" if enabled_only else ""

        script = (
            _LIST_RULES_PS
            .replace("__FILTER_NAME__", filt_name)
            .replace("__FILTER_DIR__", filt_dir)
            .replace("__FILTER_ACT__", filt_act)
            .replace("__FILTER_ENABLED__", filt_enabled)
        )

        raw = _run_ps(script)
        if raw is None:
            return []
        raw = raw.strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.debug("NetSecurity JSON decode failed: %s; raw=%s", exc, raw[:200])
            return []

        # Single-row results come back as a dict, multi-row as a list.
        if isinstance(data, dict):
            data = [data]

        out: List[FirewallRule] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append({
                "rule_name": str(item.get("rule_name") or ""),
                "direction": (item.get("direction") or "").lower(),
                "action": (item.get("action") or "").lower(),
                "enabled": bool(item.get("enabled")),
                "protocol": (item.get("protocol") or "").lower(),
                "profile": str(item.get("profile") or ""),
                "program": item.get("program") or None,
                "remote_addresses": list(item.get("remote_addresses") or []),
                "remote_ports": list(item.get("remote_ports") or []),
            })
        return out

    def list_outbound_allow_ips(self, *, rule_prefix: str) -> Set[str]:
        """NetSecurity returns RemoteAddress already split; no streaming needed."""
        ips: Set[str] = set()
        from .utils import FirewallUtils  # local import to keep module-load light
        for rule in self.list_rules(rule_prefix=rule_prefix, direction="out",
                                    action="allow", enabled_only=True):
            for addr in rule.get("remote_addresses") or []:
                addr = (addr or "").strip()
                if not addr or addr.lower() == "any":
                    continue
                if FirewallUtils.is_valid_ip(addr):
                    ips.add(addr)
        return ips

    def get_policy_status(self) -> FirewallPolicyStatus:
        raw = _run_ps(_POLICY_STATUS_PS, timeout=15)
        status: FirewallPolicyStatus = {
            "outbound_default_block": False,
            "profile_name": "",
        }
        if not raw:
            return status
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return status
        if isinstance(data, dict):
            status["outbound_default_block"] = bool(data.get("outbound_default_block"))
            status["profile_name"] = str(data.get("profile_name") or "")
        return status

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create_or_replace_rule(
        self,
        rule_name: str,
        *,
        direction: str = "out",
        action: str = "allow",
        protocol: str = "any",
        remote_addresses: Optional[Iterable[str]] = None,
        remote_ports: Optional[Iterable[str]] = None,
        program: Optional[str] = None,
        profile: str = "any",
        description: Optional[str] = None,
    ) -> bool:
        self.delete_rule(rule_name)
        lines = [
            "$ErrorActionPreference = 'Stop'",
            "$params = @{",
            f"  DisplayName = {_ps_quote(rule_name)}",
            f"  Direction = {_ps_quote(_ps_direction(direction))}",
            f"  Action = {_ps_quote(_ps_action(action))}",
            "  Enabled = 'True'",
            f"  Profile = {_ps_quote(_ps_profile(profile))}",
            f"  Protocol = {_ps_quote(_ps_protocol(protocol))}",
        ]
        if remote_addresses:
            lines.append(f"  RemoteAddress = {_ps_array(remote_addresses)}")
        if remote_ports:
            lines.append(f"  RemotePort = {_ps_array(remote_ports)}")
        if program:
            lines.append(f"  Program = {_ps_quote(program)}")
        if description:
            lines.append(f"  Description = {_ps_quote(description)}")
        lines.extend([
            "}",
            "New-NetFirewallRule @params | Out-Null",
        ])
        return _run_ps("\n".join(lines)) is not None

    def update_rule_remote_addresses(
        self,
        rule_name: str,
        remote_addresses: Iterable[str],
    ) -> bool:
        script = "\n".join([
            "$ErrorActionPreference = 'Stop'",
            f"$rule = Get-NetFirewallRule -DisplayName {_ps_quote(rule_name)} -ErrorAction Stop",
            f"$rule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress {_ps_array(remote_addresses)}",
        ])
        return _run_ps(script) is not None

    def delete_rule(self, rule_name: str) -> bool:
        script = "\n".join([
            "$ErrorActionPreference = 'Stop'",
            f"$rules = Get-NetFirewallRule -DisplayName {_ps_quote(rule_name)} -ErrorAction SilentlyContinue",
            "if ($rules) { $rules | Remove-NetFirewallRule -ErrorAction Stop }",
        ])
        return _run_ps(script) is not None

    def delete_rules_by_prefix(self, rule_prefix: str) -> int:
        script = "\n".join([
            "$ErrorActionPreference = 'Stop'",
            f"$rules = Get-NetFirewallRule -DisplayName {_ps_quote(rule_prefix + '*')} -ErrorAction SilentlyContinue",
            "$count = @($rules).Count",
            "if ($count -gt 0) { $rules | Remove-NetFirewallRule -ErrorAction Stop }",
            "Write-Output $count",
        ])
        raw = _run_ps(script)
        if raw is None:
            return 0
        try:
            return int(str(raw).strip().splitlines()[-1])
        except (TypeError, ValueError, IndexError):
            return 0

    def set_profile_outbound_policy(self, profile: str, action: str) -> bool:
        profile_name = _ps_profile(profile)
        if profile_name not in ("Domain", "Private", "Public"):
            logger.warning("Unsupported firewall profile: %s", profile)
            return False
        desired = (action or "").strip().lower()
        if desired not in ("allow", "block"):
            logger.warning("Unsupported outbound action: %s", action)
            return False
        outbound = "Block" if desired == "block" else "Allow"
        script = "\n".join([
            "$ErrorActionPreference = 'Stop'",
            "Set-NetFirewallProfile "
            f"-Profile {_ps_quote(profile_name)} "
            "-DefaultInboundAction Block "
            f"-DefaultOutboundAction {_ps_quote(outbound)}",
        ])
        return _run_ps(script) is not None


__all__ = ["NetSecurityFirewallProvider"]
