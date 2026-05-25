"""
Agent Policy Model - Per-agent policy overrides (isolate, custom whitelist)
Separated from agent_model to maintain separation of concerns:
  - agent_model = agent tier (agent self-registers/heartbeats)
  - agent_policy_model = admin/teacher tier (manages policy)
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
        "agent_id": "abc-1234",            # FK to agents.agent_id
        "override_mode": "none",            # "none" | "isolate" | "custom_whitelist"
        "custom_whitelist": [               # Only used when mode="custom_whitelist"
            {"domain": "wikipedia.org", "category": "education"},
        ],
        "applied_by": ObjectId("user_id"),  # Applied by Teacher/Admin
        "applied_by_username": "teacher_a", # Username for display
        "reason": "Watched YouTube in class",# Reason (audit trail)
        "expires_at": datetime | None,      # Auto-expire (null = permanent)
        "override_version": 1,              # Agent polls to detect changes
        "created_at": datetime,
        "updated_at": datetime,
    }
    """

    # Valid modes
    VALID_MODES = ("none", "isolate", "custom_whitelist")

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.agent_policies
        self._setup_indexes()

    def _setup_indexes(self):
        try:
            # Unique on agent_id - each agent has only 1 policy document
            self.collection.create_index(
                [("agent_id", ASCENDING)], unique=True
            )
            # For fast query by mode (e.g.: list all isolated agents)
            self.collection.create_index([("override_mode", ASCENDING)])
            # TTL index for expires_at - MongoDB auto-deletes expired documents
            # Not using TTL to delete documents; will check at runtime to preserve audit
            self.collection.create_index([("expires_at", ASCENDING)])
            self.logger.info("AgentPolicy indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating agent_policy indexes: {e}")

    # ── CRUD ──────────────────────────────────────────────────

    def get_policy(self, agent_id: str) -> Optional[Dict]:
        """Get policy for an agent. Returns None if not set (= mode none)."""
        policy = self.collection.find_one({"agent_id": agent_id})
        if policy:
            policy["_id"] = str(policy["_id"])
            if policy.get("applied_by"):
                policy["applied_by"] = str(policy["applied_by"])
        return policy

    def get_effective_mode(self, agent_id: str) -> str:
        """
        Return effective mode (considering expires_at).
        - If no policy exists → "none"
        - If exists but expired → auto-reset to "none" and return "none"
        """
        policy = self.collection.find_one(
            {"agent_id": agent_id},
            {"override_mode": 1, "expires_at": 1}
        )
        if not policy:
            return "none"

        # Check expiry
        expires = policy.get("expires_at")
        if expires and expires < now_vietnam():
            # Expired → reset to none
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
        Create or update policy for an agent.
        Uses upsert to ensure only 1 document per agent.
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

        # custom_whitelist only meaningful when mode = custom_whitelist
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
        """Shortcut: reset to mode none."""
        return self.set_policy(agent_id, "none", applied_by_user, reason="Reset to default")

    def get_custom_whitelist(self, agent_id: str) -> List[Dict]:
        """Get custom whitelist entries for agent (only meaningful when mode=custom_whitelist)."""
        policy = self.collection.find_one(
            {"agent_id": agent_id},
            {"custom_whitelist": 1}
        )
        if not policy:
            return []
        return policy.get("custom_whitelist", [])

    # ── Query helpers ─────────────────────────────────────────

    def list_isolated_agents(self) -> List[str]:
        """List of agent_ids currently isolated."""
        docs = self.collection.find(
            {"override_mode": "isolate"},
            {"agent_id": 1}
        )
        return [d["agent_id"] for d in docs]

    def list_policies_by_agent_ids(self, agent_ids: List[str]) -> Dict[str, Dict]:
        """Batch load policies for multiple agents (used for dashboard)."""
        docs = self.collection.find({"agent_id": {"$in": agent_ids}})
        result = {}
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            if doc.get("applied_by"):
                doc["applied_by"] = str(doc["applied_by"])
            result[doc["agent_id"]] = doc
        return result

    def count_by_mode(self) -> Dict[str, int]:
        """Count agents by mode (for dashboard stats)."""
        pipeline = [
            {"$group": {"_id": "$override_mode", "count": {"$sum": 1}}}
        ]
        results = list(self.collection.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in results}
