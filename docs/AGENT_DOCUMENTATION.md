# SAINT Agent - Tài Liệu Kỹ Thuật

## 1. Tổng quan

SAINT Agent là phần mềm client chạy trên Windows, thực hiện:
- **Giám sát mạng**: Bắt gói tin (Scapy), trích xuất domain truy cập
- **Quản lý Firewall**: Tự động tạo/xóa rules Windows Firewall theo whitelist
- **Đồng bộ Whitelist**: Pull danh sách domain/IP cho phép từ Server
- **Báo cáo**: Gửi logs hoạt động mạng + heartbeat về Server
- **Giao diện GUI**: Dashboard trực quan với CustomTkinter

### Công nghệ
- **GUI**: CustomTkinter (Tkinter hiện đại)
- **Packet Capture**: Scapy + WinPcap/Npcap
- **DNS**: dnspython + aiodns (async)
- **Firewall**: netsh (Windows Firewall CLI)
- **Build**: PyInstaller → SAINT.exe

---

## 2. Cấu trúc thư mục

```
agent/
├── agent_gui.py              # Entry point - khởi động GUI
├── requirements.txt          # Dependencies
├── miku.ico                  # Icon ứng dụng
│
├── core/                     # Logic lõi Agent
│   ├── agent.py              # Agent singleton - quản lý state
│   ├── lifecycle.py          # Khởi tạo & dọn dẹp components
│   ├── registry.py           # Đăng ký với Server
│   ├── handlers.py           # Xử lý sự kiện (packet, log)
│   └── token_manager.py      # Quản lý JWT token (auto-refresh)
│
├── gui/                      # Giao diện người dùng
│   ├── app.py                # FirewallControllerApp (singleton)
│   ├── views/                # Các màn hình
│   │   ├── main_window.py    # Cửa sổ chính + sidebar navigation
│   │   ├── dashboard_view.py # Dashboard: status cards, activity log
│   │   ├── firewall_view.py  # Quản lý firewall rules
│   │   ├── whitelist_view.py # Hiển thị whitelist đã sync
│   │   ├── logs_view.py      # Log console real-time
│   │   └── settings_view.py  # Cấu hình (server URL, API key)
│   ├── views/components/     # Components tái sử dụng
│   │   ├── status_card.py    # Card hiển thị trạng thái
│   │   ├── data_table.py     # Bảng dữ liệu generic
│   │   └── log_console.py    # Console hiển thị log
│   ├── controllers/          # Controllers
│   │   ├── agent_controller.py    # Điều khiển Agent lifecycle
│   │   └── whitelist_controller.py # Bridge whitelist ↔ GUI
│   ├── styles/               # Theme & colors
│   └── resources/            # Icons, assets
│
├── firewall/                 # Quản lý Windows Firewall
│   ├── manager.py            # FirewallManager (orchestrator)
│   ├── policy.py             # PolicyManager (default deny/allow)
│   ├── rules.py              # RulesManager (tạo/xóa rules)
│   └── utils.py              # Utilities (netsh wrapper)
│
├── whitelist/                # Quản lý Whitelist
│   ├── manager.py            # WhitelistManager (sync + check)
│   ├── state.py              # WhitelistState (thread-safe storage)
│   ├── sync.py               # WhitelistSyncer (HTTP client)
│   └── monitor.py            # WhitelistMonitor (file watcher)
│
├── capture/                  # Bắt gói tin mạng
│   ├── sniffer.py            # PacketSniffer (Scapy-based)
│   ├── extractors.py         # DomainExtractor (DNS, HTTP, SNI)
│   ├── scapy_config.py       # Cấu hình Scapy
│   └── winpcap_installer.py  # Tự động cài WinPcap/Npcap
│
├── network/                  # DNS Resolution
│   └── dns_resolver.py       # OptimizedDNSResolver (parallel)
│
├── config/                   # Cấu hình
│   ├── loader.py             # ConfigLoader (multi-source)
│   ├── defaults.py           # Giá trị mặc định
│   ├── validator.py          # Validation schema
│   └── crypto.py             # Mã hóa config nhạy cảm
│
├── services/                 # Dịch vụ nền
│   ├── heartbeat.py          # HeartbeatSender (20s interval)
│   └── windows_service.py    # Chạy như Windows Service
│
├── logging_module/           # Gửi log về Server
│   └── sender.py             # LogSender (batch 100, 2s interval)
│
├── cache/                    # Cache
│   └── lru_cache.py          # LRU Cache (DNS, 2000 entries)
│
├── shared/                   # Tiện ích dùng chung
│   ├── time_utils.py         # Timezone Việt Nam
│   └── os_info.py            # Thông tin hệ điều hành
│
└── utils/                    # Helpers
    ├── ip_utils.py           # IP detection, validation
    ├── admin_check.py        # Kiểm tra quyền Administrator
    └── validators.py         # Input validation
```

