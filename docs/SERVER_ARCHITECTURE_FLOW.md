# Tài liệu Kiến trúc và Flow hoạt động của Server

## Tổng quan

Server là một ứng dụng Flask với kiến trúc MVC (Model-View-Controller), sử dụng MongoDB làm database và SocketIO cho real-time communication. Server cung cấp API cho Agent kết nối, quản lý whitelist, logs, và giao diện web admin.

---

## 1. Kiến trúc tổng thể

### 1.1. Stack công nghệ

| Component | Technology |
|-----------|------------|
| Framework | Flask + Eventlet |
| Database | MongoDB Atlas |
| Real-time | Flask-SocketIO |
| Authentication | JWT + API Key |
| Frontend | Bootstrap 5 + Jinja2 |
| Timezone | Vietnam (UTC+7) |

### 1.2. Cấu trúc MVC

```
server/
├── app.py                 # Entry point, khởi tạo Flask
├── time_utils.py          # Xử lý timezone Vietnam
├── .env                   # Environment variables
│
├── config/
│   └── security_config.py # Cấu hình bảo mật
│
├── database/
│   └── config.py          # MongoDB connection
│
├── models/                # Data Access Layer
│   ├── agent_model.py
│   ├── whitelist_model.py
│   ├── log_model.py
│   ├── group_model.py
│   ├── admin_model.py
│   ├── tenant_model.py
│   └── api_key_model.py
│
├── services/              # Business Logic Layer
│   ├── agent_service.py
│   ├── whitelist_service.py
│   ├── log_service.py
│   ├── group_service.py
│   ├── admin_service.py
│   ├── jwt_service.py
│   ├── api_key_service.py
│   └── email_service.py
│
├── controllers/           # HTTP Request Handlers
│   ├── agent_controller.py
│   ├── whitelist_controller.py
│   ├── log_controller.py
│   ├── group_controller.py
│   ├── admin_controller.py
│   ├── auth_controller.py
│   └── api_key_controller.py
│
├── middleware/            # Request Processing
│   ├── auth.py           # API Key + JWT validation
│   └── security.py       # Rate limiting, sanitization
│
└── views/                 # Frontend
    ├── templates/        # Jinja2 HTML templates
    └── static/           # CSS, JS, images
```

### 1.3. Sơ đồ kiến trúc

```
                        ┌─────────────────────────────────────────────┐
                        │              CLIENTS                        │
                        ├─────────────────┬───────────────────────────┤
                        │   Agent (API)   │      Admin (Browser)      │
                        └────────┬────────┴────────────┬──────────────┘
                                 │                     │
                                 ▼                     ▼
                        ┌─────────────────────────────────────────────┐
                        │              FLASK APP                       │
                        │  ┌────────────────────────────────────────┐ │
                        │  │           MIDDLEWARE                    │ │
                        │  │  ┌──────────────┐  ┌────────────────┐  │ │
                        │  │  │ API Key Auth │  │   JWT Auth     │  │ │
                        │  │  └──────────────┘  └────────────────┘  │ │
                        │  │  ┌──────────────┐  ┌────────────────┐  │ │
                        │  │  │ Rate Limiter │  │ Input Sanitizer│  │ │
                        │  │  └──────────────┘  └────────────────┘  │ │
                        │  └────────────────────────────────────────┘ │
                        │                     │                       │
                        │  ┌────────────────────────────────────────┐ │
                        │  │           CONTROLLERS                  │ │
                        │  │  Agent | Whitelist | Log | Group | ... │ │
                        │  └────────────────────────────────────────┘ │
                        │                     │                       │
                        │  ┌────────────────────────────────────────┐ │
                        │  │            SERVICES                     │ │
                        │  │  Business Logic + Validation            │ │
                        │  └────────────────────────────────────────┘ │
                        │                     │                       │
                        │  ┌────────────────────────────────────────┐ │
                        │  │             MODELS                      │ │
                        │  │  MongoDB CRUD Operations                │ │
                        │  └────────────────────────────────────────┘ │
                        └─────────────────────┬───────────────────────┘
                                              │
                        ┌─────────────────────┴───────────────────────┐
                        │              MONGODB ATLAS                  │
                        │  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
                        │  │ agents  │ │whitelist│ │  logs   │ ...   │
                        │  └─────────┘ └─────────┘ └─────────┘       │
                        └─────────────────────────────────────────────┘
                                              │
                        ┌─────────────────────┴───────────────────────┐
                        │              SOCKETIO                       │
                        │  Real-time events to Admin Dashboard        │
                        └─────────────────────────────────────────────┘
```

