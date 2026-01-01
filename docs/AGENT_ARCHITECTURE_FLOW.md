# Tài liệu Kiến trúc và Flow hoạt động của Agent

## Tổng quan

Agent là một ứng dụng bảo mật mạng chạy trên Windows, có nhiệm vụ kiểm soát lưu lượng mạng thông qua cơ chế **DNS Proxy/Sinkhole**. Agent hoạt động như một DNS server cục bộ (127.0.0.1:53), chặn các truy vấn DNS không nằm trong whitelist bằng cách trả về NXDOMAIN.

---

## 1. Kiến trúc tổng thể

### 1.1. Các thành phần chính

| Module | Chức năng | Vai trò |
|--------|-----------|---------|
| **Core** | Quản lý vòng đời Agent | Khởi tạo, đăng ký, dừng |
| **DNS Proxy** | Xử lý truy vấn DNS | **PRIMARY** - Enforcement whitelist |
| **Whitelist** | Quản lý danh sách cho phép | Đồng bộ từ server, lưu cache |
| **Firewall** | Quản lý rule firewall | Cleanup, tương thích legacy |
| **Network** | Cấu hình mạng | Ép DNS về 127.0.0.1, chặn DoH/DoT |
| **Services** | Dịch vụ nền | Heartbeat, Windows Service |
| **Capture** | Bắt gói tin | OPTIONAL - Phát hiện bypass |
| **Logging** | Gửi log về server | Batch queue, async |
| **GUI** | Giao diện người dùng | Quản lý, giám sát |

### 1.2. Mô hình hoạt động (Phase 1 - DNS Proxy Architecture)

```
                                    ┌─────────────────┐
                                    │   Server API    │
                                    │ (Whitelist sync)│
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
            ┌───────────────┐      ┌─────────────────┐      ┌─────────────────┐
            │   Whitelist   │      │   Heartbeat     │      │   Log Sender    │
            │   Manager     │◄────►│   Sender        │      │   (Queue)       │
            └───────┬───────┘      └─────────────────┘      └─────────────────┘
                    │
                    │ (sync state)
                    ▼
            ┌───────────────────────────────────────────────────────────────┐
            │                    DNS Proxy Orchestrator                     │
            │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
            │  │ DNS Server  │  │  Network    │  │  Security   │           │
            │  │ (127.0.0.1) │  │  Manager    │  │  Manager    │           │
            │  └──────┬──────┘  └─────────────┘  └─────────────┘           │
            └─────────┼────────────────────────────────────────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │  DNS Handler    │ ←── Xử lý query, check whitelist
            │  (Query Flow)   │
            └────────┬────────┘
                     │
        ┌────────────┼────────────┐
        │ Whitelist? │            │
        ▼            ▼            ▼
    ┌───────┐   ┌────────┐   ┌────────────┐
    │ BLOCK │   │ ALLOW  │   │ Cache Hit  │
    │NXDOMAIN│  │Forward │   │ Return     │
    └───────┘   │Upstream│   └────────────┘
                └───┬────┘
                    │
                    ▼
            ┌───────────────┐
            │ Firewall Sync │ ←── Thêm rule TRƯỚC khi trả response
            │ (Blocking)    │
            └───────────────┘
```

---

## 2. Flow khởi động Agent

### 2.1. Điểm vào (Entry Point)

**File**: `agent_main.py` hoặc `agent_gui.py`

1. Load configuration từ `agent_config.json`
2. Validate configuration
3. Check quyền Administrator
4. Gọi `initialize_components(config)`

### 2.2. Thứ tự khởi tạo components (lifecycle.py)

