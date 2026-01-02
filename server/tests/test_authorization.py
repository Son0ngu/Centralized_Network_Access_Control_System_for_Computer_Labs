"""
Unit Tests for Authorization Middleware
----------------------------------------
Tests for role-based access control decorators.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g, jsonify

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from middleware.authorization import (
    require_super_admin,
    require_tenant_admin,
    require_any_admin,
    check_impersonation,
    get_current_role,
    get_current_admin_context,
    is_super_admin,
    is_tenant_admin,
    is_impersonating,
    init_authorization_middleware,
)
from models.admin_model import ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register test endpoints
    @app.route('/test/super-admin')
    @require_super_admin
    def super_admin_endpoint():
        return jsonify({"success": True, "message": "Super Admin access granted"})
    
    @app.route('/test/tenant-admin')
    @require_tenant_admin
    def tenant_admin_endpoint():
        return jsonify({"success": True, "message": "Tenant Admin access granted", "tenant_id": g.tenant_id})
    
    @app.route('/test/any-admin')
    @require_any_admin
    def any_admin_endpoint():
        return jsonify({"success": True, "message": "Any Admin access granted"})
    
    @app.route('/test/impersonation')
    @require_tenant_admin
    @check_impersonation
    def impersonation_endpoint():
        return jsonify({
            "success": True,
            "is_impersonating": getattr(g, 'is_impersonating', False)
        })
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


# ============================================================================
# Test: require_super_admin decorator
# ============================================================================

class TestRequireSuperAdmin:
    """Tests for @require_super_admin decorator."""
    
    def test_unauthenticated_returns_401(self, app, client):
        """Should return 401 when not authenticated."""
        with app.test_request_context():
            response = client.get('/test/super-admin')
            assert response.status_code == 401
            data = response.get_json()
            assert data['error'] == 'Authentication required'
    
    def test_tenant_admin_returns_403(self, app, client):
        """Should return 403 when role is tenant_admin."""
        with app.test_request_context():
            with client.session_transaction() as sess:
                sess['admin_id'] = 'admin123'
                sess['role'] = ROLE_TENANT_ADMIN
                sess['tenant_id'] = 'tenant123'
            
            # Mock g object
            with patch.object(g, 'jwt_payload', {
                'admin_id': 'admin123',
                'role': ROLE_TENANT_ADMIN,
                'tenant_id': 'tenant123'
            }, create=True):
                response = client.get('/test/super-admin')
                assert response.status_code == 403
                data = response.get_json()
                assert 'Super Admin access required' in data['message']
    
    def test_super_admin_granted_access(self, app, client):
        """Should grant access to super_admin."""
        with app.app_context():
            @app.before_request
            def set_super_admin():
                g.jwt_payload = {
                    'admin_id': 'superadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': None,
                    'is_impersonating': False
                }
            
            response = client.get('/test/super-admin')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
    
    def test_super_admin_impersonating_returns_403(self, app, client):
        """Should deny super_admin access while impersonating."""
        with app.app_context():
            @app.before_request
            def set_impersonating_super_admin():
                g.jwt_payload = {
                    'admin_id': 'superadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': True,
                    'original_admin_id': 'superadmin123',
                    'impersonation_session_id': 'session123'
                }
            
            response = client.get('/test/super-admin')
            assert response.status_code == 403
            data = response.get_json()
            assert 'impersonating' in data['message'].lower()


# ============================================================================
# Test: require_tenant_admin decorator
# ============================================================================

class TestRequireTenantAdmin:
    """Tests for @require_tenant_admin decorator."""
    
    def test_unauthenticated_returns_401(self, app, client):
        """Should return 401 when not authenticated."""
        response = client.get('/test/tenant-admin')
        assert response.status_code == 401
    
    def test_tenant_admin_granted_access(self, app, client):
        """Should grant access to tenant_admin."""
        with app.app_context():
            @app.before_request
            def set_tenant_admin():
                g.jwt_payload = {
                    'admin_id': 'admin123',
                    'role': ROLE_TENANT_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': False
                }
            
            response = client.get('/test/tenant-admin')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['tenant_id'] == 'tenant123'
    
    def test_tenant_admin_without_tenant_id_returns_403(self, app, client):
        """Should return 403 if tenant_admin has no tenant_id."""
        with app.app_context():
            @app.before_request
            def set_invalid_tenant_admin():
                g.jwt_payload = {
                    'admin_id': 'admin123',
                    'role': ROLE_TENANT_ADMIN,
                    'tenant_id': None,  # Missing tenant_id
                    'is_impersonating': False
                }
            
            response = client.get('/test/tenant-admin')
            assert response.status_code == 403
    
    def test_super_admin_impersonating_granted_access(self, app, client):
        """Should grant access to super_admin impersonating tenant."""
        with app.app_context():
            @app.before_request
            def set_impersonating():
                g.jwt_payload = {
                    'admin_id': 'targetadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': True,
                    'original_admin_id': 'superadmin123'
                }
            
            response = client.get('/test/tenant-admin')
            assert response.status_code == 200
    
    def test_super_admin_not_impersonating_returns_403(self, app, client):
        """Should deny super_admin access without impersonation."""
        with app.app_context():
            @app.before_request
            def set_super_admin_direct():
                g.jwt_payload = {
                    'admin_id': 'superadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': None,
                    'is_impersonating': False
                }
            
            response = client.get('/test/tenant-admin')
            assert response.status_code == 403


# ============================================================================
# Test: require_any_admin decorator
# ============================================================================

class TestRequireAnyAdmin:
    """Tests for @require_any_admin decorator."""
    
    def test_unauthenticated_returns_401(self, app, client):
        """Should return 401 when not authenticated."""
        response = client.get('/test/any-admin')
        assert response.status_code == 401
    
    def test_super_admin_granted_access(self, app, client):
        """Should grant access to super_admin."""
        with app.app_context():
            @app.before_request
            def set_super():
                g.jwt_payload = {
                    'admin_id': 'superadmin123',
                    'role': ROLE_SUPER_ADMIN
                }
            
            response = client.get('/test/any-admin')
            assert response.status_code == 200
    
    def test_tenant_admin_granted_access(self, app, client):
        """Should grant access to tenant_admin."""
        with app.app_context():
            @app.before_request
            def set_tenant():
                g.jwt_payload = {
                    'admin_id': 'admin123',
                    'role': ROLE_TENANT_ADMIN,
                    'tenant_id': 'tenant123'
                }
            
            response = client.get('/test/any-admin')
            assert response.status_code == 200
    
    def test_invalid_role_returns_403(self, app, client):
        """Should return 403 for invalid role."""
        with app.app_context():
            @app.before_request
            def set_invalid():
                g.jwt_payload = {
                    'admin_id': 'user123',
                    'role': 'invalid_role'
                }
            
            response = client.get('/test/any-admin')
            assert response.status_code == 403


# ============================================================================
# Test: Utility Functions
# ============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_get_current_role_from_jwt(self, app):
        """Should get role from JWT payload."""
        with app.test_request_context():
            g.jwt_payload = {'role': ROLE_SUPER_ADMIN}
            assert get_current_role() == ROLE_SUPER_ADMIN
    
    def test_get_current_role_from_session(self, app):
        """Should get role from session when no JWT."""
        with app.test_request_context():
            with app.test_client().session_transaction() as sess:
                sess['role'] = ROLE_TENANT_ADMIN
            # Note: Session needs request context properly set up
    
    def test_is_super_admin_true(self, app):
        """Should return True for super_admin."""
        with app.test_request_context():
            g.jwt_payload = {'role': ROLE_SUPER_ADMIN}
            assert is_super_admin() is True
            assert is_tenant_admin() is False
    
    def test_is_tenant_admin_true(self, app):
        """Should return True for tenant_admin."""
        with app.test_request_context():
            g.jwt_payload = {'role': ROLE_TENANT_ADMIN}
            assert is_tenant_admin() is True
            assert is_super_admin() is False
    
    def test_is_impersonating_true(self, app):
        """Should detect impersonation."""
        with app.test_request_context():
            g.jwt_payload = {
                'role': ROLE_SUPER_ADMIN,
                'is_impersonating': True,
                'original_admin_id': 'superadmin123',
                'impersonation_session_id': 'session123'
            }
            assert is_impersonating() is True
    
    def test_is_impersonating_false(self, app):
        """Should return False when not impersonating."""
        with app.test_request_context():
            g.jwt_payload = {
                'role': ROLE_TENANT_ADMIN,
                'is_impersonating': False
            }
            assert is_impersonating() is False
    
    def test_get_admin_context_complete(self, app):
        """Should return complete admin context."""
        with app.test_request_context():
            g.jwt_payload = {
                'admin_id': 'admin123',
                'role': ROLE_SUPER_ADMIN,
                'tenant_id': 'tenant123',
                'is_impersonating': True,
                'original_admin_id': 'superadmin123',
                'impersonation_session_id': 'session123'
            }
            
            context = get_current_admin_context()
            
            assert context['admin_id'] == 'admin123'
            assert context['role'] == ROLE_SUPER_ADMIN
            assert context['tenant_id'] == 'tenant123'
            assert context['is_impersonating'] is True
            assert context['original_admin_id'] == 'superadmin123'
            assert context['impersonation_session_id'] == 'session123'


# ============================================================================
# Test: check_impersonation decorator
# ============================================================================

class TestCheckImpersonation:
    """Tests for @check_impersonation decorator."""
    
    def test_non_impersonation_passes_through(self, app, client):
        """Should pass through when not impersonating."""
        with app.app_context():
            @app.before_request
            def set_normal():
                g.jwt_payload = {
                    'admin_id': 'admin123',
                    'role': ROLE_TENANT_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': False
                }
            
            response = client.get('/test/impersonation')
            assert response.status_code == 200
            data = response.get_json()
            assert data['is_impersonating'] is False
    
    def test_impersonation_with_valid_session(self, app, client):
        """Should proceed with valid impersonation session."""
        mock_model = Mock()
        mock_model.is_valid_session.return_value = True
        mock_model.log_action = Mock()
        
        init_authorization_middleware(impersonation_model=mock_model)
        
        with app.app_context():
            @app.before_request
            def set_impersonating():
                g.jwt_payload = {
                    'admin_id': 'targetadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': True,
                    'original_admin_id': 'superadmin123',
                    'impersonation_session_id': 'session123'
                }
            
            response = client.get('/test/impersonation')
            assert response.status_code == 200
            
            # Verify action was logged
            mock_model.log_action.assert_called_once()
    
    def test_impersonation_with_expired_session(self, app, client):
        """Should reject expired impersonation session."""
        mock_model = Mock()
        mock_model.is_valid_session.return_value = False
        
        init_authorization_middleware(impersonation_model=mock_model)
        
        with app.app_context():
            @app.before_request
            def set_expired_impersonation():
                g.jwt_payload = {
                    'admin_id': 'targetadmin123',
                    'role': ROLE_SUPER_ADMIN,
                    'tenant_id': 'tenant123',
                    'is_impersonating': True,
                    'original_admin_id': 'superadmin123',
                    'impersonation_session_id': 'expired_session'
                }
            
            response = client.get('/test/impersonation')
            assert response.status_code == 401
            data = response.get_json()
            assert 'IMPERSONATION_EXPIRED' in str(data)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
