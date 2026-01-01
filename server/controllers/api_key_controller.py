"""
API Key Controller - handles API key HTTP requests for admin management.
- Clean and simple
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Tuple
from models.api_key_model import APIKeyModel
from services.api_key_service import APIKeyService

# Import time utilities - Vietnam ONLY
from time_utils import now_vietnam, now_iso

# Import auth middleware for tenant isolation
from middleware.auth import get_current_tenant_id

logger = logging.getLogger(__name__)


class APIKeyController:
    """Controller for API key management operations"""
    
    def __init__(self, api_key_model: APIKeyModel, api_key_service: APIKeyService, socketio=None):
        """
        Initialize API Key Controller.
        
        Args:
            api_key_model: APIKeyModel instance
            api_key_service: APIKeyService instance
            socketio: SocketIO instance for real-time updates
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = api_key_model
        self.service = api_key_service
        self.socketio = socketio
        self.blueprint = Blueprint('api_keys', __name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register routes for this controller"""
        # CRUD operations
        self.blueprint.add_url_rule(
            '/api-keys',
            'list_api_keys',
            self.list_api_keys,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/api-keys',
            'create_api_key',
            self.create_api_key,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/api-keys/<key_id>',
            'get_api_key',
            self.get_api_key,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/api-keys/<key_id>',
            'update_api_key',
            self.update_api_key,
            methods=['PUT', 'PATCH']
        )
        self.blueprint.add_url_rule(
            '/api-keys/<key_id>',
            'delete_api_key',
            self.delete_api_key,
            methods=['DELETE']
        )
        
        # Special operations
        self.blueprint.add_url_rule(
            '/api-keys/<key_id>/revoke',
            'revoke_api_key',
            self.revoke_api_key,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/api-keys/stats',
            'get_stats',
            self.get_stats,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/api-keys/validate',
            'validate_key',
            self.validate_key,
            methods=['POST']
        )
    
    def _success_response(self, data=None, message="Success", status_code=200) -> Tuple:
        """Helper method for success responses"""
        response = {"success": True, "message": message}
        if data is not None:
            if isinstance(data, dict):
                response.update(data)
            else:
                response["data"] = data
        return jsonify(response), status_code
    
    def _error_response(self, message: str, status_code=400) -> Tuple:
        """Helper method for error responses"""
        return jsonify({"success": False, "error": message}), status_code
    
    # ========================================
    # CRUD OPERATIONS
    # ========================================
    
    def list_api_keys(self):
        """
        GET /api/api-keys
        List all API keys (paginated).
        
        Query params:
            - page: Page number (default 1)
            - limit: Items per page (default 20)
            - include_revoked: Include revoked keys (default false)
        """
        try:
            # Get tenant_id for data isolation
            tenant_id = get_current_tenant_id()
            
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            include_revoked = request.args.get('include_revoked', 'false').lower() == 'true'
            
            # Clamp values
            page = max(1, page)
            limit = min(100, max(1, limit))
            
            result = self.service.list_api_keys(
                include_revoked=include_revoked,
                page=page,
                limit=limit,
                tenant_id=tenant_id
            )
            
            return self._success_response(result)
            
        except Exception as e:
            self.logger.error(f"Error listing API keys: {e}")
            return self._error_response(str(e), 500)
    
    def create_api_key(self):
        """
        POST /api/api-keys
        Create a new API key.
        
        Request body:
        {
            "name": "Key Name",
            "description": "Optional description",
            "expires_in_days": 365,  // optional, null = never expires
            "permissions": ["register"]  // optional, default ["register"]
        }
        """
        try:
            data = request.get_json() or {}
            
            # Validate required fields
            name = data.get('name')
            if not name:
                return self._error_response("Name is required")
            
            # Optional fields
            description = data.get('description', '')
            expires_in_days = data.get('expires_in_days')
            permissions = data.get('permissions')
            
            # Validate expires_in_days if provided
            # 0 or null means never expires
            if expires_in_days is not None:
                try:
                    expires_in_days = int(expires_in_days)
                    if expires_in_days < 0:
                        return self._error_response("expires_in_days cannot be negative")
                    # Convert 0 to None (never expires)
                    if expires_in_days == 0:
                        expires_in_days = None
                except (ValueError, TypeError):
                    return self._error_response("expires_in_days must be a number")
            
            # Validate permissions if provided
            # Support both old and new permission names
            valid_permissions = [
                'register', 'sync', 'logs', 'heartbeat', 'admin',  # Legacy
                'agent_register', 'agent_read', 'whitelist_sync', 'logs_write'  # New format
            ]
            if permissions:
                if not isinstance(permissions, list):
                    return self._error_response("permissions must be a list")
                invalid = [p for p in permissions if p not in valid_permissions]
                if invalid:
                    return self._error_response(f"Invalid permissions: {invalid}")
            
            # Get tenant_id for data isolation
            tenant_id = get_current_tenant_id()
            
            # Create key with tenant isolation
            result = self.service.create_api_key(
                name=name,
                description=description,
                expires_in_days=expires_in_days,
                permissions=permissions,
                created_by="admin",  # TODO: Get from auth context
                tenant_id=tenant_id
            )
            
            if result.get('success'):
                return self._success_response(result, "API key created", 201)
            else:
                return self._error_response(result.get('error', 'Failed to create key'))
            
        except Exception as e:
            self.logger.error(f"Error creating API key: {e}")
            return self._error_response(str(e), 500)
    
    def get_api_key(self, key_id: str):
        """
        GET /api/api-keys/<key_id>
        Get details of a specific API key.
        """
        try:
            key_data = self.service.get_api_key(key_id)
            
            if key_data:
                return self._success_response({"key": key_data})
            else:
                return self._error_response("API key not found", 404)
            
        except Exception as e:
            self.logger.error(f"Error getting API key: {e}")
            return self._error_response(str(e), 500)
    
    def update_api_key(self, key_id: str):
        """
        PUT/PATCH /api/api-keys/<key_id>
        Update an API key.
        
        Request body:
        {
            "name": "New Name",  // optional
            "description": "New description",  // optional
            "permissions": ["register", "sync"],  // optional
            "is_active": true  // optional
        }
        """
        try:
            data = request.get_json() or {}
            
            if not data:
                return self._error_response("No update data provided")
            
            # Extract update fields
            name = data.get('name')
            description = data.get('description')
            permissions = data.get('permissions')
            is_active = data.get('is_active')
            
            # Validate permissions if provided
            valid_permissions = [
                'register', 'sync', 'logs', 'heartbeat', 'admin',  # Legacy
                'agent_register', 'agent_read', 'whitelist_sync', 'logs_write'  # New format
            ]
            if permissions is not None:
                if not isinstance(permissions, list):
                    return self._error_response("permissions must be a list")
                invalid = [p for p in permissions if p not in valid_permissions]
                if invalid:
                    return self._error_response(f"Invalid permissions: {invalid}")
            
            result = self.service.update_api_key(
                key_id=key_id,
                name=name,
                description=description,
                permissions=permissions,
                is_active=is_active,
                updated_by="admin"
            )
            
            if result.get('success'):
                return self._success_response(result)
            else:
                return self._error_response(result.get('error', 'Failed to update key'))
            
        except Exception as e:
            self.logger.error(f"Error updating API key: {e}")
            return self._error_response(str(e), 500)
    
    def delete_api_key(self, key_id: str):
        """
        DELETE /api/api-keys/<key_id>
        Delete (revoke) an API key.
        """
        return self.revoke_api_key(key_id)
    
    # ========================================
    # SPECIAL OPERATIONS
    # ========================================
    
    def revoke_api_key(self, key_id: str):
        """
        POST /api/api-keys/<key_id>/revoke
        Revoke an API key.
        """
        try:
            result = self.service.revoke_api_key(
                key_id=key_id,
                revoked_by="admin"
            )
            
            if result.get('success'):
                return self._success_response(result)
            else:
                return self._error_response(result.get('error', 'Failed to revoke key'))
            
        except Exception as e:
            self.logger.error(f"Error revoking API key: {e}")
            return self._error_response(str(e), 500)
    
    def get_stats(self):
        """
        GET /api/api-keys/stats
        Get API key statistics.
        """
        try:
            stats = self.service.get_stats()
            return self._success_response({"stats": stats})
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return self._error_response(str(e), 500)
    
    def validate_key(self):
        """
        POST /api/api-keys/validate
        Validate an API key (for testing).
        
        Request body:
        {
            "api_key": "fc_...",
            "permission": "register"  // optional
        }
        """
        try:
            data = request.get_json() or {}
            
            api_key = data.get('api_key')
            if not api_key:
                return self._error_response("api_key is required")
            
            permission = data.get('permission', 'register')
            
            result = self.service.validate_api_key(api_key, permission)
            
            # Don't expose internal details in response
            if result.get('valid'):
                return self._success_response({
                    "valid": True,
                    "name": result.get('name'),
                    "permissions": result.get('permissions')
                })
            else:
                return self._success_response({
                    "valid": False,
                    "error": result.get('error')
                })
            
        except Exception as e:
            self.logger.error(f"Error validating API key: {e}")
            return self._error_response(str(e), 500)
