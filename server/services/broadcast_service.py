"""
Broadcast Service
-----------------
Business logic for system broadcasts.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId

from time_utils import now_vietnam
from config.broadcast_config import (
    BROADCAST_TYPES, 
    BROADCAST_DISPLAY_CONFIG,
    sort_broadcasts_by_priority,
    is_dismissible,
    get_client_config
)

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for broadcast operations."""
    
    def __init__(self, broadcast_model, admin_model=None, tenant_model=None):
        self.broadcast_model = broadcast_model
        self.admin_model = admin_model
        self.tenant_model = tenant_model
    
    # ============ Super Admin Operations ============
    
    def create_broadcast(self, data: Dict, created_by: str) -> Dict:
        """
        Create a new system broadcast.
        
        Args:
            data: Broadcast data
            created_by: Super Admin ID
            
        Returns:
            Dict with success status and created broadcast or error
        """
        # Validate required fields
        title = data.get("title", "").strip()
        message = data.get("message", "").strip()
        
        if not title:
            return {"success": False, "error": "Title is required"}
        
        if not message:
            return {"success": False, "error": "Message is required"}
        
        if len(title) > 200:
            return {"success": False, "error": "Title must be 200 characters or less"}
        
        if len(message) > 2000:
            return {"success": False, "error": "Message must be 2000 characters or less"}
        
        # Validate type
        broadcast_type = data.get("type", "info")
        if broadcast_type not in BROADCAST_TYPES:
            return {"success": False, "error": f"Invalid type: {broadcast_type}"}
        
        # Parse dates
        start_time = self._parse_datetime(data.get("start_time"))
        end_time = self._parse_datetime(data.get("end_time"))
        
        if end_time and start_time and end_time <= start_time:
            return {"success": False, "error": "End time must be after start time"}
        
        # Validate target tenants if specific targeting
        target = data.get("target", "all")
        target_tenants = data.get("target_tenants", [])
        
        if target == "specific":
            if not target_tenants:
                return {"success": False, "error": "Target tenants required for specific targeting"}
            
            # Validate tenant IDs exist
            if self.tenant_model:
                for tid in target_tenants:
                    tenant = self.tenant_model.get_by_id(tid)
                    if not tenant:
                        return {"success": False, "error": f"Tenant not found: {tid}"}
        
        try:
            broadcast_data = {
                "title": title,
                "message": message,
                "type": broadcast_type,
                "priority": data.get("priority", "normal"),
                "target": target,
                "target_tenants": target_tenants,
                "start_time": start_time or now_vietnam(),
                "end_time": end_time,
                "created_by": created_by
            }
            
            broadcast = self.broadcast_model.create_broadcast(broadcast_data)
            
            return {
                "success": True,
                "data": self._serialize_broadcast(broadcast)
            }
            
        except Exception as e:
            logger.error(f"Error creating broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def update_broadcast(self, broadcast_id: str, data: Dict, updated_by: str) -> Dict:
        """
        Update an existing broadcast.
        
        Args:
            broadcast_id: Broadcast ID
            data: Update data
            updated_by: Super Admin ID
            
        Returns:
            Dict with success status
        """
        broadcast = self.broadcast_model.get_by_id(broadcast_id)
        if not broadcast:
            return {"success": False, "error": "Broadcast not found"}
        
        update_data = {}
        
        # Update allowed fields
        if "title" in data:
            title = data["title"].strip()
            if not title:
                return {"success": False, "error": "Title cannot be empty"}
            if len(title) > 200:
                return {"success": False, "error": "Title must be 200 characters or less"}
            update_data["title"] = title
        
        if "message" in data:
            message = data["message"].strip()
            if not message:
                return {"success": False, "error": "Message cannot be empty"}
            if len(message) > 2000:
                return {"success": False, "error": "Message must be 2000 characters or less"}
            update_data["message"] = message
        
        if "type" in data:
            if data["type"] not in BROADCAST_TYPES:
                return {"success": False, "error": f"Invalid type: {data['type']}"}
            update_data["type"] = data["type"]
            update_data["is_dismissible"] = is_dismissible(data["type"])
        
        if "priority" in data:
            update_data["priority"] = data["priority"]
        
        if "start_time" in data:
            update_data["start_time"] = self._parse_datetime(data["start_time"])
        
        if "end_time" in data:
            update_data["end_time"] = self._parse_datetime(data["end_time"])
        
        if "is_active" in data:
            update_data["is_active"] = bool(data["is_active"])
        
        if not update_data:
            return {"success": False, "error": "No valid fields to update"}
        
        try:
            success = self.broadcast_model.update_broadcast(broadcast_id, update_data)
            if success:
                updated = self.broadcast_model.get_by_id(broadcast_id)
                return {
                    "success": True,
                    "data": self._serialize_broadcast(updated)
                }
            return {"success": False, "error": "Failed to update broadcast"}
            
        except Exception as e:
            logger.error(f"Error updating broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def deactivate_broadcast(self, broadcast_id: str) -> Dict:
        """Deactivate a broadcast."""
        broadcast = self.broadcast_model.get_by_id(broadcast_id)
        if not broadcast:
            return {"success": False, "error": "Broadcast not found"}
        
        try:
            success = self.broadcast_model.deactivate_broadcast(broadcast_id)
            return {"success": success}
        except Exception as e:
            logger.error(f"Error deactivating broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_broadcast(self, broadcast_id: str) -> Dict:
        """Permanently delete a broadcast."""
        broadcast = self.broadcast_model.get_by_id(broadcast_id)
        if not broadcast:
            return {"success": False, "error": "Broadcast not found"}
        
        try:
            success = self.broadcast_model.delete_broadcast(broadcast_id)
            return {"success": success}
        except Exception as e:
            logger.error(f"Error deleting broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def list_broadcasts(self, page: int = 1, limit: int = 20, 
                        include_inactive: bool = True) -> Dict:
        """
        List all broadcasts for Super Admin.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            include_inactive: Include deactivated broadcasts
            
        Returns:
            Dict with broadcasts list and pagination info
        """
        skip = (page - 1) * limit
        
        broadcasts = self.broadcast_model.list_broadcasts(
            skip=skip, 
            limit=limit, 
            include_inactive=include_inactive
        )
        
        total = self.broadcast_model.count_broadcasts(include_inactive=include_inactive)
        
        return {
            "success": True,
            "data": {
                "broadcasts": [self._serialize_broadcast(b) for b in broadcasts],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
        }
    
    def get_broadcast_stats(self) -> Dict:
        """Get broadcast statistics for Super Admin dashboard."""
        try:
            stats = self.broadcast_model.get_broadcast_stats()
            return {"success": True, "data": stats}
        except Exception as e:
            logger.error(f"Error getting broadcast stats: {e}")
            return {"success": False, "error": str(e)}
    
    # ============ Tenant Admin Operations ============
    
    def get_active_broadcasts_for_admin(self, admin_id: str, tenant_id: str) -> Dict:
        """
        Get active broadcasts for a tenant admin.
        
        Args:
            admin_id: Admin ID (for dismiss filtering)
            tenant_id: Tenant ID (for targeting)
            
        Returns:
            Dict with active broadcasts
        """
        try:
            broadcasts = self.broadcast_model.get_active_broadcasts(
                tenant_id=tenant_id,
                admin_id=admin_id
            )
            
            # Sort by priority
            broadcasts = sort_broadcasts_by_priority(broadcasts)
            
            # Limit visible broadcasts
            max_visible = BROADCAST_DISPLAY_CONFIG.get("max_visible", 3)
            
            return {
                "success": True,
                "data": {
                    "broadcasts": [self._serialize_broadcast(b) for b in broadcasts[:max_visible]],
                    "total_count": len(broadcasts),
                    "hidden_count": max(0, len(broadcasts) - max_visible)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting broadcasts for admin: {e}")
            return {"success": False, "error": str(e)}
    
    def dismiss_broadcast(self, broadcast_id: str, admin_id: str) -> Dict:
        """
        Dismiss a broadcast for an admin.
        
        Args:
            broadcast_id: Broadcast ID
            admin_id: Admin ID
            
        Returns:
            Dict with success status
        """
        broadcast = self.broadcast_model.get_by_id(broadcast_id)
        if not broadcast:
            return {"success": False, "error": "Broadcast not found"}
        
        if not broadcast.get("is_dismissible", True):
            return {"success": False, "error": "This broadcast cannot be dismissed"}
        
        try:
            success = self.broadcast_model.dismiss_broadcast(broadcast_id, admin_id)
            if success:
                return {"success": True, "message": "Broadcast dismissed"}
            return {"success": False, "error": "Failed to dismiss broadcast"}
            
        except Exception as e:
            logger.error(f"Error dismissing broadcast: {e}")
            return {"success": False, "error": str(e)}
    
    def get_broadcast_by_id(self, broadcast_id: str) -> Dict:
        """Get a single broadcast by ID."""
        broadcast = self.broadcast_model.get_by_id(broadcast_id)
        if not broadcast:
            return {"success": False, "error": "Broadcast not found"}
        
        return {
            "success": True,
            "data": self._serialize_broadcast(broadcast)
        }
    
    # ============ Client Config ============
    
    def get_client_config(self) -> Dict:
        """Get configuration for client-side JavaScript."""
        return {
            "success": True,
            "data": get_client_config()
        }
    
    # ============ Helper Methods ============
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except:
                pass
            
            # Try common formats
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(value, fmt)
                except:
                    pass
        
        return None
    
    def _serialize_broadcast(self, broadcast: Dict) -> Dict:
        """Serialize broadcast for API response."""
        if not broadcast:
            return None
        
        broadcast_type = broadcast.get("type", "info")
        type_config = BROADCAST_TYPES.get(broadcast_type, BROADCAST_TYPES["info"])
        
        # Get creator info if available
        creator_info = None
        if self.admin_model and broadcast.get("created_by"):
            creator = self.admin_model.get_by_id(str(broadcast["created_by"]))
            if creator:
                creator_info = {
                    "id": str(creator["_id"]),
                    "full_name": creator.get("full_name", "Unknown"),
                    "email": creator.get("email", "")
                }
        
        return {
            "id": str(broadcast["_id"]),
            "title": broadcast.get("title", ""),
            "message": broadcast.get("message", ""),
            "type": broadcast_type,
            "type_config": {
                "color": type_config["color"],
                "bg_class": type_config["bg_class"],
                "icon": type_config["icon"],
                "icon_class": type_config["icon_class"]
            },
            "priority": broadcast.get("priority", "normal"),
            "target": broadcast.get("target", "all"),
            "target_tenants": [str(t) for t in broadcast.get("target_tenants", [])],
            "start_time": broadcast.get("start_time").isoformat() if broadcast.get("start_time") else None,
            "end_time": broadcast.get("end_time").isoformat() if broadcast.get("end_time") else None,
            "is_active": broadcast.get("is_active", True),
            "is_dismissible": broadcast.get("is_dismissible", True),
            "created_by": creator_info,
            "created_at": broadcast.get("created_at").isoformat() if broadcast.get("created_at") else None,
            "updated_at": broadcast.get("updated_at").isoformat() if broadcast.get("updated_at") else None
        }