---

## 3. Kiến trúc MVP + Signals

Agent sử dụng pattern **MVP (Model-View-Presenter)** với hệ thống **Signals** cho giao tiếp thread-safe:

```
┌─────────────────────────────────────────────────────────┐
│                     GUI Thread                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │Dashboard │  │Firewall  │  │Whitelist │  │Settings │ │
│  │View      │  │View      │  │View      │  │View     │ │
│  └────▲─────┘  └────▲─────┘  └────▲─────┘  └─────────┘ │
│       │              │              │                    │
│       └──────────────┼──────────────┘                    │
│                      │                                   │
│              ┌───────┴────────┐                          │
│              │ AgentSignals   │  ← Event Queue (500ms)   │
│              │ (callbacks)    │                           │
│              └───────┬────────┘                          │
└──────────────────────┼───────────────────────────────────┘
                       │
              ┌────────┴─────────┐
              │ AgentController  │  ← Singleton / Presenter
              │ (background      │
              │  thread)         │
              └────────┬─────────┘
                       │
┌──────────────────────┼───────────────────────────────────┐
│              Worker Thread(s)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │Firewall  │  │Whitelist │  │Packet    │  │Heartbeat│ │
│  │Manager   │  │Manager   │  │Sniffer   │  │Sender   │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                              ┌─────────┐ │
│                                              │LogSender│ │
│                                              └─────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Signals (Tín hiệu)

| Signal | Khi phát | Dữ liệu |
|--------|----------|----------|
| `status_changed` | Agent thay đổi trạng thái | status string |
| `packet_captured` | Bắt được gói tin | packet info |
| `log_received` | Nhận log mới | log entry |
| `error_occurred` | Có lỗi xảy ra | error message |
| `stats_updated` | Cập nhật thống kê | stats dict |
| `whitelist_synced` | Whitelist đồng bộ xong | whitelist info |

### Luồng tín hiệu:
1. Component (vd: PacketSniffer) phát signal trong worker thread
2. Signal được đẩy vào event queue
3. GUI thread xử lý queue mỗi 500ms
4. Callback được gọi → cập nhật UI an toàn

---

## 4. Core Agent Lifecycle

### 4.1 Khởi động (`core/lifecycle.py`)

```
1. register_agent(config)        → Đăng ký với Server, nhận credentials
2. init TokenManager             → Auto-refresh JWT tokens
3. init WhitelistManager         → Khởi tạo whitelist manager
4. sync_whitelist()              → Đồng bộ whitelist TỪ SERVER TRƯỚC
5. install_winpcap() (nếu cần)  → Cài WinPcap cho packet capture
6. init FirewallManager          → Khởi tạo firewall
7. setup_firewall_rules()       → Tạo rules cho whitelisted IPs
8. start PacketSniffer           → Bắt đầu bắt gói tin
9. start LogSender               → Bắt đầu gửi logs
10. start HeartbeatSender        → Bắt đầu gửi heartbeat
11. main_loop()                  → Vòng lặp chính (update stats mỗi 5s)
```

### 4.2 Dọn dẹp (Shutdown)

```
1. stop HeartbeatSender          → Dừng heartbeat
2. stop LogSender                → Gửi nốt logs còn lại, dừng
3. stop PacketSniffer            → Dừng capture
4. cleanup FirewallManager       → Khôi phục policy gốc, xóa rules
5. save state                    → Lưu trạng thái cuối
```

### 4.3 Agent Singleton (`core/agent.py`)

```python
class Agent:
    # Properties
    hostname: str           # Tên máy tính
    device_id: str          # ID phần cứng (BIOS SN + Motherboard SN + Disk SN)
    agent_id: str           # ID từ Server
    state: str              # STOPPED → STARTING → RUNNING → STOPPING

    # Component references
    firewall: FirewallManager
    whitelist: WhitelistManager
    sniffer: PacketSniffer
    log_sender: LogSender
    heartbeat: HeartbeatSender
    token_manager: TokenManager
