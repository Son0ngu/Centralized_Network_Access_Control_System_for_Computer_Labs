# Firewall Controller - Tài Liệu Chi Tiết Dự Án

**Version:** 1.0.0  
**Last Updated:** 2026-01-14  
**Author:** Firewall Controller Development Team

---

## 📋 Mục Lục

1. [Giới Thiệu Tổng Quan](#1-giới-thiệu-tổng-quan)
2. [Kiến Trúc Hệ Thống](#2-kiến-trúc-hệ-thống)
3. [Tính Năng Chính](#3-tính-năng-chính)
4. [API Documentation](#4-api-documentation)
5. [Công Nghệ Sử Dụng](#5-công-nghệ-sử-dụng)
6. [Bảo Mật](#6-bảo-mật)
7. [Cài Đặt & Triển Khai](#7-cài-đặt--triển-khai)

---

## 1. Giới Thiệu Tổng Quan

### 1.1. Firewall Controller là gì?

**Firewall Controller** là một hệ thống quản lý bảo mật mạng phân tán (Distributed Network Security Management System), cho phép quản lý tập trung các firewall rules trên nhiều máy tính Windows từ xa thông qua một giao diện web dashboard.

### 1.2. Vấn đề giải quyết

- **Quản lý Tập Trung:** Thay vì phải cấu hình firewall thủ công trên từng máy, admin có thể quản lý tất cả từ một nơi.
- **Giám Sát Real-time:** Xem trạng thái của tất cả các agents (online/offline), traffic bị block, và logs ngay lập tức.
- **Whitelist Policy:** Cho phép triển khai chính sách "Default Deny" (chặn tất cả, chỉ cho phép whitelist), tăng cường bảo mật.
- **Zero-Touch Deployment:** Agents tự động đăng ký và nhận rules từ server mà không cần cấu hình thủ công.

### 1.3. Thành phần chính

```
┌─────────────────────────────────────────────────────────────────┐
│                    FIREWALL CONTROLLER                           │
├──────────────────────────────────┬──────────────────────────────┤
│           SERVER                 │          AGENT               │
│  (Central Management)            │     (Endpoint Security)      │
├──────────────────────────────────┼──────────────────────────────┤
│ • Flask Web Application          │ • Desktop GUI (CustomTkinter)│
│ • REST API + SocketIO            │ • Packet Sniffer (Scapy)     │
│ • MongoDB Database               │ • Firewall Manager (Netsh)   │
│ • Admin Dashboard                │ • Heartbeat Service          │
│ • Group Management               │ • Whitelist Sync             │
└──────────────────────────────────┴──────────────────────────────┘
```

---

## 2. Kiến Trúc Hệ Thống

### 2.1. Mô hình triển khai

**Edge Computing Architecture:**
- **Server:** Một instance duy nhất (có thể scale horizontal với load balancer).
- **Agents:** Nhiều instances, mỗi máy một agent, xử lý traffic filtering locally.
- **Communication:** Agent-initiated HTTPS outbound (firewall-friendly).

```
       Internet Cloud
             │
    ┌────────▼────────┐
    │  SERVER (Flask) │ ◄──────┐
    │  - MongoDB      │        │ HTTPS
    │  - SocketIO     │        │ (Outbound)
    └────────┬────────┘        │
             │                 │
    ┌────────▼─────────────────┴────────────────┐
    │         Agent Network                     │
    ├──────────────┬──────────────┬─────────────┤
    │  Agent 1     │  Agent 2     │  Agent N    │
    │  (Win PC)    │  (Win PC)    │  (Win PC)   │
    └──────────────┴──────────────┴─────────────┘
```

### 2.2. Data Flow Overview

1. **Agent Registration:** Agent gửi hardware ID + hostname → Server tạo JWT tokens.
2. **Policy Sync:** Agent định kỳ GET whitelist rules → Apply vào Windows Firewall.
3. **Traffic Monitoring:** Scapy bắt packets → Check whitelist → Block/Allow.
4. **Logging:** Blocked packets → Batch POST đến server → Hiển thị trên dashboard.
5. **Heartbeat:** Mỗi 30s, agent POST status (RAM/CPU) → Server cập nhật "last_seen".

---

## 3. Tính Năng Chính

### 3.1. Server Features

#### 3.1.1. Agent Management
- ✅ **Auto-registration:** Agents tự đăng ký qua API Key.
- ✅ **Status Monitoring:** Theo dõi online/offline status real-time.
- ✅ **Resource Tracking:** Xem RAM, CPU usage của từng agent.
- ✅ **Display Name:** Đặt tên dễ nhớ cho agents.
- ✅ **Group Assignment:** Phân agents vào groups để apply rules khác nhau.

#### 3.1.2. Whitelist Management
- ✅ **Domain Whitelist:** Thêm/xóa domains cho phép (ví dụ: `google.com`).
- ✅ **IP Whitelist:** Hỗ trợ thêm IP trực tiếp.
- ✅ **Global Rules:** Rules áp dụng cho tất cả agents.
- ✅ **Group-specific Rules:** Rules chỉ áp dụng cho agents trong group cụ thể.
- ✅ **Real-time Sync:** Thay đổi whitelist → Broadcast qua SocketIO → Agents tự động sync.

#### 3.1.3. Log & Reporting
- ✅ **Traffic Logs:** Xem tất cả packets bị block (IP, Port, Protocol, Domain).
- ✅ **Search & Filter:** Lọc logs theo agent, IP, thời gian.
- ✅ **Statistics:** Dashboard hiển thị tổng số agents, logs, top blocked IPs.
- ✅ **Export:** Xuất logs ra CSV/JSON.

#### 3.1.4. Group Management
- ✅ **Create Groups:** Tạo nhóm agents (VD: "Accounting", "IT").
- ✅ **Custom Whitelists:** Mỗi group có whitelist riêng.
- ✅ **Assign Agents:** Kéo thả agents vào groups.

#### 3.1.5. API Key Management
- ✅ **Generate Keys:** Tạo API Keys cho agents đăng ký.
- ✅ **Permissions:** Cấu hình quyền (`agent_register`, `admin`).
- ✅ **Revoke:** Vô hiệu hóa keys khi cần.

### 3.2. Agent Features

#### 3.2.1. Firewall Management
- ✅ **Default Deny Policy:** Chặn tất cả traffic, chỉ cho phép whitelist.
- ✅ **Automatic Rule Creation:** Tự động tạo Windows Firewall rules từ whitelist.
- ✅ **DNS Resolution:** Tự động resolve domains → IPs và cache.
- ✅ **Essential IPs Protection:** Tự động allow localhost, DNS servers, gateway.

#### 3.2.2. Traffic Monitoring
- ✅ **Packet Capture:** Sử dụng Scapy + WinPcap/Npcap.
- ✅ **Real-time Analysis:** Phân tích packets real-time, kiểm tra whitelist.
- ✅ **Selective Logging:** Chỉ log blocked packets để tiết kiệm bandwidth.

#### 3.2.3. Desktop GUI
- ✅ **Dashboard:** Hiển thị status, resource usage, connection status.
- ✅ **Logs View:** Xem logs local real-time.
- ✅ **Whitelist View:** Xem whitelist hiện tại (read-only).
- ✅ **Settings:** Cấu hình server URL, API Key.

#### 3.2.4. Resilience
- ✅ **Offline Mode:** Khi mất kết nối server, agent tiếp tục hoạt động với cached rules.
- ✅ **Auto-reconnect:** Tự động kết nối lại khi server khả dụng.
- ✅ **Token Refresh:** Tự động refresh JWT tokens trước khi hết hạn.

---

## 4. API Documentation

### 4.1. Authentication

Hệ thống sử dụng 2 cơ chế xác thực:
1. **API Key:** Dùng cho agent registration (one-time).
2. **JWT Token:** Dùng cho tất cả các requests sau khi register.

**Token Lifecycle:**
- `access_token`: 7 ngày (có thể cấu hình).
- `refresh_token`: 30 ngày.
- Auto-refresh: Agent tự động refresh token khi còn < 1 ngày.

### 4.2. Agent Endpoints

#### 4.2.1. POST /api/agents/register
**Đăng ký agent mới vào hệ thống.**

**Authentication:** API Key (header: `X-API-Key`)

**Request Body:**
```json
{
  "hardware_id": "DESKTOP-ABC123-12345678",
  "hostname": "DESKTOP-ABC123",
  "os_info": "Windows 10 Pro",
  "os_version": "10.0.19045",
  "agent_version": "1.0.0"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Agent registered successfully",
  "data": {
    "agent_id": "60d5ec49f1b2c8a3d8e9f012",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_expires_at": "2026-01-21T10:30:00+07:00"
  }
}
```

**Use Case:** Khi agent chạy lần đầu, sử dụng API Key từ `agent_config.json` để register và nhận JWT tokens.

---

#### 4.2.2. POST /api/agents/heartbeat
**Gửi heartbeat để cập nhật trạng thái agent.**

**Authentication:** JWT (header: `Authorization: Bearer <token>`)

**Request Body:**
```json
{
  "status": "running",
  "cpu_usage": 23.5,
  "memory_usage": 45.2,
  "agent_version": "1.0.0",
  "firewall_active": true,
  "whitelist_count": 150
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Heartbeat received"
}
```

**Frequency:** Mỗi 30 giây.

**Side Effect:** Server cập nhật `last_seen` timestamp và broadcast event `agent_status_updated` qua SocketIO.

---

#### 4.2.3. GET /api/agents
**Lấy danh sách tất cả agents (Admin).**

**Authentication:** None (sẽ thêm admin auth sau)

**Query Parameters:**
- `status` (optional): `online` | `offline` | `all` (default: `all`)
- `group_id` (optional): Lọc theo group

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "agent_id": "60d5ec49f1b2c8a3d8e9f012",
      "hardware_id": "DESKTOP-ABC123-12345678",
      "hostname": "DESKTOP-ABC123",
      "display_name": "Accounting PC",
      "status": "online",
      "last_seen": "2026-01-14T15:30:45+07:00",
      "cpu_usage": 23.5,
      "memory_usage": 45.2,
      "group_id": "60d5ec49f1b2c8a3d8e9f999",
      "group_name": "Accounting"
    }
  ]
}
```

---

#### 4.2.4. GET /api/agents/<agent_id>
**Lấy thông tin chi tiết một agent.**

**Response (200):**
```json
{
  "success": true,
  "data": {
    "agent_id": "60d5ec49f1b2c8a3d8e9f012",
    "hardware_id": "DESKTOP-ABC123-12345678",
    "hostname": "DESKTOP-ABC123",
    "display_name": "Accounting PC",
    "status": "online",
    "last_seen": "2026-01-14T15:30:45+07:00",
    "registered_at": "2026-01-10T09:00:00+07:00",
    "os_info": "Windows 10 Pro",
    "agent_version": "1.0.0",
    "cpu_usage": 23.5,
    "memory_usage": 45.2,
    "group_id": "60d5ec49f1b2c8a3d8e9f999"
  }
}
```

---

#### 4.2.5. DELETE /api/agents/<agent_id>
**Xóa agent khỏi hệ thống.**

**Response (200):**
```json
{
  "success": true,
  "message": "Agent deleted successfully"
}
```

---

#### 4.2.6. PATCH /api/agents/<agent_id>/display-name
**Cập nhật tên hiển thị của agent.**

**Request Body:**
```json
{
  "display_name": "Finance PC - Room 201"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Display name updated"
}
```

---

### 4.3. Whitelist Endpoints

#### 4.3.1. GET /api/whitelist/agent-sync
**Agent lấy whitelist rules (Global + Group-specific).**

**Authentication:** JWT

**Response (200):**
```json
{
  "success": true,
  "data": {
    "domains": [
      "google.com",
      "microsoft.com",
      "github.com"
    ],
    "ips": [
      "8.8.8.8",
      "1.1.1.1"
    ],
    "last_updated": "2026-01-14T15:30:00+07:00"
  }
}
```

**Logic:**
- Trả về Global whitelist.
- Nếu agent thuộc group, thêm group-specific whitelist.

---

#### 4.3.2. GET /api/whitelist
**Lấy danh sách whitelist (Admin).**

**Query Parameters:**
- `scope` (optional): `global` | `group` (default: `all`)
- `group_id` (optional): Lọc theo group

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "60d5ec49f1b2c8a3d8e9f111",
      "domain": "google.com",
      "scope": "global",
      "added_at": "2026-01-10T10:00:00+07:00"
    },
    {
      "id": "60d5ec49f1b2c8a3d8e9f222",
      "domain": "salesforce.com",
      "scope": "group",
      "group_id": "60d5ec49f1b2c8a3d8e9f999",
      "group_name": "Sales",
      "added_at": "2026-01-12T14:00:00+07:00"
    }
  ]
}
```

---

#### 4.3.3. POST /api/whitelist
**Thêm domain/IP vào whitelist.**

**Request Body:**
```json
{
  "domain": "example.com",
  "scope": "global"
}
```

hoặc

```json
{
  "domain": "salesforce.com",
  "scope": "group",
  "group_id": "60d5ec49f1b2c8a3d8e9f999"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Domain added to whitelist",
  "data": {
    "id": "60d5ec49f1b2c8a3d8e9f333"
  }
}
```

**Side Effect:** Broadcast event `whitelist_updated` qua SocketIO → Agents tự động sync.

---

#### 4.3.4. DELETE /api/whitelist/<domain_id>
**Xóa domain khỏi whitelist.**

**Response (200):**
```json
{
  "success": true,
  "message": "Domain removed from whitelist"
}
```

---

#### 4.3.5. POST /api/whitelist/import
**Import whitelist từ file (bulk).**

**Request Body:**
```json
{
  "domains": [
    "google.com",
    "github.com",
    "stackoverflow.com"
  ],
  "scope": "global"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Imported 3 domains",
  "data": {
    "added": 3,
    "skipped": 0
  }
}
```

---

### 4.4. Log Endpoints

#### 4.4.1. POST /api/logs
**Agent gửi logs về server (batch).**

**Authentication:** JWT

**Request Body:**
```json
{
  "logs": [
    {
      "timestamp": "2026-01-14T15:30:45.123+07:00",
      "src_ip": "192.168.1.100",
      "dst_ip": "104.16.132.229",
      "dst_port": 443,
      "protocol": "TCP",
      "domain": "suspicious.com",
      "action": "blocked"
    }
  ]
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Received 1 log(s)"
}
```

---

#### 4.4.2. GET /api/logs
**Lấy danh sách logs (Admin).**

**Query Parameters:**
- `agent_id` (optional): Lọc theo agent
- `start_time` (optional): Lọc từ thời gian (ISO format)
- `end_time` (optional): Lọc đến thời gian
- `limit` (default: 100): Số logs tối đa
- `offset` (default: 0): Phân trang

**Response (200):**
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "id": "60d5ec49f1b2c8a3d8e9f444",
        "agent_id": "60d5ec49f1b2c8a3d8e9f012",
        "hostname": "DESKTOP-ABC123",
        "timestamp": "2026-01-14T15:30:45+07:00",
        "src_ip": "192.168.1.100",
        "dst_ip": "104.16.132.229",
        "dst_port": 443,
        "protocol": "TCP",
        "domain": "suspicious.com",
        "action": "blocked"
      }
    ],
    "total": 1500,
    "limit": 100,
    "offset": 0
  }
}
```

---

#### 4.4.3. DELETE /api/logs/clear
**Xóa tất cả logs (hoặc theo điều kiện).**

**Query Parameters:**
- `agent_id` (optional): Chỉ xóa logs của agent này
- `before` (optional): Xóa logs trước thời gian này (ISO format)

**Response (200):**
```json
{
  "success": true,
  "message": "Deleted 500 log(s)"
}
```

---

#### 4.4.4. GET /api/logs/stats
**Lấy thống kê logs.**

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_logs": 15000,
    "today_logs": 234,
    "top_blocked_ips": [
      {"ip": "104.16.132.229", "count": 50},
      {"ip": "142.250.185.46", "count": 30}
    ],
    "top_blocked_domains": [
      {"domain": "suspicious.com", "count": 50},
      {"domain": "ads.tracker.com", "count": 35}
    ]
  }
}
```

