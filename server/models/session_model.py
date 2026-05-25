"""
Session Model - Admin/Teacher login sessions.
- Tracks active sessions with JTI for revocation
- TTL index auto-deletes expired sessions
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam


class SessionModel:
    """Model for admin session operations (collection: admin_sessions)"""

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.admin_sessions
        self._setup_indexes()

    def _setup_indexes(self):
        """Setup indexes for admin_sessions collection"""
        try:
            self.collection.create_index([("user_id", ASCENDING)])
            self.collection.create_index(
                [("access_token_jti", ASCENDING)], unique=True, sparse=True
            )
            self.collection.create_index(
                [("refresh_token_jti", ASCENDING)], unique=True, sparse=True
            )
            # TTL index - auto-delete expired sessions
            self.collection.create_index(
                "expires_at", expireAfterSeconds=0, name="session_ttl"
            )
            self.collection.create_index([("is_revoked", ASCENDING)])
            self.logger.info("Session indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating session indexes: {e}")

    # ========================================================================
    # CRUD
    # ========================================================================

    def create(self, session_data: Dict) -> Dict:
        """Create a new session"""
        try:
            session_data.update({
                "created_at": now_vietnam(),
                "is_revoked": False,
            })
            result = self.collection.insert_one(session_data)
            session_data["_id"] = result.inserted_id
            self.logger.debug(f"Session created for user {session_data.get('user_id')}")
            return session_data
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            raise

    def find_by_access_jti(self, jti: str) -> Optional[Dict]:
        """Find session by access token JTI"""
        try:
            return self.collection.find_one({"access_token_jti": jti})
        except Exception as e:
            self.logger.error(f"Error finding session by access jti: {e}")
            return None

    def find_by_refresh_jti(self, jti: str) -> Optional[Dict]:
        """Find session by refresh token JTI"""
        try:
            return self.collection.find_one({"refresh_token_jti": jti})
        except Exception as e:
            self.logger.error(f"Error finding session by refresh jti: {e}")
            return None

    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """Get all active sessions for a user"""
        try:
            return list(self.collection.find({
                "user_id": ObjectId(user_id),
                "is_revoked": False,
            }).sort("created_at", DESCENDING))
        except Exception as e:
            self.logger.error(f"Error getting user sessions: {e}")
            return []

    # ========================================================================
    # REVOKE
    # ========================================================================

    def revoke(self, jti: str) -> bool:
        """Revoke a session by JTI (access or refresh)"""
        try:
            result = self.collection.update_one(
                {"$or": [
                    {"access_token_jti": jti},
                    {"refresh_token_jti": jti},
                ]},
                {"$set": {"is_revoked": True, "revoked_at": now_vietnam()}}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error revoking session: {e}")
            return False

    def revoke_all_user(self, user_id: str) -> int:
        """Revoke all sessions for a user"""
        try:
            result = self.collection.update_many(
                {"user_id": ObjectId(user_id), "is_revoked": False},
                {"$set": {"is_revoked": True, "revoked_at": now_vietnam()}}
            )
            self.logger.info(f"Revoked {result.modified_count} sessions for user {user_id}")
            return result.modified_count
        except Exception as e:
            self.logger.error(f"Error revoking all sessions for {user_id}: {e}")
            return 0

    def is_session_revoked(self, jti: str) -> bool:
        """Check if a session is revoked by JTI"""
        try:
            session = self.collection.find_one(
                {"$or": [
                    {"access_token_jti": jti},
                    {"refresh_token_jti": jti},
                ]}
            )
            if not session:
                return False  # Session not found = not tracked = allow
            return session.get("is_revoked", False)
        except Exception as e:
            self.logger.error(f"Error checking session revocation: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Manually cleanup expired sessions (TTL index handles this automatically)"""
        try:
            result = self.collection.delete_many({
                "expires_at": {"$lt": now_vietnam()}
            })
            return result.deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up sessions: {e}")
            return 0