```

**Device ID Generation:**
- Windows: hash(BIOS Serial + Motherboard Serial + Disk Serial) via WMI
- Fallback: MAC address hash

---

## 5. GUI Views chi tiết

### 5.1 Dashboard View (`gui/views/dashboard_view.py`)

Màn hình chính hiển thị trạng thái agent real-time.

**Components:**
- **8 Status Cards** (animated):
  - Agent Status (Running/Stopped)
  - Mode (Monitor/Whitelist Only)
  - Whitelist (số domains)
  - Uptime (thời gian chạy)
  - IPs (số IP đã resolve)
  - Packets (số gói tin bắt được)
  - Server (kết nối status)
  - Last Sync (lần sync cuối)
- **Activity Log**: Scrollable log với timestamp
- **Start/Stop Button**: Khởi động/dừng agent

**Cập nhật real-time:** Mỗi 1 giây thông qua signal `stats_updated`.

### 5.2 Firewall View (`gui/views/firewall_view.py`)

Hiển thị trạng thái firewall và danh sách rules.

**Components:**
- Policy status (Default Deny/Allow)
- Mode indicator
- Rule count
- DataTable hiển thị rules hiện tại
- Refresh button

### 5.3 Whitelist View (`gui/views/whitelist_view.py`)

Hiển thị danh sách domain/IP trong whitelist.

**Components:**
- Domain/IP listing với resolved IP addresses
- Auto-sync indicator (interval 30s)
- DNS resolution status cho mỗi domain
- Sử dụng OptimizedDNSResolver chung

### 5.4 Logs View (`gui/views/logs_view.py`)

Real-time log streaming với filtering.

**Components:**
- Log console (LogConsole component)
- Filter by level: ALL, DEBUG, INFO, WARNING, ERROR
- Export to CSV
- GUILogHandler bắt Python logging → hiển thị

### 5.5 Settings View (`gui/views/settings_view.py`)

Cấu hình agent.

**Components:**
- Server URL (primary + fallback)
- API Key input
- Heartbeat interval
- Sync interval
- Config encryption toggle

### 5.6 Main Window (`gui/views/main_window.py`)

Cửa sổ chính với sidebar navigation.

**Features:**
- Sidebar với icons cho mỗi view
- Lazy loading: views chỉ tạo khi truy cập lần đầu
- View switching (chỉ 1 view hiển thị)

---

## 6. Firewall Management

### 6.1 FirewallManager (`firewall/manager.py`)

Orchestrator chính, phối hợp 3 sub-managers:

```
FirewallManager
├── PolicyManager    → Quản lý policy tổng (Default Deny/Allow)
├── RulesManager     → Tạo/xóa individual rules
└── FirewallUtils    → Helper functions
```

### 6.2 PolicyManager (`firewall/policy.py`)

Quản lý Windows Firewall policy qua `netsh`:

| Method | Mô tả |
|--------|--------|
| `enable_default_deny()` | Chặn mặc định tất cả outbound traffic |
| `get_current_policy()` | Đọc policy hiện tại |
| `backup_current_policy()` | Backup policy gốc để restore |
| `restore_policy()` | Khôi phục policy gốc |

**Lệnh netsh sử dụng:**
```bash
# Đặt Default Deny (chặn tất cả outbound)
netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound

