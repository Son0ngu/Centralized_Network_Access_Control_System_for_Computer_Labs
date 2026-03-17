"""
Agent Policy Service - Business logic for per-agent policy overrides.
Handles isolate mode, custom whitelist, and policy merging into agent-sync.
"""

import logging
from typing import Dict, List, Optional
from datetime import timedelta

from models.agent_policy_model import AgentPolicyModel
from models.agent_model import AgentModel
from time_utils import now_vietnam


class AgentPolicyService:

    def __init__(self, policy_model: AgentPolicyModel, agent_model: AgentModel,
                 socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.policy_model = policy_model
        self.agent_model = agent_model
        self.socketio = socketio

    # ── Policy CRUD ───────────────────────────────────────────

    def get_policy(self, agent_id: str) -> Dict:
        """Get current effective policy for an agent."""
        policy = self.policy_model.get_policy(agent_id)
        if not policy:
            return {
                "agent_id": agent_id,
                "override_mode": "none",
                "custom_whitelist": [],
                "reason": "",
                "expires_at": None,
                "override_version": 0,
            }

        # Check expiry
        expires = policy.get("expires_at")
        if expires and expires < now_vietnam():
            policy["override_mode"] = "none"
            policy["custom_whitelist"] = []

        return policy

    def set_policy(self, agent_id: str, mode: str, applied_by_user: Dict,
                   reason: str = "", custom_whitelist: List[Dict] = None,
                   duration_minutes: int = None) -> Dict:
        """
        Set policy cho agent.

        Args:
            agent_id: target agent
            mode: "none" | "isolate" | "custom_whitelist"
            applied_by_user: g.current_user dict
            reason: lý do áp dụng
            custom_whitelist: danh sách domain (chỉ khi mode=custom_whitelist)
            duration_minutes: tự hết hạn sau N phút (None = vĩnh viễn)
        """
        # Validate agent exists
        agent = self.agent_model.find_by_agent_id(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Calculate expires_at
        expires_at = None
        if duration_minutes and duration_minutes > 0:
            expires_at = now_vietnam() + timedelta(minutes=duration_minutes)

        policy = self.policy_model.set_policy(
            agent_id=agent_id,
            mode=mode,
            applied_by_user=applied_by_user,
            reason=reason,
            custom_whitelist=custom_whitelist,
            expires_at=expires_at,
        )

        # Broadcast qua SocketIO để frontend cập nhật real-time
        if self.socketio:
            self.socketio.emit("agent_policy_changed", {
                "agent_id": agent_id,
                "override_mode": mode,
                "reason": reason,
                "applied_by": applied_by_user.get("username", "unknown"),
                "expires_at": expires_at.isoformat() if expires_at else None,
            })

        self.logger.info(
            f"Policy set: agent={agent_id} mode={mode} "
            f"by={applied_by_user.get('username')} reason='{reason}' "
            f"expires={expires_at}"
        )

        return policy

    def isolate_agent(self, agent_id: str, applied_by_user: Dict,
                      reason: str = "Isolated by teacher",
                      duration_minutes: int = None) -> Dict:
        """Shortcut: cắt mạng hoàn toàn 1 agent."""
        return self.set_policy(
            agent_id=agent_id,
            mode="isolate",
            applied_by_user=applied_by_user,
            reason=reason,
            duration_minutes=duration_minutes,
        )

    def reset_agent(self, agent_id: str, applied_by_user: Dict) -> Dict:
        """Shortcut: bỏ isolate/custom, trả về group whitelist bình thường."""
        return self.set_policy(
            agent_id=agent_id,
            mode="none",
            applied_by_user=applied_by_user,
            reason="Reset to group default",
        )

    # ── Merge policy vào sync response ────────────────────────

    # DNS servers cần thiết để agent resolve domain của SAINT server.
    # Nếu chặn DNS → agent không resolve được server domain → Deadlock.
    ESSENTIAL_DNS_IPS = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]

    def _build_system_entries(self, server_host: str = None, source: str = "policy_system") -> List[Dict]:
        """
        Build danh sách domain/IP hệ thống LUÔN phải có trong mọi policy override.
        Bao gồm:
          - Server host (để agent duy trì kết nối API)
          - DNS servers (để resolve server domain nếu server dùng domain thay vì IP)
        """
        entries = []
        if server_host:
            entries.append({
                "domain": server_host,
                "category": "system",
                "is_active": True,
                "source": source,
            })
        # Luôn cho phép DNS — tránh deadlock khi server dùng domain
        for dns_ip in self.ESSENTIAL_DNS_IPS:
            entries.append({
                "domain": dns_ip,
                "category": "system_dns",
                "is_active": True,
                "source": source,
            })
        return entries

    def apply_policy_to_sync(self, agent_id: str,
                             group_domains: List[Dict],
                             server_host: str = None) -> Dict:
        """
        Core function: Merge agent policy vào whitelist sync response.
        Gọi từ whitelist_service.get_agent_sync_data().

        Returns:
            {
                "domains": [...],       # Whitelist sau khi merge
                "policy_mode": "none",  # Mode hiện tại
                "policy_active": False, # Có override không
            }
        """
        effective_mode = self.policy_model.get_effective_mode(agent_id)

        if effective_mode == "none":
            # Không override → trả nguyên group whitelist
            return {
                "domains": group_domains,
                "policy_mode": "none",
                "policy_active": False,
            }

        if effective_mode == "isolate":
            # Chặn toàn bộ — chỉ giữ server IP + DNS để agent không mất kết nối
            minimal_domains = self._build_system_entries(server_host, "policy_isolate")
            return {
                "domains": minimal_domains,
                "policy_mode": "isolate",
                "policy_active": True,
            }

        if effective_mode == "custom_whitelist":
            # Thay thế group whitelist bằng custom list
            custom_entries = self.policy_model.get_custom_whitelist(agent_id)
            # Server host + DNS luôn có trong list
            domains = self._build_system_entries(server_host, "policy_custom")
            for entry in custom_entries:
                domains.append({
                    "domain": entry.get("domain"),
                    "category": entry.get("category", "custom"),
                    "is_active": True,
                    "source": "policy_custom",
                })
            return {
                "domains": domains,
                "policy_mode": "custom_whitelist",
                "policy_active": True,
            }

        # Fallback
        return {
            "domains": group_domains,
            "policy_mode": "none",
            "policy_active": False,
        }

    # ── Dashboard helpers ─────────────────────────────────────

    def get_policies_for_agents(self, agent_ids: List[str]) -> Dict[str, Dict]:
        """Batch load policies (cho list_agents dashboard)."""
        return self.policy_model.list_policies_by_agent_ids(agent_ids)

    def get_stats(self) -> Dict:
        """Thống kê policy (cho dashboard)."""
        return self.policy_model.count_by_mode()
