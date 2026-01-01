"""
Tenant Model - Multi-tenancy support
-------------------------------------
Manages organizations/tenants in the system.
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from time_utils import now_vietnam

logger = logging.getLogger(__name__)


class TenantModel:
    """Model for tenant data operations."""
    
    def __init__(self, db: Database):
        self.collection: Collection = db.tenants
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create database indexes."""
        self.collection.create_index([("slug", ASCENDING)], unique=True)
        self.collection.create_index([("created_at", ASCENDING)])
        self.collection.create_index([("status", ASCENDING)])
    
    def create_tenant(self, tenant_data: Dict) -> Dict:
        """
        Create new tenant.
        
        Args:
            tenant_data: {
                "name": "ACME Corp",
                "slug": "acme-corp",
                "email": "admin@acme.com",
                "phone": "+84xxxxxxxxx",
                "plan": "enterprise",  # free, basic, pro, enterprise
                "max_admins": 10,
                "max_agents": 100,
                "features": ["2fa", "audit_logs", "api_access"],
                "settings": {}
            }
        
        Returns:
            Created tenant document
        """
        now = now_vietnam()
        
        # Auto-generate slug from name if not provided
        import re
        slug = tenant_data.get("slug")
        if not slug:
            # Convert name to slug: lowercase, replace spaces with hyphens, remove special chars
            slug = tenant_data["name"].lower().strip()
            slug = re.sub(r'[^a-z0-9\s-]', '', slug)
            slug = re.sub(r'[\s_]+', '-', slug)
            slug = re.sub(r'-+', '-', slug).strip('-')
            # Add timestamp to ensure uniqueness
            import time
            slug = f"{slug}-{int(time.time()) % 100000}"
        
        tenant = {
            "name": tenant_data["name"],
            "slug": slug,
            "email": tenant_data.get("email"),
            "phone": tenant_data.get("phone"),
            "plan": tenant_data.get("plan", "free"),
            "status": "active",  # active, suspended, trial
            "max_admins": tenant_data.get("max_admins", 5),
            "max_agents": tenant_data.get("max_agents", 10),
            "features": tenant_data.get("features", []),
            "settings": tenant_data.get("settings", {}),
            "created_at": now,
            "updated_at": now,
            "trial_ends_at": None,
            "suspended_at": None,
            "deleted_at": None,
        }
        
        result = self.collection.insert_one(tenant)
        tenant["_id"] = result.inserted_id
        
        logger.info(f"Created tenant: {tenant['name']} ({tenant['slug']})")
        return tenant
    
    def get_by_id(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant by ID."""
        try:
            return self.collection.find_one({"_id": ObjectId(tenant_id)})
        except:
            return None
    
    def get_by_slug(self, slug: str) -> Optional[Dict]:
        """Get tenant by slug."""
        return self.collection.find_one({"slug": slug})
    
    def list_tenants(self, filters: Dict = None, skip: int = 0, limit: int = 50) -> List[Dict]:
        """List all tenants."""
        query = filters or {}
        
        # Exclude deleted tenants by default
        if "deleted_at" not in query:
            query["deleted_at"] = None
        
        cursor = self.collection.find(query).skip(skip).limit(limit)
        return list(cursor)
    
    def update_tenant(self, tenant_id: str, update_data: Dict) -> bool:
        """Update tenant information."""
        update_data["updated_at"] = now_vietnam()
        
        result = self.collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated tenant: {tenant_id}")
            return True
        return False
    
    def suspend_tenant(self, tenant_id: str, reason: str) -> bool:
        """Suspend tenant."""
        result = self.collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {"$set": {
                "status": "suspended",
                "suspended_at": now_vietnam(),
                "suspension_reason": reason
            }}
        )
        
        if result.modified_count > 0:
            logger.warning(f"Suspended tenant: {tenant_id} - Reason: {reason}")
            return True
        return False
    
    def activate_tenant(self, tenant_id: str) -> bool:
        """Activate suspended tenant."""
        result = self.collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {"$set": {
                "status": "active",
                "suspended_at": None,
                "suspension_reason": None
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Activated tenant: {tenant_id}")
            return True
        return False
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Soft delete tenant."""
        result = self.collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {"$set": {
                "status": "deleted",
                "deleted_at": now_vietnam()
            }}
        )
        
        if result.modified_count > 0:
            logger.warning(f"Deleted tenant: {tenant_id}")
            return True
        return False
    
    def get_tenant_stats(self, tenant_id: str) -> Dict:
        """Get tenant statistics."""
        from models.admin_model import AdminModel
        from models.agent_model import AgentModel
        
        admin_count = AdminModel(self.collection.database).count_by_tenant(tenant_id)
        agent_count = AgentModel(self.collection.database).count_by_tenant(tenant_id)
        
        tenant = self.get_by_id(tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "admin_count": admin_count,
            "agent_count": agent_count,
            "max_admins": tenant.get("max_admins", 0),
            "max_agents": tenant.get("max_agents", 0),
            "plan": tenant.get("plan"),
            "status": tenant.get("status"),
        }
    
    def check_limits(self, tenant_id: str, resource_type: str) -> bool:
        """
        Check if tenant can add more resources.
        
        Args:
            tenant_id: Tenant ID
            resource_type: 'admin' or 'agent'
        
        Returns:
            True if under limit, False if at/over limit
        """
        tenant = self.get_by_id(tenant_id)
        if not tenant:
            return False
        
        stats = self.get_tenant_stats(tenant_id)
        
        if resource_type == "admin":
            return stats["admin_count"] < stats["max_admins"]
        elif resource_type == "agent":
            return stats["agent_count"] < stats["max_agents"]
        
        return False