# Khôi phục mặc định
netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound
```

### 6.3 RulesManager (`firewall/rules.py`)

Tạo/xóa firewall rules cho từng IP:

| Method | Mô tả |
|--------|--------|
| `create_allow_rule(ip)` | Tạo rule cho phép outbound đến IP |
| `remove_allow_rule(ip)` | Xóa rule |
| `create_allow_rules_batch(ips)` | Tạo hàng loạt rules |
| `cleanup_all_rules()` | Xóa tất cả SAINT rules |

**Lệnh netsh sử dụng:**
```bash
# Tạo rule cho phép
netsh advfirewall firewall add rule name="SAINT_ALLOW_8.8.8.8" ^
  dir=out action=allow remoteip=8.8.8.8 enable=yes

# Xóa rule
netsh advfirewall firewall delete rule name="SAINT_ALLOW_8.8.8.8"
```

### 6.4 Chế độ hoạt động

| Mode | Mô tả | Yêu cầu Admin |
|------|--------|----------------|
| `monitor` | Chỉ giám sát, không chặn | Không |
| `whitelist_only` | Chặn tất cả trừ whitelist | Có |

- Auto-detect: Nếu không có quyền Admin → tự động chuyển về `monitor`
- Khi `whitelist_only`: Default Deny + rules ALLOW cho mỗi IP trong whitelist

---

## 7. Network Monitoring

### 7.1 PacketSniffer (`capture/sniffer.py`)

Bắt gói tin mạng sử dụng Scapy:

- **Filter**: TCP port 80 (HTTP), 443 (HTTPS), 53 (DNS)
- **Threading**: Chạy trong thread riêng, graceful shutdown
- **Callback**: Gọi handler cho mỗi packet bắt được
- **Statistics**: Đếm packets, domains detected

### 7.2 DomainExtractor (`capture/extractors.py`)

Trích xuất domain từ packets:

| Phương pháp | Áp dụng cho | Cách trích xuất |
|------------|-------------|-----------------|
| DNS Query | Port 53 | Đọc domain từ DNS question section |
| HTTP Host | Port 80 | Đọc Host header từ HTTP request |
| TLS SNI | Port 443 | Đọc Server Name Indication từ TLS ClientHello |

### 7.3 OptimizedDNSResolver (`network/dns_resolver.py`)

Phân giải domain → IP hiệu suất cao:

| Method | Mô tả |
|--------|--------|
| `resolve_domain_sync(domain)` | Phân giải 1 domain (đồng bộ) |
| `resolve_domain_async(domain)` | Phân giải 1 domain (async) |
| `resolve_multiple_parallel(domains)` | Nhiều domain song song (ThreadPool) |
| `resolve_multiple_async(domains)` | Nhiều domain async (aiodns) |

**Tối ưu hóa:**
- ThreadPoolExecutor: 5-10 workers
- Chunking: 20 domains/chunk
- Dual-stack: dnspython (sync) + aiodns (async)
- Fallback: socket.getaddrinfo()
- Trả về `DNSRecord(ipv4_tuple, cname, ttl, timestamp)`

---

## 8. Whitelist Management

### 8.1 WhitelistManager (`whitelist/manager.py`)

Quản lý whitelist trung tâm:

| Method | Mô tả |
|--------|--------|
| `sync_now()` | Đồng bộ whitelist từ Server ngay |
| `is_allowed(domain)` | Kiểm tra domain có trong whitelist |
| `is_ip_allowed(ip)` | Kiểm tra IP có trong whitelist |
| `add_domain(domain)` | Thêm domain vào whitelist local |
| `remove_domain(domain)` | Xóa domain khỏi whitelist local |
| `get_stats()` | Thống kê (domains, IPs, sync count) |

**Thread Safety:** Sử dụng RLock cho mọi thao tác read/write.

### 8.2 WhitelistState (`whitelist/state.py`)

Lưu trữ trạng thái whitelist thread-safe:

```python
class WhitelistState:
    domains: set          # Tập domain cho phép
    patterns: set         # Tập pattern (*.google.com)
    ips: set              # Tập IP đã resolve
    version: int          # Version từ Server
