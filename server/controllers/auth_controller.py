"""
Auth Controller - handles authentication endpoints (token refresh, logout).
Vietnam ONLY - Clean and simple
"""

import logging
from flask import Blueprint, request, jsonify, g
from typing import Tuple

from services.jwt_service import JWTService
from time_utils import now_iso

logger = logging.getLogger(__name__)


class AuthController:
    """Controller for authentication operations"""
    
    def __init__(self, jwt_service: JWTService, agent_model=None, socketio=None):
        """
        Initialize Auth Controller.
        
        Args:
            jwt_service: JWTService instance
            agent_model: AgentModel instance for agent verification
            socketio: SocketIO instance for real-time updates
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.jwt_service = jwt_service
        self.agent_model = agent_model
        self.socketio = socketio
        self.blueprint = Blueprint('auth', __name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register routes for this controller"""
        # Token operations
        self.blueprint.add_url_rule(
            '/auth/refresh',
            'refresh_token',
            self.refresh_token,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/auth/logout',
            'logout',
            self.logout,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/auth/verify',
            'verify_token',
            self.verify_token,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/auth/token-info',
            'token_info',
            self.token_info,
            methods=['GET']
        )
    
    def _success_response(self, data=None, message="Success", status_code=200) -> Tuple:
        """Helper method for success responses"""
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return jsonify(response), status_code
    
    def _error_response(self, message: str, status_code=400, code=None) -> Tuple:
        """Helper method for error responses"""
        response = {"success": False, "error": message}
        if code:
            response["code"] = code
        return jsonify(response), status_code
    
    def refresh_token(self):
        """
        Refresh access token using refresh token.
        
        Request body:
            {
                "refresh_token": "eyJ...",
                "rotate": false  // Optional: if true, also rotates refresh token
            }
        
        Response (without rotation):
            {
                "success": true,
                "data": {
                    "access_token": "eyJ...",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                    "expires_at": "2025-12-02T..."
                }
            }
        
        Response (with rotation):
            {
                "success": true,
                "data": {
                    "access_token": "eyJ...",
                    "refresh_token": "eyJ...",  // New refresh token
                    "token_type": "Bearer",
                    ...
                }
            }
        """
        try:
            if not request.is_json:
                return self._error_response("Request must be JSON", 400)
            
            data = request.get_json()
            refresh_token = data.get("refresh_token")
            rotate = data.get("rotate", False)  # Optional rotation
            
            if not refresh_token:
                return self._error_response("refresh_token is required", 400)
            
            # Refresh the token (with or without rotation)
            if rotate:
                success, result, error = self.jwt_service.refresh_tokens_with_rotation(refresh_token)
            else:
                success, result, error = self.jwt_service.refresh_access_token(refresh_token)
            
            if not success:
                # Determine appropriate error code
                if "expired" in (error or "").lower():
                    return self._error_response(error, 401, "REFRESH_TOKEN_EXPIRED")
                elif "revoked" in (error or "").lower():
                    return self._error_response(error, 401, "TOKEN_REVOKED")
                else:
                    return self._error_response(error or "Token refresh failed", 401)
            
            self.logger.info(f"Token refreshed for agent (rotation={rotate})")
            
            # Emit socket event for monitoring
            if self.socketio:
                token_info = self.jwt_service.decode_token_without_verification(result["access_token"])
                self.socketio.emit("token_refreshed", {
                    "agent_id": token_info.get("sub") if token_info else None,
                    "rotated": rotate,
                    "timestamp": now_iso()
                })
            
            return self._success_response(result, "Token refreshed successfully")
            
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            return self._error_response("Token refresh failed", 500)
    
    def logout(self):
        """
        Logout agent by revoking tokens.
        
        Request headers:
            Authorization: Bearer <access_token>
        
        Request body (optional):
            {
                "refresh_token": "eyJ...",
                "revoke_all": false
            }
        """
        try:
            # Get access token from header
            auth_header = request.headers.get("Authorization", "")
            access_token = None
            
            if auth_header.startswith("Bearer "):
                access_token = auth_header[7:].strip()
            
            # Get refresh token from body
            refresh_token = None
            revoke_all = False
            
            if request.is_json:
                data = request.get_json()
                refresh_token = data.get("refresh_token")
                revoke_all = data.get("revoke_all", False)
            
            # Extract agent_id for logging
            agent_id = None
            if access_token:
                token_info = self.jwt_service.decode_token_without_verification(access_token)
                agent_id = token_info.get("sub") if token_info else None
            
            # Revoke tokens
            revoked_count = 0
            
            if access_token:
                if self.jwt_service.revoke_token(access_token, "access"):
                    revoked_count += 1
            
            if refresh_token:
                if self.jwt_service.revoke_token(refresh_token, "refresh"):
                    revoked_count += 1
            
            if revoke_all and agent_id:
                self.jwt_service.revoke_all_agent_tokens(agent_id)
                revoked_count += 1
            
            self.logger.info(f"Logout: revoked {revoked_count} token(s) for agent {agent_id}")
            
            # Emit socket event
            if self.socketio and agent_id:
                self.socketio.emit("agent_logout", {
                    "agent_id": agent_id,
                    "timestamp": now_iso()
                })
            
            return self._success_response({
                "revoked_count": revoked_count
            }, "Logged out successfully")
            
        except Exception as e:
            self.logger.error(f"Error during logout: {e}")
            return self._error_response("Logout failed", 500)
    
    def verify_token(self):
        """
        Verify if a token is valid.
        
        Request body:
            {
                "token": "eyJ...",
                "token_type": "access"  // or "refresh"
            }
        
        Response:
            {
                "success": true,
                "data": {
                    "valid": true,
                    "agent_id": "...",
                    "expires_at": "..."
                }
            }
        """
        try:
            if not request.is_json:
                return self._error_response("Request must be JSON", 400)
            
            data = request.get_json()
            token = data.get("token")
            token_type = data.get("token_type", "access")
            
            if not token:
                return self._error_response("token is required", 400)
            
            # Validate token
            if token_type == "refresh":
                is_valid, payload, error = self.jwt_service.validate_refresh_token(token)
            else:
                is_valid, payload, error = self.jwt_service.validate_access_token(token)
            
            if is_valid:
                return self._success_response({
                    "valid": True,
                    "agent_id": payload.get("sub"),
                    "user_id": payload.get("user_id"),
                    "token_type": payload.get("type"),
                    "expires_at": payload.get("exp"),
                })
            else:
                return self._success_response({
                    "valid": False,
                    "error": error
                })
            
        except Exception as e:
            self.logger.error(f"Error verifying token: {e}")
            return self._error_response("Token verification failed", 500)
    
    def token_info(self):
        """
        Get information about a token without full validation.
        
        Request headers:
            Authorization: Bearer <token>
        
        Response:
            {
                "success": true,
                "data": {
                    "agent_id": "...",
                    "token_type": "access",
                    "is_expired": false,
                    "is_revoked": false,
                    "expires_at": "..."
                }
            }
        """
        try:
            auth_header = request.headers.get("Authorization", "")
            
            if not auth_header.startswith("Bearer "):
                return self._error_response("Bearer token required in Authorization header", 400)
            
            token = auth_header[7:].strip()
            
            if not token:
                return self._error_response("Token required", 400)
            
            # Get token info
            info = self.jwt_service.get_token_info(token)
            
            return self._success_response(info)
            
        except Exception as e:
            self.logger.error(f"Error getting token info: {e}")
            return self._error_response("Failed to get token info", 500)
