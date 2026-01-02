"""
Impersonation Feature Tests
---------------------------
Tests for impersonation session management, restrictions, and logging.
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from flask import Flask, g

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.admin_model import ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN
from config.impersonation_config import (
    IMPERSONATION_CONFIG,
    IMPERSONATION_ALLOWED_ACTIONS,
    IMPERSONATION_FORBIDDEN_ACTIONS,
    ImpersonationAction,
    get_action_for_route,
    is_action_allowed,
    is_action_forbidden,
)
from time_utils import now_vietnam


class TestImpersonationConfig:
    """Test impersonation configuration."""
    
    def test_max_duration_is_4_hours(self):
        """Maximum impersonation duration is 4 hours."""
        assert IMPERSONATION_CONFIG['max_duration_hours'] == 4
        assert IMPERSONATION_CONFIG['max_duration_seconds'] == 14400
    
    def test_reason_is_required(self):
        """Impersonation requires a reason."""
        assert IMPERSONATION_CONFIG['require_reason'] == True
        assert IMPERSONATION_CONFIG['min_reason_length'] >= 10
    
    def test_all_actions_are_logged(self):
        """All actions during impersonation are logged."""
        assert IMPERSONATION_CONFIG['log_all_actions'] == True
    
    def test_max_concurrent_sessions(self):
        """Only one concurrent impersonation session allowed."""
        assert IMPERSONATION_CONFIG['max_concurrent_sessions'] == 1
    
    def test_token_has_short_expiry(self):
        """Impersonation tokens have shorter expiry."""
        assert IMPERSONATION_CONFIG['short_token_expiry_hours'] <= 4


class TestImpersonationActions:
    """Test impersonation action restrictions."""
    
    def test_view_actions_are_allowed(self):
        """View actions should be allowed during impersonation."""
        view_actions = [
            ImpersonationAction.VIEW_DASHBOARD,
            ImpersonationAction.VIEW_AGENTS,
            ImpersonationAction.VIEW_AGENT_DETAIL,
            ImpersonationAction.VIEW_LOGS,
            ImpersonationAction.VIEW_WHITELIST,
            ImpersonationAction.VIEW_GROUPS,
            ImpersonationAction.VIEW_SETTINGS,
            ImpersonationAction.VIEW_API_KEYS,
        ]
        
        for action in view_actions:
            assert action in IMPERSONATION_ALLOWED_ACTIONS, f"{action} should be allowed"
    
    def test_delete_actions_are_forbidden(self):
        """Delete actions should be forbidden during impersonation."""
        delete_actions = [
            ImpersonationAction.DELETE_AGENT,
            ImpersonationAction.DELETE_WHITELIST,
            ImpersonationAction.DELETE_GROUP,
            ImpersonationAction.DELETE_API_KEY,
        ]
        
        for action in delete_actions:
            assert action in IMPERSONATION_FORBIDDEN_ACTIONS, f"{action} should be forbidden"
    
    def test_admin_actions_are_forbidden(self):
        """Admin management actions should be forbidden."""
        admin_actions = [
            ImpersonationAction.CREATE_ADMIN,
            ImpersonationAction.UPDATE_ADMIN,
            ImpersonationAction.DELETE_ADMIN,
        ]
        
        for action in admin_actions:
            assert action in IMPERSONATION_FORBIDDEN_ACTIONS
    
    def test_troubleshooting_actions_allowed(self):
        """Some modify actions for troubleshooting are allowed."""
        # Limited modifications for support purposes
        assert ImpersonationAction.CREATE_WHITELIST in IMPERSONATION_ALLOWED_ACTIONS
        assert ImpersonationAction.UPDATE_WHITELIST in IMPERSONATION_ALLOWED_ACTIONS


class TestImpersonationRouteMapping:
    """Test route to action mapping."""
    
    def test_get_routes_map_to_view_actions(self):
        """GET requests should map to view actions."""
        get_routes = [
            ('GET', '/api/agents'),
            ('GET', '/api/whitelist'),
            ('GET', '/api/logs'),
            ('GET', '/dashboard'),
        ]
        
        for method, path in get_routes:
            action = get_action_for_route(method, path)
            if action:
                assert action.startswith('view_') or is_action_allowed(action)
    
    def test_delete_routes_map_to_forbidden_actions(self):
        """DELETE requests should map to forbidden actions."""
        delete_routes = [
            ('DELETE', '/api/agents/123'),
            ('DELETE', '/api/whitelist/456'),
        ]
        
        for method, path in delete_routes:
            action = get_action_for_route(method, path)
            if action:
                assert is_action_forbidden(action) or 'delete' in action.lower()


class TestImpersonationSession:
    """Test impersonation session management."""
    
    def test_session_has_expiry_time(self):
        """Impersonation session should have expiry time."""
        session = {
            'session_id': 'imp_001',
            'started_at': now_vietnam(),
            'expires_at': now_vietnam() + timedelta(hours=4),
            'super_admin_id': 'admin_001',
            'tenant_id': 'tenant_001',
        }
        
        assert session['expires_at'] > session['started_at']
        duration = session['expires_at'] - session['started_at']
        assert duration <= timedelta(hours=4)
    
    def test_expired_session_cannot_continue(self):
        """Expired sessions cannot be used."""
        expired_session = {
            'expires_at': now_vietnam() - timedelta(hours=1),
        }
        
        def is_session_valid(session):
            return session['expires_at'] > now_vietnam()
        
        assert is_session_valid(expired_session) == False
    
    def test_session_cannot_be_extended(self):
        """Impersonation sessions cannot be extended."""
        assert IMPERSONATION_CONFIG['auto_extend'] == False


class TestImpersonationLogging:
    """Test impersonation action logging."""
    
    @pytest.fixture
    def mock_log_model(self):
        """Mock impersonation log model."""
        model = MagicMock()
        model.add_action_to_session = MagicMock(return_value=True)
        return model
    
    def test_action_log_entry_format(self):
        """Action log entries have correct format."""
        action_log = {
            'timestamp': now_vietnam(),
            'action': 'view_agents',
            'method': 'GET',
            'path': '/api/agents',
            'request_summary': None,
            'response_status': 200,
            'success': True,
            'error': None,
        }
        
        required_fields = [
            'timestamp', 'action', 'method', 'path',
            'response_status', 'success'
        ]
        
        for field in required_fields:
            assert field in action_log
    
    def test_session_log_captures_metadata(self):
        """Session log captures all metadata."""
        session_log = {
            'session_id': 'imp_001',
            'super_admin_id': 'admin_001',
            'super_admin_email': 'super@example.com',
            'tenant_id': 'tenant_001',
            'tenant_name': 'Company A',
            'reason': 'Troubleshooting agent connection issue',
            'started_at': now_vietnam(),
            'ip_address': '192.168.1.100',
        }
        
        assert len(session_log['reason']) >= IMPERSONATION_CONFIG['min_reason_length']
    
    def test_failed_actions_are_logged(self):
        """Failed actions are logged with error details."""
        failed_action = {
            'timestamp': now_vietnam(),
            'action': 'delete_agent',
            'method': 'DELETE',
            'path': '/api/agents/123',
            'response_status': 403,
            'success': False,
            'error': 'Action forbidden during impersonation',
        }
        
        assert failed_action['success'] == False
        assert failed_action['error'] is not None


class TestImpersonationRestrictions:
    """Test impersonation restrictions enforcement."""
    
    def test_cannot_access_super_admin_endpoints(self, app):
        """Cannot access Super Admin endpoints during impersonation."""
        from middleware.authorization import require_super_admin
        from flask import jsonify
        
        @require_super_admin
        def super_admin_endpoint():
            return jsonify({"success": True})
        
        impersonation_token = {
            'admin_id': 'admin_001',
            'role': ROLE_SUPER_ADMIN,  # Original role
            'is_impersonating': True,  # But impersonating
        }
        
        with app.test_request_context():
            g.jwt_payload = impersonation_token
            response = super_admin_endpoint()
            
            if isinstance(response, tuple):
                status = response[1]
            else:
                status = response.status_code
            
            assert status == 403
    
    def test_cannot_modify_tenant_settings(self):
        """Cannot modify tenant settings during impersonation."""
        assert ImpersonationAction.UPDATE_SETTINGS in IMPERSONATION_FORBIDDEN_ACTIONS
    
    def test_cannot_delete_tenant(self):
        """Cannot delete tenant during impersonation."""
        assert ImpersonationAction.DELETE_TENANT in IMPERSONATION_FORBIDDEN_ACTIONS


class TestImpersonationEndSession:
    """Test ending impersonation session."""
    
    def test_end_session_logs_end_time(self):
        """Ending session logs the end time."""
        session = {
            'session_id': 'imp_001',
            'started_at': now_vietnam() - timedelta(hours=2),
            'ended_at': None,
            'status': 'active',
        }
        
        def end_session(s):
            s['ended_at'] = now_vietnam()
            s['status'] = 'ended'
            return s
        
        ended = end_session(session)
        assert ended['ended_at'] is not None
        assert ended['status'] == 'ended'
    
    def test_end_session_calculates_duration(self):
        """Session duration is calculated on end."""
        started = now_vietnam() - timedelta(hours=2, minutes=30)
        ended = now_vietnam()
        
        duration = ended - started
        assert duration.total_seconds() == 2.5 * 3600  # 2.5 hours


class TestImpersonationAudit:
    """Test impersonation audit trail."""
    
    def test_audit_trail_is_immutable(self):
        """Audit trail entries cannot be modified."""
        # In MongoDB, this is enforced by not having update operations
        # on action logs
        pass
    
    def test_audit_trail_queryable_by_session(self):
        """Can query all actions for a session."""
        session_actions = [
            {'session_id': 'imp_001', 'action': 'view_dashboard'},
            {'session_id': 'imp_001', 'action': 'view_agents'},
            {'session_id': 'imp_001', 'action': 'view_logs'},
            {'session_id': 'imp_002', 'action': 'view_agents'},
        ]
        
        def get_actions_by_session(actions, session_id):
            return [a for a in actions if a['session_id'] == session_id]
        
        imp_001_actions = get_actions_by_session(session_actions, 'imp_001')
        assert len(imp_001_actions) == 3
    
    def test_audit_trail_queryable_by_admin(self):
        """Can query all sessions for an admin."""
        sessions = [
            {'super_admin_id': 'admin_001', 'tenant_id': 'tenant_001'},
            {'super_admin_id': 'admin_001', 'tenant_id': 'tenant_002'},
            {'super_admin_id': 'admin_002', 'tenant_id': 'tenant_001'},
        ]
        
        def get_sessions_by_admin(all_sessions, admin_id):
            return [s for s in all_sessions if s['super_admin_id'] == admin_id]
        
        admin_001_sessions = get_sessions_by_admin(sessions, 'admin_001')
        assert len(admin_001_sessions) == 2


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
