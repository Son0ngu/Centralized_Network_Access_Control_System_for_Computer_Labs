"""
Agent Controller - handles agent HTTP requests
vietnam ONLY - Clean and simple
"""

import logging
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify
from typing import Dict, Tuple
from models.agent_model import AgentModel
from services.agent_service import AgentService

# Import time utilities - vietnam ONLY
from time_utils import now_vietnam, now_iso

class AgentController:
    """Controller for agent operations"""
    
    def __init__(self, agent_model: AgentModel, agent_service: AgentService, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = agent_model
        self.service = agent_service
        self.socketio = socketio
        self.blueprint = Blueprint('agents', __name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register routes for this controller"""
        #  FIX: Add missing '/agents' prefix to routes
        
        # Core agent management routes
        self.blueprint.add_url_rule('/agents/register', 'register_agent', self.register_agent, methods=['POST'])
        self.blueprint.add_url_rule('/agents/heartbeat', 'heartbeat', self.heartbeat, methods=['POST'])
        self.blueprint.add_url_rule('/agents', 'list_agents', self.list_agents, methods=['GET'])  #  FIX: Add this route
        self.blueprint.add_url_rule('/agents/statistics', 'get_statistics', self.get_statistics, methods=['GET'])  #  FIX: Add agents prefix
        
        # Individual agent routes
        self.blueprint.add_url_rule('/agents/<agent_id>', 'get_agent', self.get_agent, methods=['GET'])
        self.blueprint.add_url_rule('/agents/<agent_id>', 'delete_agent', self.delete_agent, methods=['DELETE'])
        self.blueprint.add_url_rule('/agents/<agent_id>/display-name', 'update_display_name', self.update_display_name, methods=['PATCH'])
        self.blueprint.add_url_rule('/agents/<agent_id>/group', 'update_group', self.update_group, methods=['PATCH'])
        
        #  DEBUG: Add debug routes (optional - remove in production)
        self.blueprint.add_url_rule('/agents/debug/status', 'debug_status', self.debug_status, methods=['GET'])
        self.blueprint.add_url_rule('/agents/debug/direct', 'debug_direct_call', self.debug_direct_call, methods=['GET'])

    def _success_response(self, data=None, message="Success", status_code=200) -> Tuple:
        """Helper method for success responses"""
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return jsonify(response), status_code
    
    def _error_response(self, message: str, status_code=400) -> Tuple:
        """Helper method for error responses"""
        return jsonify({"success": False, "error": message}), status_code
    
    def _validate_json_request(self, required_fields=None) -> Dict:
        """Validate JSON request"""
        if not request.is_json:
            raise ValueError("Request must be JSON")
        
        data = request.get_json()
        if not data:
            raise ValueError("Invalid JSON data")
        
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        return data
    
    def _get_pagination_params(self) -> Dict:
        """Get pagination parameters"""
        try:
            limit = min(int(request.args.get('limit', 50)), 1000)
            skip = int(request.args.get('skip', 0))
            page = int(request.args.get('page', 1))
            
            if 'page' in request.args:
                skip = (page - 1) * limit
            
            return {"limit": limit, "skip": skip, "page": page}
        except ValueError:
            return {"limit": 50, "skip": 0, "page": 1}
    
    def _get_filter_params(self, allowed_filters=None) -> Dict:
        """Get filter parameters"""
        filters = {}
        allowed_filters = allowed_filters or []
        
        for key, value in request.args.items():
            if key in allowed_filters and value:
                filters[key] = value
        
        return filters
    
    def _serialize_agent(self, agent: Dict) -> Dict:
        """Ensure agent dict is JSON serializable."""
        if not agent:
            return {}

        serialized = {}
        for key, value in agent.items():
            if isinstance(value, ObjectId):
                serialized[key] = str(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value

        return serialized
    
    def register_agent(self):
        """Register a new agent"""
        try:
            data = self._validate_json_request(['hostname', 'device_id'])
            client_ip = request.remote_addr or data.get("ip_address", "unknown")
            
            # Call service method
            result = self.service.register_agent(data, client_ip)
            
            # Broadcast notification via SocketIO
            if self.socketio:
                self.socketio.emit("agent_registered", {
                    "agent_id": result["agent_id"],
                    "user_id": result["user_id"],
                    "hostname": data.get("hostname"),
                    "ip_address": data.get("ip_address"),
                    "status": "active",
                    "timestamp": result["server_time"]
                })
            
            return self._success_response(result, "Agent registered successfully")
            
        except ValueError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            self.logger.error(f"Error registering agent: {e}")
            return self._error_response("Failed to register agent", 500)
    
    def heartbeat(self):
        """Process agent heartbeat"""
        try:
            data = self._validate_json_request(['agent_id', 'token'])
            client_ip = request.remote_addr
            
            # Call service method
            result = self.service.process_heartbeat(
                data['agent_id'], 
                data['token'], 
                data, 
                client_ip
            )
            
            # ENHANCED: Broadcast với detailed status info
            if self.socketio:
                agent = self.model.find_by_agent_id(data['agent_id'])
                
                # Calculate time since last heartbeat
                current_time = now_vietnam()
                last_heartbeat = agent.get("last_heartbeat") if agent else None
                time_since_last = 0  # Just received, so 0
                
                # Determine actual status based on heartbeat timing
                if agent:
                    # Use service thresholds
                    actual_status = result.get('status', 'active')
                else:
                    actual_status = 'active'
                
                broadcast_data = {
                    "agent_id": data['agent_id'],
                    "hostname": agent.get("hostname") if agent else "Unknown",
                    "status": actual_status,  # Use calculated status
                    "last_heartbeat": now_iso(),
                    "time_since_heartbeat": time_since_last,
                    "metrics": data.get("metrics", {}),
                    "client_ip": client_ip,
                    "timestamp": now_iso(),
                    "agent_version": data.get("agent_version"),
                    "platform": data.get("platform"),
                    "group_id": str(agent.get("group_id")) if agent and agent.get("group_id") else None
                }
                
                self.logger.info(f"Broadcasting heartbeat: {data['agent_id']} - {actual_status}")
                self.socketio.emit("agent_heartbeat", broadcast_data)
            
            return self._success_response(result)
            
        except ValueError as e:
            status_code = 401 if "Invalid token" in str(e) else 400
            return self._error_response(str(e), status_code)
        except Exception as e:
            self.logger.error(f"Error processing heartbeat: {e}")
            return self._error_response("Failed to process heartbeat", 500)
    
    def list_agents(self):
        """List all agents with filtering - COMPLETE VERSION - vietnam only"""
        try:
            self.logger.info(" List agents called")
            
            pagination = self._get_pagination_params()
            filters = self._get_filter_params(['status', 'hostname','group_id'])
            
            agents_with_status = self.service.get_agents_with_status()
            self.logger.info(f" Found {len(agents_with_status)} agents")
            
            # Apply filters
            filtered_agents = agents_with_status
            if filters.get("status"):
                status_filter = filters["status"]
                filtered_agents = [a for a in filtered_agents if a.get('status') == status_filter]
            
            if filters.get("hostname"):
                hostname_filter = filters["hostname"].lower()
                filtered_agents = [a for a in filtered_agents if hostname_filter in a.get('hostname', '').lower()]
            
            if filters.get("group_id"):
                filtered_agents = [a for a in filtered_agents if str(a.get('group_id')) == filters['group_id']]

            # Apply pagination
            total_count = len(filtered_agents)
            agents_list = filtered_agents[pagination['skip']:pagination['skip']+pagination['limit']]
            
            # Format for API response - vietnam only
            formatted_agents = []
            for agent in agents_list:
                last_heartbeat_iso = None
                if agent.get("last_heartbeat"):
                    if isinstance(agent["last_heartbeat"], str):
                        last_heartbeat_iso = agent["last_heartbeat"]
                    else:
                        last_heartbeat_iso = agent["last_heartbeat"].isoformat()
                
                registered_date_iso = None
                if agent.get("registered_date"):
                    if isinstance(agent["registered_date"], str):
                        registered_date_iso = agent["registered_date"]
                    else:
                        registered_date_iso = agent["registered_date"].isoformat()
                
                formatted_agent = {
                    "agent_id": agent.get("agent_id"),
                    "hostname": agent.get("hostname", "Unknown"),
                    "display_name": agent.get("display_name") or agent.get("hostname", "Unknown"),
                    "ip_address": agent.get("ip_address", "Unknown"),
                    "platform": agent.get("platform", "Unknown"),
                    "os_info": agent.get("os_info", "Unknown"),
                    "agent_version": agent.get("agent_version", "Unknown"),
                    "status": agent.get("status"),
                    "group_id": str(agent.get("group_id")) if agent.get("group_id") else None,
                    "registered_date": registered_date_iso,
                    "last_heartbeat": last_heartbeat_iso,
                    "time_since_heartbeat": agent.get("time_since_heartbeat"),
                    "metrics": agent.get("metrics"),
                    "user_id": agent.get("device_id") or agent.get("ip_address")
                }
                
                formatted_agents.append(formatted_agent)
            
            return jsonify({
                "agents": formatted_agents,
                "total": total_count,
                "success": True,
                "pagination": {
                    "total": total_count,
                    "limit": pagination['limit'],
                    "skip": pagination['skip'],
                    "page": pagination['page']
                }
            }), 200
            
        except Exception as e:
            self.logger.error(f"Error listing agents: {e}")
            return self._error_response("Failed to list agents", 500)
    
    def get_agent(self, agent_id: str):
        """Get detailed agent information"""
        try:
            # Call service method
            agent_data = self.service.get_agent_details(agent_id)
            return self._success_response(agent_data)
            
        except ValueError as e:
            return self._error_response(str(e), 404)
        except Exception as e:
            self.logger.error(f"Error retrieving agent: {e}")
            return self._error_response("Failed to retrieve agent details", 500)
    
    def delete_agent(self, agent_id: str):
        """Delete an agent"""
        try:
            #  THÊM: Get agent info trước khi delete
            agent = self.model.find_by_agent_id(agent_id)
            if not agent:
                return self._error_response("Agent not found", 404)
            
            #  SỬA: Gọi service để delete
            success = self.service.delete_agent(agent_id)
            
            if success:
                #  THÊM: Broadcast deletion qua SocketIO - vietnam only
                if self.socketio:
                    self.socketio.emit("agent_deleted", {
                        "agent_id": agent_id,
                        "hostname": agent.get("hostname"),
                        "timestamp": now_iso()
                    })
                
                return self._success_response(
                    message=f"Agent {agent.get('hostname', agent_id)} deleted successfully"
                )
            else:
                return self._error_response("Failed to delete agent", 500)
                
        except ValueError as e:
            return self._error_response(str(e), 404)
        except Exception as e:
            self.logger.error(f"Error deleting agent {agent_id}: {e}")
            return self._error_response("Internal server error", 500)

    def update_display_name(self, agent_id: str):
        """Update agent display name"""
        try:
            data = self._validate_json_request(['display_name'])
            self.service.update_display_name(agent_id, data.get('display_name'))
            return self._success_response(message="Display name updated")
        except ValueError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            self.logger.error(f"Error updating display name: {e}")
            return self._error_response("Failed to update display name", 500)

    def update_group(self, agent_id: str):
        """Move agent to a new group"""
        try:
            data = self._validate_json_request(['group_id'])
            agent = self.service.move_agent_to_group(agent_id, data.get('group_id'))
            
            # Serialize ObjectId before returning
            serialized_agent = self._serialize_agent(agent)
            
            # IMPROVED: Broadcast via SocketIO
            if self.socketio:
                self.socketio.emit("agent_group_updated", {
                    "agent_id": agent_id,
                    "hostname": serialized_agent.get("hostname"),
                    "group_id": serialized_agent.get("group_id"),
                    "status": serialized_agent.get("status"),
                    "timestamp": now_iso()
                })
            
            return self._success_response(
                data=serialized_agent,
                message="Agent moved to group successfully"
            )
            
        except ValueError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            self.logger.error(f"Error updating agent group: {e}")
            return self._error_response("Failed to update agent group", 500)

    def get_statistics(self):
        """Get agent statistics"""
        try:
            #  CRITICAL: Use calculate_statistics method
            stats = self.service.calculate_statistics()
            self.logger.info(f" Statistics calculated: {stats}")
            return self._success_response(stats)
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return self._error_response("Failed to get statistics", 500)

    def debug_status(self):
        """Return debug information for troubleshooting"""
        try:
            stats = self.service.calculate_statistics()
            sample_agents = [
                self._serialize_agent(agent)
                for agent in self.model.get_all_agents(limit=5)
            ]

            debug_info = {
                "controller": "AgentController",
                "socketio_enabled": bool(self.socketio),
                "thresholds": {
                    "active_seconds": getattr(self.service, "active_threshold", None),
                    "inactive_seconds": getattr(self.service, "inactive_threshold", None)
                },
                "statistics": stats,
                "sample_agents": sample_agents,
                "timestamp": now_iso()
            }

            return self._success_response(debug_info, "Debug status retrieved")
        except Exception as e:
            self.logger.error(f"Error in debug_status: {e}")
            return self._error_response("Failed to retrieve debug status", 500)

    def debug_direct_call(self):
        """Simple endpoint to verify controller accessibility"""
        try:
            return self._success_response(
                {
                    "message": "Agent controller is reachable",
                    "routes": [
                        "/agents/register",
                        "/agents/heartbeat",
                        "/agents",
                        "/agents/statistics",
                        "/agents/<agent_id>",
                        "/agents/<agent_id>/display-name",
                        "/agents/<agent_id>/group",
                        "/agents/debug/status",
                        "/agents/debug/direct"
                    ],
                    "timestamp": now_iso()
                },
                "Debug endpoint is active"
            )
        except Exception as e:
            self.logger.error(f"Error in debug_direct_call: {e}")
            return self._error_response("Debug endpoint failed", 500)