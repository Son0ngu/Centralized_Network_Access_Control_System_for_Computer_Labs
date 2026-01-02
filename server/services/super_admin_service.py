"""
Super Admin Service - Business logic for platform-wide administration
-----------------------------------------------------------------------
Handles:
- Tenant management (CRUD, suspend/activate)
- Platform-wide statistics
- Impersonation sessions
- System broadcasts
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from models.tenant_model import TenantModel
from models.admin_model import AdminModel, ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN
from models.agent_model import AgentModel
from models.log_model import LogModel
from models.broadcast_model import BroadcastModel
from models.impersonation_log_model import ImpersonationLogModel
from services.jwt_service import JWTService
from time_utils import now_vietnam, now_iso

logger = logging.getLogger(__name__)


class SuperAdminService:
    """Service for Super Admin operations."""
    
    def __init__(
        self,
        tenant_model: TenantModel,
        admin_model: AdminModel,
        agent_model: AgentModel,
        log_model: LogModel,
        broadcast_model: BroadcastModel,
        impersonation_model: ImpersonationLogModel,
        jwt_service: JWTService = None,
        socketio=None
    ):
        self.tenant_model = tenant_model
        self.admin_model = admin_model
        self.agent_model = agent_model
        self.log_model = log_model
        self.broadcast_model = broadcast_model
        self.impersonation_model = impersonation_model
        self.jwt_service = jwt_service
        self.socketio = socketio
        self.logger = logging.getLogger(self.__class__.__name__)
    
    # ========================================================================
    # Dashboard Statistics
    # ========================================================================
    
    def get_dashboard_stats(self) -> Dict:
        """
        Get platform-wide dashboard statistics.
        
        Returns:
            Dict with counts and health metrics for all tenants
        """
        try:
            # Tenant statistics
            all_tenants = self.tenant_model.list_tenants(limit=1000)
            active_tenants = [t for t in all_tenants if t.get("status") == "active"]
            suspended_tenants = [t for t in all_tenants if t.get("status") == "suspended"]
            
            # Admin statistics
            total_admins = self.admin_model.collection.count_documents({
                "role": ROLE_TENANT_ADMIN
            })
            active_admins = self.admin_model.collection.count_documents({
                "role": ROLE_TENANT_ADMIN,
                "status": "active"
            })
            
            # Agent statistics (across all tenants)
            total_agents = self.agent_model.collection.count_documents({})
            
            # Calculate online agents (heartbeat within last 5 minutes)
            five_min_ago = now_vietnam() - timedelta(minutes=5)
            online_agents = self.agent_model.collection.count_documents({
                "last_heartbeat": {"$gte": five_min_ago}
            })
            
            # Log statistics for today
            today_start = now_vietnam().replace(hour=0, minute=0, second=0, microsecond=0)
            total_logs_today = self.log_model.count_logs({
                "timestamp": {"$gte": today_start}
            })
            blocked_logs_today = self.log_model.count_logs({
                "timestamp": {"$gte": today_start},
                "action": "blocked"
            })
            
            # Calculate tenant health
            tenants_by_health = self._calculate_tenant_health(all_tenants)
            
            # Active broadcasts
            active_broadcasts = len(self.broadcast_model.get_active_broadcasts())
            
            return {
                "success": True,
                "data": {
                    "tenants": {
                        "total": len(all_tenants),
                        "active": len(active_tenants),
                        "suspended": len(suspended_tenants),
                    },
                    "admins": {
                        "total": total_admins,
                        "active": active_admins,
                    },
                    "agents": {
                        "total": total_agents,
                        "online": online_agents,
                        "offline": total_agents - online_agents,
                    },
                    "logs": {
                        "today_total": total_logs_today,
                        "today_blocked": blocked_logs_today,
                    },
                    "health": tenants_by_health,
                    "broadcasts": {
                        "active": active_broadcasts,
                    },
                    "generated_at": now_iso(),
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting dashboard stats: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_tenant_health(self, tenants: List[Dict]) -> Dict:
        """Calculate health status for each tenant."""
        health_counts = {"healthy": 0, "warning": 0, "critical": 0}
        
        for tenant in tenants:
            if tenant.get("status") == "suspended":
                health_counts["critical"] += 1
                continue
            
            tenant_id = str(tenant["_id"])
            
            # Check agent health
            agent_count = self.agent_model.count_by_tenant(tenant_id)
            
            if agent_count == 0:
                health_counts["warning"] += 1
            else:
                # Check online ratio
                five_min_ago = now_vietnam() - timedelta(minutes=5)
                online_count = self.agent_model.collection.count_documents({
                    "tenant_id": ObjectId(tenant_id),
                    "last_heartbeat": {"$gte": five_min_ago}
                })
                
                online_ratio = online_count / agent_count if agent_count > 0 else 0
                
                if online_ratio >= 0.8:
                    health_counts["healthy"] += 1
                elif online_ratio >= 0.5:
                    health_counts["warning"] += 1
                else:
                    health_counts["critical"] += 1
        
        return health_counts
    
    def get_system_health(self) -> Dict:
        """Get detailed health information for all tenants."""
        try:
            tenants = self.tenant_model.list_tenants(limit=1000)
            
            health_data = []
            for tenant in tenants:
                tenant_id = str(tenant["_id"])
                
                # Agent counts
                total_agents = self.agent_model.count_by_tenant(tenant_id)
                five_min_ago = now_vietnam() - timedelta(minutes=5)
                online_agents = self.agent_model.collection.count_documents({
                    "tenant_id": ObjectId(tenant_id),
                    "last_heartbeat": {"$gte": five_min_ago}
                })
                
                # Admin count
                admin_count = self.admin_model.collection.count_documents({
                    "tenant_id": ObjectId(tenant_id),
                    "status": "active"
                })
                
                # Calculate health status
                if tenant.get("status") == "suspended":
                    health_status = "critical"
                elif total_agents == 0:
                    health_status = "warning"
                else:
                    online_ratio = online_agents / total_agents
                    if online_ratio >= 0.8:
                        health_status = "healthy"
                    elif online_ratio >= 0.5:
                        health_status = "warning"
                    else:
                        health_status = "critical"
                
                health_data.append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant.get("name"),
                    "tenant_slug": tenant.get("slug"),
                    "status": tenant.get("status"),
                    "plan": tenant.get("plan"),
                    "health_status": health_status,
                    "agents": {
                        "total": total_agents,
                        "online": online_agents,
                        "offline": total_agents - online_agents,
                    },
                    "admins": admin_count,
                    "created_at": tenant.get("created_at"),
                })
            
            return {
                "success": True,
                "data": health_data,
                "count": len(health_data)
            }
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {"success": False, "error": str(e)}
    
    # ========================================================================
    # Tenant Management
    # ========================================================================
    
    def list_tenants(self, filters: Dict = None, page: int = 1, limit: int = 20) -> Dict:
        """List all tenants with pagination."""
        try:
            skip = (page - 1) * limit
            tenants = self.tenant_model.list_tenants(filters=filters, skip=skip, limit=limit)
            
            # Enrich with stats
            for tenant in tenants:
                tenant_id = str(tenant["_id"])
                tenant["admin_count"] = self.admin_model.collection.count_documents({
                    "tenant_id": ObjectId(tenant_id)
                })
                tenant["agent_count"] = self.agent_model.count_by_tenant(tenant_id)
                tenant["_id"] = tenant_id
            
            total = self.tenant_model.collection.count_documents(filters or {"deleted_at": None})
            
            return {
                "success": True,
                "data": tenants,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        except Exception as e:
            self.logger.error(f"Error listing tenants: {e}")
            return {"success": False, "error": str(e)}
    
    def create_tenant(self, tenant_data: Dict, first_admin_data: Dict = None) -> Dict:
        """
        Create new tenant with optional first admin.
        
        Args:
            tenant_data: Tenant creation data
            first_admin_data: Optional data for first tenant admin
        """
        try:
            # Create tenant
            tenant = self.tenant_model.create_tenant(tenant_data)
            tenant_id = str(tenant["_id"])
            
            result = {
                "success": True,
                "tenant": tenant,
                "admin": None
            }
            
            # Create first admin if provided
            if first_admin_data:
                first_admin_data["tenant_id"] = tenant_id
                first_admin_data["role"] = ROLE_TENANT_ADMIN
                
                try:
                    admin = self.admin_model.create_admin(first_admin_data)
                    admin["_id"] = str(admin["_id"])
                    result["admin"] = admin
                    self.logger.info(f"Created first admin for tenant {tenant_id}: {admin['email']}")
                except Exception as e:
                    self.logger.error(f"Failed to create first admin: {e}")
                    result["admin_error"] = str(e)
            
            # Emit socket event
            if self.socketio:
                self.socketio.emit('tenant_created', {
                    "tenant_id": tenant_id,
                    "tenant_name": tenant.get("name")
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error creating tenant: {e}")
            return {"success": False, "error": str(e)}
    
    def get_tenant(self, tenant_id: str) -> Dict:
        """Get tenant details with stats."""
        try:
            tenant = self.tenant_model.get_by_id(tenant_id)
            if not tenant:
                return {"success": False, "error": "Tenant not found"}
            
            # Enrich with stats
            tenant["admin_count"] = self.admin_model.collection.count_documents({
                "tenant_id": ObjectId(tenant_id)
            })
            tenant["agent_count"] = self.agent_model.count_by_tenant(tenant_id)
            
            # Get admins list
            admins = list(self.admin_model.collection.find({
                "tenant_id": ObjectId(tenant_id)
            }))
            for admin in admins:
                admin["_id"] = str(admin["_id"])
                admin.pop("password_hash", None)
                admin.pop("password_history", None)
            
            tenant["admins"] = admins
            tenant["_id"] = str(tenant["_id"])
            
            return {"success": True, "data": tenant}
        except Exception as e:
            self.logger.error(f"Error getting tenant: {e}")
            return {"success": False, "error": str(e)}
    
    def update_tenant(self, tenant_id: str, update_data: Dict) -> Dict:
        """Update tenant information."""
        try:
            # Prevent updating protected fields
            protected_fields = ["_id", "created_at", "slug"]
            for field in protected_fields:
                update_data.pop(field, None)
            
            success = self.tenant_model.update_tenant(tenant_id, update_data)
            if success:
                tenant = self.tenant_model.get_by_id(tenant_id)
                return {"success": True, "data": tenant}
            return {"success": False, "error": "Failed to update tenant"}
        except Exception as e:
            self.logger.error(f"Error updating tenant: {e}")
            return {"success": False, "error": str(e)}
    
    def suspend_tenant(self, tenant_id: str, reason: str) -> Dict:
        """Suspend a tenant."""
        try:
            success = self.tenant_model.suspend_tenant(tenant_id, reason)
            if success:
                # Emit socket event
                if self.socketio:
                    self.socketio.emit('tenant_suspended', {
                        "tenant_id": tenant_id,
                        "reason": reason
                    })
                return {"success": True, "message": f"Tenant {tenant_id} suspended"}
            return {"success": False, "error": "Failed to suspend tenant"}
        except Exception as e:
            self.logger.error(f"Error suspending tenant: {e}")
            return {"success": False, "error": str(e)}
    
    def activate_tenant(self, tenant_id: str) -> Dict:
        """Activate a suspended tenant."""
        try:
            success = self.tenant_model.activate_tenant(tenant_id)
            if success:
                if self.socketio:
                    self.socketio.emit('tenant_activated', {"tenant_id": tenant_id})
                return {"success": True, "message": f"Tenant {tenant_id} activated"}
            return {"success": False, "error": "Failed to activate tenant"}
        except Exception as e:
            self.logger.error(f"Error activating tenant: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_tenant(self, tenant_id: str) -> Dict:
        """Soft delete a tenant."""
        try:
            success = self.tenant_model.delete_tenant(tenant_id)
            if success:
                if self.socketio:
                    self.socketio.emit('tenant_deleted', {"tenant_id": tenant_id})
                return {"success": True, "message": f"Tenant {tenant_id} deleted"}
            return {"success": False, "error": "Failed to delete tenant"}
        except Exception as e:
            self.logger.error(f"Error deleting tenant: {e}")
            return {"success": False, "error": str(e)}
    
    # ========================================================================
    # Admin Management (across all tenants)
    # ========================================================================
    
    def list_all_admins(self, filters: Dict = None, page: int = 1, limit: int = 20) -> Dict:
        """List all tenant admins across the platform."""
        try:
            skip = (page - 1) * limit
            query = {"role": ROLE_TENANT_ADMIN}
            if filters:
                query.update(filters)
            
            admins = list(self.admin_model.collection.find(query).skip(skip).limit(limit))
            
            # Enrich with tenant info
            for admin in admins:
                admin["_id"] = str(admin["_id"])
                admin.pop("password_hash", None)
                admin.pop("password_history", None)
                
                if admin.get("tenant_id"):
                    tenant = self.tenant_model.get_by_id(str(admin["tenant_id"]))
                    if tenant:
                        admin["tenant_name"] = tenant.get("name")
                        admin["tenant_slug"] = tenant.get("slug")
            
            total = self.admin_model.collection.count_documents(query)
            
            return {
                "success": True,
                "data": admins,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        except Exception as e:
            self.logger.error(f"Error listing admins: {e}")
            return {"success": False, "error": str(e)}
    
    def create_admin(self, admin_data: Dict) -> Dict:
        """Create a tenant admin."""
        try:
            admin_data["role"] = ROLE_TENANT_ADMIN
            admin = self.admin_model.create_admin(admin_data)
            admin["_id"] = str(admin["_id"])
            
            return {"success": True, "data": admin}
        except Exception as e:
            self.logger.error(f"Error creating admin: {e}")
            return {"success": False, "error": str(e)}
    
    def update_admin(self, admin_id: str, update_data: Dict) -> Dict:
        """Update a tenant admin."""
        try:
            # Prevent role change to super_admin
            if update_data.get("role") == ROLE_SUPER_ADMIN:
                return {"success": False, "error": "Cannot change role to Super Admin"}
            
            success = self.admin_model.update(admin_id, update_data)
            if success:
                admin = self.admin_model.get_by_id(admin_id)
                if admin:
                    admin["_id"] = str(admin["_id"])
                return {"success": True, "data": admin}
            return {"success": False, "error": "Failed to update admin"}
        except Exception as e:
            self.logger.error(f"Error updating admin: {e}")
            return {"success": False, "error": str(e)}
    
    def suspend_admin(self, admin_id: str, reason: str) -> Dict:
        """Suspend a tenant admin."""
        try:
            admin = self.admin_model.get_by_id(admin_id)
            if not admin:
                return {"success": False, "error": "Admin not found"}
            
            if admin.get("role") == ROLE_SUPER_ADMIN:
                return {"success": False, "error": "Cannot suspend Super Admin"}
            
            self.admin_model.collection.update_one(
                {"_id": ObjectId(admin_id)},
                {"$set": {
                    "status": "suspended",
                    "suspended_at": now_vietnam(),
                    "suspension_reason": reason
                }}
            )
            
            return {"success": True, "message": f"Admin {admin_id} suspended"}
        except Exception as e:
            self.logger.error(f"Error suspending admin: {e}")
            return {"success": False, "error": str(e)}
    
    # ========================================================================
    # Impersonation
    # ========================================================================
    
    def start_impersonation(
        self,
        super_admin_id: str,
        target_tenant_id: str,
        reason: str,
        ip_address: str
    ) -> Dict:
        """
        Start an impersonation session.
        
        Security checks:
        - Verify super admin role
        - Validate reason (min length)
        - Check no existing active session
        - Verify target tenant exists and is active
        """
        from config.impersonation_config import (
            validate_impersonation_reason,
            get_impersonation_hours,
            IMPERSONATION_CONFIG
        )
        
        try:
            # Verify super admin
            super_admin = self.admin_model.get_by_id(super_admin_id)
            if not super_admin or super_admin.get("role") != ROLE_SUPER_ADMIN:
                return {"success": False, "error": "Not authorized - Super Admin role required"}
            
            # Validate reason
            is_valid, error = validate_impersonation_reason(reason)
            if not is_valid:
                return {"success": False, "error": error}
            
            # Verify tenant exists
            tenant = self.tenant_model.get_by_id(target_tenant_id)
            if not tenant:
                return {"success": False, "error": "Tenant not found"}
            
            # Check tenant status
            if tenant.get("status") == "deleted":
                return {"success": False, "error": "Cannot impersonate a deleted tenant"}
            
            # Check for existing active session
            existing = self.impersonation_model.get_active_session(super_admin_id)
            if existing:
                return {
                    "success": False,
                    "error": "You already have an active impersonation session. Please end it first.",
                    "session_id": existing["session_id"],
                    "target_tenant": existing.get("target_tenant_id")
                }
            
            # Get first admin of tenant (or create virtual context)
            target_admin = self.admin_model.collection.find_one({
                "tenant_id": ObjectId(target_tenant_id),
                "role": ROLE_TENANT_ADMIN,
                "status": "active"
            })
            
            target_admin_id = str(target_admin["_id"]) if target_admin else None
            
            # Start impersonation session
            session = self.impersonation_model.start_impersonation({
                "super_admin_id": super_admin_id,
                "target_tenant_id": target_tenant_id,
                "target_admin_id": target_admin_id,
                "reason": reason,
                "ip_address": ip_address
            })
            
            # Generate impersonation token
            if self.jwt_service:
                impersonation_token = self.jwt_service.generate_impersonation_token(
                    super_admin_id=super_admin_id,
                    target_admin_id=target_admin_id or super_admin_id,
                    target_tenant_id=target_tenant_id,
                    impersonation_session_id=session["session_id"],
                    expires_hours=4
                )
                
                return {
                    "success": True,
                    "session_id": session["session_id"],
                    "impersonation_token": impersonation_token,
                    "tenant": {
                        "id": target_tenant_id,
                        "name": tenant.get("name"),
                        "slug": tenant.get("slug")
                    },
                    "expires_at": session["expires_at"].isoformat()
                }
            
            return {
                "success": True,
                "session_id": session["session_id"],
                "message": "Impersonation started (no token - JWT service not available)"
            }
        except Exception as e:
            self.logger.error(f"Error starting impersonation: {e}")
            return {"success": False, "error": str(e)}
    
    def end_impersonation(self, session_id: str) -> Dict:
        """End an impersonation session."""
        try:
            success = self.impersonation_model.end_impersonation(session_id, "manual")
            if success:
                return {"success": True, "message": "Impersonation ended"}
            return {"success": False, "error": "Session not found or already ended"}
        except Exception as e:
            self.logger.error(f"Error ending impersonation: {e}")
            return {"success": False, "error": str(e)}
    
    def get_impersonation_logs(
        self,
        super_admin_id: str = None,
        tenant_id: str = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict:
        """Get impersonation audit logs."""
        try:
            skip = (page - 1) * limit
            query = {}
            
            if super_admin_id:
                query["super_admin_id"] = ObjectId(super_admin_id)
            if tenant_id:
                query["target_tenant_id"] = ObjectId(tenant_id)
            
            logs = list(
                self.impersonation_model.collection
                .find(query)
                .sort("started_at", -1)
                .skip(skip)
                .limit(limit)
            )
            
            # Enrich with names
            for log in logs:
                log["_id"] = str(log["_id"])
                log["super_admin_id"] = str(log["super_admin_id"])
                log["target_tenant_id"] = str(log["target_tenant_id"])
                if log.get("target_admin_id"):
                    log["target_admin_id"] = str(log["target_admin_id"])
                
                # Get names
                super_admin = self.admin_model.get_by_id(log["super_admin_id"])
                if super_admin:
                    log["super_admin_email"] = super_admin.get("email")
                
                tenant = self.tenant_model.get_by_id(log["target_tenant_id"])
                if tenant:
                    log["tenant_name"] = tenant.get("name")
            
            total = self.impersonation_model.collection.count_documents(query)
            
            return {
                "success": True,
                "data": logs,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting impersonation logs: {e}")
            return {"success": False, "error": str(e)}
    
    # ========================================================================
    # Broadcasts
    # ========================================================================
    
    def list_broadcasts(self, include_inactive: bool = False, page: int = 1, limit: int = 20) -> Dict:
        """List all system broadcasts."""
        try:
            skip = (page - 1) * limit
            query = {} if include_inactive else {"is_active": True}
            
            broadcasts = list(
                self.broadcast_model.collection
                .find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            
            for broadcast in broadcasts:
                broadcast["_id"] = str(broadcast["_id"])
                broadcast["created_by"] = str(broadcast["created_by"])
            
            total = self.broadcast_model.collection.count_documents(query)
            
            return {
                "success": True,
                "data": broadcasts,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        except Exception as e:
            self.logger.error(f"Error listing broadcasts: {e}")
            return {"success": False, "error": str(e)}
    
    def create_broadcast(self, broadcast_data: Dict, created_by: str) -> Dict:
        """Create a system broadcast."""
        try:
            broadcast_data["created_by"] = created_by
            broadcast = self.broadcast_model.create_broadcast(broadcast_data)
            broadcast["_id"] = str(broadcast["_id"])
            
            # Emit to all connected clients
            if self.socketio:
                self.socketio.emit('new_broadcast', {
                    "id": broadcast["_id"],
                    "title": broadcast["title"],
                    "message": broadcast["message"],
                    "type": broadcast["type"]
                })
            
            return {"success": True, "data": broadcast}
        except Exception as e:
            self.logger.error(f"Error creating broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def update_broadcast(self, broadcast_id: str, update_data: Dict) -> Dict:
        """Update a broadcast."""
        try:
            protected_fields = ["_id", "created_at", "created_by"]
            for field in protected_fields:
                update_data.pop(field, None)
            
            update_data["updated_at"] = now_vietnam()
            
            result = self.broadcast_model.collection.update_one(
                {"_id": ObjectId(broadcast_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                broadcast = self.broadcast_model.get_by_id(broadcast_id)
                return {"success": True, "data": broadcast}
            return {"success": False, "error": "Failed to update broadcast"}
        except Exception as e:
            self.logger.error(f"Error updating broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_broadcast(self, broadcast_id: str) -> Dict:
        """Deactivate a broadcast."""
        try:
            result = self.broadcast_model.collection.update_one(
                {"_id": ObjectId(broadcast_id)},
                {"$set": {"is_active": False, "updated_at": now_vietnam()}}
            )
            
            if result.modified_count > 0:
                if self.socketio:
                    self.socketio.emit('broadcast_removed', {"id": broadcast_id})
                return {"success": True, "message": "Broadcast deactivated"}
            return {"success": False, "error": "Broadcast not found"}
        except Exception as e:
            self.logger.error(f"Error deleting broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def get_broadcast_stats(self) -> Dict:
        """Get broadcast statistics."""
        try:
            stats = self.broadcast_model.get_broadcast_stats()
            return {"success": True, "data": stats}
        except Exception as e:
            self.logger.error(f"Error getting broadcast stats: {e}")
            return {"success": False, "error": str(e)}