```

### 8.3 WhitelistSyncer (`whitelist/sync.py`)

Client HTTP gọi Server API:

```
GET /api/whitelist/agent-sync
Authorization: Bearer <jwt-token>

→ Response: {whitelist, whitelist_version, active_profile, policy}
```

- Retry logic với exponential backoff
- Fallback server support
- JWT authentication

### 8.4 Luồng đồng bộ

```
1. WhitelistSyncer.sync() → GET /api/whitelist/agent-sync
2. Server trả về domains + patterns + policy
3. WhitelistState cập nhật domains/patterns
4. OptimizedDNSResolver resolve domains → IPs (parallel)
5. WhitelistState cập nhật IPs
6. FirewallManager cập nhật rules (nếu whitelist_only mode)
7. Callbacks thông báo GUI
```

---

## 9. Communication Protocol

### 9.1 Đăng ký Agent (`core/registry.py`)

```
Agent → POST /api/agents/register
Headers: { X-API-Key: "api-key-here" }
Body: {
  hostname: "PC-LAB01",
  device_id: "hw-hash-123",
  ip_address: "192.168.1.100",
  platform: "Windows 10",
  os_info: { version: "10.0.19045", arch: "AMD64" },
  is_admin: true,
  capabilities: ["firewall", "capture", "dns"]
}

Server → 200 OK
{
  agent_id: "agent_abc123",
  agent_token: "jwt-token-for-agent"
}
```

### 9.2 Heartbeat (`services/heartbeat.py`)

Gửi mỗi **20 giây** (configurable):

```
Agent → POST /api/agents/heartbeat
Headers: { Authorization: "Bearer <jwt>" }
Body: {
  agent_id: "agent_abc123",
  hostname: "PC-LAB01",
  ip_address: "192.168.1.100",
  status: "online",
  metrics: { cpu: 45.2, memory: 62.1, uptime: 7200 },
  logs: [ ... batch logs ... ]
}

Server → 200 OK
{
  whitelist_version: 5,
  whitelist_version_changed: true,   ← Cần sync lại whitelist
  force_sync: false,                 ← Server yêu cầu sync ngay
  policy_version: 2,
  policy_changed: false
}
```

### 9.3 Log Sending (`logging_module/sender.py`)

- **Queue-based**: Logs được đẩy vào queue, gửi batch
- **Batch size**: 100 logs/request
- **Interval**: 2 giây
- **Endpoint**: `POST /api/logs`

### 9.4 Token Management (`core/token_manager.py`)

- Auto-refresh JWT trước khi hết hạn
- Callback khi token refresh/expire
- Trigger re-registration nếu token không thể refresh

### 9.5 Authentication Headers

```python
def get_auth_headers(config):
    # Ưu tiên JWT
    if config.jwt_token:
        return {"Authorization": f"Bearer {config.jwt_token}"}
    # Fallback legacy token
    elif config.agent_token:
        return {"X-Agent-Token": config.agent_token}
