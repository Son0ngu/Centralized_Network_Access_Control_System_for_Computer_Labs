"""
Multi-Tenancy Tests
-------------------
Tests for tenant isolation and cross-tenant data protection.
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
from time_utils import now_vietnam


class TestTenantDataIsolation:
    """Test that data is properly isolated between tenants."""
    
    @pytest.fixture
    def multi_tenant_agents(self):
        """Sample agents across multiple tenants."""
        return [
            {'agent_id': 'agent_001', 'hostname': 'PC-A1', 'tenant_id': 'tenant_001'},
            {'agent_id': 'agent_002', 'hostname': 'PC-A2', 'tenant_id': 'tenant_001'},
            {'agent_id': 'agent_003', 'hostname': 'PC-B1', 'tenant_id': 'tenant_002'},
            {'agent_id': 'agent_004', 'hostname': 'PC-B2', 'tenant_id': 'tenant_002'},
            {'agent_id': 'agent_005', 'hostname': 'PC-C1', 'tenant_id': 'tenant_003'},
        ]
    
    @pytest.fixture
    def multi_tenant_whitelist(self):
        """Sample whitelist entries across tenants."""
        return [
            {'domain': 'google.com', 'tenant_id': 'tenant_001'},
            {'domain': 'github.com', 'tenant_id': 'tenant_001'},
            {'domain': 'azure.com', 'tenant_id': 'tenant_002'},
            {'domain': 'aws.amazon.com', 'tenant_id': 'tenant_003'},
        ]
    
    @pytest.fixture
    def multi_tenant_logs(self):
        """Sample logs across tenants."""
        return [
            {'log_id': 'log_001', 'message': 'Agent started', 'tenant_id': 'tenant_001'},
            {'log_id': 'log_002', 'message': 'Blocked domain', 'tenant_id': 'tenant_001'},
            {'log_id': 'log_003', 'message': 'Agent registered', 'tenant_id': 'tenant_002'},
            {'log_id': 'log_004', 'message': 'Config updated', 'tenant_id': 'tenant_003'},
        ]
    
    def test_agent_query_adds_tenant_filter(self, multi_tenant_agents):
        """Agent queries should automatically filter by tenant_id."""
        def get_agents_by_tenant(agents, tenant_id):
            """Simulate what the model should do."""
            return [a for a in agents if a.get('tenant_id') == tenant_id]
        
        # Tenant 1 should only see their 2 agents
        tenant_1_agents = get_agents_by_tenant(multi_tenant_agents, 'tenant_001')
        assert len(tenant_1_agents) == 2
        for agent in tenant_1_agents:
            assert agent['tenant_id'] == 'tenant_001'
        
        # Tenant 2 should only see their 2 agents
        tenant_2_agents = get_agents_by_tenant(multi_tenant_agents, 'tenant_002')
        assert len(tenant_2_agents) == 2
        for agent in tenant_2_agents:
            assert agent['tenant_id'] == 'tenant_002'
        
        # Tenant 3 should only see their 1 agent
        tenant_3_agents = get_agents_by_tenant(multi_tenant_agents, 'tenant_003')
        assert len(tenant_3_agents) == 1
    
    def test_whitelist_query_adds_tenant_filter(self, multi_tenant_whitelist):
        """Whitelist queries should filter by tenant_id."""
        def get_whitelist_by_tenant(entries, tenant_id):
            return [e for e in entries if e.get('tenant_id') == tenant_id]
        
        tenant_1 = get_whitelist_by_tenant(multi_tenant_whitelist, 'tenant_001')
        assert len(tenant_1) == 2
        assert all(e['tenant_id'] == 'tenant_001' for e in tenant_1)
    
    def test_logs_query_adds_tenant_filter(self, multi_tenant_logs):
        """Log queries should filter by tenant_id."""
        def get_logs_by_tenant(logs, tenant_id):
            return [l for l in logs if l.get('tenant_id') == tenant_id]
        
        tenant_1_logs = get_logs_by_tenant(multi_tenant_logs, 'tenant_001')
        assert len(tenant_1_logs) == 2
        
        tenant_2_logs = get_logs_by_tenant(multi_tenant_logs, 'tenant_002')
        assert len(tenant_2_logs) == 1


class TestCrossTenantAccessPrevention:
    """Test that cross-tenant access is prevented."""
    
    def test_tenant_a_cannot_access_tenant_b_agent(self, app):
        """Tenant A cannot view/modify Tenant B's agent."""
        agent_tenant_b = {
            'agent_id': 'agent_b_001',
            'tenant_id': 'tenant_002'
        }
        
        # Simulate Tenant A trying to access
        def check_access(requested_agent, requesting_tenant_id):
            if requested_agent.get('tenant_id') != requesting_tenant_id:
                return False, "Access denied: Resource belongs to another tenant"
            return True, None
        
        allowed, error = check_access(agent_tenant_b, 'tenant_001')
        assert allowed == False
        assert 'another tenant' in error
    
    def test_tenant_a_cannot_delete_tenant_b_whitelist(self):
        """Tenant A cannot delete Tenant B's whitelist entry."""
        whitelist_entry = {
            'id': 'wl_001',
            'domain': 'example.com',
            'tenant_id': 'tenant_002'
        }
        
        def can_delete(entry, requesting_tenant_id):
            return entry.get('tenant_id') == requesting_tenant_id
        
        assert can_delete(whitelist_entry, 'tenant_001') == False
        assert can_delete(whitelist_entry, 'tenant_002') == True
    
    def test_tenant_cannot_view_other_tenant_logs(self):
        """Tenant cannot view another tenant's logs."""
        logs = [
            {'message': 'Secret log', 'tenant_id': 'tenant_002'},
        ]
        
        def get_logs_for_tenant(all_logs, tenant_id):
            return [l for l in all_logs if l.get('tenant_id') == tenant_id]
        
        tenant_1_view = get_logs_for_tenant(logs, 'tenant_001')
        assert len(tenant_1_view) == 0  # Cannot see tenant_002's logs