```
Step 1: Register with Server
    │
    ├── POST /api/agents/register
    ├── Nhận agent_id, agent_token (JWT)
    └── Lưu credentials vào config
    │
Step 2: Initialize Token Manager
    │
    ├── Load tokens từ config
    ├── Start auto-refresh thread
    └── Callback: re-register nếu token hết hạn
    │
Step 3: Initialize Whitelist Manager
    │
    ├── Create WhitelistState (lưu domains, patterns, IPs)
    ├── Create WhitelistSyncer (gọi API server)
    └── Sync immediately (lấy whitelist từ server)
    │
Step 4: Initialize Firewall Manager
    │
    ├── Load existing rules
    ├── Backup current policy
    └── Mode: DNS Proxy (rules disabled, chỉ cleanup)
    │
Step 4.5: Start Whitelist Periodic Sync
    │
    └── Thread chạy mỗi 60s để sync whitelist
    │
Step 5: Initialize DNS Proxy Orchestrator (PRIMARY)
    │
    ├── 5.1: Start Enhanced Firewall Sync
    ├── 5.2: Start Security Manager (block DoH/DoT)
    ├── 5.3: Start DNS Server (127.0.0.1:53) ← PHẢI trước Network Manager
    └── 5.4: Start Network Manager (ép DNS về 127.0.0.1)
    │
Step 6: Initialize Log Sender
    │
    ├── Create queue (max 1000 logs)
    └── Start sender thread (batch mỗi 2s)
    │
Step 7: Initialize Heartbeat Sender
    │
    └── POST /api/agents/heartbeat mỗi 20s
    │
Step 8: Initialize Packet Sniffer (OPTIONAL)
    │
    ├── Mode: bypass_detection_only
    └── Chỉ phát hiện DoH bypass, không block
```

---

## 3. Flow xử lý DNS Query

### 3.1. Luồng xử lý chính (DNSQueryHandler)

```
[1] Client gửi DNS Query
        │
        ▼
[2] DNS Server nhận query (UDP/TCP port 53)
        │
        ▼
[3] Parse DNS packet → Extract domain name
        │
        ▼
[4] Check Essential Domains
    │   (Server URLs bypass whitelist)
    │
    ├── YES → Bỏ qua whitelist check
    │
    └── NO ↓
            │
[5] Check Whitelist (WhitelistState)
    │
    ├── Domain có trong _domains? → ALLOWED
    ├── Match pattern trong _patterns? → ALLOWED
    ├── IP có trong _ips? → ALLOWED
    │
    └── Không match → BLOCKED
            │
            ▼
[6] BLOCKED: Return NXDOMAIN
        │
        ├── Cache blocked response
        ├── Log blocked domain
        └── Return NXDOMAIN to client
            │
            (Client không thể kết nối domain)
```

### 3.2. Luồng khi domain được ALLOWED

```
[5] Domain ALLOWED
        │
        ▼
[6] Check DNS Cache
    │
    ├── Cache HIT → Return cached response
    │
    └── Cache MISS ↓
            │
[7] Query Upstream Resolver
        │
        ├── Primary: 8.8.8.8
        ├── Fallback: 1.1.1.1, 208.67.222.222
        └── Nhận IPs + TTL
            │
            ▼
[8] ★ BLOCKING: Add Firewall Rules ★
        │
        ├── Timeout: 3 giây (configurable)
        ├── Thêm rule ALLOW cho mỗi IP
        ├── Track TTL để cleanup sau
        │
        ├── SUCCESS → Continue
        │
        └── TIMEOUT/FAIL → Return SERVFAIL
                │
                (Không trả IP nếu firewall chưa sẵn sàng)
            │
            ▼
[9] Cache Response
        │
        ├── Lưu domain → IPs mapping
        ├── Lưu TTL
        └── Mark firewall_rules_added = true
            │
            ▼
[10] Return DNS Response to Client
        │
        └── Client có thể kết nối (firewall đã allow)
```

---

## 4. Flow đồng bộ Whitelist

### 4.1. Sync từ Server

```
[1] WhitelistManager.sync_now()
        │
        ▼
[2] WhitelistSyncer.sync_with_server()
        │
        ├── Build URL: /api/whitelist/agent-sync
        ├── Add JWT headers (Authorization: Bearer <token>)
        └── Send params: agent_id, last_sync_time, checksum
            │
            ▼
[3] Server Response
        │
        ├── has_updates: true/false
        ├── domains: ["example.com", "*.google.com"]
        ├── ips: ["192.168.1.1"]
        ├── patterns: ["*.cdn.com"]
        └── version, checksum
            │
            ▼
[4] WhitelistState.update(data)
        │
        ├── Update _domains set
        ├── Update _patterns set
        ├── Update _ips set
        ├── Calculate new checksum
        └── Update metadata
            │
            ▼
[5] Notify DNS Proxy
        │
        └── Handler sử dụng state mới ngay lập tức
```

