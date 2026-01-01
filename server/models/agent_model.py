"""
Agent Model - handles agent data operations
- Clean and simple
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

# Import time utilities - vietnam ONLY
from time_utils import now_vietnam, parse_agent_timestamp

class AgentModel:
    """Model for agent data operations"""
    
    def __init__(self, db: Database):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db
        self.collection: Collection = self.db.agents
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Setup indexes for agents collection"""
        try:
            # Unique index on agent_id
            self.collection.create_index([("agent_id", ASCENDING)], unique=True)
            # Unique device_id when provided
            self.collection.create_index([("device_id", ASCENDING)], unique=True, sparse=True)
            # Indexes for queries
            self.collection.create_index([("hostname", ASCENDING)])
            self.collection.create_index([("ip_address", ASCENDING)])
            self.collection.create_index([("last_heartbeat", DESCENDING)])
            self.collection.create_index([("status", ASCENDING)])
            # Compound index for hostname + IP combination
            self.collection.create_index([("hostname", ASCENDING), ("ip_address", ASCENDING)])
            self.collection.create_index([("group_id", ASCENDING)])
            # Tenant isolation index
            self.collection.create_index([("tenant_id", ASCENDING)], name="tenant_idx")
            self.logger.info("Agent indexes created successfully")
        except Exception as e:
            self.logger.warning(f"Error creating indexes: {e}")

    def register_agent(self, agent_data: Dict, tenant_id: str = None) -> Dict:
        """Register a new agent (CREATE only, not update) - vietnam ONLY
        
        Args:
            agent_data: Agent registration data
            tenant_id: Tenant ID for isolation (required for multi-tenancy)
        """
        try:
            # Use vietnam time for registration
            current_time = now_vietnam()  # vietnam naive for MongoDB
            
            # Set tenant_id for isolation
            if tenant_id:
                agent_data["tenant_id"] = tenant_id
            
            agent_data.update({
                "registered_date": current_time,
                "updated_date": current_time,
                "last_heartbeat": current_time,
                "status": agent_data.get("status", "pending"),
                "group_id": agent_data.get("group_id"),
                "display_name": agent_data.get("display_name", agent_data.get("hostname")),
            })
            
            result = self.collection.insert_one(agent_data)
            agent_data["_id"] = result.inserted_id
            
            self.logger.info(f"Agent registered: {agent_data.get('agent_id')}")
            return agent_data
            
        except Exception as e:
            self.logger.error(f"Error registering agent: {e}")
            raise

    def update_agent(self, agent_id: str, update_data: Dict) -> bool:
        """Update existing agent - vietnam ONLY"""
        try:
            update_data["updated_date"] = now_vietnam()  
            result = self.collection.update_one(
                {"agent_id": agent_id},
                {"$set": update_data}
            )
            self.logger.debug(f"Agent {agent_id} updated: {result.modified_count} records")
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error updating agent {agent_id}: {e}")
            return False
    
    def update_agent_group(self, agent_id: str, group_id: str, status: Optional[str] = None) -> bool:
        try:
            payload = {"group_id": group_id, "updated_date": now_vietnam()}
            if status:
                payload["status"] = status
            result = self.collection.update_one({"agent_id": agent_id}, {"$set": payload})
            return result.modified_count > 0
        except Exception as exc:
            self.logger.error(f"Error updating agent group {agent_id}: {exc}")
            return False
        
    def update_heartbeat(self, agent_id: str, update_data: Dict) -> bool:
        """Update agent heartbeat - vietnam ONLY"""
        try:
            heartbeat_value = update_data.get("last_heartbeat")
            heartbeat_time = parse_agent_timestamp(heartbeat_value)
            current_time = now_vietnam()

            update_data_with_heartbeat = {**update_data}
            update_data_with_heartbeat["last_heartbeat"] = heartbeat_time
            update_data_with_heartbeat["updated_date"] = current_time
            
            result = self.collection.update_one(
                {"agent_id": agent_id},
                {"$set": update_data_with_heartbeat}
            )
            
            self.logger.debug(f"Updated heartbeat for {agent_id}: {current_time}")
            return result.modified_count > 0
            
        except Exception as e:
            self.logger.error(f"Error updating heartbeat for {agent_id}: {e}")
            return False
    
    def find_by_agent_id(self, agent_id: str) -> Optional[Dict]:
        """Find agent by agent_id"""
        try:
            return self.collection.find_one({"agent_id": agent_id})
        except Exception as e:
            self.logger.error(f"Error finding agent {agent_id}: {e}")
            return None
    
    def count_by_group(self, group_id: str) -> int:
        try:
            return self.collection.count_documents({"group_id": group_id})
        except Exception as exc:
            self.logger.error(f"Error counting agents for group {group_id}: {exc}")
            return 0
    
    def count_by_tenant(self, tenant_id: str) -> int:
        """Count agents belonging to a tenant (via tenant_id field if exists, else return all)"""
        try:
            # Check if tenant_id field exists in agents
            # For now, if no tenant_id field, return total count (single-tenant mode)
            if self.collection.find_one({"tenant_id": {"$exists": True}}):
                return self.collection.count_documents({"tenant_id": tenant_id})
            else:
                # Single-tenant mode - return all agents
                return self.collection.count_documents({})
        except Exception as exc:
            self.logger.error(f"Error counting agents for tenant {tenant_id}: {exc}")
            return 0
        
    def find_by_hostname(self, hostname: str) -> List[Dict]:
        """Find agents by hostname"""
        try:
            return list(self.collection.find({"hostname": {"$regex": hostname, "$options": "i"}}))
        except Exception as e:
            self.logger.error(f"Error finding agents by hostname {hostname}: {e}")
            return []
        
    def find_by_device_id(self, device_id: str) -> Optional[Dict]:
        """Find agent by device ID"""
        try:
            return self.collection.find_one({"device_id": device_id})
        except Exception as e:
            self.logger.error(f"Error finding agent by device ID {device_id}: {e}")
            return None
        
    def get_all_agents(self, query: Dict = None, limit: int = 100, skip: int = 0, tenant_id: str = None) -> List[Dict]:
        """Get all agents with optional filtering
        
        Args:
            query: Additional query filters
            limit: Max results
            skip: Skip first N results
            tenant_id: Filter by tenant (for isolation)
        """
        try:
            if query is None:
                query = {}
            
            # Filter by tenant_id for isolation
            if tenant_id:
                query["tenant_id"] = tenant_id
            
            return list(self.collection.find(query).sort("last_heartbeat", -1).skip(skip).limit(limit))
        except Exception as e:
            self.logger.error(f"Error getting agents: {e}")
            return []
    
    def count_agents(self, query: Dict = None) -> int:
        """Count agents with optional filtering"""
        try:
            if query is None:
                query = {}
            return self.collection.count_documents(query)
        except Exception as e:
            self.logger.error(f"Error counting agents: {e}")
            return 0
    
    def get_active_agents(self, inactive_threshold_minutes: int = 5) -> List[Dict]:
        """Get list of active agents - vietnam ONLY"""
        try:
            from datetime import timedelta
            current_time = now_vietnam()
            threshold = current_time - timedelta(minutes=inactive_threshold_minutes)
            return list(self.collection.find({
                "last_heartbeat": {"$gte": threshold}
            }))
        except Exception as e:
            self.logger.error(f"Error getting active agents: {e}")
            return []
    
    def get_inactive_agents(self, inactive_threshold_minutes: int = 5) -> List[Dict]:
        """Get list of inactive agents - vietnam ONLY"""
        try:
            from datetime import timedelta
            current_time = now_vietnam()
            threshold = current_time - timedelta(minutes=inactive_threshold_minutes)
            return list(self.collection.find({
                "last_heartbeat": {"$lt": threshold}
            }))
        except Exception as e:
            self.logger.error(f"Error getting inactive agents: {e}")
            return []
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        try:
            result = self.collection.delete_one({"agent_id": agent_id})
            self.logger.info(f"Agent {agent_id} deleted: {result.deleted_count} records")
            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Error deleting agent {agent_id}: {e}")
            return False
    
    def get_agent_statistics(self, inactive_threshold_minutes: int = 5) -> Dict:
        """Get agent statistics - vietnam ONLY"""
        try:
            from datetime import timedelta
            current_time = now_vietnam()
            inactive_threshold = current_time - timedelta(minutes=inactive_threshold_minutes)
            
            pipeline = [
                {
                    "$addFields": {
                        "actual_status": {
                            "$cond": {
                                "if": {"$gte": ["$last_heartbeat", inactive_threshold]},
                                "then": "active",
                                "else": {
                                    "$cond": {
                                        "if": {"$eq": ["$last_heartbeat", None]},
                                        "then": "offline",
                                        "else": "inactive"
                                    }
                                }
                            }
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$actual_status",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            results = list(self.collection.aggregate(pipeline))
            
            stats = {"total": 0, "active": 0, "inactive": 0, "offline": 0}
            
            for result in results:
                status = result["_id"]
                count = result["count"]
                stats[status] = count
                stats["total"] += count
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting agent statistics: {e}")
            return {"total": 0, "active": 0, "inactive": 0, "offline": 0}