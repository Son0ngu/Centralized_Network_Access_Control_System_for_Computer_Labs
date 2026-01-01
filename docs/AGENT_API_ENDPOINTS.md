# AGENT ENDPOINTS & INTERFACES - TÀI LIỆU CHI TIẾT

## Mục lục
1. [Tổng quan](#1-tổng-quan)
2. [DNS Proxy Server (Port 53)](#2-dns-proxy-server-port-53)
3. [Server API Endpoints (Agent gọi đến Server)](#3-server-api-endpoints-agent-gọi-đến-server)
4. [Internal Service Interfaces](#4-internal-service-interfaces)
5. [GUI Controllers](#5-gui-controllers)
6. [Configuration Endpoints](#6-configuration-endpoints)

---

## 1. Tổng quan

### Agent Architecture
Agent là một ứng dụng desktop Python chạy trên Windows, bao gồm các thành phần chính:

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENT APPLICATION                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   DNS Proxy      │  │   GUI App        │                 │
│  │   (Port 53)      │  │   (CustomTkinter)│                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
│           │                     │                            │
│  ┌────────┴─────────────────────┴─────────┐                 │
│  │              Core Services              │                 │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │                 │
│  │  │Whitelist│ │Heartbeat│ │  Log    │   │                 │
│  │  │ Manager │ │ Sender  │ │ Sender  │   │                 │
│  │  └─────────┘ └─────────┘ └─────────┘   │                 │
│  └─────────────────────────────────────────┘                 │
│           │                                                  │
│  ┌────────┴─────────────────────────────────┐               │
│  │           Network Layer                   │               │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐     │               │
│  │  │Firewall │ │ Token   │ │ Network │     │               │
│  │  │ Manager │ │ Manager │ │ Manager │     │               │
│  │  └─────────┘ └─────────┘ └─────────┘     │               │
│  └───────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SERVER     │
                    │  (Flask API) │
                    └──────────────┘
```

### Loại Endpoints

| Loại | Mô tả |
|------|-------|
| **DNS Proxy** | Server DNS chạy trên localhost:53, nhận DNS queries |
| **Outbound API** | Endpoints trên Server mà Agent gọi đến |
| **Internal Services** | Interfaces nội bộ giữa các components |
| **GUI Controllers** | Controllers điều khiển GUI |

---

## 2. DNS Proxy Server (Port 53)

### 2.1 Tổng quan DNS Proxy

DNS Proxy là thành phần **CHÍNH** của Agent, chịu trách nhiệm:
- Nhận tất cả DNS queries từ hệ thống
- Kiểm tra domain với whitelist
- Block domains không được phép (trả về NXDOMAIN)
- Forward queries hợp lệ đến upstream DNS
- Đồng bộ firewall rules với DNS responses

### 2.2 UDP DNS Handler

**Listen Address:** `127.0.0.1:53` (IPv4) và `::1:53` (IPv6)

**Protocol:** UDP (chuẩn DNS)

**Flow xử lý:**
```
Client App → DNS Query → Agent (Port 53) → Whitelist Check
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        │                                           │
                        ▼                                           ▼
                 [NOT IN WHITELIST]                        [IN WHITELIST]
                        │                                           │
                        ▼                                           ▼
                 Return NXDOMAIN                          Query Upstream DNS
                 (Domain blocked)                                   │
                                                                    ▼
                                                           Add Firewall Rules
                                                           (BLOCKING OPERATION)
                                                                    │
                                                                    ▼
                                                           Return DNS Response
```

**Request Format:** Standard DNS Query (RFC 1035)
```
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ID                         |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QNAME                      |
|                    QTYPE                      |
|                    QCLASS                     |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
```

**Response - Domain Allowed:**
```
DNS Response với:
- RCODE: 0 (NOERROR)
- Answer Section: IP addresses từ upstream DNS
- TTL: Theo upstream response (min 60s, max 86400s)
```

**Response - Domain Blocked:**
```
DNS Response với:
- RCODE: 3 (NXDOMAIN)
- Answer Section: Empty
- TTL: 300 seconds (negative TTL)
```

---

### 2.3 TCP DNS Handler

**Listen Address:** `127.0.0.1:53` (IPv4) và `::1:53` (IPv6)

**Protocol:** TCP (cho large responses)

**Đặc điểm:**
- Xử lý DNS queries > 512 bytes
- TCP fallback khi UDP truncated
- Format: 2-byte length prefix + DNS message

---

### 2.4 DNS Query Handler - Chi tiết xử lý

**File:** `dns_proxy/handler.py`

**Class:** `DNSQueryHandler`

#### 2.4.1 handle_query(query_data: bytes) → QueryResult

**Mô tả:** Xử lý một DNS query

**Input:**
- `query_data`: Raw DNS query bytes

**Output:**
```python
@dataclass
class QueryResult:
    success: bool           # Query xử lý thành công hay không
    response_data: bytes    # DNS response bytes để gửi về client
    domain: str             # Domain được query
    action: str             # "allowed" | "blocked" | "cached" | "error"
    ips: List[str]          # Danh sách IP resolved (nếu allowed)
    ttl: int                # TTL của response
    processing_time_ms: float  # Thời gian xử lý (ms)
    cache_hit: bool         # Có hit cache không
    firewall_synced: bool   # Đã sync firewall chưa
    error: Optional[str]    # Error message nếu có
```

**Flow chi tiết:**

```
1. Parse DNS Query
   ├─ Sử dụng dnspython library
   ├─ Extract: domain, query type (A, AAAA, MX, etc.)
   └─ Nếu parse fail → Return SERVFAIL

2. Check Essential Domains
   ├─ Essential domains: Server URLs, DNS providers
   └─ Nếu essential → Bypass whitelist check

3. Check Whitelist
   ├─ Exact match: google.com
   ├─ Wildcard match: *.google.com
   ├─ IP match (nếu query IP trực tiếp)
   └─ Nếu KHÔNG match → Return NXDOMAIN (BLOCKED)

4. Check Cache (nếu allowed)
   ├─ Cache key: domain name
   ├─ Nếu cache hit → Return cached response
   └─ Nếu cache miss → Continue

5. Query Upstream DNS
   ├─ Primary: 8.8.8.8, 8.8.4.4 (Google DNS)
   ├─ Fallback: 1.1.1.1, 1.0.0.1 (Cloudflare)
   ├─ Timeout: 5 seconds
   └─ Retry: 2 lần với failover

6. Sync Firewall Rules (BLOCKING)
   ├─ Extract IPs từ DNS response
   ├─ Add firewall allow rules cho mỗi IP
   ├─ Timeout: 3 seconds
   └─ QUAN TRỌNG: Block cho đến khi firewall rules được add

7. Cache Response
   ├─ Cache với TTL từ DNS response
   ├─ Min TTL: 60 seconds
   └─ Max TTL: 86400 seconds (1 ngày)

8. Return Response
   └─ Gửi DNS response bytes về client
```

---

### 2.5 Upstream Resolver Configuration

**File:** `dns_proxy/resolver.py`

**Default Upstream DNS:**
```python
UPSTREAM_RESOLVERS = [
    {"address": "8.8.8.8", "port": 53, "priority": 1},     # Google Primary
    {"address": "8.8.4.4", "port": 53, "priority": 2},     # Google Secondary
    {"address": "1.1.1.1", "port": 53, "priority": 3},     # Cloudflare Primary
    {"address": "1.0.0.1", "port": 53, "priority": 4},     # Cloudflare Secondary
]
```

**Health Check:**
- Interval: 30 seconds
- Domain: `dns.google`
- Max consecutive failures: 3
- Recovery wait time: 60 seconds

---

### 2.6 DNS Cache

**File:** `dns_proxy/cache.py`

**Configuration:**
```python
@dataclass
class CacheConfig:
    enabled: bool = True
    max_entries: int = 10000
    min_ttl: int = 60           # Minimum 60 seconds
    max_ttl: int = 86400        # Maximum 1 day
    negative_ttl: int = 300     # NXDOMAIN cache: 5 minutes
    cleanup_interval: int = 60  # Cleanup every 60 seconds
```

**Cache Entry:**
```python
@dataclass
class DNSCacheEntry:
    domain: str
    ips: List[str]
    ttl: int
    created_at: float
    expires_at: float
    is_blocked: bool = False
```

---

### 2.7 Firewall Sync

**File:** `dns_proxy/firewall_sync.py`

**Configuration:**
```python
@dataclass
class FirewallSyncConfig:
    timeout: float = 3.0        # 3 seconds max wait
    retry_on_failure: bool = True
    max_retries: int = 2
    retry_delay: float = 0.5
```

**Sync Result:**
```python
@dataclass
class SyncResult:
    success: bool
    rules_added: int
    ips: List[str]
    ttl: int
    error: Optional[str] = None
```

**Flow:**
```
1. Nhận IPs từ DNS response
2. Với mỗi IP:
   a. Kiểm tra rule đã tồn tại chưa
   b. Nếu chưa → Add Windows Firewall rule
   c. Set TTL cho rule (để auto-remove khi hết hạn)
3. Return kết quả
```

---

## 3. Server API Endpoints (Agent gọi đến Server)

Agent gọi các endpoints sau trên Server:

### 3.1 POST /api/agents/register
**Agent đăng ký với Server**

**Trigger:** Khi Agent khởi động lần đầu hoặc chưa có agent_id

**File:** `core/registry.py`

**Headers:**
```
Content-Type: application/json
X-API-Key: fc_xxxxxxxxxxxxxxxx  # Required for authentication
```

**Request Body:**
```json
{
  "hostname": "DESKTOP-ABC123",
  "device_id": "sha256-hash-of-hardware-ids",
  "ip_address": "192.168.1.100",
  "platform": "Windows 10 Pro",
  "os_info": "Windows 10.0.19041",
  "agent_version": "1.0.0",
  "python_version": "3.11.0",
  "admin_privileges": true,
  "capabilities": {
    "packet_capture": true,
    "firewall_management": true,
    "whitelist_sync": true
  },
  "registration_time": "2025-01-01T12:00:00+07:00",
  "registration_timestamp": 1735711200.0
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "agent_id": "agt_abc123def456",
    "user_id": "device-id-hash",
    "token": "legacy-token",
    "jwt": {
      "access_token": "eyJ...",
      "refresh_token": "eyJ...",
      "token_type": "Bearer",
      "access_expires_at": "2025-01-02T12:00:00+07:00",
      "refresh_expires_at": "2025-01-31T12:00:00+07:00"
    },
    "server_time": "2025-01-01T12:00:00+07:00",
    "config": {
      "heartbeat_interval": 60,
      "log_batch_size": 50
    }
  }
}
```

**Lưu trữ sau khi đăng ký:**
- `config['agent_id']` = agent_id
- `config['agent_token']` = legacy token
- `config['jwt']` = JWT tokens
- `agent_state['agent_id']` = agent_id
- `agent_state['registration_completed']` = True

---

### 3.2 POST /api/agents/heartbeat
**Gửi heartbeat định kỳ**

**Trigger:** Mỗi 20-60 giây (configurable)

**File:** `services/heartbeat.py`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer eyJ...  # JWT Access Token
```

**Request Body:**
```json
{
  "agent_id": "agt_abc123def456",
  "token": "legacy-token",
  "device_id": "device-id-hash",
  "timestamp": "2025-01-01T12:00:00+07:00",
  "status": "active",
  "platform": "Windows 10 Pro",
  "os_info": "Windows 10.0.19041",
  "agent_version": "1.0.0",
  "metrics": {
    "memory_percent": 65.5,
    "disk_percent": 45.2,
    "uptime_seconds": 86400,
    "timestamp": "2025-01-01T12:00:00+07:00"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "status": "active",
    "server_time": "2025-01-01T12:00:00+07:00",
    "sync_required": false,
    "config_update": null
  }
}
```

**Retry Logic:**
- Interval: 20 seconds (default)
- Retry interval on failure: 5 seconds
- Max consecutive failures: 3
- Exponential backoff: None (fixed retry interval)

---

### 3.3 GET /api/whitelist/agent-sync
**Đồng bộ whitelist từ Server**

**Trigger:** 
- Khi Agent khởi động
- Định kỳ mỗi 60 giây
- Khi nhận thông báo sync_required từ heartbeat

**File:** `whitelist/sync.py`

**Headers:**
```
User-Agent: FirewallController-Agent/2.2-Modular
Authorization: Bearer eyJ...  # JWT Access Token
```

**Query Parameters:**
| Parameter | Type | Mô tả |
|-----------|------|-------|
| version | int | Phiên bản whitelist hiện tại của agent |
| group_version | int | Phiên bản group whitelist |

**Response (200):**
```json
{
  "success": true,
  "domains": [
    {
      "id": "wl_abc123",
      "value": "google.com",
      "type": "domain",
      "category": "search",
      "is_active": true,
      "scope": "global"
    },
    {
      "id": "wl_def456",
      "value": "*.microsoft.com",
      "type": "wildcard",
      "category": "software",
      "is_active": true,
      "scope": "group"
    }
  ],
  "version": 16,
  "group_version": 5,
  "count": 2,
  "timestamp": "2025-01-01T12:00:00+07:00"
}
```

**Retry Logic:**
- Max retries: 3
- Backoff: Exponential (2^attempt seconds)
- Fallback: Try alternative server URLs

---

### 3.4 POST /api/logs
**Gửi logs lên Server**

**Trigger:** 
- Khi batch đủ 100 logs
- Hoặc mỗi 2 giây nếu có logs trong queue

**File:** `logging_module/sender.py`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer eyJ...  # JWT Access Token
```

**Request Body:**
```json
{
  "logs": [
    {
      "timestamp": "2025-01-01T12:00:00+07:00",
      "agent_id": "agt_abc123",
      "level": "INFO",
      "action": "ALLOWED",
      "domain": "google.com",
      "source_ip": "192.168.1.100",
      "dest_ip": "142.250.66.46",
      "protocol": "DNS",
      "port": "53",
      "message": "DNS query allowed for google.com"
    },
    {
      "timestamp": "2025-01-01T12:00:01+07:00",
      "agent_id": "agt_abc123",
      "level": "WARNING",
      "action": "BLOCKED",
      "domain": "malware.com",
      "source_ip": "192.168.1.100",
      "dest_ip": "unknown",
      "protocol": "DNS",
      "port": "53",
      "message": "Domain blocked - not in whitelist"
    }
  ]
}
```

**Response (200):**
```json
{
  "success": true,
  "received_count": 2,
  "server_time": "2025-01-01T12:00:05+07:00"
}
```

**Queue Configuration:**
- Max queue size: 1000 logs
- Batch size: 100 logs
- Send interval: 2 seconds
- Timeout: 15 seconds

---

### 3.5 POST /api/auth/refresh
**Làm mới JWT Access Token**

**Trigger:** Khi access token sắp hết hạn (trước 5 phút)

**File:** `core/token_manager.py`

**Headers:**
```
Content-Type: application/json
```

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
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "expires_at": "2025-01-02T12:00:00+07:00"
  }
}
```

**Response (200) - với rotate=true:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_at": "2025-01-02T12:00:00+07:00",
    "refresh_expires_at": "2025-01-31T12:00:00+07:00"
  }
}
```

**Token Refresh Logic:**
```
1. Check access_token expiry
2. If expires within 5 minutes:
   a. Call /api/auth/refresh
   b. Update stored tokens
   c. Continue operations
3. If refresh fails:
   a. Check error code
   b. REFRESH_TOKEN_EXPIRED → Re-register agent
   c. TOKEN_REVOKED → Re-register agent
   d. Other → Retry
```

---

## 4. Internal Service Interfaces

### 4.1 WhitelistManager

**File:** `whitelist/manager.py`

**Interface:**
```python
class WhitelistManager:
    def __init__(self, config: Dict):
        """Khởi tạo với configuration"""
    
    def start_sync(self) -> None:
        """Bắt đầu periodic sync với server"""
    
    def stop_sync(self) -> None:
        """Dừng periodic sync"""
    
    def sync_now(self) -> bool:
        """Sync ngay lập tức, return True nếu thành công"""
    
    def is_allowed(self, domain: str, ip: Optional[str] = None) -> bool:
        """Kiểm tra domain/IP có trong whitelist không"""
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Kiểm tra IP có được phép không"""
    
    def get_stats(self) -> Dict:
        """Lấy thống kê whitelist"""
    
    def get_cache_info(self) -> Dict:
        """Lấy thông tin cache"""
    
    def on_sync_complete(self, callback: Callable[[], None]) -> None:
        """Đăng ký callback khi sync hoàn thành"""
```

**Statistics:**
```python
{
    "domains_count": 150,
    "patterns_count": 20,
    "ips_count": 30,
    "last_sync": "2025-01-01T12:00:00+07:00",
    "sync_errors": 0,
    "version": 16
}
```

---

### 4.2 WhitelistState

**File:** `whitelist/state.py`

**Interface:**
```python
class WhitelistState:
    def __init__(self):
        """Khởi tạo state rỗng"""
    
    def update(self, data: Dict) -> bool:
        """Cập nhật state từ server response"""
    
    def is_domain_allowed(self, domain: str) -> bool:
        """Kiểm tra domain - exact + wildcard match"""
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Kiểm tra IP"""
    
    def get_stats(self) -> Dict:
        """Lấy thống kê"""
    
    def get_all_domains(self) -> Set[str]:
        """Lấy tất cả domains"""
    
    def get_all_patterns(self) -> Set[str]:
        """Lấy tất cả wildcard patterns"""
    
    def get_all_ips(self) -> Set[str]:
        """Lấy tất cả IPs"""
    
    def clear(self) -> None:
        """Xóa toàn bộ state"""
```

**Domain Matching Algorithm:**
```python
def is_domain_allowed(self, domain: str) -> bool:
    domain = domain.lower().strip().rstrip('.')
    
    # 1. Exact match
    if domain in self._domains:
        return True
    
    # 2. Wildcard match (*.example.com)
    parts = domain.split('.')
    for i in range(len(parts)):
        pattern = '*.' + '.'.join(parts[i:])
        if pattern in self._patterns:
            return True
    
    # 3. Parent domain match
    for i in range(1, len(parts)):
        parent = '.'.join(parts[i:])
        if parent in self._domains:
            return True
    
    return False
```

---

### 4.3 HeartbeatSender

**File:** `services/heartbeat.py`

**Interface:**
```python
class HeartbeatSender:
    def __init__(self, config: Dict):
        """Khởi tạo với configuration"""
    
    def set_agent_credentials(self, agent_id: str, token: str) -> None:
        """Set credentials sau khi đăng ký"""
    
    def start(self) -> None:
        """Bắt đầu gửi heartbeat định kỳ"""
    
    def stop(self) -> None:
        """Dừng heartbeat"""
    
    def get_status(self) -> Dict:
        """Lấy trạng thái hiện tại"""
```

**Configuration:**
```python
{
    "heartbeat": {
        "enabled": True,
        "interval": 20,          # seconds
        "timeout": 10,           # seconds
        "retry_interval": 5,     # seconds
        "max_failures": 3
    }
}
```

---

### 4.4 LogSender

**File:** `logging_module/sender.py`

**Interface:**
```python
class LogSender:
    def __init__(self, config: Dict):
        """Khởi tạo với configuration"""
    
    def start(self) -> None:
        """Bắt đầu sender thread"""
    
    def stop(self) -> None:
        """Dừng và flush logs còn lại"""
    
    def queue_log(self, log_data: Dict) -> bool:
        """Queue một log để gửi, return True nếu thành công"""
```

**Log Format:**
```python
{
    "timestamp": "2025-01-01T12:00:00+07:00",
    "agent_id": "agt_abc123",
    "level": "INFO",              # INFO, WARNING, ERROR, DEBUG
    "action": "ALLOWED",          # ALLOWED, BLOCKED
    "domain": "google.com",
    "source_ip": "192.168.1.100",
    "dest_ip": "142.250.66.46",
    "protocol": "DNS",
    "port": "53",
    "message": "DNS query allowed"
}
```

---

### 4.5 TokenManager

**File:** `core/token_manager.py`

**Interface:**
```python
class TokenManager:
    def __init__(self, config: Dict):
        """Khởi tạo và load tokens từ config"""
    
    def set_tokens(
        self, 
        access_token: str, 
        refresh_token: str,
        access_expires_at: str = None, 
        refresh_expires_at: str = None
    ):
        """Set tokens sau khi đăng ký/refresh"""
    
    @property
    def access_token(self) -> Optional[str]:
        """Lấy access token (auto-refresh nếu cần)"""
    
    @property
    def refresh_token(self) -> Optional[str]:
        """Lấy refresh token"""
    
    @property
    def is_authenticated(self) -> bool:
        """Kiểm tra có tokens hợp lệ không"""
    
    @property
    def is_expired(self) -> bool:
        """Kiểm tra access token đã hết hạn chưa"""
    
    def get_auth_header(self) -> Dict[str, str]:
        """Lấy Authorization header"""
    
    def on_token_refreshed(self, callback: Callable) -> None:
        """Đăng ký callback khi token được refresh"""
    
    def on_reregistration_required(self, callback: Callable) -> None:
        """Đăng ký callback khi cần đăng ký lại"""
```

**Auto-refresh Logic:**
```python
# Trong access_token property:
1. Check if token exists
2. If not → return None
3. Check if should refresh (expires within 5 minutes)
4. If should refresh → call _do_refresh()
5. Return current access token
```

---

### 4.6 FirewallManager

**File:** `firewall/manager.py`

**Interface:**
```python
class FirewallManager:
    def __init__(self, config: Dict):
        """Khởi tạo với configuration"""
    
    def add_allow_rule(self, ip: str, port: int = None, ttl: int = 3600) -> bool:
        """Thêm rule cho phép IP"""
    
    def remove_rule(self, ip: str) -> bool:
        """Xóa rule cho IP"""
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Kiểm tra IP có rule allow không"""
    
    def clear_rules(self) -> None:
        """Xóa tất cả rules đã tạo"""
    
    def get_stats(self) -> Dict:
        """Lấy thống kê rules"""
```

---

### 4.7 NetworkManager

**File:** `dns_proxy/network/network_manager.py`

**Interface:**
```python
class NetworkManager:
    def __init__(self, config: NetworkConfig = None):
        """Khởi tạo với configuration"""
    
    def start(self) -> bool:
        """Khởi động network manager"""
    
    def stop(self) -> None:
        """Dừng network manager"""
    
    def get_adapters(self) -> List[NetworkAdapter]:
        """Lấy danh sách network adapters"""
    
    def enforce_dns(self) -> EnforcementResult:
        """Enforce DNS settings (set to 127.0.0.1)"""
    
    def restore_dns(self) -> EnforcementResult:
        """Restore DNS về original settings"""
    
    def block_doh(self) -> BlockerResult:
        """Block DNS-over-HTTPS providers"""
    
    def unblock_doh(self) -> BlockerResult:
        """Unblock DNS-over-HTTPS"""
    
    def get_status(self) -> NetworkStatus:
        """Lấy trạng thái hiện tại"""
```

**Network Modes:**
```python
class NetworkMode(Enum):
    DISABLED = "disabled"     # Không làm gì
    MONITOR = "monitor"       # Chỉ theo dõi, không thay đổi
    ACTIVE = "active"         # Áp dụng thay đổi và theo dõi
```

---

## 5. GUI Controllers

### 5.1 AgentController

**File:** `gui/controllers/agent_controller.py`

**Interface:**
```python
class AgentController:
    @property
    def status(self) -> AgentStatus:
        """Trạng thái agent hiện tại"""
    
    @property
    def is_running(self) -> bool:
        """Agent có đang chạy không"""
    
    @property
    def is_connected(self) -> bool:
        """Có kết nối với server không"""
    
    def start_agent(self) -> None:
        """Khởi động agent"""
    
    def stop_agent(self) -> None:
        """Dừng agent"""
    
    def restart_agent(self) -> None:
        """Restart agent"""
    
    def sync_whitelist(self) -> None:
        """Sync whitelist ngay"""
    
    def get_stats(self) -> Dict:
        """Lấy thống kê"""
    
    def get_logs(self) -> List[Dict]:
        """Lấy logs gần đây"""
```

**Agent Status:**
```python
class AgentStatus(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()
```

**Signals (Events):**
```python
signals = AgentSignals()
signals.connect("status_changed", callback)
signals.connect("stats_updated", callback)
signals.connect("log_added", callback)
signals.connect("error", callback)
signals.connect("whitelist_synced", callback)
```

---

### 5.2 WhitelistController (GUI)

**File:** `gui/controllers/whitelist_controller.py`

**Interface:**
```python
class WhitelistController:
    def set_whitelist_manager(self, manager: WhitelistManager) -> None:
        """Set whitelist manager reference"""
    
    def get_domains(self) -> List[Dict]:
        """Lấy danh sách domains"""
    
    def get_patterns(self) -> List[Dict]:
        """Lấy danh sách wildcard patterns"""
    
    def get_ips(self) -> List[Dict]:
        """Lấy danh sách IPs"""
    
    def remove_ip(self, ip: str) -> bool:
        """Xóa IP khỏi local whitelist"""
    
    def trigger_sync(self) -> None:
        """Trigger sync từ server"""
    
    def on_data_changed(self, callback: Callable) -> None:
        """Đăng ký callback khi data thay đổi"""
    
    def on_error(self, callback: Callable) -> None:
        """Đăng ký callback khi có lỗi"""
    
    def on_success(self, callback: Callable) -> None:
        """Đăng ký callback khi thành công"""
```

---

## 6. Configuration Endpoints

### 6.1 Configuration File

**File:** `agent_config.json`

**Structure:**
```json
{
  "server": {
    "url": "https://firewall-controller.onrender.com",
    "urls": [
      "https://firewall-controller.onrender.com",
      "http://localhost:5000"
    ],
    "connect_timeout": 15,
    "read_timeout": 30
  },
  "auth": {
    "api_key": "fc_xxxxxxxxxxxxxxxxxxxxxxxx"
  },
  "heartbeat": {
    "enabled": true,
    "interval": 20,
    "timeout": 10,
    "retry_interval": 5,
    "max_failures": 3
  },
  "whitelist": {
    "sync_interval": 60,
    "cache_ttl": 300
  },
  "logging": {
    "max_queue_size": 1000,
    "batch_size": 100,
    "send_interval": 2
  },
  "firewall": {
    "enabled": true,
    "default_action": "block"
  },
  "dns_proxy": {
    "enabled": true,
    "listen_ip": "127.0.0.1",
    "port": 53,
    "upstream_dns": ["8.8.8.8", "8.8.4.4"],
    "cache_enabled": true,
    "cache_max_entries": 10000
  },
  "network": {
    "mode": "active",
    "enforce_dns": true,
    "block_doh": true,
    "monitor_drift": true
  }
}
```

---

### 6.2 Config Loader

**File:** `config/loader.py`

**Interface:**
```python
def get_config() -> Dict:
    """Load configuration từ file và environment"""

def save_config(config: Dict) -> bool:
    """Lưu configuration vào file"""

def validate_config(config: Dict) -> Tuple[bool, List[str], List[str]]:
    """Validate config, return (is_valid, errors, warnings)"""
```

---

## 7. Tổng kết Endpoints

### 7.1 DNS Proxy Endpoints (Port 53)

| Protocol | Address | Chức năng |
|----------|---------|-----------|
| UDP | 127.0.0.1:53 | Standard DNS queries (IPv4) |
| UDP | [::1]:53 | Standard DNS queries (IPv6) |
| TCP | 127.0.0.1:53 | Large DNS responses (IPv4) |
| TCP | [::1]:53 | Large DNS responses (IPv6) |

### 7.2 Server API Endpoints (Agent calls)

| Method | Endpoint | Auth | Chức năng |
|--------|----------|------|-----------|
| POST | /api/agents/register | API Key | Đăng ký agent |
| POST | /api/agents/heartbeat | JWT | Gửi heartbeat |
| GET | /api/whitelist/agent-sync | JWT | Đồng bộ whitelist |
| POST | /api/logs | JWT | Gửi logs |
| POST | /api/auth/refresh | None | Refresh JWT token |

### 7.3 Internal Services

| Service | Chức năng |
|---------|-----------|
| WhitelistManager | Quản lý và sync whitelist |
| WhitelistState | Lưu trữ và kiểm tra whitelist |
| HeartbeatSender | Gửi heartbeat định kỳ |
| LogSender | Queue và gửi logs |
| TokenManager | Quản lý JWT tokens |
| FirewallManager | Quản lý Windows Firewall rules |
| NetworkManager | Quản lý network adapters và DNS |
| DNSProxyServer | DNS server chính |
| DNSQueryHandler | Xử lý DNS queries |

---

*Tài liệu này được tạo tự động dựa trên source code.*
*Phiên bản: 1.0.0 | Cập nhật: 2025*
