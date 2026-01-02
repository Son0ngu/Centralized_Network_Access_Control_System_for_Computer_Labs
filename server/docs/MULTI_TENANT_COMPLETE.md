# Firewall Controller - Multi-Tenant Authorization System

## Complete Project Documentation

**Version:** 2.0.0  
**Last Updated:** January 2, 2026  
**Status:** Production Ready ✅

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Phase Implementation Summary](#phase-implementation-summary)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Security Features](#security-features)
7. [UI/UX Components](#uiux-components)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Configuration](#configuration)

---

## Project Overview

### Description

Firewall Controller là một hệ thống quản lý firewall tập trung với khả năng multi-tenant, cho phép:

- **Super Admin**: Quản lý toàn bộ platform, các tenants, và có khả năng impersonate tenant admins
- **Tenant Admin**: Quản lý agents, whitelist, logs trong phạm vi tenant của mình

### Key Features

| Feature | Description |
|---------|-------------|
| 🏢 Multi-Tenancy | Hoàn toàn isolated data giữa các tenants |
| 👤 Role-Based Access | Super Admin & Tenant Admin roles |
| 🎭 Impersonation | Super Admin có thể view-as tenant để hỗ trợ |
| 📢 System Broadcasts | Thông báo từ Super Admin đến tất cả tenants |
| 🔐 Security | JWT auth, rate limiting, input sanitization |
| 📊 Audit Logging | Ghi log đầy đủ mọi thao tác |

### Technology Stack

```
Backend:
├── Python 3.12
├── Flask 2.x
├── MongoDB (PyMongo)
├── Socket.IO
└── JWT Authentication

Frontend:
├── HTML5 / CSS3
├── Bootstrap 5.3
├── JavaScript (Vanilla)
└── Font Awesome 6

Testing:
├── Pytest
└── 89 automated tests
```

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FIREWALL CONTROLLER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ Super Admin  │     │ Tenant Admin │     │    Agent     │    │
│  │   Dashboard  │     │   Dashboard  │     │   (Client)   │    │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘    │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Flask Application                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │ Controllers │  │ Middleware  │  │  Services   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                       MongoDB                            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐   │   │
│  │  │ admins  │ │ tenants │ │ agents  │ │ whitelists  │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
server/
├── app.py                      # Main application entry
├── time_utils.py               # Timezone utilities (Vietnam)
├── config/
│   ├── security_config.py      # Security settings
│   ├── impersonation_config.py # Impersonation rules
│   └── broadcast_config.py     # Broadcast settings
├── controllers/
│   ├── admin_controller.py     # Admin auth & management
│   ├── super_admin_controller.py # Super Admin APIs
│   ├── impersonation_controller.py # Impersonation APIs
│   ├── broadcast_controller.py # Broadcast APIs
│   ├── agent_controller.py     # Agent management
│   ├── whitelist_controller.py # Whitelist management
│   └── ...
├── middleware/
│   ├── auth.py                 # JWT & API key auth
│   ├── authorization.py        # Role-based access control
│   ├── impersonation.py        # Impersonation handling
│   └── security.py             # Input sanitization, rate limiting
├── models/
│   ├── admin_model.py          # Admin users
│   ├── tenant_model.py         # Tenants/Organizations
│   ├── impersonation_log_model.py # Impersonation audit
│   ├── broadcast_model.py      # System broadcasts
│   ├── agent_model.py          # Firewall agents
│   └── ...
├── services/
│   ├── admin_service.py        # Admin business logic
│   ├── jwt_service.py          # Token management
│   ├── broadcast_service.py    # Broadcast logic
│   └── ...
├── views/
│   ├── templates/
│   │   ├── base.html           # Tenant Admin base
│   │   └── super_admin/
│   │       ├── base_super.html # Super Admin base
│   │       ├── dashboard.html
│   │       ├── tenants.html
│   │       ├── broadcasts.html
│   │       └── ...
│   └── static/
│       ├── css/
│       ├── js/
│       │   ├── admin.js
│       │   ├── impersonation.js
│       │   └── broadcast.js
│       └── ...
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── test_authorization.py   # 23 tests
│   ├── test_security.py        # 25 tests
│   ├── test_multi_tenancy.py   # 16 tests
│   ├── test_impersonation.py   # 25 tests
│   └── security_audit.py       # Automated audit
└── docs/
    ├── PHASE7_TESTING_AUDIT.md
    └── MULTI_TENANT_COMPLETE.md (this file)
```

---

## Phase Implementation Summary

### Phase 1: Database Schema & Models ✅

**Deliverables:**
- `AdminModel` với roles (super_admin, tenant_admin)
- `TenantModel` cho organizations
- `ImpersonationLogModel` cho audit trail
- `BroadcastModel` cho system notifications

**Key Changes:**
```python
# Admin roles
ROLE_SUPER_ADMIN = "super_admin"
ROLE_TENANT_ADMIN = "tenant_admin"

# Admin document structure
{
    "_id": ObjectId,
    "email": str,
    "password_hash": str,
    "role": "super_admin" | "tenant_admin",
    "tenant_id": ObjectId | None,  # None for super_admin
    "full_name": str,
    "status": "active" | "suspended",
    "created_at": datetime,
}
```

---

### Phase 2: Authorization Middleware ✅

**Deliverables:**
- `@require_super_admin` decorator
- `@require_tenant_admin` decorator  
- `@require_any_admin` decorator
- Impersonation context handling

**Usage:**
```python
from middleware.authorization import require_super_admin, require_tenant_admin

@app.route('/api/super/tenants')
@require_super_admin
def list_tenants():
    # Only Super Admin can access
    pass

@app.route('/api/agents')
@require_tenant_admin
def list_agents():
    # Tenant Admin or impersonating Super Admin
    tenant_id = g.tenant_id  # Auto-set
    pass
```

---

### Phase 3: Super Admin Dashboard & APIs ✅

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/super-admin/` | Dashboard |
| GET | `/super-admin/tenants` | Tenant list page |
| GET | `/super-admin/health` | System health |
| GET | `/api/super/tenants` | List all tenants |
| POST | `/api/super/tenants` | Create tenant |
| PATCH | `/api/super/tenants/<id>` | Update tenant |
| POST | `/api/super/tenants/<id>/suspend` | Suspend tenant |
| GET | `/api/super/stats` | Platform statistics |

---

### Phase 4: Impersonation Feature ✅

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/super/impersonate/<tenant_id>` | Start impersonation |
| POST | `/api/impersonation/end` | End session |
| GET | `/api/impersonation/status` | Check status |
| GET | `/super-admin/impersonation-logs` | View logs |
| GET | `/api/super/impersonation/logs` | API logs |

**Configuration:**
```python
IMPERSONATION_CONFIG = {
    "max_duration_hours": 4,        # Auto-expire
    "require_reason": True,         # Must provide reason
    "min_reason_length": 10,
    "log_all_actions": True,        # Full audit trail
    "max_concurrent_sessions": 1,
}
```

**Restrictions:**
- ✅ View operations allowed
- ✅ Create/Update whitelist allowed (troubleshooting)
- ❌ Delete operations forbidden
- ❌ Admin management forbidden
- ❌ Tenant settings forbidden

---

### Phase 5: System Broadcast Feature ✅

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/super-admin/broadcasts` | Manage broadcasts |
| GET | `/api/super/broadcasts` | List all broadcasts |
| POST | `/api/super/broadcasts` | Create broadcast |
| PATCH | `/api/super/broadcasts/<id>` | Update |
| DELETE | `/api/super/broadcasts/<id>` | Delete |
| GET | `/api/broadcasts/active` | Active for tenant |
| POST | `/api/broadcasts/<id>/dismiss` | Dismiss |

**Broadcast Types:**
```python
BROADCAST_TYPES = {
    "info": {
        "bgClass": "alert-info",
        "icon": "fa-info-circle",
        "dismissible": True,
    },
    "warning": {
        "bgClass": "alert-warning",
        "icon": "fa-exclamation-triangle",
        "dismissible": True,
    },
    "danger": {
        "bgClass": "alert-danger",
        "icon": "fa-exclamation-circle",
        "dismissible": False,  # Cannot dismiss
    },
}
```

---

### Phase 6: UI/UX Updates ✅

**Components:**

1. **Super Admin Layout** (`base_super.html`)
   - Fixed sidebar navigation (250px)
   - Dark gradient theme
   - Sections: Platform, Communication, Audit, Settings
   - Mobile-responsive with hamburger menu

2. **Login Redirect**
   - Super Admin → `/super-admin/`
   - Tenant Admin → `/dashboard`

3. **Impersonation Banner** (`impersonation.js`)
   - Fixed red gradient at top
   - Shows tenant name, session ID, timer
   - Exit button with confirmation
   - Marks restricted actions

4. **Broadcast Banner** (`broadcast.js`)
   - Auto-loads active broadcasts
   - WebSocket for real-time updates
   - Dismiss tracking

5. **Responsive Design**
   - Mobile breakpoints: 768px, 576px
   - Sidebar collapse on mobile
   - Touch-friendly buttons

---

### Phase 7: Testing & Security Audit ✅

**Test Results:**

| Suite | Tests | Status |
|-------|-------|--------|
| Authorization | 23 | ✅ PASSED |
| Security | 25 | ✅ PASSED |
| Multi-Tenancy | 16 | ✅ PASSED |
| Impersonation | 25 | ✅ PASSED |
| **Total** | **89** | **✅ ALL PASSED** |

**Security Score: 80%**

---

## Database Schema

### Collections

#### admins
```javascript
{
    _id: ObjectId,
    email: String (unique),
    password_hash: String,
    role: "super_admin" | "tenant_admin",
    tenant_id: ObjectId | null,
    full_name: String,
    status: "active" | "suspended" | "pending",
    two_factor_enabled: Boolean,
    last_login: Date,
    login_attempts: Number,
    created_at: Date,
    updated_at: Date,
}
```

#### tenants
```javascript
{
    _id: ObjectId,
    name: String,
    slug: String (unique),
    status: "active" | "suspended" | "trial",
    plan: "free" | "basic" | "premium" | "enterprise",
    settings: {
        max_agents: Number,
        max_admins: Number,
        features: [String],
    },
    contact_email: String,
    created_at: Date,
    suspended_at: Date,
    suspension_reason: String,
}
```

#### impersonation_logs
```javascript
{
    _id: ObjectId,
    session_id: String (unique),
    super_admin_id: ObjectId,
    super_admin_email: String,
    tenant_id: ObjectId,
    tenant_name: String,
    reason: String,
    started_at: Date,
    ended_at: Date,
    expires_at: Date,
    status: "active" | "ended" | "expired",
    ip_address: String,
    user_agent: String,
    actions: [{
        timestamp: Date,
        action: String,
        method: String,
        path: String,
        response_status: Number,
        success: Boolean,
    }],
}
```

#### broadcasts
```javascript
{
    _id: ObjectId,
    title: String,
    message: String,
    type: "info" | "warning" | "danger",
    priority: Number,
    is_active: Boolean,
    start_date: Date,
    end_date: Date,
    target_tenants: [ObjectId] | null,  // null = all
    created_by: ObjectId,
    dismissed_by: [{
        admin_id: ObjectId,
        dismissed_at: Date,
    }],
    created_at: Date,
    updated_at: Date,
}
```

---

## API Reference

### Authentication

#### Login
```http
POST /api/admin/login
Content-Type: application/json

{
    "email": "admin@example.com",
    "password": "SecurePass123!"
}

Response:
{
    "success": true,
    "data": {
        "access_token": "eyJ...",
        "refresh_token": "eyJ...",
        "admin": { "id", "email", "role", "full_name" },
        "tenant": { "id", "name", "slug" }  // if tenant_admin
    }
}
```

#### Refresh Token
```http
POST /api/auth/refresh
Authorization: Bearer <refresh_token>

Response:
{
    "success": true,
    "data": {
        "access_token": "eyJ...",
        "refresh_token": "eyJ..."
    }
}
```

### Super Admin APIs

All require `Authorization: Bearer <token>` with `role: super_admin`

#### List Tenants
```http
GET /api/super/tenants?page=1&limit=20&status=active

Response:
{
    "success": true,
    "data": {
        "tenants": [...],
        "pagination": { "page", "limit", "total", "pages" }
    }
}
```

#### Start Impersonation
```http
POST /api/super/impersonate/<tenant_id>
Content-Type: application/json

{
    "reason": "User reported issue with whitelist sync"
}

Response:
{
    "success": true,
    "data": {
        "impersonation_token": "eyJ...",
        "session_id": "imp_xxx",
        "tenant": { "id", "name" },
        "expires_at": "2026-01-02T18:00:00+07:00"
    }
}
```

### Tenant Admin APIs

All require `Authorization: Bearer <token>` with valid `tenant_id`

#### List Agents
```http
GET /api/agents

Response:
{
    "success": true,
    "data": {
        "agents": [...],
        "statistics": { "total", "active", "inactive" }
    }
}
```

---

## Security Features

### 1. Authentication
- JWT tokens (access: 24h, refresh: 7d)
- 2FA support via email
- Bcrypt password hashing

### 2. Authorization
- Role-based decorators
- Tenant isolation
- Impersonation restrictions

### 3. Input Validation
```python
# NoSQL injection prevention
InputSanitizer.sanitize_nosql(data)
# Blocks: $gt, $ne, $where, $regex, etc.

# XSS prevention
InputSanitizer.sanitize_string(value)
# HTML escapes, length limits

# Universal sanitizer
InputSanitizer.sanitize_input(value)
```

### 4. Rate Limiting
```python
RATE_LIMIT_CONFIG = {
    "login": {"requests": 5, "window": 300},
    "register": {"requests": 5, "window": 300},
    "api_call": {"requests": 100, "window": 60},
}
```

### 5. Password Policy
```python
PASSWORD_CONFIG = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_special": True,
    "max_length": 128,
}
```

### 6. Security Headers
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## UI/UX Components

### Super Admin Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  🛡️ Firewall Controller  [Super Admin]           👤 Admin ▼│
├────────────┬────────────────────────────────────────────────┤
│            │                                                │
│ PLATFORM   │    📊 Dashboard                               │
│ ─────────  │                                                │
│ 📊 Dash    │    ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│ 🏢 Tenants │    │ Tenants │ │ Agents  │ │ Active  │       │
│ 💓 Health  │    │   12    │ │   156   │ │   89    │       │
│            │    └─────────┘ └─────────┘ └─────────┘       │
│ COMMS      │                                                │
│ ─────────  │    Recent Activity                            │
│ 📢 Bcasts  │    ├─ Tenant "Corp A" created                │
│            │    ├─ Impersonation session ended             │
│ AUDIT      │    └─ New broadcast published                 │
│ ─────────  │                                                │
│ 🎭 Imp.Log │                                                │
│            │                                                │
│ SETTINGS   │                                                │
│ ─────────  │                                                │
│ ⚙️ Config  │                                                │
│            │                                                │
│ [Logout]   │                                                │
└────────────┴────────────────────────────────────────────────┘
```

### Impersonation Banner

```
┌─────────────────────────────────────────────────────────────┐
│ 🎭 IMPERSONATION MODE                                       │
│ Viewing as: Company ABC | Session: imp_abc123 | ⏱️ 3:45:00 │
│                                    [End Impersonation]      │
└─────────────────────────────────────────────────────────────┘
```

### Broadcast Alert

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ System Maintenance                                    ✕  │
│ Scheduled maintenance on Jan 5, 2026 from 2:00-4:00 AM UTC │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing

### Running Tests

```bash
# Activate virtual environment
cd server
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # Linux/Mac

# Run all tests
python -m pytest tests/ -v

# Run specific suite
python -m pytest tests/test_authorization.py -v
python -m pytest tests/test_security.py -v

# Run security audit
python tests/security_audit.py

# Generate coverage report
python -m pytest tests/ --cov=. --cov-report=html
```

### Test Categories

| Category | File | Description |
|----------|------|-------------|
| Authorization | test_authorization.py | Role decorators, access control |
| Security | test_security.py | Injection, JWT, rate limiting |
| Multi-Tenancy | test_multi_tenancy.py | Data isolation |
| Impersonation | test_impersonation.py | Session, restrictions |

---

## Deployment

### Requirements

```
Python >= 3.10
MongoDB >= 5.0
Redis (optional, for production rate limiting)
```

### Environment Variables

```bash
# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB=firewall_controller

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key

# Email (2FA)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# Flask
FLASK_ENV=production
SECRET_KEY=your-flask-secret
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: ./server
    ports:
      - "5000:5000"
    environment:
      - MONGO_URI=mongodb://mongo:27017
      - MONGO_DB=firewall_controller
    depends_on:
      - mongo

  mongo:
    image: mongo:6.0
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

### Production Checklist

- [ ] Set strong JWT_SECRET_KEY (32+ chars)
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Configure CORS properly
- [ ] Set up MongoDB authentication
- [ ] Configure log rotation
- [ ] Set up monitoring (health endpoints)
- [ ] Create Super Admin account
- [ ] Test impersonation restrictions
- [ ] Verify rate limiting works

---

## Configuration

### config/security_config.py

```python
PASSWORD_CONFIG = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_special": True,
    "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?",
    "max_length": 128,
    "min_entropy": 40,
}

ACCOUNT_CONFIG = {
    "max_login_attempts": 5,
    "lockout_duration": 900,  # 15 minutes
    "session_timeout": 3600,  # 1 hour
}

RATE_LIMIT_CONFIG = {
    "login": {"requests": 5, "window": 300},
    "register": {"requests": 5, "window": 300},
    "api_call": {"requests": 100, "window": 60},
}
```

### config/impersonation_config.py

```python
IMPERSONATION_CONFIG = {
    "max_duration_hours": 4,
    "max_duration_seconds": 14400,
    "require_reason": True,
    "min_reason_length": 10,
    "log_all_actions": True,
    "notify_tenant": False,
    "max_concurrent_sessions": 1,
    "auto_extend": False,
    "short_token_expiry_hours": 4,
}
```

### config/broadcast_config.py

```python
BROADCAST_CONFIG = {
    "max_active_broadcasts": 10,
    "default_duration_days": 7,
    "max_title_length": 200,
    "max_message_length": 2000,
}
```

---

## Changelog

### v2.0.0 (January 2026)
- ✅ Multi-tenant architecture
- ✅ Super Admin role
- ✅ Impersonation feature
- ✅ System broadcasts
- ✅ Enhanced security (NoSQL injection, rate limiting)
- ✅ 89 automated tests
- ✅ Responsive UI

### v1.0.0 (Initial)
- Basic firewall agent management
- Single-tenant architecture
- Whitelist management
- Log viewing

---

## Support

For issues or questions:
1. Check existing documentation in `/docs`
2. Run security audit: `python tests/security_audit.py`
3. Run tests: `python -m pytest tests/ -v`

---

*Documentation generated: January 2, 2026*