---

### 4.5. Group Endpoints

#### 4.5.1. GET /api/groups
**Lấy danh sách groups.**

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "60d5ec49f1b2c8a3d8e9f999",
      "name": "Accounting",
      "description": "Accounting department",
      "agent_count": 5,
      "whitelist_count": 20,
      "created_at": "2026-01-05T10:00:00+07:00"
    }
  ]
}
```

---

#### 4.5.2. POST /api/groups
**Tạo group mới.**

**Request Body:**
```json
{
  "name": "IT Team",
  "description": "IT Department",
  "whitelist": ["github.com", "stackoverflow.com"]
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "60d5ec49f1b2c8a3d8e9f888"
  }
}
```

---

#### 4.5.3. GET /api/groups/<group_id>
**Lấy thông tin chi tiết group.**

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "60d5ec49f1b2c8a3d8e9f999",
    "name": "Accounting",
    "description": "Accounting department",
    "whitelist": ["salesforce.com", "quickbooks.com"],
    "agents": [
      {
        "agent_id": "60d5ec49f1b2c8a3d8e9f012",
        "hostname": "ACC-PC-01"
      }
    ]
  }
}
```

---

#### 4.5.4. PATCH /api/groups/<group_id>
**Cập nhật group.**

**Request Body:**
```json
{
  "name": "Accounting & Finance",
  "whitelist": ["salesforce.com", "quickbooks.com", "stripe.com"]
}
```

