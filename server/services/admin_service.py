"""
Admin Service - Business logic for admin operations
----------------------------------------------------
Handles admin authentication, management, and multi-tenant operations.
"""

import logging
from typing import Dict, List, Optional
from datetime import timedelta

from models.admin_model import AdminModel
from models.tenant_model import TenantModel
from services.email_service import get_email_service, get_2fa_service
from time_utils import now_vietnam, now_iso
from middleware.security import audit_log

logger = logging.getLogger(__name__)


class AdminService:
    """Service class for admin business logic."""
    
    def __init__(self, admin_model: AdminModel, tenant_model: TenantModel, jwt_service=None, socketio=None):
        self.admin_model = admin_model
        self.tenant_model = tenant_model
        self.jwt_service = jwt_service
        self.socketio = socketio
    
    def authenticate(self, email: str, password: str, ip_address: str) -> Dict:
        """
        Authenticate admin user.
        
        Returns:
            {
                "success": True,
                "admin": {...},
                "tenant": {...},
                "requires_2fa": False,
                "access_token": "...",
                "refresh_token": "..."
            }
        """
        admin = self.admin_model.verify_password(email, password)
        
        if not admin:
            audit_log('failed_login', {'email': email, 'reason': 'invalid_credentials'})
            return {
                "success": False,
                "error": "Invalid email or password"
            }
        
        # Check if account is active
        if admin.get('status') != 'active':
            audit_log('failed_login', {'email': email, 'reason': 'account_not_active'})
            return {
                "success": False,
                "error": f"Account is {admin.get('status')}"
            }
        
        # Super Admin has no tenant - skip tenant check
        tenant = None
        if admin.get('role') == 'super_admin':
            # Super Admin doesn't need tenant validation
            logger.info(f"Super Admin login: {email}")
        else:
            # Get tenant for regular admins
            tenant = self.tenant_model.get_by_id(str(admin.get('tenant_id')))
            if not tenant or tenant.get('status') != 'active':
                audit_log('failed_login', {'email': email, 'reason': 'tenant_not_active'})
                return {
                    "success": False,
                    "error": "Tenant is not active"
                }
        
        # Check if 2FA is required
        if admin.get('2fa_enabled'):
            # Generate and send 2FA code
            tfa_service = get_2fa_service()
            if tfa_service:
                tfa_service.send_code(str(admin['_id']), email)
            
            return {
                "success": True,
                "requires_2fa": True,
                "admin_id": str(admin['_id']),
                "email": email,
                "message": "2FA code sent to your email"
            }
        
        # Update last login
        self.admin_model.update_last_login(str(admin['_id']), ip_address)
        
        # Generate tokens
        tokens = self._generate_tokens(admin, tenant)
        
        audit_log('login', {'admin_id': str(admin['_id']), 'email': email})
        
        return {
            "success": True,
            "requires_2fa": False,
            "admin": self._sanitize_admin(admin),
            "tenant": self._sanitize_tenant(tenant),
            **tokens
        }
    
    def verify_2fa(self, admin_id: str, code: str, ip_address: str) -> Dict:
        """Verify 2FA code and complete login."""
        tfa_service = get_2fa_service()
        if not tfa_service:
            return {"success": False, "error": "2FA service not available"}
        
        if not tfa_service.verify_code(admin_id, code):
            audit_log('failed_2fa', {'admin_id': admin_id})
            return {"success": False, "error": "Invalid or expired code"}
        
        admin = self.admin_model.get_by_id(admin_id)
        if not admin:
            return {"success": False, "error": "Admin not found"}
        
        # Super Admin has no tenant
        tenant = None
        if admin.get('role') != 'super_admin' and admin.get('tenant_id'):
            tenant = self.tenant_model.get_by_id(str(admin['tenant_id']))
        
        # Update last login
        self.admin_model.update_last_login(admin_id, ip_address)
        
        # Generate tokens
        tokens = self._generate_tokens(admin, tenant)
        
        audit_log('login', {'admin_id': admin_id, 'email': admin['email'], '2fa': True})
        
        return {
            "success": True,
            "admin": self._sanitize_admin(admin),
            "tenant": self._sanitize_tenant(tenant),
            **tokens
        }
    
    def _generate_tokens(self, admin: Dict, tenant: Dict = None) -> Dict:
        """Generate JWT tokens."""
        if not self.jwt_service:
            return {}
        
        payload = {
            "admin_id": str(admin['_id']),
            "email": admin['email'],
            "tenant_id": str(tenant['_id']) if tenant else None,
            "role": admin.get('role', 'tenant_admin'),
            "type": "admin"
        }
        
        access_token = self.jwt_service.generate_access_token(payload)
        refresh_token = self.jwt_service.generate_refresh_token(payload)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    
    def create_admin(self, admin_data: Dict, created_by: str = None) -> Dict:
        """Create new admin in tenant."""
        tenant_id = admin_data.get('tenant_id')
        
        # Check tenant limits
        if not self.tenant_model.check_limits(tenant_id, 'admin'):
            return {
                "success": False,
                "error": "Tenant has reached maximum admin limit"
            }
        
        # Create admin
        admin_data['created_by'] = created_by
        admin = self.admin_model.create_admin(admin_data)
        
        # Send welcome email
        email_service = get_email_service()
        if email_service:
            email_service.send_welcome_email(
                admin['email'],
                admin.get('full_name') or admin['email']
            )
        
        audit_log('admin_created', {
            'admin_id': str(admin['_id']),
            'email': admin['email'],
            'created_by': created_by
        })
        
        return {
            "success": True,
            "admin": self._sanitize_admin(admin)
        }
    
    def update_admin(self, admin_id: str, update_data: Dict, updated_by: str = None) -> Dict:
        """Update admin information."""
        success = self.admin_model.update_admin(admin_id, update_data)
        
        if success:
            audit_log('admin_updated', {
                'admin_id': admin_id,
                'updated_by': updated_by,
                'fields': list(update_data.keys())
            })
            
            admin = self.admin_model.get_by_id(admin_id)
            return {
                "success": True,
                "admin": self._sanitize_admin(admin)
            }
        
        return {"success": False, "error": "Failed to update admin"}
    
    def change_password(self, admin_id: str, old_password: str, new_password: str) -> Dict:
        """Change admin password."""
        try:
            success = self.admin_model.change_password(admin_id, old_password, new_password)
            
            if success:
                admin = self.admin_model.get_by_id(admin_id)
                
                # Send security alert
                email_service = get_email_service()
                if email_service:
                    email_service.send_security_alert(
                        admin['email'],
                        "Password Changed",
                        f"Your password was changed at {now_vietnam().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                
                audit_log('password_change', {'admin_id': admin_id})
                
                return {"success": True, "message": "Password changed successfully"}
            
            return {"success": False, "error": "Invalid old password"}
            
        except ValueError as e:
            return {"success": False, "error": str(e)}
    
    def enable_2fa(self, admin_id: str, method: str = "email") -> Dict:
        """Enable 2FA for admin."""
        if method == "email":
            success = self.admin_model.enable_2fa(admin_id, method)
            
            if success:
                admin = self.admin_model.get_by_id(admin_id)
                
                # Send confirmation email
                email_service = get_email_service()
                if email_service:
                    email_service.send_security_alert(
                        admin['email'],
                        "2FA Enabled",
                        "Two-factor authentication has been enabled for your account"
                    )
                
                audit_log('2fa_enable', {'admin_id': admin_id, 'method': method})
                
                return {"success": True, "message": "2FA enabled successfully"}
            
            return {"success": False, "error": "Failed to enable 2FA"}
        
        return {"success": False, "error": "Unsupported 2FA method"}
    
    def disable_2fa(self, admin_id: str) -> Dict:
        """Disable 2FA for admin."""
        success = self.admin_model.disable_2fa(admin_id)
        
        if success:
            admin = self.admin_model.get_by_id(admin_id)
            
            # Send security alert
            email_service = get_email_service()
            if email_service:
                email_service.send_security_alert(
                    admin['email'],
                    "2FA Disabled",
                    "Two-factor authentication has been disabled for your account"
                )
            
            audit_log('2fa_disable', {'admin_id': admin_id})
            
            return {"success": True, "message": "2FA disabled successfully"}
        
        return {"success": False, "error": "Failed to disable 2FA"}
    
    def list_admins(self, tenant_id: str, skip: int = 0, limit: int = 50) -> Dict:
        """List all admins in tenant."""
        admins = self.admin_model.list_by_tenant(tenant_id, skip, limit)
        total = self.admin_model.count_by_tenant(tenant_id)
        
        return {
            "success": True,
            "admins": [self._sanitize_admin(a) for a in admins],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    def suspend_admin(self, admin_id: str, reason: str, suspended_by: str = None) -> Dict:
        """Suspend admin account."""
        success = self.admin_model.suspend_admin(admin_id, reason)
        
        if success:
            admin = self.admin_model.get_by_id(admin_id)
            
            audit_log('admin_suspended', {
                'admin_id': admin_id,
                'reason': reason,
                'suspended_by': suspended_by
            })
            
            return {"success": True, "message": "Admin suspended successfully"}
        
        return {"success": False, "error": "Failed to suspend admin"}
    
    def activate_admin(self, admin_id: str, activated_by: str = None) -> Dict:
        """Activate suspended admin."""
        success = self.admin_model.activate_admin(admin_id)
        
        if success:
            audit_log('admin_activated', {
                'admin_id': admin_id,
                'activated_by': activated_by
            })
            
            return {"success": True, "message": "Admin activated successfully"}
        
        return {"success": False, "error": "Failed to activate admin"}
    
    def _sanitize_admin(self, admin: Dict) -> Dict:
        """Remove sensitive fields from admin object."""
        if not admin:
            return None
        
        sanitized = dict(admin)
        sanitized.pop('password_hash', None)
        sanitized.pop('password_history', None)
        sanitized.pop('2fa_secret', None)
        
        # Convert ObjectId to string
        if '_id' in sanitized:
            sanitized['_id'] = str(sanitized['_id'])
        if 'tenant_id' in sanitized:
            sanitized['tenant_id'] = str(sanitized['tenant_id'])
        
        return sanitized
    
    def _sanitize_tenant(self, tenant: Dict) -> Dict:
        """Remove sensitive fields from tenant object."""
        if not tenant:
            return None
        
        sanitized = dict(tenant)
        
        # Convert ObjectId to string
        if '_id' in sanitized:
            sanitized['_id'] = str(sanitized['_id'])
        
        return sanitized