---

## 2. Flow khởi động Server

### 2.1. Khởi tạo ứng dụng (app.py → create_app())

```
[1] Eventlet Monkey Patch
        │
        └── Patch standard library cho async I/O
            │
            ▼
[2] Create Flask App
        │
        ├── Load config từ .env
        ├── Set SECRET_KEY
        └── Configure template/static folders
            │
            ▼
[3] Setup CORS
        │
        └── Allow /api/* từ tất cả origins
            │
            ▼
[4] Initialize SocketIO
        │
        └── async_mode='eventlet'
            │
            ▼
[5] Connect MongoDB
        │
        ├── Get connection string từ MONGO_URI
        ├── Create MongoClient
        └── Initialize database indexes
            │
            ▼
[6] Register MVC Components
        │
        ├── 6.1: Create Models
        │       │
        │       ├── AgentModel(db)
        │       ├── WhitelistModel(db)
        │       ├── LogModel(db)
        │       ├── GroupModel(db)
        │       ├── AdminModel(db)
        │       ├── TenantModel(db)
        │       └── APIKeyModel(db)
        │
        ├── 6.2: Create Services
        │       │
        │       ├── JWTService(db) ← Token management
        │       ├── APIKeyService(model, socketio)
        │       ├── GroupService(model, agent_model)
        │       ├── AgentService(model, group_model, socketio, jwt)
        │       ├── WhitelistService(model, agent_model, group_model, socketio)
        │       ├── LogService(model, agent_model, socketio)
        │       └── AdminService(model, tenant_model, jwt, socketio)
        │
        ├── 6.3: Initialize Auth Middleware
        │       │
        │       └── init_auth_middleware(api_key_service, jwt_service)
        │
        └── 6.4: Create Controllers & Register Blueprints
                │
                ├── AgentController → /api/agents/*
                ├── WhitelistController → /api/whitelist/*
                ├── LogController → /api/logs/*
                ├── GroupController → /api/groups/*
                ├── AuthController → /api/auth/*
                ├── AdminController → /api/admin/*
                └── APIKeyController → /api/api-keys/*
            │
            ▼
[7] Register Routes & Error Handlers
        │
        ├── Main routes (/, /dashboard, /whitelist, etc.)
        ├── Error handlers (404, 500)
        └── SocketIO events
            │
            ▼
[8] Server Ready
        │
        └── socketio.run(app, host='0.0.0.0', port=5000)
```

---

## 3. Authentication Flows

### 3.1. API Key Authentication (cho Agent Registration)

```
[1] Agent gửi POST /api/agents/register
        │
        ├── Header: X-API-Key: fc_xxxxxxxxxxxx
        └── Body: { hostname, device_id, ip_address, ... }
            │
            ▼
[2] Middleware: require_api_key("agent_register")
        │
        ├── Extract API key từ header
        │       │
        │       ├── X-API-Key header (preferred)
        │       ├── Authorization: Bearer <key>
        │       └── ?api_key=<key> (fallback)
        │
        ├── Validate API key
        │       │
        │       ├── Check key exists trong database
        │       ├── Check key chưa bị revoke
        │       ├── Check key chưa expired
        │       └── Check permission "agent_register"
        │
        ├── VALID → Set g.api_key_info, continue
        │
        └── INVALID → Return 401 Unauthorized
            │
            ▼
[3] Controller xử lý request
        │
        └── Có thể access g.api_key_info, g.tenant_id
```

### 3.2. JWT Authentication (cho Agent Heartbeat, Whitelist Sync)

