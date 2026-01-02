"""
Pytest Configuration and Fixtures
----------------------------------
Shared test fixtures for all test modules.
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from flask import Flask, g

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from time_utils import now_vietnam
from models.admin_model import ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN


# ==============================================================================
# Mock Objects
# ==============================================================================

class MockDB:
    """Mock MongoDB database."""
    def __init__(self):
        self.collections = {}
    
    def __getattr__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]


class MockCollection:
    """Mock MongoDB collection."""
    def __init__(self):
        self.data = []
    
    def find(self, query=None):
        return MockCursor(self.data)
    
    def find_one(self, query):
        for doc in self.data:
            if self._matches(doc, query):
                return doc
        return None
    
    def insert_one(self, doc):
        from bson import ObjectId
        doc['_id'] = ObjectId()
        self.data.append(doc)
        return MagicMock(inserted_id=doc['_id'])
    
    def update_one(self, query, update):
        for doc in self.data:
            if self._matches(doc, query):
                if '$set' in update:
                    doc.update(update['$set'])
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)
    
    def delete_one(self, query):
        for i, doc in enumerate(self.data):
            if self._matches(doc, query):
                del self.data[i]
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)
    
    def count_documents(self, query=None):
        if not query:
            return len(self.data)
        return sum(1 for doc in self.data if self._matches(doc, query))
    
    def create_index(self, *args, **kwargs):
        pass
    
    def _matches(self, doc, query):
        if not query:
            return True
        for key, value in query.items():
            if key not in doc:
                return False
            if doc[key] != value:
                return False
        return True


class MockCursor:
    """Mock MongoDB cursor."""
    def __init__(self, data):
        self.data = data
        self._limit = None
        self._skip = 0
        self._sort_key = None
        self._sort_order = 1
    
    def sort(self, *args):
        return self
    
    def skip(self, n):
        self._skip = n
        return self
    
    def limit(self, n):
        self._limit = n
        return self
    
    def __iter__(self):
        data = self.data[self._skip:]
        if self._limit:
            data = data[:self._limit]
        return iter(data)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db():
    """Mock database fixture."""
    return MockDB()


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def super_admin_token():
    """Generate a mock Super Admin JWT token payload."""
    return {
        'sub': 'super_admin_001',
        'admin_id': 'super_admin_001',
        'email': 'superadmin@system.local',
        'role': ROLE_SUPER_ADMIN,
        'tenant_id': None,
        'is_impersonating': False,
        'exp': (now_vietnam() + timedelta(hours=24)).timestamp(),
        'iat': now_vietnam().timestamp(),
    }


@pytest.fixture
def tenant_admin_token():
    """Generate a mock Tenant Admin JWT token payload."""
    return {
        'sub': 'tenant_admin_001',
        'admin_id': 'tenant_admin_001',
        'email': 'admin@tenant1.com',
        'role': ROLE_TENANT_ADMIN,
        'tenant_id': 'tenant_001',
        'is_impersonating': False,
        'exp': (now_vietnam() + timedelta(hours=24)).timestamp(),
        'iat': now_vietnam().timestamp(),
    }


@pytest.fixture
def tenant_admin_b_token():
    """Generate a mock Tenant Admin B JWT token (different tenant)."""
    return {
        'sub': 'tenant_admin_002',
        'admin_id': 'tenant_admin_002',
        'email': 'admin@tenant2.com',
        'role': ROLE_TENANT_ADMIN,
        'tenant_id': 'tenant_002',
        'is_impersonating': False,
        'exp': (now_vietnam() + timedelta(hours=24)).timestamp(),
        'iat': now_vietnam().timestamp(),
    }


@pytest.fixture
def impersonation_token():
    """Generate a mock impersonation token payload."""
    return {
        'sub': 'super_admin_001',
        'admin_id': 'super_admin_001',
        'email': 'superadmin@system.local',
        'role': ROLE_TENANT_ADMIN,  # Acting as tenant admin
        'tenant_id': 'tenant_001',
        'is_impersonating': True,
        'original_admin_id': 'super_admin_001',
        'impersonation_session_id': 'imp_session_001',
        'exp': (now_vietnam() + timedelta(hours=4)).timestamp(),  # Short expiry
        'iat': now_vietnam().timestamp(),
    }


@pytest.fixture
def expired_impersonation_token():
    """Generate an expired impersonation token."""
    return {
        'sub': 'super_admin_001',
        'admin_id': 'super_admin_001',
        'role': ROLE_TENANT_ADMIN,
        'tenant_id': 'tenant_001',
        'is_impersonating': True,
        'original_admin_id': 'super_admin_001',
        'impersonation_session_id': 'imp_session_expired',
        'exp': (now_vietnam() - timedelta(hours=1)).timestamp(),  # Expired
        'iat': (now_vietnam() - timedelta(hours=5)).timestamp(),
    }


@pytest.fixture
def mock_jwt_service():
    """Mock JWT service."""
    service = MagicMock()
    service.validate_token.return_value = (True, None)
    service.decode_token.return_value = {}
    return service


@pytest.fixture
def sample_agents():
    """Sample agent data for different tenants."""
    from bson import ObjectId
    return [
        {
            '_id': ObjectId(),
            'agent_id': 'agent_tenant1_001',
            'hostname': 'PC-TENANT1-001',
            'tenant_id': 'tenant_001',
            'status': 'active',
            'created_at': now_vietnam(),
        },
        {
            '_id': ObjectId(),
            'agent_id': 'agent_tenant1_002',
            'hostname': 'PC-TENANT1-002',
            'tenant_id': 'tenant_001',
            'status': 'inactive',
            'created_at': now_vietnam(),
        },
        {
            '_id': ObjectId(),
            'agent_id': 'agent_tenant2_001',
            'hostname': 'PC-TENANT2-001',
            'tenant_id': 'tenant_002',
            'status': 'active',
            'created_at': now_vietnam(),
        },
    ]


@pytest.fixture
def sample_whitelist():
    """Sample whitelist entries for different tenants."""
    from bson import ObjectId
    return [
        {
            '_id': ObjectId(),
            'domain': 'google.com',
            'type': 'domain',
            'tenant_id': 'tenant_001',
            'added_date': now_vietnam(),
        },
        {
            '_id': ObjectId(),
            'domain': 'facebook.com',
            'type': 'domain',
            'tenant_id': 'tenant_002',
            'added_date': now_vietnam(),
        },
    ]


# ==============================================================================
# Helper Functions
# ==============================================================================

def set_g_jwt_payload(app, payload):
    """Set g.jwt_payload for testing authorization."""
    with app.test_request_context():
        g.jwt_payload = payload
        yield


def create_auth_header(token_string='test_token'):
    """Create authorization header."""
    return {'Authorization': f'Bearer {token_string}'}
