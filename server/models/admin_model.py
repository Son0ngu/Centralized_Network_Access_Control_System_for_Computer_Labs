"""
Admin Model - Admin user management with multi-tenancy
-------------------------------------------------------
Manages administrative users within tenants.
"""

import logging
import bcrypt
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam
from utils.password_validator import validate_password

logger = logging.getLogger(__name__)


class AdminModel:
    """Model for admin user operations."""
    
    def __init__(self, db: Database):
        self.collection: Collection = db.admins
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create database indexes."""
        self.collection.create_index([("email", ASCENDING)], unique=True)
        self.collection.create_index([("tenant_id", ASCENDING)])
        self.collection.create_index([("created_at", DESCENDING)])
        self.collection.create_index([("status", ASCENDING)])
        self.collection.create_index([("role", ASCENDING)])
    
    def create_admin(self, admin_data: Dict) -> Dict:
        """
        Create new admin user.
        
        Args:
            admin_data: {
                "tenant_id": "tenant_id",
                "email": "admin@example.com",
                "password": "SecurePass123!",
                "full_name": "John Doe",
                "phone": "+84xxxxxxxxx"
            }
        
        Returns:
            Created admin document (password excluded)
        
        Note: Each admin belongs to exactly one tenant.
              All resources (whitelist, agents, API keys) are isolated per tenant.
        """
        # Validate password
        is_valid, errors = validate_password(
            admin_data["password"],
            admin_data["email"].split('@')[0]
        )
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(errors)}")
        
        # Hash password
        password_hash = bcrypt.hashpw(
            admin_data["password"].encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')
        
        now = now_vietnam()
        
        admin = {
            "tenant_id": ObjectId(admin_data["tenant_id"]),
            "email": admin_data["email"].lower().strip(),
            "password_hash": password_hash,
            "full_name": admin_data.get("full_name", ""),
            "phone": admin_data.get("phone"),
            "role": "admin",  # Always 'admin' - system admin will be separate
            "status": "active",  # active, suspended
            "email_verified": False,
            "2fa_enabled": False,
            "2fa_method": None,  # email, totp
            "2fa_secret": None,
            "backup_codes": [],
            "password_history": [password_hash],
            "password_changed_at": now,
            "password_expires_at": None,
            "failed_login_attempts": 0,
            "locked_until": None,
            "last_login_at": None,
            "last_login_ip": None,
            "created_at": now,
            "updated_at": now,
            "created_by": admin_data.get("created_by"),
        }
        
        result = self.collection.insert_one(admin)
        admin["_id"] = result.inserted_id
        
        # Remove password from response
        admin.pop("password_hash", None)
        admin.pop("password_history", None)
        
        logger.info(f"Created admin: {admin['email']} in tenant {admin['tenant_id']}")
        return admin
    
    def get_by_id(self, admin_id: str) -> Optional[Dict]:
        """Get admin by ID."""
        try:
            admin = self.collection.find_one({"_id": ObjectId(admin_id)})
            if admin:
                admin.pop("password_hash", None)
                admin.pop("password_history", None)
            return admin
        except:
            return None
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """Get admin by email (includes password hash for authentication)."""
        return self.collection.find_one({"email": email.lower().strip()})
    
    def verify_password(self, email: str, password: str) -> Optional[Dict]:
        """
        Verify admin credentials.
        
        Returns:
            Admin document if valid, None if invalid
        """
        admin = self.get_by_email(email)
        if not admin:
            return None
        
        # Check if account is locked
        if admin.get("locked_until"):
            if now_vietnam() < admin["locked_until"]:
                logger.warning(f"Login attempt for locked account: {email}")
                return None
        
        # Verify password
        try:
            if bcrypt.checkpw(password.encode('utf-8'), admin["password_hash"].encode('utf-8')):
                # Reset failed attempts
                self.collection.update_one(
                    {"_id": admin["_id"]},
                    {"$set": {"failed_login_attempts": 0, "locked_until": None}}
                )
                
                # Remove sensitive data
                admin.pop("password_hash", None)
                admin.pop("password_history", None)
                return admin
            else:
                # Increment failed attempts
                self._handle_failed_login(admin["_id"])
                return None
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return None
    
    def _handle_failed_login(self, admin_id: ObjectId):
        """Handle failed login attempt."""
        from config.security_config import ACCOUNT_CONFIG
        
        admin = self.collection.find_one({"_id": admin_id})
        failed_attempts = admin.get("failed_login_attempts", 0) + 1
        
        update_data = {"failed_login_attempts": failed_attempts}
        
        # Lock account if max attempts exceeded
        if failed_attempts >= ACCOUNT_CONFIG["max_login_attempts"]:
            from datetime import timedelta
            lockout_duration = ACCOUNT_CONFIG["lockout_duration"]
            locked_until = now_vietnam() + timedelta(seconds=lockout_duration)
            update_data["locked_until"] = locked_until
            logger.warning(f"Account locked: {admin['email']} until {locked_until}")
        
        self.collection.update_one({"_id": admin_id}, {"$set": update_data})
    
    def update_last_login(self, admin_id: str, ip_address: str):
        """Update last login timestamp and IP."""
        self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "last_login_at": now_vietnam(),
                "last_login_ip": ip_address
            }}
        )
    
    def change_password(self, admin_id: str, old_password: str, new_password: str) -> bool:
        """Change admin password."""
        admin = self.collection.find_one({"_id": ObjectId(admin_id)})
        if not admin:
            return False
        
        # Verify old password
        if not bcrypt.checkpw(old_password.encode('utf-8'), admin["password_hash"].encode('utf-8')):
            return False
        
        # Validate new password
        is_valid, errors = validate_password(new_password, admin["email"].split('@')[0])
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(errors)}")
        
        # Check password history
        password_history = admin.get("password_history", [])
        for old_hash in password_history[-5:]:  # Check last 5 passwords
            if bcrypt.checkpw(new_password.encode('utf-8'), old_hash.encode('utf-8')):
                raise ValueError("Password was used recently. Please choose a different password.")
        
        # Hash new password
        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        
        # Update password
        password_history.append(new_hash)
        
        self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "password_hash": new_hash,
                "password_history": password_history[-5:],  # Keep only last 5
                "password_changed_at": now_vietnam()
            }}
        )
        
        logger.info(f"Password changed for admin: {admin['email']}")
        return True
    
    def enable_2fa(self, admin_id: str, method: str, secret: str = None) -> bool:
        """Enable 2FA for admin."""
        self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "2fa_enabled": True,
                "2fa_method": method,
                "2fa_secret": secret,
                "updated_at": now_vietnam()
            }}
        )
        
        logger.info(f"2FA enabled for admin {admin_id} with method: {method}")
        return True
    
    def disable_2fa(self, admin_id: str) -> bool:
        """Disable 2FA for admin."""
        self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "2fa_enabled": False,
                "2fa_method": None,
                "2fa_secret": None,
                "updated_at": now_vietnam()
            }}
        )
        
        logger.info(f"2FA disabled for admin {admin_id}")
        return True
    
    def list_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 50) -> List[Dict]:
        """List all admins in tenant."""
        cursor = self.collection.find(
            {"tenant_id": ObjectId(tenant_id)}
        ).skip(skip).limit(limit)
        
        admins = []
        for admin in cursor:
            admin.pop("password_hash", None)
            admin.pop("password_history", None)
            admins.append(admin)
        
        return admins
    
    def count_by_tenant(self, tenant_id: str) -> int:
        """Count admins in tenant."""
        return self.collection.count_documents({"tenant_id": ObjectId(tenant_id)})
    
    def update_admin(self, admin_id: str, update_data: Dict) -> bool:
        """Update admin information."""
        # Don't allow password change through this method
        update_data.pop("password", None)
        update_data.pop("password_hash", None)
        
        update_data["updated_at"] = now_vietnam()
        
        result = self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated admin: {admin_id}")
            return True
        return False
    
    def suspend_admin(self, admin_id: str, reason: str) -> bool:
        """Suspend admin account."""
        result = self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "status": "suspended",
                "suspended_at": now_vietnam(),
                "suspension_reason": reason
            }}
        )
        
        if result.modified_count > 0:
            logger.warning(f"Suspended admin: {admin_id} - Reason: {reason}")
            return True
        return False
    
    def activate_admin(self, admin_id: str) -> bool:
        """Activate suspended admin."""
        result = self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {
                "status": "active",
                "suspended_at": None,
                "suspension_reason": None
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Activated admin: {admin_id}")
            return True
        return False