```
[1] Agent gửi POST /api/agents/heartbeat
        │
        ├── Header: Authorization: Bearer <JWT_ACCESS_TOKEN>
        └── Body: { agent_id, metrics, ... }
            │
            ▼
[2] Middleware: require_jwt
        │
        ├── Extract JWT từ Authorization header
        │
        ├── Validate JWT
        │       │
        │       ├── Decode với secret key
        │       ├── Check signature
        │       ├── Check expiration (exp claim)
        │       ├── Check issuer (iss = "firewall-controller")
        │       └── Check token chưa bị revoke
        │
        ├── VALID → Set g.jwt_payload, g.agent_id
        │
        └── INVALID/EXPIRED → Return 401
            │
            ▼
[3] Controller xử lý request
```

### 3.3. Token Refresh Flow

```
[1] Agent phát hiện access token sắp hết hạn
        │
        ▼
[2] POST /api/auth/refresh
        │
        ├── Header: Authorization: Bearer <REFRESH_TOKEN>
        │
        └── Body: { agent_id, with_rotation: true/false }
            │
            ▼
[3] JWTService.refresh_tokens()
        │
        ├── Validate refresh token
        │
        ├── Check agent vẫn active
        │
        ├── Generate new access token
        │
        └── (Optional) Rotate refresh token
            │
            ▼
[4] Response
        │
        ├── access_token (new)
        ├── refresh_token (new if rotated)
        ├── access_expires_at
        └── refresh_expires_at
```

### 3.4. Admin Authentication (2FA)

```
[1] POST /api/admin/login
        │
        └── Body: { email, password }
            │
            ▼
[2] AdminService.authenticate()
        │
        ├── Verify email exists
        ├── Check account not locked (max 5 failed attempts)
        ├── Verify password (bcrypt)
        │
        ├── SUCCESS:
        │       │
        │       ├── 2FA enabled?
        │       │       │
        │       │       ├── YES → Generate 6-digit code
        │       │       │         Send via email
        │       │       │         Return { requires_2fa: true }
        │       │       │
        │       │       └── NO → Generate JWT tokens
        │       │                Return { access_token, refresh_token }
        │       │
        │       └── Update last_login
        │
        └── FAILURE:
                │
                ├── Increment failed_login_attempts
                └── Return 401 Invalid credentials
            │
            ▼
[3] (Nếu 2FA) POST /api/admin/verify-2fa
        │
        └── Body: { admin_id, code }
            │
            ▼
[4] TwoFactorAuthService.verify_code()
        │
        ├── Check code đúng
        ├── Check code chưa expired (5 phút)
        ├── Check attempts < 3
        │
        ├── SUCCESS → Generate JWT tokens
        │
        └── FAILURE → Return 401
```

---

## 4. Agent Registration Flow

### 4.1. Luồng đăng ký Agent

```
[1] Agent gửi POST /api/agents/register
        │
        ├── Headers:
        │   └── X-API-Key: fc_xxxxxxxxxxxx
        │
        └── Body:
            {
                "hostname": "DESKTOP-ABC",
                "device_id": "sha256_hardware_hash",
                "ip_address": "192.168.1.100",
                "platform": "Windows 10",
                "os_info": { "version": "10.0.19045" },
                "agent_version": "2.2.0"
            }
            │
            ▼
[2] API Key Validation (middleware)
        │
        └── Validate key, get tenant_id
            │
            ▼
[3] AgentService.register_agent()
        │
        ├── Check device_id required
        │
        ├── Find existing agent
        │       │
        │       ├── By device_id (primary)
        │       └── By hostname + IP (fallback legacy)
        │
        ├── EXISTING AGENT:
        │       │
        │       ├── Update: hostname, ip, platform, os_info, version
        │       ├── Update: last_heartbeat = now_vietnam()
        │       ├── Keep existing agent_token
        │       └── Keep existing group_id
        │
        └── NEW AGENT:
                │
                ├── Generate agent_id = uuid4()
                ├── Generate agent_token = secrets.token_hex(32)
                ├── Set status = "pending"
                ├── Assign to "Pending" group
                └── Insert vào database
            │
            ▼
[4] Generate JWT Tokens (nếu JWTService available)
        │
        ├── access_token (24h expiry)
        └── refresh_token (7 days expiry)
            │
            ▼
[5] SocketIO Broadcast
        │
        └── Emit "agent_registered" event
            │
            ▼
[6] Response to Agent
        │
        {
            "success": true,
            "agent_id": "uuid-xxx",
            "user_id": "device_id",
            "token": "legacy_token",
            "status": "pending",
            "server_time": "2026-01-01T12:00:00+07:00",
            "jwt": {
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "access_expires_at": "...",
                "refresh_expires_at": "..."
            }
        }
```