### 4.2. Periodic Sync Loop

```
[WhitelistManager._sync_loop]
        │
        └── while running:
                │
                ├── sync_now()
                ├── sleep(sync_interval) # default 60s
                └── repeat
```

---

## 5. Flow Network Manager

### 5.1. DNS Enforcement

```
[1] NetworkManager.apply()
        │
        ▼
[2] DNSEnforcer.enforce_all_adapters()
        │
        ├── Scan tất cả network adapters
        ├── Filter: chỉ Ethernet, Wi-Fi (không Virtual)
        │
        └── Với mỗi adapter:
                │
                ├── Backup DNS hiện tại
                ├── Set DNS IPv4 = 127.0.0.1
                └── Set DNS IPv6 = ::1 (nếu enabled)
            │
            ▼
[3] Start Drift Monitor
        │
        └── Check mỗi 30s:
                │
                ├── DNS bị thay đổi? (user/malware)
                └── AUTO_RESTORE nếu bị thay đổi
```

### 5.2. DoH/DoT Blocking

```
[1] SecurityManager.enable()
        │
        ▼
[2] DoHBlocker.block_all()
        │
        ├── Lấy danh sách DoH providers
        │   (dns.google, cloudflare-dns.com, ...)
        │
        ├── Block by Domain (hosts file)
        │
        └── Block by IP (firewall rules)
                │
                ├── 8.8.8.8:443 (Google DoH)
                ├── 1.1.1.1:443 (Cloudflare DoH)
                └── ... (100+ IPs)
            │
            ▼
[3] Block DoT port 853
        │
        └── Firewall rule: Block outbound TCP 853
```

---

## 6. Flow Heartbeat và Token

### 6.1. Heartbeat Loop

```
[HeartbeatSender._heartbeat_loop]
        │
        └── while running:
                │
                ├── Collect metrics (CPU, RAM, uptime)
                ├── POST /api/agents/heartbeat
                │       │
                │       ├── Headers: Authorization: Bearer <token>
                │       └── Body: agent_id, metrics, timestamp
                │
                ├── Success → reset failure counter
                ├── Failure → increment counter
                │       │
                │       └── 3 failures → trigger reconnect
                │
                └── sleep(interval) # default 20s
```

### 6.2. Token Auto-Refresh

```
[TokenManager._auto_refresh_loop]
        │
        └── while running:
                │
                ├── Check: token sắp hết hạn? (< 5 phút)
                │       │
                │       └── YES → POST /api/auth/refresh
                │               │
                │               ├── Success → update tokens
                │               └── Fail → trigger re-registration
                │
                └── sleep(60s)
```

---

## 7. Flow Log Sender

### 7.1. Queue và Batch Send

```
[1] Gọi log_sender.queue_log(data)
        │
        ▼
[2] Add to Queue (thread-safe)
        │
        └── Queue full? → Drop log với warning
            │
            ▼
[3] Sender Loop (background thread)
        │
        └── Check mỗi 1s:
                │
                ├── Queue >= batch_size (100)?
                │   HOẶC
                ├── Có log và > send_interval (2s)?
                │
                └── YES → _send_logs()
                        │
                        ▼
[4] POST /api/logs/batch
        │
        ├── Headers: Authorization + Content-Type
        ├── Body: { logs: [...], agent_id }
        │
        ├── Success → clear batch from queue
        └── Fail → retry với server fallback
```

---

## 8. Flow Cleanup/Shutdown

### 8.1. Graceful Shutdown

```
[1] Agent.stop() hoặc Signal (SIGINT/SIGTERM)
        │
        ▼
[2] cleanup(config)
        │
        ├── Stop DNS Proxy Orchestrator
        │       │
        │       ├── Stop Network Manager FIRST
        │       │   (restore DNS trước khi tắt server)
        │       │
        │       ├── Stop DNS Server
        │       ├── Stop Security Manager
        │       └── Stop Firewall Sync
        │
        ├── Stop Whitelist Manager
        │       └── Stop sync thread
        │
        ├── Stop Heartbeat Sender
        │
        ├── Stop Log Sender
        │       └── Flush remaining logs
        │
        ├── Stop Token Manager
        │       └── Stop auto-refresh
        │
        ├── Stop Packet Sniffer (if running)
        │
        └── Cleanup Firewall Rules
                │
                └── Remove all rules với prefix "FirewallController"
```

