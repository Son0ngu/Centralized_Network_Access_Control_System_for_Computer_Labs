"""UI-safe firewall application operations.

The Qt settings view should not know how to restore policies or delete SAINT
rules. It delegates here, and this service delegates to FirewallManager /
RulesManager so backend selection stays in the firewall package.
"""

import logging
from typing import Optional

from .manager import DEFAULT_SNAPSHOT_FILENAME, FirewallManager
from .rules import RulesManager

logger = logging.getLogger("firewall.application_service")


class FirewallApplicationService:
    """Thin facade for GUI/manual firewall operations."""

    def __init__(
        self,
        *,
        rule_prefix: str = "FirewallController",
        manager: Optional[FirewallManager] = None,
    ):
        self.rule_prefix = rule_prefix
        self.manager = manager

    def restore_firewall_snapshot(
        self,
        path: str = DEFAULT_SNAPSHOT_FILENAME,
    ) -> bool:
        manager = self.manager or FirewallManager(self.rule_prefix)
        return manager.restore_snapshot(path)

    def clear_saint_rules(self) -> bool:
        if self.manager:
            return self.manager.clear_all_rules()
        return RulesManager(self.rule_prefix).clear_all_rules()


__all__ = ["FirewallApplicationService"]
