"""
Agent Policy Model - Per-agent policy overrides (isolate, custom whitelist)
Tách riêng khỏi agent_model để giữ separation of concerns:
  - agent_model = agent tier (agent tự register/heartbeat)
  - agent_policy_model = admin/teacher tier (quản lý policy)
"""

import logging
from typing import Dict, Optional, List
from bson import ObjectId
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam


class AgentPolicyModel:
    """
    Collection: agent_policies
    Document schema:
    {
        "_id": ObjectId,
        "agent_id": "abc-1234",            # FK tới agents.agent_id
        "override_mode": "none",            # "none" | "isolate" | "custom_whitelist"
        "custom_whitelist": [               # Chỉ dùng khi mode="custom_whitelist"
            {"domain": "wikipedia.org", "category": "education"},
        ],
        "applied_by": ObjectId("user_id"),  # Teacher/Admin đã áp dụng
        "applied_by_username": "teacher_a", # Username để hiển thị
        "reason": "Xem YouTube trong giờ",  # Lý do (audit trail)
        "expires_at": datetime | None,      # Tự hết hạn (null = vĩnh viễn)
        "override_version": 1,              # Agent poll để biết có thay đổi
        "created_at": datetime,
        "updated_at": datetime,
    }
    """

    # Các mode hợp lệ
    VALID_MODES = ("none", "isolate", "custom_whitelist")

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.agent_policies
        self._setup_indexes()

    def _setup_indexes(self):
        try:
            # Unique trên agent_id — mỗi agent chỉ 1 policy document
            self.collection.create_index(
                [("agent_id", ASCENDING)], unique=True
            )
            # Để query nhanh theo mode (vd: list tất cả agent đang bị isolate)
            self.collection.create_index([("override_mode", ASCENDING)])
            # TTL index cho expires_at — MongoDB tự xóa document hết hạn
            # Không dùng TTL xóa document mà sẽ check runtime, vì cần giữ audit
            self.collection.create_index([("expires_at", ASCENDING)])
            self.logger.info("AgentPolicy indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating agent_policy indexes: {e}")

    # ── CRUD ──────────────────────────────────────────────────

    def get_policy(self, agent_id: str) -> Optional[Dict]:
        """Lấy policy của 1 agent. Trả None nếu chưa có (= mode none)."""
        policy = self.collection.find_one({"agent_id": agent_id})
        if policy:
            policy["_id"] = str(policy["_id"])
            if policy.get("applied_by"):
                policy["applied_by"] = str(policy["applied_by"])
        return policy

    def get_effective_mode(self, agent_id: str) -> str:
        """
        Trả mode hiệu lực (đã xét expires_at).
        - Nếu chưa có policy → "none"
        - Nếu có nhưng đã hết hạn → tự reset về "none" và trả "none"
        """
        policy = self.collection.find_one(
            {"agent_id": agent_id},
            {"override_mode": 1, "expires_at": 1}
        )
        if not policy:
            return "none"

        # Check hết hạn
        expires = policy.get("expires_at")
        if expires and expires < now_vietnam():
            # Hết hạn → reset về none
            self.collection.update_one(
                {"agent_id": agent_id},
                {"$set": {
                    "override_mode": "none",
                    "custom_whitelist": [],
                    "updated_at": now_vietnam(),
                }}
            )
            return "none"

        return policy.get("override_mode", "none")

    def set_policy(self, agent_id: str, mode: str, applied_by_user: Dict,
                   reason: str = "", custom_whitelist: List[Dict] = None,
                   expires_at=None) -> Dict:
        """
        Tạo hoặc cập nhật policy cho agent.
        Dùng upsert để đảm bảo chỉ 1 document/agent.
        """
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {self.VALID_MODES}")

        now = now_vietnam()
        user_id = applied_by_user.get("_id")
        username = applied_by_user.get("username", "unknown")

        update_data = {
            "override_mode": mode,
            "applied_by": ObjectId(str(user_id)) if user_id else None,
            "applied_by_username": username,
            "reason": reason,
            "expires_at": expires_at,
            "updated_at": now,
        }

        # custom_whitelist chỉ có ý nghĩa khi mode = custom_whitelist
        if mode == "custom_whitelist":
            update_data["custom_whitelist"] = custom_whitelist or []
        elif mode in ("none", "isolate"):
            update_data["custom_whitelist"] = []

        result = self.collection.update_one(
            {"agent_id": agent_id},
            {
                "$set": update_data,
                "$inc": {"override_version": 1},
                "$setOnInsert": {"agent_id": agent_id, "created_at": now},
            },
            upsert=True,
        )

        return self.get_policy(agent_id)

    def reset_policy(self, agent_id: str, applied_by_user: Dict) -> Dict:
        """Shortcut: reset về mode none."""
        return self.set_policy(agent_id, "none", applied_by_user, reason="Reset to default")

    def get_custom_whitelist(self, agent_id: str) -> List[Dict]:
        """Lấy custom whitelist entries của agent (chỉ có ý nghĩa khi mode=custom_whitelist)."""
        policy = self.collection.find_one(
            {"agent_id": agent_id},
            {"custom_whitelist": 1}
        )
        if not policy:
            return []
        return policy.get("custom_whitelist", [])

    # ── Query helpers ─────────────────────────────────────────

    def list_isolated_agents(self) -> List[str]:
        """Danh sách agent_id đang bị isolate."""
        docs = self.collection.find(
            {"override_mode": "isolate"},
            {"agent_id": 1}
        )
        return [d["agent_id"] for d in docs]

    def list_policies_by_agent_ids(self, agent_ids: List[str]) -> Dict[str, Dict]:
        """Batch load policies cho nhiều agents (dùng cho dashboard)."""
        docs = self.collection.find({"agent_id": {"$in": agent_ids}})
        result = {}
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            if doc.get("applied_by"):
                doc["applied_by"] = str(doc["applied_by"])
            result[doc["agent_id"]] = doc
        return result

    def count_by_mode(self) -> Dict[str, int]:
        """Thống kê số agent theo mode (cho dashboard stats)."""
        pipeline = [
            {"$group": {"_id": "$override_mode", "count": {"$sum": 1}}}
        ]
        results = list(self.collection.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in results}