---

#### 4.5.5. DELETE /api/groups/<group_id>
**Xóa group.**

**Response (200):**
```json
{
  "success": true,
  "message": "Group deleted"
}
```

---

### 4.6. Auth Endpoints

#### 4.6.1. POST /api/auth/refresh
**Refresh JWT token.**

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2026-01-21T10:30:00+07:00"
  }
}
```

---

#### 4.6.2. POST /api/auth/logout
**Logout (invalidate token).**

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

### 4.7. API Key Endpoints

#### 4.7.1. GET /api/api-keys
**Lấy danh sách API Keys (Admin).**

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "60d5ec49f1b2c8a3d8e9f777",
      "name": "Production Key",
      "key": "fwc_1234567890abcdef",
      "permissions": ["agent_register"],
      "is_active": true,
      "created_at": "2026-01-01T10:00:00+07:00"
    }
  ]
}
```

---

#### 4.7.2. POST /api/api-keys
**Tạo API Key mới.**

**Request Body:**
```json
{
  "name": "Development Key",
  "permissions": ["agent_register"]
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "60d5ec49f1b2c8a3d8e9f666",
    "key": "fwc_abcdef1234567890"
  }
}
```

---

#### 4.7.3. DELETE /api/api-keys/<key_id>
**Xóa (revoke) API Key.**

