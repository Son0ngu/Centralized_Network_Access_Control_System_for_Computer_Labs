# SERVER API ENDPOINTS - TÀI LIỆU CHI TIẾT

## Mục lục
1. [Tổng quan](#1-tổng-quan)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [Agent Endpoints](#3-agent-endpoints)
4. [Whitelist Endpoints](#4-whitelist-endpoints)
5. [Log Endpoints](#5-log-endpoints)
6. [Group Endpoints](#6-group-endpoints)
7. [API Key Endpoints](#7-api-key-endpoints)
8. [Auth Endpoints](#8-auth-endpoints)
9. [Admin Endpoints](#9-admin-endpoints)
10. [Web Pages & Utility Endpoints](#10-web-pages--utility-endpoints)
11. [SocketIO Events](#11-socketio-events)

---

## 1. Tổng quan

### Base URL
```
http://localhost:5000/api
```

### Response Format
Tất cả API responses đều theo format chuẩn:
```json
{
  "success": true/false,
  "message": "Mô tả kết quả",
  "data": { ... },          // Nếu có data trả về
  "error": "Mô tả lỗi",     // Nếu có lỗi
  "timestamp": "2025-01-01T12:00:00+07:00"  // Vietnam timezone
}
```

### HTTP Status Codes
| Code | Ý nghĩa |
|------|---------|
| 200 | Thành công |
| 201 | Tạo mới thành công |
| 400 | Bad Request - Dữ liệu không hợp lệ |
| 401 | Unauthorized - Chưa xác thực |
| 403 | Forbidden - Không có quyền |
| 404 | Not Found - Không tìm thấy |
| 500 | Internal Server Error |

---

## 2. Authentication & Authorization

### 2.1 API Key Authentication
Sử dụng cho: **Agent Registration**

Header:
```
X-API-KEY: fc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2.2 JWT Authentication
Sử dụng cho: **Agent operations sau khi đăng ký**

Header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2.3 Session Authentication
Sử dụng cho: **Web UI (Admin Dashboard)**

Cookie-based session sau khi admin login.

---

## 3. Agent Endpoints

### 3.1 POST /api/agents/register
**Đăng ký agent mới**

**Authentication:** API Key (X-API-KEY header)

**Request Body:**
```json
{
  "hostname": "DESKTOP-ABC123",
  "device_id": "unique-device-id-12345",
  "ip_address": "192.168.1.100",
  "platform": "Windows 10 Pro",
  "os_info": "Windows 10.0.19041",
  "agent_version": "1.0.0"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Agent registered successfully",
  "data": {
    "agent_id": "agt_abc123def456",
    "user_id": "unique-device-id-12345",
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_expires_in": 86400,
    "server_time": "2025-01-01T12:00:00+07:00",
    "config": {
      "heartbeat_interval": 60,
      "log_batch_size": 50
    }
  }
}
```

**Chức năng chi tiết:**
- Tạo agent_id duy nhất dựa trên hostname và device_id
- Tạo cặp JWT tokens (access + refresh)
- Lưu thông tin agent vào database với trạng thái "active"
- Emit SocketIO event "agent_registered"
- Áp dụng tenant isolation nếu có multi-tenancy

---

### 3.2 POST /api/agents/heartbeat
**Gửi heartbeat từ agent**

**Authentication:** JWT Bearer Token

**Request Body:**
```json
{
  "agent_id": "agt_abc123def456",
  "token": "current-access-token",
  "agent_version": "1.0.0",
  "platform": "Windows 10 Pro",
  "metrics": {
    "cpu_usage": 25.5,
    "memory_usage": 60.2,
    "network_status": "connected"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Heartbeat processed",
  "data": {
    "status": "active",
    "server_time": "2025-01-01T12:00:00+07:00",
    "sync_required": false,
    "config_update": null
  }
}
```

**Chức năng chi tiết:**
- Cập nhật `last_heartbeat` timestamp
- Tính toán trạng thái agent (active/inactive/offline)
- Emit SocketIO event "agent_heartbeat" với metrics
- Trả về thông tin sync nếu cần cập nhật whitelist

---

### 3.3 GET /api/agents
**Lấy danh sách tất cả agents**

**Authentication:** Session (Admin Web UI)

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| limit | int | 50 | Số lượng tối đa |
| skip | int | 0 | Số bản ghi bỏ qua |
| page | int | 1 | Số trang |
| status | string | - | Filter theo status (active/inactive/offline) |
| hostname | string | - | Filter theo hostname |
| group_id | string | - | Filter theo group |
| exclude_group_id | string | - | Loại trừ agents trong group |

**Response (200):**
```json
{
  "success": true,
  "agents": [
    {
      "agent_id": "agt_abc123",
      "hostname": "DESKTOP-ABC",
      "display_name": "Main Server",
      "ip_address": "192.168.1.100",
      "platform": "Windows 10 Pro",
      "os_info": "Windows 10.0.19041",
      "agent_version": "1.0.0",
      "status": "active",
      "group_id": "grp_xyz789",
      "registered_date": "2025-01-01T10:00:00+07:00",
      "last_heartbeat": "2025-01-01T12:00:00+07:00",
      "time_since_heartbeat": 30,
      "metrics": { ... }
    }
  ],
  "total": 25,
  "pagination": {
    "total": 25,
    "limit": 50,
    "skip": 0,
    "page": 1
  }
}
```

**Chức năng chi tiết:**
- Tính toán trạng thái real-time dựa trên last_heartbeat
- Thresholds: active (<120s), inactive (120s-300s), offline (>300s)
- Hỗ trợ filtering và pagination
- Tenant isolation cho multi-tenancy

---

### 3.4 GET /api/agents/statistics
**Lấy thống kê agents**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total": 25,
    "active": 18,
    "inactive": 5,
    "offline": 2,
    "by_platform": {
      "Windows 10": 20,
      "Windows 11": 5
    },
    "by_version": {
      "1.0.0": 15,
      "1.0.1": 10
    }
  }
}
```

---

### 3.5 GET /api/agents/{agent_id}
**Lấy chi tiết một agent**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "data": {
    "agent_id": "agt_abc123",
    "hostname": "DESKTOP-ABC",
    "display_name": "Main Server",
    "ip_address": "192.168.1.100",
    "platform": "Windows 10 Pro",
    "os_info": "Windows 10.0.19041",
    "agent_version": "1.0.0",
    "status": "active",
    "group_id": "grp_xyz789",
    "group_name": "Development Team",
    "registered_date": "2025-01-01T10:00:00+07:00",
    "last_heartbeat": "2025-01-01T12:00:00+07:00",
    "metrics": { ... },
    "whitelist_version": 15
  }
}
```

---

### 3.6 DELETE /api/agents/{agent_id}
**Xóa một agent**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "message": "Agent DESKTOP-ABC deleted successfully"
}
```

**Chức năng:**
- Xóa agent khỏi database
- Emit SocketIO event "agent_deleted"

---

### 3.7 PATCH /api/agents/{agent_id}/display-name
**Cập nhật display name của agent**

**Authentication:** Session

**Request Body:**
```json
{
  "display_name": "Production Server 01"
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

### 3.8 PATCH /api/agents/{agent_id}/group
**Di chuyển agent sang group khác**

**Authentication:** Session

**Request Body:**
```json
{
  "group_id": "grp_newgroup123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Agent moved to group successfully",
  "data": {
    "agent_id": "agt_abc123",
    "hostname": "DESKTOP-ABC",
    "group_id": "grp_newgroup123",
    "status": "active"
  }
}
```

**Chức năng:**
- Cập nhật group_id của agent
- Emit SocketIO event "agent_group_updated"

---

### 3.9 GET /api/agents/debug/status
**Debug endpoint - Lấy thông tin debug**

**Response (200):**
```json
{
  "success": true,
  "data": {
    "controller": "AgentController",
    "socketio_enabled": true,
    "thresholds": {
      "active_seconds": 120,
      "inactive_seconds": 300
    },
    "statistics": { ... },
    "sample_agents": [ ... ],
    "timestamp": "2025-01-01T12:00:00+07:00"
  }
}
```

---

## 4. Whitelist Endpoints

### 4.1 GET /api/whitelist/agent-sync
**Agent đồng bộ whitelist (Agent gọi)**

**Authentication:** JWT Bearer Token

**Query Parameters:**
| Parameter | Type | Mô tả |
|-----------|------|-------|
| version | int | Phiên bản whitelist hiện tại của agent |
| group_version | int | Phiên bản group whitelist |

**Response (200):**
```json
{
  "success": true,
  "agent_id": "agt_abc123",
  "domains": [
    {
      "id": "wl_domain1",
      "value": "google.com",
      "type": "domain",
      "category": "search",
      "is_active": true,
      "scope": "global"
    },
    {
      "id": "wl_domain2",
      "value": "*.microsoft.com",
      "type": "wildcard",
      "category": "software",
      "is_active": true,
      "scope": "group"
    }
  ],
  "count": 2,
  "version": 16,
  "group_version": 5,
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Chức năng chi tiết:**
- Trả về whitelist domains applicable cho agent
- Bao gồm: Global domains + Group-specific domains + Agent-specific domains
- So sánh version để quyết định có trả về hay không
- Hỗ trợ wildcard domains (*.example.com)

---

### 4.2 GET /api/whitelist
**Lấy danh sách whitelist domains**

**Authentication:** Session

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| limit | int | 100 | Số lượng tối đa (max 1000) |
| offset | int | 0 | Vị trí bắt đầu |
| search | string | - | Tìm kiếm theo domain |
| agent_id | string | - | Filter theo agent cụ thể |
| group_id | string | - | Filter theo group |

**Response (200):**
```json
{
  "success": true,
  "domains": [
    {
      "_id": "wl_abc123",
      "value": "google.com",
      "type": "domain",
      "category": "search",
      "is_active": true,
      "scope": "global",
      "created_at": "2025-01-01T10:00:00+07:00",
      "created_by": "admin"
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0,
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

---

### 4.3 POST /api/whitelist
**Thêm domain mới vào whitelist**

**Authentication:** Session

**Request Body:**
```json
{
  "value": "example.com",
  "type": "domain",
  "category": "business",
  "scope": "global",
  "description": "Company main website"
}
```

**Supported Types:**
- `domain`: Domain cụ thể (google.com)
- `wildcard`: Wildcard domain (*.google.com)
- `ip`: IP address (192.168.1.1)
- `cidr`: IP range (192.168.1.0/24)
- `url`: URL cụ thể (https://example.com/path)

**Supported Scopes:**
- `global`: Áp dụng cho tất cả agents
- `group`: Áp dụng cho agents trong group cụ thể
- `agent`: Áp dụng cho agent cụ thể

**Response (201):**
```json
{
  "success": true,
  "message": "Domain added successfully",
  "domain_id": "wl_newdomain123",
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Chức năng:**
- Validate domain format
- Kiểm tra duplicate
- Emit SocketIO event "whitelist_updated"
- Auto-increment version number

---

### 4.4 DELETE /api/whitelist/{domain_id}
**Xóa domain khỏi whitelist**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "message": "Domain deleted successfully",
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Chức năng:**
- Soft delete (đánh dấu is_active = false) hoặc hard delete
- Emit SocketIO event "whitelist_updated"

---

### 4.5 POST /api/whitelist/import
**Import nhiều domains từ file/list**

**Authentication:** Session

**Request Body:**
```json
{
  "domains": [
    "google.com",
    "*.microsoft.com",
    "facebook.com"
  ],
  "category": "imported"
}
```

**Response (200):**
```json
{
  "success": true,
  "added_count": 3,
  "skipped_count": 0,
  "errors": [],
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Chức năng:**
- Bulk import domains
- Skip duplicates
- Report errors for invalid domains
- Emit SocketIO event "whitelist_updated"

---

### 4.6 GET /api/whitelist/export
**Export whitelist domains**

**Authentication:** Session

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| format | string | json | Format export (json/txt) |
| category | string | - | Filter theo category |

**Response (200) - JSON:**
```json
{
  "success": true,
  "data": [
    "google.com",
    "*.microsoft.com"
  ],
  "count": 150,
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Response (200) - TXT:**
```
google.com
*.microsoft.com
facebook.com
```
(Với Content-Disposition: attachment)

---

### 4.7 GET /api/whitelist/statistics
**Lấy thống kê whitelist**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "statistics": {
    "total": 150,
    "active": 145,
    "inactive": 5,
    "by_type": {
      "domain": 100,
      "wildcard": 30,
      "ip": 15,
      "url": 5
    },
    "by_category": {
      "business": 50,
      "social": 30,
      "search": 20,
      "other": 50
    },
    "by_scope": {
      "global": 100,
      "group": 30,
      "agent": 20
    }
  },
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

---

### 4.8 POST /api/whitelist/bulk
**Bulk add nhiều entries**

**Authentication:** Session

**Request Body:**
```json
{
  "items": [
    {
      "value": "google.com",
      "type": "domain",
      "category": "search"
    },
    {
      "value": "192.168.1.0/24",
      "type": "cidr",
      "category": "internal"
    }
  ]
}
```

**Response (200):**
```json
{
  "success": true,
  "added_count": 2,
  "error_count": 0,
  "errors": [],
  "server_time": "2025-01-01T12:00:00+07:00"
}
```

**Limits:**
- Maximum 1000 items per request

---

### 4.9 POST /api/whitelist/bulk-update
**Bulk update nhiều entries**

**Authentication:** Session

**Request Body:**
```json
{
  "item_ids": ["wl_abc123", "wl_def456"],
  "active": true
}
```

**Response (200):**
```json
{
  "success": true,
  "updated_count": 2,
  "error_count": 0,
  "errors": [],
  "server_time": "2025-01-01T12:00:00+07:00"
}
```

---

### 4.10 POST /api/whitelist/bulk-delete
**Bulk delete nhiều entries**

**Authentication:** Session

**Request Body:**
```json
{
  "item_ids": ["wl_abc123", "wl_def456"]
}
```

**Response (200):**
```json
{
  "success": true,
  "deleted_count": 2,
  "error_count": 0,
  "errors": [],
  "server_time": "2025-01-01T12:00:00+07:00"
}
```

---

## 5. Log Endpoints

### 5.1 POST /api/logs
**Agent gửi logs lên server**

**Authentication:** JWT Bearer Token

**Request Body:**
```json
{
  "agent_id": "agt_abc123",
  "logs": [
    {
      "timestamp": "2025-01-01T12:00:00+07:00",
      "level": "INFO",
      "action": "ALLOWED",
      "domain": "google.com",
      "source_ip": "192.168.1.100",
      "destination_ip": "142.250.66.46",
      "protocol": "DNS",
      "message": "DNS query allowed"
    },
    {
      "timestamp": "2025-01-01T12:00:01+07:00",
      "level": "WARNING",
      "action": "BLOCKED",
      "domain": "malware.com",
      "source_ip": "192.168.1.100",
      "message": "Domain not in whitelist - NXDOMAIN"
    }
  ]
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logs received",
  "received_count": 2,
  "server_time": "2025-01-01T12:00:05+07:00"
}
```

**Chức năng chi tiết:**
- Nhận batch logs từ agent
- Parse và validate timestamps
- Lưu vào database với agent_id
- Emit SocketIO event "logs_received"

---

### 5.2 GET /api/logs
**Lấy danh sách logs**

**Authentication:** Session

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| limit | int | 100 | Số lượng tối đa |
| offset | int | 0 | Vị trí bắt đầu |
| level | string | - | Filter theo level (INFO/WARNING/ERROR) |
| action | string | - | Filter theo action (ALLOWED/BLOCKED) |
| agent_id | string | - | Filter theo agent |
| search | string | - | Tìm kiếm (domain, message) |
| time_range | string | - | Khoảng thời gian (1h/24h/7d/30d) |
| start_date | string | - | Từ ngày (ISO format) |
| end_date | string | - | Đến ngày (ISO format) |

**Response (200):**
```json
{
  "success": true,
  "logs": [
    {
      "_id": "log_abc123",
      "agent_id": "agt_abc123",
      "hostname": "DESKTOP-ABC",
      "timestamp": "2025-01-01T12:00:00+07:00",
      "level": "INFO",
      "action": "ALLOWED",
      "domain": "google.com",
      "source_ip": "192.168.1.100",
      "message": "DNS query allowed"
    }
  ],
  "total": 5000,
  "limit": 100,
  "offset": 0,
  "applied_filters": {
    "level": "INFO",
    "action": "ALLOWED"
  }
}
```

---

### 5.3 GET /api/logs/stats
**Lấy thống kê logs chi tiết**

**Authentication:** Session

**Query Parameters:**
(Giống như GET /api/logs - có thể filter)

**Response (200):**
```json
{
  "success": true,
  "total": 10000,
  "allowed": 8000,
  "blocked": 1500,
  "warnings": 500,
  "filtered_total": 1000,
  "filtered_allowed": 800,
  "filtered_blocked": 150,
  "filtered_warnings": 50,
  "has_filters": true,
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Chức năng:**
- Trả về tổng số logs và phân loại theo action
- Hỗ trợ filtered statistics khi có filters

---

### 5.4 DELETE /api/logs/clear
**Xóa logs với filters**

**Authentication:** Session

**Request Body:**
```json
{
  "action": "filtered",
  "filters": {
    "agent_id": "agt_abc123",
    "time_range": "30d"
  }
}
```

**Actions:**
- `all`: Xóa tất cả logs
- `old`: Xóa logs > 30 ngày
- `selected`: Xóa logs theo log_ids
- `filtered`: Xóa logs theo filters

**Response (200):**
```json
{
  "success": true,
  "deleted_count": 500,
  "message": "Logs cleared successfully"
}
```

**Chức năng:**
- Xóa logs theo điều kiện
- Emit SocketIO event "logs_cleared"

---

### 5.5 DELETE /api/logs
**Xóa tất cả logs**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "deleted_count": 10000,
  "message": "All logs cleared"
}
```

---

### 5.6 GET /api/logs/export
**Export logs**

**Authentication:** Session

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| format | string | json | Format (json/csv) |
| (filters) | - | - | Tất cả filter params như GET /api/logs |

**Response (200) - JSON:**
```json
{
  "success": true,
  "data": [ ... ],
  "count": 1000
}
```

**Response (200) - CSV:**
```csv
timestamp,agent_id,level,action,domain,message
2025-01-01T12:00:00+07:00,agt_abc123,INFO,ALLOWED,google.com,DNS query allowed
```
(Với Content-Disposition: attachment)

---

## 6. Group Endpoints

### 6.1 GET /api/groups
**Lấy danh sách groups**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "_id": "grp_abc123",
      "name": "Development Team",
      "description": "Developers group",
      "agent_count": 5,
      "whitelist_count": 20,
      "created_at": "2025-01-01T10:00:00+07:00"
    }
  ]
}
```

---

### 6.2 POST /api/groups
**Tạo group mới**

**Authentication:** Session

**Request Body:**
```json
{
  "name": "QA Team",
  "description": "Quality Assurance team",
  "whitelist": ["google.com", "*.jira.com"]
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "_id": "grp_newgroup123",
    "name": "QA Team",
    "description": "Quality Assurance team",
    "whitelist": ["google.com", "*.jira.com"],
    "agent_count": 0,
    "created_at": "2025-01-01T12:00:00+07:00"
  }
}
```

---

### 6.3 GET /api/groups/{group_id}
**Lấy chi tiết group**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "data": {
    "_id": "grp_abc123",
    "name": "Development Team",
    "description": "Developers group",
    "whitelist": ["*.github.com", "*.stackoverflow.com"],
    "agents": [
      {
        "agent_id": "agt_abc123",
        "hostname": "DEV-PC-01",
        "status": "active"
      }
    ],
    "agent_count": 5,
    "created_at": "2025-01-01T10:00:00+07:00"
  }
}
```

---

### 6.4 PATCH /api/groups/{group_id}
**Cập nhật group**

**Authentication:** Session

**Request Body:**
```json
{
  "name": "Development Team - Updated",
  "description": "New description",
  "whitelist": ["*.github.com", "*.stackoverflow.com", "*.docker.com"]
}
```

**Response (200):**
```json
{
  "success": true,
  "data": { ... }
}
```

---

### 6.5 DELETE /api/groups/{group_id}
**Xóa group**

**Authentication:** Session

**Response (200):**
```json
{
  "success": true,
  "message": "Group deleted"
}
```

**Chức năng:**
- Xóa group
- Agents trong group sẽ được đặt group_id = null

---

## 7. API Key Endpoints

### 7.1 GET /api/api-keys
**Lấy danh sách API keys**

**Authentication:** Session (Admin)

**Query Parameters:**
| Parameter | Type | Default | Mô tả |
|-----------|------|---------|-------|
| page | int | 1 | Số trang |
| limit | int | 20 | Số lượng/trang (max 100) |
| include_revoked | bool | false | Bao gồm keys đã revoke |

**Response (200):**
```json
{
  "success": true,
  "keys": [
    {
      "_id": "key_abc123",
      "name": "Production Key",
      "description": "Main production API key",
      "key_prefix": "fc_abc1...",
      "permissions": ["register", "sync"],
      "is_active": true,
      "usage_count": 150,
      "last_used": "2025-01-01T12:00:00+07:00",
      "expires_at": null,
      "created_at": "2024-12-01T10:00:00+07:00"
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 20
}
```

**Lưu ý:** API key value chỉ hiển thị khi tạo mới, sau đó chỉ hiển thị prefix.

---

### 7.2 POST /api/api-keys
**Tạo API key mới**

**Authentication:** Session (Admin)

**Request Body:**
```json
{
  "name": "Development Key",
  "description": "For development environment",
  "expires_in_days": 365,
  "permissions": ["register", "sync", "logs"]
}
```

**Permissions Available:**
- `register`: Cho phép agent registration
- `sync`: Cho phép whitelist sync
- `logs`: Cho phép gửi logs
- `heartbeat`: Cho phép heartbeat
- `admin`: Full admin access

**Response (201):**
```json
{
  "success": true,
  "message": "API key created",
  "key_id": "key_newkey123",
  "api_key": "fc_abcdef123456789...",
  "name": "Development Key",
  "permissions": ["register", "sync", "logs"],
  "expires_at": "2026-01-01T12:00:00+07:00"
}
```

**⚠️ QUAN TRỌNG:** API key chỉ hiển thị MỘT LẦN khi tạo. Sau đó không thể xem lại.

---

### 7.3 GET /api/api-keys/{key_id}
**Lấy chi tiết API key**

**Authentication:** Session (Admin)

**Response (200):**
```json
{
  "success": true,
  "key": {
    "_id": "key_abc123",
    "name": "Production Key",
    "description": "Main production API key",
    "key_prefix": "fc_abc1...",
    "permissions": ["register", "sync"],
    "is_active": true,
    "usage_count": 150,
    "last_used": "2025-01-01T12:00:00+07:00",
    "created_at": "2024-12-01T10:00:00+07:00"
  }
}
```

---

### 7.4 PUT/PATCH /api/api-keys/{key_id}
**Cập nhật API key**

**Authentication:** Session (Admin)

**Request Body:**
```json
{
  "name": "Updated Key Name",
  "description": "Updated description",
  "permissions": ["register"],
  "is_active": true
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "API key updated",
  "key": { ... }
}
```

---

### 7.5 DELETE /api/api-keys/{key_id}
**Xóa (revoke) API key**

**Authentication:** Session (Admin)

Equivalent to POST /api/api-keys/{key_id}/revoke

---

### 7.6 POST /api/api-keys/{key_id}/revoke
**Revoke API key**

**Authentication:** Session (Admin)

**Response (200):**
```json
{
  "success": true,
  "message": "API key revoked"
}
```

**Chức năng:**
- Đánh dấu key là revoked
- Key không thể sử dụng nữa
- Không thể un-revoke

---

### 7.7 GET /api/api-keys/stats
**Lấy thống kê API keys**

**Authentication:** Session (Admin)

**Response (200):**
```json
{
  "success": true,
  "stats": {
    "total": 10,
    "active": 8,
    "revoked": 2,
    "expiring_soon": 1,
    "total_usage": 5000
  }
}
```

---

### 7.8 POST /api/api-keys/validate
**Validate API key (testing)**

**Authentication:** Session (Admin)

**Request Body:**
```json
{
  "api_key": "fc_abcdef123456789...",
  "permission": "register"
}
```

**Response (200):**
```json
{
  "success": true,
  "valid": true,
  "name": "Production Key",
  "permissions": ["register", "sync"]
}
```

---

## 8. Auth Endpoints

### 8.1 POST /api/auth/refresh
**Refresh access token**

**Request Body:**
```json
{
  "refresh_token": "eyJ...",
  "rotate": false
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "expires_at": "2025-01-02T12:00:00+07:00"
  }
}
```

**Với rotate=true:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 86400
  }
}
```

**Chức năng:**
- Tạo access token mới từ refresh token
- Nếu rotate=true, tạo refresh token mới (security best practice)
- Emit SocketIO event "token_refreshed"

---

### 8.2 POST /api/auth/logout
**Logout agent**

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body (optional):**
```json
{
  "refresh_token": "eyJ...",
  "revoke_all": false
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out successfully",
  "data": {
    "revoked_count": 2
  }
}
```

**Chức năng:**
- Revoke access token
- Revoke refresh token (nếu provided)
- Nếu revoke_all=true, revoke tất cả tokens của agent
- Emit SocketIO event "agent_logout"

---

### 8.3 POST /api/auth/verify
**Verify token**

**Request Body:**
```json
{
  "token": "eyJ...",
  "token_type": "access"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "valid": true,
    "agent_id": "agt_abc123",
    "user_id": "device-123",
    "token_type": "access",
    "expires_at": 1704067200
  }
}
```

---

### 8.4 GET /api/auth/token-info
**Lấy thông tin token**

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "agent_id": "agt_abc123",
    "token_type": "access",
    "is_expired": false,
    "is_revoked": false,
    "expires_at": "2025-01-02T12:00:00+07:00"
  }
}
```

---

## 9. Admin Endpoints

### 9.1 POST /api/admin/login
**Admin login**

**Rate Limited:** Yes

**Request Body:**
```json
{
  "email": "admin@example.com",
  "password": "secure_password"
}
```

**Response (200) - Không có 2FA:**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "admin": {
      "id": "adm_abc123",
      "email": "admin@example.com",
      "full_name": "John Admin",
      "role": "admin"
    },
    "tenant": {
      "id": "tnt_xyz789",
      "name": "My Organization"
    },
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

**Response (200) - Yêu cầu 2FA:**
```json
{
  "success": true,
  "data": {
    "requires_2fa": true,
    "admin_id": "adm_abc123",
    "email": "admin@example.com",
    "message": "2FA verification required"
  }
}
```

---

### 9.2 POST /api/admin/verify-2fa
**Verify 2FA code**

**Rate Limited:** Yes

**Request Body:**
```json
{
  "admin_id": "adm_abc123",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "admin": { ... },
    "tenant": { ... },
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

---

### 9.3 POST /api/admin/register
**Register admin mới**

**Rate Limited:** Yes

**Request Body:**
```json
{
  "email": "newadmin@example.com",
  "password": "secure_password",
  "full_name": "New Admin",
  "tenant_name": "New Organization"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Admin created successfully",
  "data": {
    "id": "adm_newabc123",
    "email": "newadmin@example.com",
    "full_name": "New Admin",
    "tenant_id": "tnt_newxyz789"
  }
}
```

**Chức năng:**
- Tạo tenant mới (organization)
- Tạo admin với role "admin"
- Admin là owner của tenant

---

### 9.4 POST /api/admin/logout
**Admin logout**

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

**Chức năng:**
- Clear session
- Client xóa tokens

---

### 9.5 POST /api/admin/set-session
**Set session cookie sau login**

**Request Body:**
```json
{
  "admin_id": "adm_abc123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Session established"
}
```

---

### 9.6 GET /api/admin/profile
**Lấy profile admin**

**Query Parameters:**
| Parameter | Type | Mô tả |
|-----------|------|-------|
| admin_id | string | ID của admin |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "adm_abc123",
    "email": "admin@example.com",
    "full_name": "John Admin",
    "phone": "+84123456789",
    "role": "admin",
    "two_factor_enabled": false,
    "created_at": "2024-12-01T10:00:00+07:00"
  }
}
```

---

### 9.7 PUT /api/admin/profile
**Cập nhật profile**

**Request Body:**
```json
{
  "admin_id": "adm_abc123",
  "full_name": "Updated Name",
  "phone": "+84987654321"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "data": { ... }
}
```

---

### 9.8 POST /api/admin/change-password
**Đổi password**

**Request Body:**
```json
{
  "admin_id": "adm_abc123",
  "old_password": "current_password",
  "new_password": "new_secure_password"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

---

### 9.9 POST /api/admin/2fa/enable
**Bật 2FA**

**Request Body:**
```json
{
  "admin_id": "adm_abc123",
  "method": "email"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "2FA enabled successfully"
}
```

---

### 9.10 POST /api/admin/2fa/disable
**Tắt 2FA**

**Request Body:**
```json
{
  "admin_id": "adm_abc123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "2FA disabled successfully"
}
```

---

### 9.11 GET /api/admin/list
**Lấy danh sách admins trong tenant**

**Query Parameters:**
| Parameter | Type | Mô tả |
|-----------|------|-------|
| tenant_id | string | ID của tenant |
| skip | int | Bỏ qua bao nhiêu records |
| limit | int | Số lượng tối đa |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "admins": [
      {
        "id": "adm_abc123",
        "email": "admin@example.com",
        "full_name": "John Admin",
        "role": "admin",
        "status": "active"
      }
    ],
    "total": 3
  }
}
```

---

### 9.12 POST /api/admin/create
**Tạo admin mới trong tenant**

**Request Body:**
```json
{
  "email": "newadmin@example.com",
  "password": "secure_password",
  "full_name": "New Admin",
  "tenant_id": "tnt_xyz789"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Admin created successfully",
  "data": { ... }
}
```

---

### 9.13 PUT /api/admin/{admin_id}
**Cập nhật admin**

**Request Body:**
```json
{
  "full_name": "Updated Name",
  "role": "admin"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Admin updated successfully",
  "data": { ... }
}
```

---

### 9.14 POST /api/admin/{admin_id}/suspend
**Suspend admin**

**Request Body:**
```json
{
  "reason": "Policy violation"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Admin suspended successfully"
}
```

---

### 9.15 POST /api/admin/{admin_id}/activate
**Activate admin**

**Response (200):**
```json
{
  "success": true,
  "message": "Admin activated successfully"
}
```

---

## 10. Web Pages & Utility Endpoints

### 10.1 Web Pages (HTML)

| Route | Authentication | Mô tả |
|-------|----------------|-------|
| GET / | None | Dashboard |
| GET /agents | Session | Agent management page |
| GET /groups | Session | Group management page |
| GET /groups/{group_id} | Session | Group detail page |
| GET /whitelist | Session | Whitelist management page |
| GET /logs | Session | Logs page |
| GET /api-keys | Session | API Keys management page |
| GET /admin | None | Admin login page |

---

### 10.2 GET /api/health
**Health check endpoint**

**Authentication:** None

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "architecture": "MVC",
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

---

### 10.3 GET /api/config
**Client configuration**

**Authentication:** None

**Response (200):**
```json
{
  "socketio_enabled": true,
  "version": "1.0.0",
  "architecture": "MVC",
  "environment": "production",
  "timezone": "vietnam",
  "server_time": "2025-01-01T12:00:00+07:00"
}
```

---

## 11. SocketIO Events

### 11.1 Client → Server Events

| Event | Payload | Mô tả |
|-------|---------|-------|
| `connect` | - | Client kết nối |
| `disconnect` | - | Client ngắt kết nối |
| `ping` | `{ data: any }` | Ping server |

### 11.2 Server → Client Events

| Event | Payload | Trigger |
|-------|---------|---------|
| `server_message` | `{ type, message, timestamp }` | Welcome khi connect |
| `pong` | `{ timestamp, client_data }` | Response to ping |
| `agent_registered` | `{ agent_id, user_id, hostname, ip_address, status, timestamp }` | Agent đăng ký mới |
| `agent_heartbeat` | `{ agent_id, hostname, status, last_heartbeat, metrics, ... }` | Agent heartbeat |
| `agent_deleted` | `{ agent_id, hostname, timestamp }` | Agent bị xóa |
| `agent_group_updated` | `{ agent_id, hostname, group_id, status, timestamp }` | Agent đổi group |
| `agent_logout` | `{ agent_id, timestamp }` | Agent logout |
| `whitelist_updated` | `{ action, type/count, timestamp }` | Whitelist thay đổi |
| `logs_received` | `{ agent_id, count, timestamp }` | Logs nhận được |
| `logs_cleared` | `{ action, deleted_count, timestamp }` | Logs bị xóa |
| `token_refreshed` | `{ agent_id, rotated, timestamp }` | Token được refresh |

---

## Phụ lục: Error Codes

| Code | Ý nghĩa |
|------|---------|
| `INVALID_API_KEY` | API Key không hợp lệ hoặc hết hạn |
| `INVALID_TOKEN` | JWT token không hợp lệ |
| `TOKEN_EXPIRED` | JWT token hết hạn |
| `REFRESH_TOKEN_EXPIRED` | Refresh token hết hạn |
| `TOKEN_REVOKED` | Token đã bị revoke |
| `PERMISSION_DENIED` | Không có quyền |
| `RATE_LIMITED` | Quá nhiều request |
| `VALIDATION_ERROR` | Dữ liệu không hợp lệ |
| `NOT_FOUND` | Không tìm thấy resource |
| `DUPLICATE_ENTRY` | Entry đã tồn tại |

---

## Phụ lục: Rate Limits

| Endpoint | Limit |
|----------|-------|
| POST /api/admin/login | 5 requests/minute |
| POST /api/admin/register | 3 requests/minute |
| POST /api/admin/verify-2fa | 5 requests/minute |
| POST /api/agents/register | 10 requests/minute per IP |
| POST /api/agents/heartbeat | 60 requests/minute per agent |
| POST /api/logs | 100 requests/minute per agent |

---

*Tài liệu này được tạo tự động dựa trên source code.*
*Phiên bản: 1.0.0 | Cập nhật: 2025*