---

## 9. Các chế độ hoạt động

### 9.1. DNS Proxy Modes

| Mode | DNS Server | Whitelist Check | Firewall Rules |
|------|------------|-----------------|----------------|
| DISABLED | Tắt | Không | Không |
| MONITOR | Chạy | Log only | Không |
| ACTIVE | Chạy | Enforce (NXDOMAIN) | Có |
| PARALLEL | Chạy | Enforce | Có + PacketSniffer |

### 9.2. Firewall Modes (Legacy)

| Mode | Hành động |
|------|-----------|
| monitor | Chỉ log, không block |
| warn | Log + cảnh báo |
| block | Block IP không whitelist |
| whitelist_only | Chỉ allow whitelist |

**Lưu ý**: Với DNS Proxy Architecture, firewall mode gần như không còn tác dụng vì blocking được thực hiện ở tầng DNS.

---

## 10. Xử lý lỗi và Recovery

### 10.1. Token Expired

```
Token hết hạn
    │
    ├── Auto-refresh thất bại
    │
    └── Trigger re-registration
            │
            ├── POST /api/agents/register
            ├── Nhận token mới
            └── Continue operation
```

### 10.2. Server Unreachable

```
Server không kết nối được
    │
    ├── Thử fallback servers
    ├── Whitelist: dùng cache cũ
    ├── Logs: queue locally
    └── Heartbeat: retry mỗi 5s
```

### 10.3. DNS Server Port Conflict

```
Port 53 đã bị chiếm
    │
    ├── Log error
    ├── Fall back to PacketSniffer
    └── Hoặc: chờ port available
```

### 10.4. Firewall Sync Timeout

```
Add firewall rule timeout (>3s)
    │
    ├── Return SERVFAIL cho client
    ├── Log error
    └── Không trả IP để tránh kết nối không kiểm soát
```

---

## 11. Bảo mật

### 11.1. Authentication Flow

1. **Registration**: Agent gửi device_id + API key → nhận JWT tokens
2. **Access Token**: Dùng cho tất cả API calls, expire sau 1 giờ
3. **Refresh Token**: Dùng để lấy access token mới, expire sau 7 ngày
4. **Re-registration**: Tự động nếu refresh thất bại

### 11.2. Chống Bypass

| Threat | Mitigation |
|--------|------------|
| User đổi DNS | Drift Monitor auto-restore |
| DoH (DNS over HTTPS) | Block known providers |
| DoT (DNS over TLS) | Block port 853 |
| Direct IP access | PacketSniffer detect |
| Hosts file edit | Security monitoring |

---

## 12. Cấu hình quan trọng

### 12.1. agent_config.json

```json
{
  "server": {
    "url": "https://server.example.com",
    "urls": ["https://primary.com", "https://backup.com"]
  },
  "dns_proxy": {
    "enabled": true,
    "mode": "active",
    "port": 53,
    "upstream_resolvers": [
      {"address": "8.8.8.8", "priority": 1}
    ],
    "firewall_sync": {
      "timeout": 3.0,
      "grace_period": 60
    }
  },
  "whitelist": {
    "auto_sync": true,
    "sync_interval": 60,
    "cache_ttl": 300
  },
  "security": {
    "block_doh": true,
    "block_dot": true
  }
}
```

---

## 13. Tóm tắt Flow chính

```
STARTUP:
  Register → Token → Whitelist Sync → Firewall → DNS Proxy → Services

DNS QUERY:
  Receive → Parse → Check Whitelist → [BLOCK: NXDOMAIN] 
                                    → [ALLOW: Upstream → Firewall Sync → Cache → Response]

SYNC:
  Every 60s → Fetch whitelist → Update state → DNS Handler uses new state

SHUTDOWN:
  Stop Network → Stop DNS → Stop Security → Stop Services → Cleanup Rules
```

---

*Tài liệu này mô tả kiến trúc Phase 1 - DNS Proxy/Sinkhole của Agent. Cập nhật lần cuối: 2026-01-01*