**Response (200):**
```json
{
  "success": true,
  "message": "API Key revoked"
}
```

---

### 4.8. SocketIO Events

#### 4.8.1. Server → Client Events

**Event: `agent_status_updated`**
```json
{
  "agent_id": "60d5ec49f1b2c8a3d8e9f012",
  "status": "online",
  "last_seen": "2026-01-14T15:30:45+07:00"
}
```

**Event: `whitelist_updated`**
```json
{
  "message": "Whitelist has been updated",
  "timestamp": "2026-01-14T15:30:00+07:00"
}
```

**Event: `new_log`**
```json
{
  "log": {
    "agent_id": "60d5ec49f1b2c8a3d8e9f012",
    "hostname": "DESKTOP-ABC123",
    "dst_ip": "104.16.132.229",
    "domain": "suspicious.com"
  }
}
```

#### 4.8.2. Client → Server Events

**Event: `connect`**
```javascript
socket.on('connect', () => {
  console.log('Connected to server');
});
```

**Event: `disconnect`**
```javascript
socket.on('disconnect', () => {
  console.log('Disconnected from server');
});
```

---

## 5. Công Nghệ Sử Dụng

### 5.1. Server Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Web Framework** | Flask | 3.0+ | REST API & Web Server |
| **Database** | MongoDB | 4.4+ | Document storage |
| **Real-time** | SocketIO | 4.7+ | WebSocket communication |
| **Async I/O** | Eventlet | 0.35+ | Concurrent handling |
| **Authentication** | JWT | PyJWT 2.8+ | Token-based auth |
| **Timezone** | ZoneInfo | Python 3.9+ | Vietnam timezone (Asia/Ho_Chi_Minh) |
| **Web Server** | Gunicorn/Eventlet | - | Production WSGI server |