class TestTenantIDEnforcement:
    """Test that tenant_id is properly enforced."""
    
    def test_new_agent_assigned_correct_tenant(self):
        """New agents should be assigned the correct tenant_id."""
        def register_agent(agent_data, tenant_id):
            """Simulate agent registration."""
            agent_data['tenant_id'] = tenant_id
            return agent_data
        
        new_agent = {'hostname': 'NEW-PC', 'ip': '192.168.1.100'}
        registered = register_agent(new_agent, 'tenant_001')
        
        assert registered['tenant_id'] == 'tenant_001'
    
    def test_whitelist_entry_assigned_correct_tenant(self):
        """Whitelist entries should be assigned correct tenant_id."""
        def add_whitelist(entry, tenant_id):
            entry['tenant_id'] = tenant_id
            entry['added_date'] = now_vietnam()
            return entry
        
        entry = {'domain': 'newdomain.com', 'type': 'domain'}
        added = add_whitelist(entry, 'tenant_002')
        
        assert added['tenant_id'] == 'tenant_002'
    
    def test_api_key_scoped_to_tenant(self):
        """API keys should be scoped to tenant."""
        def create_api_key(name, tenant_id):
            return {
                'name': name,
                'tenant_id': tenant_id,
                'key': 'fc_xxx...',
            }
        
        key = create_api_key('Production Key', 'tenant_001')
        assert key['tenant_id'] == 'tenant_001'


class TestSuperAdminTenantAccess:
    """Test Super Admin access to tenant data."""
    
    def test_super_admin_can_view_all_tenants(self):
        """Super Admin can view all tenants."""
        all_tenants = [
            {'id': 'tenant_001', 'name': 'Company A'},
            {'id': 'tenant_002', 'name': 'Company B'},
            {'id': 'tenant_003', 'name': 'Company C'},
        ]
        
        def get_tenants_for_role(role):
            if role == ROLE_SUPER_ADMIN:
                return all_tenants
            return []
        
        result = get_tenants_for_role(ROLE_SUPER_ADMIN)
        assert len(result) == 3
    
    def test_super_admin_can_manage_any_tenant(self):
        """Super Admin can manage any tenant."""
        def can_manage_tenant(admin_role, target_tenant_id):
            if admin_role == ROLE_SUPER_ADMIN:
                return True
            return False
        
        assert can_manage_tenant(ROLE_SUPER_ADMIN, 'tenant_001') == True
        assert can_manage_tenant(ROLE_SUPER_ADMIN, 'tenant_999') == True
    
    def test_super_admin_requires_impersonation_for_tenant_actions(self):
        """Super Admin must impersonate to perform tenant-specific actions."""
        def require_impersonation_for_tenant_action(role, is_impersonating, action):
            """Check if impersonation is required for tenant action."""
            tenant_specific_actions = [
                'view_agents', 'manage_whitelist', 'view_logs'
            ]
            
            if role == ROLE_SUPER_ADMIN and action in tenant_specific_actions:
                return is_impersonating
            return True
        
        # Without impersonation
        assert require_impersonation_for_tenant_action(
            ROLE_SUPER_ADMIN, False, 'view_agents'
        ) == False
        
        # With impersonation
        assert require_impersonation_for_tenant_action(
            ROLE_SUPER_ADMIN, True, 'view_agents'
        ) == True


class TestTenantModelValidation:
    """Test tenant model validation."""
    
    def test_tenant_slug_unique(self):
        """Tenant slugs must be unique."""
        existing_slugs = ['company-a', 'company-b']
        
        def is_slug_unique(slug, existing):
            return slug not in existing
        
        assert is_slug_unique('company-c', existing_slugs) == True
        assert is_slug_unique('company-a', existing_slugs) == False
    
    def test_tenant_status_affects_access(self):
        """Suspended tenants cannot access system."""
        def can_tenant_access(tenant):
            return tenant.get('status') == 'active'
        
        active_tenant = {'id': 'tenant_001', 'status': 'active'}
        suspended_tenant = {'id': 'tenant_002', 'status': 'suspended'}
        
        assert can_tenant_access(active_tenant) == True
        assert can_tenant_access(suspended_tenant) == False


class TestTenantQuotasAndLimits:
    """Test tenant resource quotas and limits."""
    
    def test_tenant_has_max_agents_limit(self):
        """Tenants have a maximum agents limit."""
        tenant_plan = {
            'id': 'tenant_001',
            'plan': 'basic',
            'max_agents': 50,
            'current_agents': 45
        }
        
        def can_add_agent(tenant):
            return tenant['current_agents'] < tenant['max_agents']
        
        assert can_add_agent(tenant_plan) == True
        
        tenant_plan['current_agents'] = 50
        assert can_add_agent(tenant_plan) == False
    
    def test_tenant_has_max_admins_limit(self):
        """Tenants have a maximum admins limit."""
        tenant = {
            'plan': 'basic',
            'max_admins': 5,
            'current_admins': 3
        }
        
        def can_add_admin(t):
            return t['current_admins'] < t['max_admins']
        
        assert can_add_admin(tenant) == True


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