---

## 5. Heartbeat Flow

### 5.1. Agent gửi Heartbeat

```
[1] Agent gửi POST /api/agents/heartbeat (mỗi 20s)
        │
        ├── Headers:
        │   └── Authorization: Bearer <JWT_ACCESS_TOKEN>
        │
        └── Body:
            {
                "agent_id": "uuid-xxx",
                "token": "legacy_token",
                "metrics": {
                    "cpu_percent": 25.5,
                    "memory_percent": 60.2,
                    "uptime": 3600
                },
                "agent_version": "2.2.0",
                "platform": "Windows"
            }
            │
            ▼
[2] JWT Validation (middleware)
        │
        └── Validate token, extract agent_id
            │
            ▼
[3] AgentService.process_heartbeat()
        │
        ├── Find agent by agent_id
        │
        ├── Verify token matches
        │
        ├── Update database:
        │       │
        │       ├── last_heartbeat = now_vietnam()
        │       ├── ip_address = client_ip
        │       ├── metrics = { cpu, memory, uptime }
        │       └── status = "active"
        │
        └── Return whitelist version để agent check sync
            │
            ▼
[4] SocketIO Broadcast
        │
        └── Emit "agent_heartbeat" {
                agent_id,
                hostname,
                status: "active",
                last_heartbeat,
                metrics
            }
            │
            ▼
[5] Response to Agent
        │
        {
            "success": true,
            "status": "active",
            "server_time": "2026-01-01T12:00:00+07:00",
            "whitelist_version": 42
        }
```

### 5.2. Status Calculation

```
Agent Status được tính dựa trên thời gian từ last_heartbeat:

┌─────────────────────────────────────────────────────────┐
│ Thời gian từ heartbeat cuối │      Status              │
├─────────────────────────────┼───────────────────────────│
│ ≤ 5 phút                    │ 🟢 active                │
│ 5 phút - 30 phút            │ 🟡 inactive              │
│ > 30 phút                   │ 🔴 offline               │
│ Chưa có heartbeat           │ ⚪ pending               │
│ Bị admin disable            │ ⛔ disabled              │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Whitelist Sync Flow

### 6.1. Agent đồng bộ Whitelist

```
[1] Agent gửi POST /api/whitelist/agent-sync
        │
        ├── Headers:
        │   └── Authorization: Bearer <JWT_ACCESS_TOKEN>
        │
        └── Body:
            {
                "agent_id": "uuid-xxx",
                "last_sync_time": "2026-01-01T11:00:00+07:00",
                "checksum": "abc123...",
                "version": 41
            }
            │
            ▼
[2] JWT Validation (middleware)
            │
            ▼