### 5.2. Agent Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **GUI** | CustomTkinter | 5.2+ | Modern desktop interface |
| **Packet Capture** | Scapy | 2.5+ | Network traffic analysis |
| **Driver** | Npcap/WinPcap | - | Packet capture driver |
| **Firewall** | Netsh (Windows) | Built-in | Windows Firewall management |
| **HTTP Client** | Requests | 2.31+ | API communication |
| **DNS Resolution** | dnspython | 2.4+ | Domain → IP resolution |
| **Caching** | LRU Cache | Custom | High-performance caching |

### 5.3. Deployment

**Server:**
- Docker (Recommended)
- Ubuntu 20.04+ / Windows Server 2019+
- Nginx (Reverse Proxy + SSL Termination)

**Agent:**
- Windows Installer (`.exe` via PyInstaller)
- Service Mode (Windows Service)

---

## 6. Bảo Mật

### 6.1. Authentication Flow

```
Agent                           Server
  │                               │
  ├─ POST /agents/register ──────►│ (API Key)
  │  (API Key: fwc_xxx)           │
  │                               │
  │◄─ 201 Created ────────────────┤
  │  {access_token, refresh_token}│
  │                               │
  ├─ POST /logs ─────────────────►│ (JWT)
  │  (Authorization: Bearer xxx)  │
  │                               │
  │◄─ 200 OK ─────────────────────┤
```

