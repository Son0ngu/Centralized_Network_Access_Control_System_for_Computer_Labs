"""
Agent Service - Business logic for agent operations
- Clean and simple
"""

import logging
import secrets
import uuid
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models.agent_model import AgentModel

# Import time utilities - vietnam ONLY
from time_utils import (
    now_vietnam,
    to_vietnam,
    now_iso,
    parse_agent_timestamp,
    format_datetime,
    get_time_ago_string,
)

class AgentService:
    """Service class for agent business logic - vietnam ONLY"""
    
    def __init__(self, agent_model: AgentModel, group_model, socketio=None, jwt_service=None,
                 policy_model=None):
        """Initialize AgentService with proper parameters"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = agent_model
        self.group_model = group_model
        self.socketio = socketio
        self.jwt_service = jwt_service  # NEW: JWT service for token generation
        self.policy_model = policy_model  # AgentPolicyModel for force_sync check
        
        # Get database from model, not from parameter
        self.db = self.model.db
        self.pending_group = self.group_model.ensure_pending_group()
        
        # - no timezone complexity
        self.active_threshold = 300      # 5 minutes
        self.inactive_threshold = 1800   # 30 minutes
        
        self.logger.info("AgentService initialized with vietnam timezone support")
        self.logger.info(f"Status thresholds: active≤{self.active_threshold}s, inactive≤{self.inactive_threshold}s")
    
    def set_jwt_service(self, jwt_service):
        """Set JWT service (for late initialization)"""
        self.jwt_service = jwt_service
        self.logger.info("JWT service attached to AgentService")

    def _persist_status_change(self, agent: Dict, new_status: str) -> None:
        """Persist status change to database when calculated status differs"""
        try:
            agent_id = agent.get("agent_id")
            previous_status = agent.get("status")

            if not agent_id or not new_status:
                return

            if previous_status == new_status:
                return

            updated = self.model.update_agent(agent_id, {"status": new_status})
            if updated:
                self.logger.info(
                    "Persisted status change for %s: %s -> %s",
                    agent.get("hostname", agent_id),
                    previous_status,
                    new_status,
                )
            else:
                self.logger.warning(
                    "Failed to persist status change for %s", agent.get("hostname", agent_id)
                )
        except Exception as exc:
            self.logger.error(f"Error persisting status for {agent.get('agent_id')}: {exc}")
            
    def register_agent(self, agent_data: Dict, client_ip: str) -> Dict:
        """Register a new agent using hostname+IP as identifier - vietnam ONLY"""
        try:
            hostname = agent_data.get("hostname")
            
            self.logger.info(f"Agent registration: {hostname} from {client_ip}")
            
            if not hostname:
                raise ValueError("Hostname is required")
            
            # Use agent's reported IP if available
            agent_ip = agent_data.get("ip_address") or client_ip
            if agent_ip == "127.0.0.1" and client_ip != "127.0.0.1":
                agent_ip = client_ip
        
            device_id = agent_data.get("device_id")
            if not device_id:
                raise ValueError("Device ID is required for agent registration")

            # Prefer device_id to detect existing agents, fallback to hostname/IP for legacy records
            existing_agent = self.model.find_by_device_id(device_id)
            if not existing_agent:
                query = {"$or": [
                    {"ip_address": agent_ip},
                    {"hostname": hostname},
                    {"$and": [{"hostname": hostname}, {"ip_address": agent_ip}]}
                ]}

                agents = self.model.get_all_agents(query, limit=1)
                legacy_agent = agents[0] if agents else None
                if legacy_agent and not legacy_agent.get("device_id"):
                    existing_agent = legacy_agent
            
            # Use vietnam time for all timestamps
            current_time = now_vietnam()
            
            if existing_agent:
                # Update existing agent
                agent_id = existing_agent.get("agent_id")
                update_data = {
                    "hostname": hostname,
                    "device_id": device_id,
                    "ip_address": agent_ip,
                    "platform": agent_data.get("platform"),
                    "os_info": agent_data.get("os_info"),
                    "agent_version": agent_data.get("agent_version"),
                    "last_heartbeat": current_time,
                    "updated_date": current_time,
                    
                }
                if existing_agent.get("status") not in ["pending", "disabled"]:
                    update_data["status"] = "active"

                if not existing_agent.get("group_id"):
                    update_data["group_id"] = str(self.pending_group.get("_id"))
                if not existing_agent.get("display_name"):
                    update_data["display_name"] = hostname
                
                self.model.update_agent(agent_id, update_data)
                agent_token = existing_agent.get("agent_token")
                if not agent_token:
                    agent_token = secrets.token_hex(32)
                    self.model.update_agent(agent_id, {"agent_token": agent_token})
                
                self.logger.info(f"Updated existing agent: {agent_id}")
            else:
                # Create new agent
                agent_id = str(uuid.uuid4())
                agent_token = secrets.token_hex(32)
                
                agent_registration_data = {
                    "agent_id": agent_id,
                    "device_id": device_id,
                    "hostname": hostname,
                    "display_name": hostname,
                    "ip_address": agent_ip,
                    "platform": agent_data.get("platform"),
                    "os_info": agent_data.get("os_info"),
                    "agent_version": agent_data.get("agent_version"),
                    "agent_token": agent_token,
                    "registered_date": current_time,
                    "last_heartbeat": current_time,
                    "status": "pending",
                    "group_id": str(self.pending_group.get("_id")),
                }
                
                self.model.register_agent(agent_registration_data)
                self.logger.info(f"Created new agent: {agent_id}")

            # Emit SocketIO event - vietnam only
            if self.socketio:
                self.socketio.emit("agent_registered", {
                    "agent_id": agent_id,
                    "hostname": hostname,
                    "ip_address": agent_ip,
                    "status": agent_registration_data.get("status") if not existing_agent else existing_agent.get("status"),
                    "timestamp": now_iso()  # vietnam ISO
                })
            
            # Build response
            response = {
                "agent_id": agent_id,
                "user_id": device_id,
                "token": agent_token,  # Legacy token for backward compatibility
                "status": agent_registration_data.get("status") if not existing_agent else update_data.get("status", existing_agent.get("status")),
                "message": f"Agent {'updated' if existing_agent else 'registered'} successfully",
                "server_time": now_iso()  # vietnam ISO
            }
            
            # Generate JWT tokens if JWT service is available
            if self.jwt_service:
                try:
                    jwt_tokens = self.jwt_service.generate_tokens(
                        agent_id=agent_id,
                        user_id=device_id,
                        additional_claims={
                            "hostname": hostname,
                            "ip_address": agent_ip
                        }
                    )
                    # Add JWT tokens to response
                    response["jwt"] = jwt_tokens
                    self.logger.info(f"JWT tokens generated for agent {agent_id}")
                except Exception as jwt_error:
                    self.logger.warning(f"Failed to generate JWT tokens: {jwt_error}")
                    # Continue without JWT - fallback to legacy token
            
            return response
        
        except Exception as e:
            self.logger.error(f"Agent registration failed: {e}")
            raise

    def get_agents_with_status(self) -> List[Dict]:
        """Get all agents with status calculation - vietnam ONLY"""
        try:
            self.logger.info("get_agents_with_status() called - vietnam VERSION")
            
            agents = self.model.get_all_agents()
            self.logger.info(f"Found {len(agents)} agents from database")
            
            # Use vietnam time for status calculation
            current_time = now_vietnam()
            
            self.logger.info(f"Current vietnam time: {current_time}")
            
            for agent in agents:
                hostname = agent.get('hostname', 'Unknown')
                last_heartbeat = agent.get('last_heartbeat')
                
                agent.setdefault('display_name', hostname)

                current_status = agent.get("status")

                if current_status in ["pending", "disabled"]:
                    if last_heartbeat:
                        try:
                            last_dt = parse_agent_timestamp(last_heartbeat)
                            agent['time_since_heartbeat'] = (current_time - last_dt).total_seconds() / 60
                        except Exception:
                            agent['time_since_heartbeat'] = None
                    continue

                if last_heartbeat:
                    self.logger.info(f"{hostname}: Processing heartbeat {last_heartbeat} (type: {type(last_heartbeat)})")
                    
                    try:
                        last_heartbeat_vietnam = parse_agent_timestamp(last_heartbeat)

                        time_diff_seconds = (current_time - last_heartbeat_vietnam).total_seconds()
                        
                        if time_diff_seconds < 0:
                            self.logger.warning(
                                "%s: Heartbeat %s ahead of server time %s by %.2fs; clamping to 0",
                                hostname,
                                last_heartbeat_vietnam,
                                current_time,
                                abs(time_diff_seconds),
                            )
                            time_diff_seconds = 0.0

                        self.logger.info(f"{hostname}: Time calculation:")
                        self.logger.info(f"   Current vietnam: {current_time}")
                        self.logger.info(f"   Heartbeat vietnam: {last_heartbeat_vietnam}")
                        self.logger.info(f"   Difference: {time_diff_seconds:.2f} seconds")
                        
                        if time_diff_seconds <= self.active_threshold:
                            status = 'active'
                            self.logger.info(f"{hostname}: {time_diff_seconds:.2f}s ≤ {self.active_threshold}s → ACTIVE")
                        elif time_diff_seconds <= self.inactive_threshold:
                            status = 'inactive'
                            self.logger.info(f"{hostname}: {time_diff_seconds:.2f}s ≤ {self.inactive_threshold}s → INACTIVE")
                        else:                                               # > 30 minutes = offline
                            status = 'offline'
                            self.logger.info(f"{hostname}: {time_diff_seconds:.2f}s > {self.inactive_threshold}s → OFFLINE")
                        
                        self._persist_status_change(agent, status)
                        agent['status'] = status
                        agent['time_since_heartbeat'] = time_diff_seconds / 60
                        agent['last_heartbeat'] = last_heartbeat_vietnam

                        
                        self.logger.info(f"{hostname}: FINAL → {time_diff_seconds:.2f}s = {status}")
                        
                    except Exception as e:
                        self.logger.error(f"{hostname}: Error processing heartbeat: {e}")
                        self.logger.error(f"{hostname}: Traceback: {traceback.format_exc()}")
                        self._persist_status_change(agent, 'offline')
                        agent['status'] = 'offline'
                        agent['time_since_heartbeat'] = 999
                else:
                    self.logger.info(f"{hostname}: No heartbeat found")
                    self._persist_status_change(agent, 'offline')
                    agent['status'] = 'offline'
                    agent['time_since_heartbeat'] = None

            self.logger.info(f"Returning {len(agents)} agents with status")
            return agents
            
        except Exception as e:
            self.logger.error(f"get_agents_with_status error: {e}")
            self.logger.error(traceback.format_exc())
            return []

    def calculate_statistics(self) -> Dict:
        """Calculate agent statistics - vietnam ONLY"""
        try:
            agents = self.get_agents_with_status()
            
            total = len(agents)
            active = len([a for a in agents if a.get('status') == 'active'])
            inactive = len([a for a in agents if a.get('status') == 'inactive'])
            offline = len([a for a in agents if a.get('status') == 'offline'])
            pending = len([a for a in agents if a.get('status') == 'pending'])

            # Calculate percentages
            active_percentage = (active / total * 100) if total > 0 else 0
            
            stats = {
                'total': total,
                'active': active,
                'inactive': inactive,
                'offline': offline,
                'pending': pending,
                'active_percentage': round(active_percentage, 1),
                'health_status': 'good' if active_percentage > 70 else 'warning' if active_percentage > 30 else 'critical',
                'last_calculated': now_iso(),  # vietnam ISO
                'thresholds': {
                    'active_seconds': self.active_threshold,
                    'inactive_seconds': self.inactive_threshold
                }
            }
            
            self.logger.info(f"Statistics: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating statistics: {e}")
            return {
                'total': 0, 
                'active': 0, 
                'inactive': 0, 
                'offline': 0,
                'pending': 0,
                'active_percentage': 0,
                'health_status': 'error',
                'last_calculated': now_iso(),
                'error': str(e)
            }

    def process_heartbeat(self, agent_id: str, token: str, heartbeat_data: Dict, client_ip: str) -> Dict:
        """Process agent heartbeat - vietnam ONLY"""
        try:
            # Validate agent and token
            agent = self.model.find_by_agent_id(agent_id)
            if not agent:
                raise ValueError("Unknown agent")
            
            if agent.get("agent_token") != token:
                raise ValueError("Invalid token")
            
            incoming_device_id = heartbeat_data.get("device_id")
            stored_device_id = agent.get("device_id")
            if stored_device_id and incoming_device_id and stored_device_id != incoming_device_id:
                raise ValueError("Device ID mismatch")
            
            # Parse agent timestamp using vietnam parsing
            agent_timestamp = heartbeat_data.get("timestamp")
            if agent_timestamp:
                try:
                    heartbeat_time = parse_agent_timestamp(agent_timestamp)
                    self.logger.info(f"Agent {agent_id} sent: '{agent_timestamp}' → parsed: {heartbeat_time}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse agent timestamp '{agent_timestamp}': {e}")
                    heartbeat_time = now_vietnam()
            else:
                heartbeat_time = now_vietnam()
        
            # Update heartbeat with parsed timestamp
            new_status = agent.get("status")
            if new_status not in ["pending", "disabled"]:
                new_status = heartbeat_data.get("status", "active")

            update_data = {
                "client_ip": client_ip,
                "metrics": heartbeat_data.get("metrics", {}),
                "status": new_status,
                "agent_version": heartbeat_data.get("agent_version"),
                "last_heartbeat_data": heartbeat_data,
                "platform": heartbeat_data.get("platform"),
                "os_info": heartbeat_data.get("os_info"),
                "last_heartbeat": heartbeat_time
            }
            
            if incoming_device_id and not stored_device_id:
                update_data["device_id"] = incoming_device_id
                
            self.logger.info(f"Setting heartbeat for {agent_id}: {heartbeat_time}")
            
            success = self.model.update_heartbeat(agent_id, update_data)
            
            if not success:
                raise ValueError("Failed to update heartbeat")
            
            # Emit real-time status update - vietnam only
            if self.socketio:
                self.socketio.emit("agent_heartbeat", {
                    "agent_id": agent_id,
                    "hostname": agent.get("hostname"),
                    "status": "active",
                    "last_heartbeat": now_iso(),  # vietnam ISO
                    "metrics": heartbeat_data.get("metrics", {}),
                    "client_ip": client_ip
                })
            
            self.logger.info(f"Heartbeat processed for agent: {agent_id}")
            
            # Calculate next heartbeat time
            next_heartbeat_time = now_vietnam() + timedelta(seconds=60)
            
            # Check if agent has an active policy override → tell agent to force sync
            force_sync = False
            policy_mode = "none"
            if self.policy_model:
                try:
                    policy_mode = self.policy_model.get_effective_mode(agent_id)
                    if policy_mode != "none":
                        force_sync = True
                except Exception as pe:
                    self.logger.warning(f"Policy check failed for {agent_id}: {pe}")

            return {
                "agent_id": agent_id,
                "status": new_status,
                "next_heartbeat": int(next_heartbeat_time.timestamp() * 1000),
                "server_time": now_iso(),  # vietnam ISO
                "force_sync": force_sync,
                "policy_mode": policy_mode,
            }
            
        except Exception as e:
            self.logger.error(f"Heartbeat processing failed: {e}")
            raise

    def get_total_agents(self) -> int:
        """Get total number of agents"""
        try:
            return self.model.count_agents({})
        except Exception as e:
            self.logger.error(f"Error getting total agents: {e}")
            return 0
    
    def get_active_agents_count(self) -> int:
        """Get count of active agents"""
        try:
            agents = self.get_agents_with_status()
            return len([a for a in agents if a.get('status') == 'active'])
        except Exception as e:
            self.logger.error(f"Error getting active agents count: {e}")
            return 0

    def get_all_agents(self, filters: Dict = None) -> List[Dict]:
        """Get all agents with optional filtering - vietnam ONLY"""
        try:
            agents = self.get_agents_with_status()
            
            # Apply filters if provided
            if filters:
                if filters.get("status"):
                    status_filter = filters["status"]
                    agents = [a for a in agents if a.get('status') == status_filter]
                
                if filters.get("hostname"):
                    hostname_filter = filters["hostname"].lower()
                    agents = [a for a in agents if hostname_filter in a.get('hostname', '').lower()]
            
            # Format for response
            formatted_agents = []
            for agent in agents:
                formatted_agent = {
                    "id": str(agent.get("_id", "")),
                    "agent_id": agent.get("agent_id", "unknown"),
                    "hostname": agent.get("hostname", "unknown"),
                    "ip_address": agent.get("ip_address", "unknown"),
                    "status": agent.get("status", "unknown"),
                    "last_seen": agent.get("last_heartbeat"),
                    "version": agent.get("agent_version", "unknown"),
                    "os_info": agent.get("os_info", {}),
                    "platform": agent.get("platform", "unknown"),
                    "created_at": agent.get("registered_date"),
                    "updated_at": agent.get("last_heartbeat"),
                    "time_since_heartbeat": agent.get("time_since_heartbeat")
                }
                
                # Format timestamps - vietnam only
                for time_field in ["last_seen", "created_at", "updated_at"]:
                    if agent.get(time_field):
                        try:
                            timestamp = agent[time_field]
                            if isinstance(timestamp, datetime):
                                vietnam_dt = to_vietnam(timestamp)
                                formatted_agent[time_field] = vietnam_dt.isoformat()
                            elif isinstance(timestamp, str):
                                formatted_agent[time_field] = parse_agent_timestamp(timestamp).isoformat()
                            else:
                                formatted_agent[time_field] = str(timestamp)
                        except Exception as e:
                            self.logger.warning(f"Error formatting {time_field}: {e}")
                            formatted_agent[time_field] = None
                
                formatted_agents.append(formatted_agent)
            
            return formatted_agents
            
        except Exception as e:
            self.logger.error(f"Error getting all agents: {e}")
            return []

    def get_agent_details(self, agent_id: str) -> Dict:
        """Get detailed agent information - vietnam ONLY"""
        try:
            agent = self.model.find_by_agent_id(agent_id)
            if not agent:
                raise ValueError("Agent not found")
            
            # Calculate status using get_agents_with_status for consistency
            agents_with_status = self.get_agents_with_status()
            agent_with_status = next((a for a in agents_with_status if a.get('agent_id') == agent_id), None)
            
            if agent_with_status:
                actual_status = agent_with_status.get('status', 'offline')
                time_since_heartbeat = agent_with_status.get('time_since_heartbeat')
            else:
                actual_status = 'offline'
                time_since_heartbeat = None
            
            # Format timestamps for display 
            registered_date = agent.get("registered_date")
            last_heartbeat = agent.get("last_heartbeat")
            
            return {
                "agent_id": agent.get("agent_id"),
                "hostname": agent.get("hostname"),
                "ip_address": agent.get("ip_address"),
                "mac_address": agent.get("mac_address"),
                "platform": agent.get("platform"),
                "os_info": agent.get("os_info"),
                "agent_version": agent.get("agent_version"),
                "status": actual_status,
                "registered_date": format_datetime(registered_date) if registered_date else None,
                "last_heartbeat": format_datetime(last_heartbeat) if last_heartbeat else None,
                "time_since_heartbeat": time_since_heartbeat,
                "server_time": now_iso()  # vietnam ISO
            }
            
        except Exception as e:
            self.logger.error(f"Error getting agent details: {e}")
            raise

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent and related data - vietnam ONLY"""
        try:
            # Check if agent exists
            agent = self.model.find_by_agent_id(agent_id)
            if not agent:
                raise ValueError("Agent not found")
            
            # Delete agent
            success = self.model.delete_agent(agent_id)
            
            if success and self.socketio:
                self.socketio.emit("agent_deleted", {
                    "agent_id": agent_id,
                    "hostname": agent.get("hostname"),
                    "timestamp": now_iso()  # vietnam ISO
                })
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error deleting agent {agent_id}: {e}")
            raise
    
    def update_display_name(self, agent_id: str, display_name: str) -> bool:
        if not display_name:
            raise ValueError("display_name is required")
        updated = self.model.update_agent(agent_id, {"display_name": display_name})
        if not updated:
            raise ValueError("Agent not found or not updated")
        return True

    def update_position(self, agent_id: str, position: int) -> bool:
        """Update agent position in layout"""
        try:
            position = int(position) if position is not None else None
            
            updated = self.model.update_agent(agent_id, {"position": position})
            if not updated:
                raise ValueError("Agent not found or not updated")
            return True
        except ValueError as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error updating position for agent {agent_id}: {e}")
            raise

    def move_agent_to_group(self, agent_id: str, group_id: str) -> Dict:
        """Move agent to a new group"""
        try:
            agent = self.model.find_by_agent_id(agent_id)
            if not agent:
                raise ValueError("Agent not found")

            group = self.group_model.find_by_id(group_id)
            if not group:
                raise ValueError("Group not found")

            #  FIX: Convert ObjectId to string immediately
            group_id_str = str(group.get("_id"))
            
            # Preserve the agent's current status unless we need to change it based on the destination group.
            current_status = agent.get("status") or "pending"
            is_pending_group = group.get("is_system") and group.get("name") == "pending"
            leaving_pending_group = current_status == "pending" and not is_pending_group

            # Force "pending" when explicitly moving into the pending group. When leaving the pending system group, immediately mark the agent as active so it will be picked up by the normal status calculation logic on the next refresh.
            if is_pending_group:
                status_to_set = "pending"
            elif leaving_pending_group:
                status_to_set = "active"
            else:
                status_to_set = None

            final_status = status_to_set or current_status

            # Update agent group (status is only updated when necessary)
            success = self.model.update_agent_group(agent_id, group_id_str, status_to_set)

            if not success:
                raise ValueError("Failed to move agent to group")

            #  FIX: Return serializable dict
            return {
                "agent_id": agent_id,
                "hostname": agent.get("hostname"),
                "display_name": agent.get("display_name"),
                "ip_address": agent.get("ip_address"),
                "group_id": group_id_str,  
                "group_name": group.get("name"),
                "status": final_status,
                "last_heartbeat": agent.get("last_heartbeat"),
                "platform": agent.get("platform"),
                "os_info": agent.get("os_info"),
                "agent_version": agent.get("agent_version")
            }
            
        except Exception as e:
            self.logger.error(f"Error moving agent to group: {e}")
            raise
