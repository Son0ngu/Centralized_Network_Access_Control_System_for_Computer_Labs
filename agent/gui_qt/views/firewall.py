"""Firewall rules view for the Qt GUI.

Reads firewall rules from the agent's `FirewallManager` (set by MainWindow when
the agent reports running). When the manager isn't available the view falls
back to parsing `netsh advfirewall firewall show rule` directly.

Visibility-aware: the 5s refresh timer only does work while the view is on
screen (Qt's `showEvent`/`hideEvent` make this trivial — no buggy `hasattr`
check needed).
"""

import logging
import subprocess
import threading
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..components.data_table import DataTable
from ..styles import (
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED, FG_PRIMARY,
    FG_SECONDARY,
)

logger = logging.getLogger("gui_qt.firewall")


_REFRESH_INTERVAL_MS = 5_000


class _LoadSignals(QObject):
    """Carrier for the background rule-load thread to deliver results back
    to the GUI thread via a Qt signal."""
    finished = Signal(list, str, str)  # rules, policy_status, mode


class FirewallView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._firewall_manager = None
        self._load_signals = _LoadSignals()
        self._load_signals.finished.connect(self._on_load_finished)

        # Periodic refresh — only active while visible (see showEvent/hideEvent).
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._refresh_rules)

        self._build_ui()

    # =======================================================================
    # UI construction
    # =======================================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addWidget(self._build_stats_panel())
        root.addWidget(self._build_table(), stretch=1)
        root.addWidget(self._build_status_bar())

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("🔥 Firewall Rules")
        title.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {ACCENT_BLUE};"
        )
        layout.addWidget(title)
        layout.addStretch(1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumHeight(36)
        refresh_btn.clicked.connect(self._refresh_rules)
        layout.addWidget(refresh_btn)
        return layout

    def _build_stats_panel(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("card")
        wrap.setFixedHeight(72)
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(30)

        self._policy_label = QLabel("🛡 Policy: Loading...")
        self._policy_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {FG_PRIMARY};"
        )
        layout.addWidget(self._policy_label)

        self._rule_count_label = QLabel("Rules: --")
        self._rule_count_label.setStyleSheet(
            f"font-size: 14px; color: {FG_SECONDARY};"
        )
        layout.addWidget(self._rule_count_label)

        self._mode_label = QLabel("⚙️ Mode: --")
        self._mode_label.setStyleSheet(
            f"font-size: 14px; color: {FG_SECONDARY};"
        )
        layout.addWidget(self._mode_label)
        layout.addStretch(1)
        return wrap

    def _build_table(self) -> QWidget:
        # Widths chosen for typical content:
        #   ip:        IPv4 fits in ~140px
        #   direction: "Outbound" / "Inbound" → 90px
        #   action:    "Allow" / "Block" → 80px
        #   protocol:  "Any" / "TCP" / "UDP" → 80px
        #   rule_name: "FirewallController_Allow_192_168_170_129" — the wide
        #              tail; let this column auto-stretch to fill window width.
        columns = [
            {"key": "ip", "title": "IP Address", "width": 150},
            {"key": "direction", "title": "Direction", "width": 90},
            {"key": "action", "title": "Action", "width": 80},
            {"key": "protocol", "title": "Protocol", "width": 80},
            {"key": "rule_name", "title": "Rule Name", "width": 300},  # auto-stretches
        ]
        self._table = DataTable(columns, parent=self)
        return self._table

    def _build_status_bar(self) -> QWidget:
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        return self._status_label

    # =======================================================================
    # External wiring
    # =======================================================================

    def set_firewall_manager(self, manager) -> None:
        """Wired by MainWindow when the agent reports running."""
        self._firewall_manager = manager
        self._refresh_rules()

    # =======================================================================
    # Visibility-aware refresh — Qt does this cleanly with showEvent/hideEvent.
    # No more "hasattr typo" bug.
    # =======================================================================

    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._refresh_rules()
        self._refresh_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._refresh_timer.stop()
        super().hideEvent(event)

    # =======================================================================
    # Rule loading (background thread → Qt signal)
    # =======================================================================

    def _refresh_rules(self) -> None:
        self._status_label.setText("Refreshing...")
        self._status_label.setStyleSheet(f"color: {ACCENT_ORANGE};")
        thread = threading.Thread(
            target=self._load_rules,
            daemon=True,
            name="QtFirewallRulesLoader",
        )
        thread.start()

    def _load_rules(self) -> None:
        rules: List[Dict] = []
        policy_status = "Unknown"
        mode = "Unknown"

        try:
            if self._firewall_manager:
                allowed_ips = getattr(self._firewall_manager, "allowed_ips", [])
                rule_prefix = getattr(
                    self._firewall_manager, "rule_prefix", "FirewallController"
                )
                for ip in allowed_ips:
                    rules.append({
                        "ip": ip,
                        "direction": "Outbound",
                        "action": "Allow",
                        "protocol": "Any",
                        "rule_name": f"{rule_prefix}_Allow_{ip.replace('.', '_')}",
                    })

                pm = getattr(self._firewall_manager, "policy_manager", None)
                if pm is not None:
                    policy_status = (
                        "Default Deny (Active)"
                        if getattr(pm, "default_deny_enabled", False)
                        else "Default Allow"
                    )

                if getattr(self._firewall_manager, "whitelist_mode_active", False):
                    mode = "Whitelist Only"
                else:
                    mode = "Whitelist Only (idle)"
            else:
                # No manager wired yet — fall back to netsh.
                rules = self._get_rules_from_netsh()
                policy_status = self._get_policy_from_netsh()
        except Exception as e:
            logger.error(f"Firewall load failed: {e}")

        self._load_signals.finished.emit(rules, policy_status, mode)

    def _on_load_finished(
        self, rules: List[Dict], policy_status: str, mode: str
    ) -> None:
        # Policy
        if "Deny" in policy_status or "Block" in policy_status:
            self._policy_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {ACCENT_GREEN};"
            )
        else:
            self._policy_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {ACCENT_ORANGE};"
            )
        self._policy_label.setText(f"🛡 Policy: {policy_status}")

        # Counts
        self._rule_count_label.setText(f"Rules: {len(rules)}")

        # Mode
        if mode == "Whitelist Only":
            self._mode_label.setStyleSheet(
                f"font-size: 14px; color: {ACCENT_GREEN};"
            )
        else:
            self._mode_label.setStyleSheet(
                f"font-size: 14px; color: {FG_SECONDARY};"
            )
        self._mode_label.setText(f"⚙️ Mode: {mode}")

        self._table.set_data(rules)
        self._status_label.setText(f"Loaded {len(rules)} rules")
        self._status_label.setStyleSheet(f"color: {ACCENT_GREEN};")

    # =======================================================================
    # netsh fallback (used when no FirewallManager is wired)
    # =======================================================================

    @staticmethod
    def _get_rules_from_netsh() -> List[Dict]:
        rules: List[Dict] = []
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule",
                 "name=all", "dir=out", "status=enabled"],
                capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                return rules
            current: Dict[str, str] = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line:
                    if current.get("rule_name", "").startswith("FirewallController"):
                        rules.append(current)
                    current = {}
                elif ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if "rule name" in key:
                        current["rule_name"] = value
                    elif "direction" in key:
                        current["direction"] = value
                    elif "action" in key:
                        current["action"] = value
                    elif "protocol" in key:
                        current["protocol"] = value
                    elif "remoteip" in key:
                        current["ip"] = value
            if current.get("rule_name", "").startswith("FirewallController"):
                rules.append(current)
        except Exception as e:
            logger.debug(f"netsh fallback failed: {e}")
        return rules

    @staticmethod
    def _get_policy_from_netsh() -> str:
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "currentprofile"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                return "Unknown"
            for line in result.stdout.split("\n"):
                if "Outbound" in line and "Block" in line:
                    return "Default Deny (Active)"
                if "Outbound" in line and "Allow" in line:
                    return "Default Allow"
        except Exception:
            pass
        return "Unknown"