### 6.2. Security Features

1. **API Key Rotation:** Admin có thể revoke và tạo keys mới.
2. **JWT Expiration:** Tokens tự động hết hạn sau 7 ngày.
3. **HTTPS Enforcement:** Tất cả communication đều qua TLS.
4. **Input Validation:** Tất cả API inputs được validate.
5. **Rate Limiting:** (TODO) Sẽ implement để chống abuse.
6. **Firewall Backup:** Agent tự động backup firewall rules trước khi thay đổi.

### 6.3. Data Privacy

- **No Sensitive Data:** Chỉ log metadata (IP, port, protocol), không log payload.
- **Local Processing:** Packet analysis hoàn toàn trên agent, không gửi raw packets về server.
- **Configurable Retention:** Logs có thể tự động xóa sau N ngày.

---

## 7. Cài Đặt & Triển Khai

### 7.1. Server Installation (Docker)

```bash
# 1. Clone repository
git clone https://github.com/yourorg/firewall-controller.git
cd firewall-controller/server

# 2. Configure environment
cp .env.example .env
nano .env  # Edit MongoDB URI, JWT secret

# 3. Build & Run
docker-compose up -d

# 4. Access Dashboard
# http://localhost:5000
```

### 7.2. Agent Installation (Windows)

```powershell
# 1. Download installer
# https://yourserver.com/downloads/FirewallAgent-Setup.exe

# 2. Run installer (requires Admin)
.\FirewallAgent-Setup.exe

# 3. Configure (First Run)
# - Server URL: https://yourserver.com
# - API Key: fwc_xxx (get from admin dashboard)

# 4. Register
# Agent tự động register và nhận JWT tokens

# 5. Verify
# Check dashboard: Agent should appear "Online"
```

