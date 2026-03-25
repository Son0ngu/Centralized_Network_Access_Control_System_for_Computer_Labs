"""
User Model - Admin & Teacher accounts.
- Brute-force protection (failed_login_attempts + locked_until)
- Only 2 roles: admin, teacher
"""

import logging
import re
from datetime import timedelta
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam

# Lock account after 5 failed password attempts
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15


class UserModel:
    """Model for admin/teacher user operations"""

    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.users
        self._setup_indexes()

    def _setup_indexes(self):
        """Setup indexes for users collection"""
        try:
            self.collection.create_index([("username", ASCENDING)], unique=True)
            self.collection.create_index([("email", ASCENDING)], unique=True, sparse=True)
            self.collection.create_index([("role", ASCENDING), ("is_active", ASCENDING)])
            self.collection.create_index([("created_by", ASCENDING)])
            self.collection.create_index([("created_at", DESCENDING)])
            self.logger.info("User indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating user indexes: {e}")

    # ========================================================================
    # CREATE
    # ========================================================================

    def create(self, user_data: Dict) -> Dict:
        """Create a new user"""
        try:
            current_time = now_vietnam()
            user_data.update({
                "is_active": user_data.get("is_active", True),
                "created_at": current_time,
                "updated_at": current_time,
                "last_login": None,
                "failed_login_attempts": 0,
                "locked_until": None,
            })

            result = self.collection.insert_one(user_data)
            user_data["_id"] = result.inserted_id

            self.logger.info(f"User created: {user_data.get('username')} (role: {user_data.get('role')})")
            return user_data

        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            raise

    # ========================================================================
    # READ
    # ========================================================================

    def find_by_id(self, user_id: str) -> Optional[Dict]:
        """Find user by _id"""
        try:
            return self.collection.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            self.logger.error(f"Error finding user by id {user_id}: {e}")
            return None

    def find_by_username(self, username: str) -> Optional[Dict]:
        """Find user by username (case-insensitive, regex-safe)"""
        try:
            safe_username = re.escape(username.strip())
            return self.collection.find_one(
                {"username": {"$regex": f"^{safe_username}$", "$options": "i"}}
            )
        except Exception as e:
            self.logger.error(f"Error finding user by username {username}: {e}")
            return None

    def find_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email (case-insensitive, regex-safe)"""
        try:
            safe_email = re.escape(email.strip())
            return self.collection.find_one(
                {"email": {"$regex": f"^{safe_email}$", "$options": "i"}}
            )
        except Exception as e:
            self.logger.error(f"Error finding user by email {email}: {e}")
            return None

    def get_all_users(self, query: Dict = None, limit: int = 100, skip: int = 0) -> List[Dict]:
        """Get all users with optional filtering"""
        try:
            if query is None:
                query = {}
            return list(
                self.collection.find(query)
                .sort("created_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
        except Exception as e:
            self.logger.error(f"Error getting users: {e}")
            return []

    def count_users(self, query: Dict = None) -> int:
        """Count users"""
        try:
            if query is None:
                query = {}
            return self.collection.count_documents(query)
        except Exception as e:
            self.logger.error(f"Error counting users: {e}")
            return 0

    # ========================================================================
    # UPDATE
    # ========================================================================

    def update(self, user_id: str, update_data: Dict) -> bool:
        """Update user by _id"""
        try:
            update_data["updated_at"] = now_vietnam()
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error updating user {user_id}: {e}")
            return False

    def update_last_login(self, user_id: str) -> bool:
        """Update last login timestamp"""
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_login": now_vietnam(), "updated_at": now_vietnam()}}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error updating last login for {user_id}: {e}")
            return False

    # ========================================================================
    # BRUTE-FORCE PROTECTION
    # ========================================================================

    def increment_failed_attempts(self, user_id: str) -> int:
        """Increment failed login attempts, lock if >= MAX"""
        try:
            user = self.find_by_id(user_id)
            if not user:
                return 0

            new_count = user.get("failed_login_attempts", 0) + 1
            update = {"failed_login_attempts": new_count, "updated_at": now_vietnam()}

            # Lock account if max attempts reached
            if new_count >= MAX_FAILED_ATTEMPTS:
                update["locked_until"] = now_vietnam() + timedelta(minutes=LOCK_DURATION_MINUTES)
                self.logger.warning(
                    f"Account {user.get('username')} locked for {LOCK_DURATION_MINUTES} min "
                    f"(failed attempts: {new_count})"
                )

            self.collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
            return new_count

        except Exception as e:
            self.logger.error(f"Error incrementing failed attempts: {e}")
            return 0

    def reset_failed_attempts(self, user_id: str) -> bool:
        """Reset failed login attempts after successful login"""
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "failed_login_attempts": 0,
                    "locked_until": None,
                    "updated_at": now_vietnam(),
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error resetting failed attempts: {e}")
            return False

    def is_locked(self, user: Dict) -> bool:
        """Check if user account is currently locked"""
        locked_until = user.get("locked_until")
        if locked_until is None:
            return False
        return now_vietnam() < locked_until

    def lock_account(self, user_id: str, duration_minutes: int = LOCK_DURATION_MINUTES) -> bool:
        """Manually lock an account"""
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "locked_until": now_vietnam() + timedelta(minutes=duration_minutes),
                    "updated_at": now_vietnam(),
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error locking account {user_id}: {e}")
            return False

    # ========================================================================
    # DELETE
    # ========================================================================

    def delete(self, user_id: str) -> bool:
        """Delete a user"""
        try:
            result = self.collection.delete_one({"_id": ObjectId(user_id)})
            self.logger.info(f"User {user_id} deleted: {result.deleted_count}")
            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Error deleting user {user_id}: {e}")
            return False

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_user_statistics(self) -> Dict:
        """Get user statistics by role"""
        try:
            pipeline = [
                {"$group": {"_id": "$role", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            results = list(self.collection.aggregate(pipeline))

            stats = {"total": 0, "by_role": {}, "active": 0, "inactive": 0}
            for r in results:
                role = r["_id"] or "unknown"
                stats["by_role"][role] = r["count"]
                stats["total"] += r["count"]

            stats["active"] = self.count_users({"is_active": True})
            stats["inactive"] = self.count_users({"is_active": False})
            return stats

        except Exception as e:
            self.logger.error(f"Error getting user statistics: {e}")
            return {"total": 0, "by_role": {}, "active": 0, "inactive": 0}