[3] WhitelistService.agent_sync()
        │
        ├── Get agent's group_id
        │
        ├── Get global whitelist version
        │
        ├── Compare với agent's version
        │       │
        │       ├── SAME → Return { has_updates: false }
        │       │
        │       └── DIFFERENT ↓
        │
        ├── Collect whitelist entries:
        │       │
        │       ├── Global entries (scope = "global")
        │       │
        │       └── Group-specific entries (group's whitelist)
        │
        ├── Format response:
        │       │
        │       ├── domains: ["example.com", "*.google.com"]
        │       ├── ips: ["192.168.1.1"]
        │       └── patterns: ["*.cdn.com"]
        │
        └── Calculate new checksum
            │
            ▼
[4] Response to Agent
        │
        {
            "success": true,
            "has_updates": true,
            "data": {
                "domains": [...],
                "ips": [...],
                "patterns": [...]
            },
            "version": 42,
            "checksum": "xyz789...",
            "server_time": "2026-01-01T12:00:00+07:00"
        }
```

### 6.2. Whitelist Versioning

```
Mỗi thay đổi whitelist → Bump global version

┌─────────────────────────────────────────┐
│ Action                    │ Version ++  │
├───────────────────────────┼─────────────│
│ Add domain/IP             │ Yes         │
│ Delete domain/IP          │ Yes         │
│ Update entry              │ Yes         │
│ Update group whitelist    │ Yes         │
│ Bulk import               │ Yes         │
└───────────────────────────────────────────┘

Agent chỉ cần so sánh version number để biết cần sync hay không.
```

---

## 7. Log Receiving Flow

### 7.1. Agent gửi Logs

```
[1] Agent gửi POST /api/logs/receive (batch)
        │
        ├── Headers:
        │   └── Authorization: Bearer <JWT_ACCESS_TOKEN>
        │
        └── Body:
            {
                "logs": [
                    {
                        "timestamp": "2026-01-01T12:00:00+07:00",
                        "level": "INFO",
                        "action": "ALLOW",
                        "domain": "google.com",
                        "dest_ip": "142.250.1.100",
                        "source_ip": "192.168.1.50",
                        "protocol": "HTTPS",
                        "port": 443,
                        "message": "Domain allowed via whitelist"
                    },
                    ...
                ],
                "agent_id": "uuid-xxx"
            }
            │
            ▼
[2] JWT Validation (middleware)
            │
            ▼
[3] LogService.receive_logs()
        │
        ├── Validate logs array
        │
        ├── For each log:
        │       │
        │       ├── Parse timestamp → vietnam timezone
        │       ├── Add agent_id if missing
        │       ├── Add received_at = now_vietnam()
        │       ├── Normalize fields
        │       └── Validate required fields
        │
        ├── Batch insert vào MongoDB
        │
        └── Update statistics
            │
            ▼
[4] SocketIO Broadcast
        │
        └── Emit "logs_received" {
                agent_id,
                count,
                timestamp
            }
            │
            ▼
[5] Response to Agent
        │
        {
            "success": true,
            "received": 25,
            "server_time": "2026-01-01T12:00:00+07:00"
        }
```

---

## 8. Group Management Flow

### 8.1. Group Structure

```
┌─────────────────────────────────────────────────────────┐
│                      GROUPS                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────┐    ┌─────────────────┐             │
│  │ 📁 Pending      │    │ 📁 Phòng IT     │             │
│  │ (System group)  │    │                 │             │
│  │                 │    │ Whitelist:      │             │
│  │ Agents mới      │    │ - *.office.com  │             │
│  │ chưa assign     │    │ - github.com    │             │
│  │                 │    │                 │             │
│  │ Agents: 5       │    │ Agents: 10      │             │
│  └─────────────────┘    └─────────────────┘             │
│                                                          │
│  ┌─────────────────┐    ┌─────────────────┐             │
│  │ 📁 Phòng Kế toán│    │ 📁 Phòng Hành chính          │
│  │                 │    │                 │             │
│  │ Whitelist:      │    │ Whitelist:      │             │
│  │ - *.misa.vn     │    │ - mail.google.com│            │
│  │ - taxonline.gov │    │ - drive.google.com│           │
│  │                 │    │                 │             │
│  │ Agents: 8       │    │ Agents: 15      │             │
│  └─────────────────┘    └─────────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 8.2. Assign Agent to Group

```
[1] Admin PATCH /api/agents/<agent_id>/group
        │
        └── Body: { "group_id": "group-uuid" }
            │
            ▼
[2] AgentService.update_agent_group()
        │
        ├── Validate group exists
        ├── Update agent.group_id
        ├── (Optional) Update agent status
        └── Bump group's whitelist version
            │
            ▼
[3] SocketIO Broadcast
        │
        └── Emit "agent_group_changed"
            │
            ▼
[4] Agent sẽ nhận whitelist mới ở lần sync tiếp theo
```

---

## 9. Real-time Events (SocketIO)

### 9.1. Server → Client Events

| Event | Trigger | Data |
|-------|---------|------|
| `agent_registered` | Agent đăng ký mới | agent_id, hostname, status |
| `agent_heartbeat` | Agent gửi heartbeat | agent_id, status, metrics |
| `agent_status_changed` | Status thay đổi | agent_id, old_status, new_status |
| `agent_group_changed` | Assign group | agent_id, group_id |
| `whitelist_added` | Thêm entry | type, value, category |
| `whitelist_deleted` | Xóa entry | id, value |
| `whitelist_updated` | Cập nhật | id, changes |
| `logs_received` | Nhận logs | agent_id, count |
| `group_created` | Tạo group | group |
| `group_updated` | Cập nhật group | group |
| `group_deleted` | Xóa group | group_id |

### 9.2. Client → Server Events

| Event | Purpose | Data |
|-------|---------|------|
| `join_dashboard` | Subscribe dashboard updates | - |
| `join_agent_room` | Subscribe specific agent | agent_id |
| `leave_agent_room` | Unsubscribe agent | agent_id |

---

## 10. API Endpoints Summary

### 10.1. Agent APIs (yêu cầu API Key hoặc JWT)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/agents/register` | API Key | Đăng ký agent mới |
| POST | `/api/agents/heartbeat` | JWT | Gửi heartbeat |
| GET | `/api/agents` | - | Lấy danh sách agents |
| GET | `/api/agents/<id>` | - | Lấy thông tin agent |
| DELETE | `/api/agents/<id>` | - | Xóa agent |
| PATCH | `/api/agents/<id>/group` | - | Assign group |
| PATCH | `/api/agents/<id>/display-name` | - | Đổi tên hiển thị |
| GET | `/api/agents/statistics` | - | Thống kê agents |

### 10.2. Whitelist APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/whitelist/agent-sync` | JWT | Agent sync whitelist |
| GET | `/api/whitelist/domains` | - | Lấy danh sách entries |
| POST | `/api/whitelist/domains` | - | Thêm entry |
| DELETE | `/api/whitelist/domains/<id>` | - | Xóa entry |
| POST | `/api/whitelist/import` | - | Import bulk |
| GET | `/api/whitelist/export` | - | Export |
| POST | `/api/whitelist/bulk-add` | - | Bulk add |
| GET | `/api/whitelist/statistics` | - | Thống kê |

### 10.3. Log APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/logs/receive` | JWT | Agent gửi logs |
| GET | `/api/logs` | - | Lấy danh sách logs |
| DELETE | `/api/logs` | - | Xóa logs |
| GET | `/api/logs/export` | - | Export logs |
| GET | `/api/logs/statistics` | - | Thống kê |

### 10.4. Group APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/groups` | - | Danh sách groups |
| POST | `/api/groups` | - | Tạo group |
| GET | `/api/groups/<id>` | - | Chi tiết group |
| PATCH | `/api/groups/<id>` | - | Cập nhật group |
| DELETE | `/api/groups/<id>` | - | Xóa group |

### 10.5. Auth APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/refresh` | Refresh Token | Refresh access token |
| POST | `/api/auth/logout` | JWT | Logout (revoke tokens) |
| GET | `/api/auth/verify` | JWT | Verify token |
| GET | `/api/auth/token-info` | JWT | Get token info |

### 10.6. Admin APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/admin/login` | - | Login admin |
| POST | `/api/admin/verify-2fa` | - | Verify 2FA code |
| POST | `/api/admin/register` | - | Register admin |
| POST | `/api/admin/logout` | Session | Logout admin |
| GET | `/api/admin/profile` | Session | Get profile |
| PATCH | `/api/admin/profile` | Session | Update profile |

### 10.7. API Key Management APIs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/api-keys` | Admin | Danh sách keys |
| POST | `/api/api-keys` | Admin | Tạo key mới |
| GET | `/api/api-keys/<id>` | Admin | Chi tiết key |
| DELETE | `/api/api-keys/<id>` | Admin | Revoke key |

---

## 11. Database Collections

### 11.1. MongoDB Collections

```
┌─────────────────────────────────────────────────────────┐
│ Collection        │ Purpose                             │
├───────────────────┼─────────────────────────────────────│
│ agents            │ Agent records                       │
│ whitelist         │ Whitelist entries                   │
│ logs              │ Activity logs from agents           │
│ groups            │ Agent groups with whitelist         │
│ admins            │ Admin users                         │
│ tenants           │ Organizations (multi-tenant)        │
│ api_keys          │ API keys for authentication         │
│ revoked_tokens    │ Revoked JWT tokens (TTL indexed)    │
│ whitelist_meta    │ Global version tracking             │
└─────────────────────────────────────────────────────────┘
```

### 11.2. Indexes

```
agents:
  - agent_id (unique)
  - device_id (unique)
  - hostname + ip_address
  - tenant_id
  - status
  - last_heartbeat

whitelist:
  - value (unique)
  - type
  - category
  - is_active
  - added_date
  - tenant_id

logs:
  - timestamp (descending)
  - agent_id
  - action
  - level
  - domain

api_keys:
  - key_hash (unique)
  - is_revoked
  - expires_at (TTL)

revoked_tokens:
  - jti (unique)
  - expires_at (TTL - auto delete)
```

---

## 12. Security Features

### 12.1. Input Sanitization

```python
# Middleware tự động sanitize:
- Strip whitespace
- Limit string length (max 1000 chars)
- Normalize unicode
- Limit JSON depth (max 10)
- Limit array length (max 1000)
```

### 12.2. Rate Limiting

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Login | 5 requests | 5 phút |
| Register | 5 requests | 5 phút |
| API calls | 100 requests | 1 phút |

### 12.3. Password Policy

```
- Minimum 8 characters
- At least 1 uppercase
- At least 1 lowercase
- At least 1 digit
- At least 1 special character (!@#$%^&*...)
- Maximum 128 characters
```

### 12.4. Account Lockout

```
- Max 5 failed login attempts
- Lockout duration: 15 phút
- Session timeout: 1 giờ
```

---

## 13. Multi-tenancy

### 13.1. Tenant Isolation

```
Mỗi Tenant (Organization) có:
├── Admins riêng
├── Agents riêng
├── Whitelist riêng
├── Logs riêng
├── API Keys riêng
└── Groups riêng

Data được filter theo tenant_id trong:
- Database queries
- API responses
- SocketIO broadcasts
```

### 13.2. Tenant Context

```python
# Middleware tự động set tenant_id từ:
1. JWT token claim (tenant_id)
2. Session (tenant_id)
3. API Key (tenant_id)

# Access trong code:
from middleware.auth import get_current_tenant_id
tenant_id = get_current_tenant_id()
```

---

## 14. Error Handling

### 14.1. Standard Error Response

```json
{
    "success": false,
    "error": "Error message",
    "code": "ERROR_CODE",
    "timestamp": "2026-01-01T12:00:00+07:00"
}
```

### 14.2. HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

---

## 15. Timezone Handling

### 15.1. Vietnam Timezone (UTC+7)

```python
# Tất cả timestamps sử dụng Vietnam timezone
from time_utils import now_vietnam, now_iso, parse_agent_timestamp

# Lưu database: datetime với timezone
current_time = now_vietnam()

# API response: ISO format với offset
timestamp = now_iso()  # "2026-01-01T12:00:00+07:00"

# Parse từ agent:
dt = parse_agent_timestamp("2026-01-01T12:00:00+07:00")
```

---

## 16. Tóm tắt Flow chính

```
AGENT REGISTRATION:
  Agent → API Key Auth → Create/Update Agent → Generate JWT → Response

HEARTBEAT:
  Agent → JWT Auth → Update last_heartbeat → Calculate status → Broadcast

WHITELIST SYNC:
  Agent → JWT Auth → Compare version → Return updates if changed

LOG RECEIVING:
  Agent → JWT Auth → Validate & Store → Broadcast → Response

ADMIN LOGIN:
  Email/Password → Verify → 2FA (optional) → Generate JWT → Session

TOKEN REFRESH:
  Refresh Token → Validate → Generate new Access Token
```

---

*Tài liệu này mô tả kiến trúc Server Flask MVC. Cập nhật lần cuối: 2026-01-01*