### 7.3. Configuration Files

**Server: `.env`**
```env
MONGODB_URI=mongodb://localhost:27017/firewall_controller
JWT_SECRET=your-secret-key-change-this
PORT=5000
```

**Agent: `agent_config.json`**
```json
{
  "server_url": "https://yourserver.com",
  "api_key": "fwc_1234567890abcdef",
  "agent_id": "",
  "access_token": "",
  "refresh_token": ""
}
```

---

## 8. Workflow Examples

### 8.1. Thêm Domain Mới vào Whitelist

1. Admin mở Dashboard → Whitelist → "Add Domain"
2. Nhập `facebook.com` → Chọn scope: `Global` → Save
3. Server lưu vào MongoDB
4. Server broadcast event `whitelist_updated` qua SocketIO
5. Tất cả agents online nhận event → Gọi `GET /api/whitelist/agent-sync`
6. Agents nhận `facebook.com` → Resolve DNS → Add Windows Firewall rule
7. Users có thể truy cập Facebook ngay lập tức

### 8.2. Xem Log Bị Block

1. User trên Agent truy cập `malware.com`
2. Scapy bắt packet → Check whitelist → Không có → Block
3. Agent log vào buffer local
4. Sau 2 giây (hoặc 100 logs), Agent batch POST `/api/logs`
5. Server nhận logs → Lưu MongoDB → Emit event `new_log`
6. Dashboard nhận event → Update bảng logs real-time
7. Admin thấy log ngay lập tức

### 8.3. Agent Offline Recovery

1. Agent mất kết nối (mất mạng)
2. Agent switch sang "Offline Mode"
3. Firewall rules vẫn hoạt động (dựa vào cache local)
4. Logs được buffer trong memory
5. Khi có mạng lại, Agent:
   - Reconnect WebSocket
   - POST heartbeat
   - POST buffered logs
   - Sync whitelist (kiểm tra updates)

---

## 9. Performance Metrics

### 9.1. Server Capacity

- **Agents:** Hỗ trợ ~10,000 agents đồng thời (single instance).
- **Logs:** ~10,000 logs/second (với MongoDB indexed).
- **SocketIO:** ~5,000 concurrent WebSocket connections.

### 9.2. Agent Performance

- **CPU Usage:** 2-5% (idle), 10-15% (high traffic).
- **Memory:** ~150MB RAM.
- **Packet Processing:** ~100,000 packets/second (depends on NIC).

---

## 10. Troubleshooting

### 10.1. Agent không online

**Nguyên nhân:**
- Sai Server URL
- Firewall chặn port 5000/443
- API Key không hợp lệ

**Giải pháp:**
```bash
# Check connectivity
curl https://yourserver.com/api/health

# Check API Key
# Dashboard → API Keys → Verify key is active

# Check Agent logs
# %APPDATA%\FirewallAgent\logs\agent.log
```

### 10.2. Whitelist không sync

**Nguyên nhân:**
- SocketIO connection failed
- Agent JWT expired

**Giải pháp:**
```bash
# Manual sync
# Agent GUI → Settings → "Force Sync"

# Check token expiry
# Dashboard → Agents → View token info
```

---

## 11. Roadmap

- [ ] **v1.1:** Role-based access control (Admin/Viewer).
- [ ] **v1.2:** Email alerts khi có traffic bất thường.
- [ ] **v1.3:** Machine Learning để detect anomalies.
- [ ] **v1.4:** Multi-tenancy (nhiều organizations).
- [ ] **v2.0:** Linux Agent support.

---

**Liên hệ:**  
Email: support@firewallcontroller.com  
GitHub: https://github.com/yourorg/firewall-controller

*Document Version: 1.0.0 - Last Updated: 2026-01-14*