```

---

## 10. Configuration

### 10.1 File cấu hình (`config/loader.py`)

Ưu tiên tìm kiếm (từ cao → thấp):
1. Environment variables
2. `agent_config.json` (cùng thư mục agent)
3. `agent_config.json` (thư mục hiện tại)
4. `~/.firewall-controller/agent_config.json`
5. `C:\ProgramData\FirewallController\agent_config.json`
6. Giá trị mặc định (`config/defaults.py`)

### 10.2 Giá trị mặc định (`config/defaults.py`)

```python
DEFAULT_CONFIG = {
    "server": {
        "url": "http://localhost:5000",
        "fallback_urls": [],
        "timeout_connect": 15,    # giây
        "timeout_read": 45        # giây
    },
    "whitelist": {
        "auto_sync": True,
        "sync_interval": 30,      # giây
        "max_retries": 3
    },
    "firewall": {
        "enabled": False,
        "mode": "monitor"         # monitor | whitelist_only
    },
    "logging": {
        "batch_size": 100,
        "queue_size": 1000,
        "send_interval": 2        # giây
    },
    "heartbeat": {
        "enabled": True,
        "interval": 20            # giây
    }
}
```

### 10.3 Mã hóa cấu hình (`config/crypto.py`)

- Mã hóa file config chứa API key, token
- Sử dụng thư viện `cryptography`
- File mã hóa có đuôi `.enc`

---

## 11. Build & Packaging

### 11.1 PyInstaller Spec (`FirewallAgent.spec`)

```python
# Cấu hình chính
a = Analysis(
    ['agent/agent_gui.py'],          # Entry point
    hiddenimports=[                   # Tất cả modules cần thiết
        'customtkinter', 'scapy', 'dns', 'requests',
        'psutil', 'cryptography', ...
    ],
    datas=[
        ('agent/', 'agent/'),         # Agent source files
        ('customtkinter/', ...),      # CTk assets
    ]
)

exe = EXE(
    name='SAINT',                     # Tên file exe
    icon='agent/miku.ico',           # Icon
    console=False,                    # Không hiện console
    uac_admin=False,                  # Không yêu cầu Admin (monitor mode)
)
```

### 11.2 Build command

```bash
# Build SAINT.exe
pyinstaller FirewallAgent.spec

# Output: dist/SAINT.exe
```

### 11.3 Dependencies (`agent/requirements.txt`)

| Package | Mục đích |
|---------|----------|
| scapy >= 2.4.5 | Packet capture |
| pydivert >= 2.1.0 | Network interception |
| dnspython | DNS resolution |
| aiodns | Async DNS |
| requests >= 2.28.0 | HTTP client |
| psutil >= 5.9.0 | System monitoring |
| pywin32 | Windows API |
| netifaces >= 0.11.0 | Network interfaces |
| customtkinter >= 5.0.0 | GUI framework |
| cryptography | Config encryption |
| distro >= 1.6.0 | OS detection |
| python-dateutil >= 2.8.0 | Date utilities |

---

## 12. Các Pattern thiết kế sử dụng

| Pattern | Áp dụng | Mô tả |
|---------|---------|--------|
| **Singleton** | Agent, AgentController, App | Chỉ 1 instance trong toàn app |
| **Observer** | AgentSignals | Callback registration/dispatch |
| **MVP** | GUI architecture | Model-View-Presenter |
| **Thread Pool** | DNS Resolver | ThreadPoolExecutor (5-10 workers) |
| **Queue** | LogSender, Events | Queue-based async communication |
| **Lazy Loading** | MainWindow views | Views tạo khi truy cập lần đầu |
| **State Machine** | Agent state | STOPPED→STARTING→RUNNING→STOPPING |
| **Strategy** | Firewall mode | monitor vs whitelist_only |

---

## 13. Yêu cầu hệ thống

| Yêu cầu | Chi tiết |
|----------|----------|
| **OS** | Windows 10/11 |
| **Python** | 3.8+ (nếu chạy source) |
| **WinPcap/Npcap** | Cần cho packet capture |
| **Quyền Admin** | Tùy chọn (cần cho whitelist_only mode) |
| **Mạng** | Kết nối được đến Server |
| **RAM** | ~100-200 MB |
| **Disk** | ~50 MB (SAINT.exe) |
