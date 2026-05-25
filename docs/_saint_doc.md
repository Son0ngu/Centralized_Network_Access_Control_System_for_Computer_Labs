

SAINT
Security Agent Integrated Network Tool


Tài liệu kỹ thuật tổng hợp — Hệ thống quản lý truy cập mạng tập trung cho phòng máy tính (Centralized Network Access Control System for Computer Labs)








Phiên bản 1.0 · 2025

# Mục lục
(Mở file bằng Microsoft Word và nhấn F9 để cập nhật mục lục.)

# Chương 1 — Tổng quan hệ thống
## 1.1 Giới thiệu
SAINT (Security Agent Integrated Network Tool) là hệ thống quản lý bảo mật mạng phân tán, được thiết kế cho môi trường giáo dục. Hệ thống cho phép quản trị viên và giáo viên giám sát, kiểm soát truy cập mạng của các máy tính trong phòng lab/lớp học thông qua cơ chế whitelist và Windows Firewall tự động.
## 1.2 Vấn đề & giải pháp
Vấn đề cần giải quyết:
Học sinh/sinh viên truy cập các trang web không phù hợp trong giờ học.
Thiếu công cụ quản lý mạng tập trung cho môi trường giáo dục.
Giáo viên không có khả năng kiểm soát truy cập mạng theo lớp/nhóm.
Không có hệ thống giám sát real-time hoạt động mạng.
Giải pháp SAINT:
Agent cài trên máy học sinh: tự động đồng bộ whitelist và áp Windows Firewall.
Server quản lý tập trung: REST API + Dashboard web + WebSocket realtime.
RBAC Admin/Teacher: giáo viên tự quản lớp mình, admin quản toàn hệ thống.
Audit trail đầy đủ: mọi hành động Admin/Teacher đều được ghi lại.
## 1.3 Kiến trúc tổng thể
Hệ thống gồm 3 thành phần chính giao tiếp với nhau qua REST API (JWT/API Key) và WebSocket:

## 1.4 Technology Stack
Server:

Agent:

## 1.5 Số liệu dự án
Khoảng 50 API endpoints phục vụ Agent và Web Dashboard.
12 MongoDB collections lưu trữ toàn bộ dữ liệu hệ thống.
2 roles RBAC (Admin, Teacher) với hệ thống permission chi tiết theo resource:action.
5 GUI views trên Agent: Dashboard, Firewall, Whitelist, Logs, Settings.
7 test files kiểm thử Server (pytest).

# Chương 2 — Server
## 2.1 Vai trò
SAINT Server là thành phần quản lý tập trung, đóng vai trò control plane cho toàn bộ hệ thống. Server expose REST API cho Agent giao tiếp (đăng ký, heartbeat, sync whitelist, gửi logs), Web Dashboard cho Admin/Teacher quản lý, và WebSocket để push notifications realtime đến browser.
## 2.2 Cấu trúc thư mục
server/
├── app.py                          # Khởi tạo Flask app, đăng ký routes
├── time_utils.py                   # Timezone Việt Nam
├── config/rbac_config.py           # Cấu hình roles & permissions
├── database/config.py              # Kết nối MongoDB, indexes
├── models/                         # MongoDB CRUD (12 collection)
├── services/                       # Business logic
├── controllers/                    # API endpoints
├── middleware/auth.py + rbac.py    # Authentication & authorization
├── views/templates + static        # HTML, CSS, JS
└── tests/                          # pytest test suite
## 2.3 Kiến trúc MVC
Request → Middleware (Auth/RBAC) → Controller → Service → Model → MongoDB
                                                  ↓
                                              Response (JSON)
Middleware: xác thực JWT/API key và phân quyền trước khi request vào controller.
Controller: nhận request, validate input, gọi service, trả response.
Service: business logic, gọi model.
Model: CRUD trực tiếp với MongoDB.
Tất cả timestamps dùng timezone Asia/Ho_Chi_Minh qua time_utils.py.
## 2.4 Database schema (MongoDB)
Hệ thống dùng 12 collection chính:

## 2.5 Trạng thái Agent

## 2.6 API endpoints
Nhóm endpoints theo chức năng:
Agent registration & heartbeat

Agent management (web)

Agent policy

Whitelist management

Group management

Whitelist profiles (teacher)

Logs

Admin & user management

API keys & audit

## 2.7 Hệ thống xác thực
Xác thực Agent: hai bước API Key → JWT.
Bước 1: Agent POST /api/agents/register với header X-API-Key, server verify HMAC hash trong DB và phát hành agent_token (JWT). Bước 2: mọi request sau (heartbeat, sync, logs) dùng header Authorization: Bearer <token>.
Xác thực Admin/Teacher: cookie JWT (httpOnly + secure).
Browser POST /api/admin/auth/login với username/password, server verify bcrypt rồi set cookie access_token (24h) và refresh_token (7 ngày). Mọi API call tiếp theo dùng cookie tự động.
## 2.8 RBAC — phân quyền chi tiết
Hai role được hỗ trợ:

Permissions teacher (format resource:action):
profile:read, profile:change_password
groups:read, groups:update, groups:manage_agents (chỉ nhóm mình)
agents:read, agents:detail (chỉ trong nhóm mình)
whitelist:read/create/update/delete/sync
logs:read (chỉ logs từ nhóm mình)
profiles:create/update/delete/activate (whitelist profile)
Admin có thêm:
users:create/read/update/delete/reset_password
agents:delete/command
api_keys:read/create/revoke
logs:export/delete
system:config
audit:read
Data filtering cho Teacher:
Middleware rbac.py inject current_user vào request.g; service layer filter dữ liệu theo logic created_by == user_id HOẶC user_id thuộc teacher_ids của group. Áp dụng cho groups, agents, whitelist, logs.
## 2.9 WebSocket events realtime

## 2.10 Triển khai
Biến môi trường .env:

Chạy server:
cd server
pip install -r requirements.txt
cp .env.example .env  # rồi điền MONGO_URI, JWT_SECRET_KEY, ...
python app.py         # Server lắng nghe http://0.0.0.0:5000

# Chương 3 — Agent (SAINT.exe)
## 3.1 Tổng quan
Agent là phần mềm chạy trên máy Windows của học sinh. Mỗi máy chạy 1 instance Agent kết nối tới Server. Agent có 5 chức năng chính: giám sát mạng, áp dụng Windows Firewall, đồng bộ whitelist, gửi logs + heartbeat, và GUI trực quan.
## 3.2 Cấu trúc thư mục
agent/
├── agent_gui.py              # Entry point — khởi động GUI
├── requirements.txt
├── miku.ico
│
├── core/                     # Logic lõi
│   ├── agent.py              # Agent singleton
│   ├── lifecycle.py          # Khởi tạo & cleanup
│   ├── registry.py           # Đăng ký với Server
│   ├── handlers.py           # Packet/log handlers
│   └── token_manager.py      # JWT auto-refresh
│
├── gui/                      # CustomTkinter UI
│   ├── app.py                # FirewallControllerApp
│   ├── views/                # Dashboard, Firewall, Whitelist, Logs, Settings
│   └── controllers/          # AgentController, WhitelistController
│
├── firewall/                 # Windows Firewall qua netsh
│   ├── manager.py            # FirewallManager (orchestrator)
│   ├── policy.py             # Default Allow/Deny
│   └── rules.py              # Tạo/xóa rules theo IP
│
├── whitelist/                # Sync + state thread-safe
│   ├── manager.py            # WhitelistManager
│   ├── state.py              # WhitelistState
│   ├── sync.py               # HTTP client sync
│   └── monitor.py            # WhitelistMonitor (periodic)
│
├── capture/                  # Scapy packet capture
│   ├── sniffer.py            # PacketSniffer
│   ├── extractors.py         # DomainExtractor (DNS/HTTP/SNI)
│   └── winpcap_installer.py  # Auto-install WinPcap/Npcap
│
├── network/dns_resolver.py   # OptimizedDNSResolver (parallel)
├── config/ (loader, defaults, validator, crypto)
├── services/ (heartbeat, windows_service)
├── logging_module/sender.py  # LogSender (batch 100, 2s interval)
└── utils/, cache/, shared/
## 3.3 Kiến trúc MVP + Signals
Agent dùng pattern MVP với hệ thống Signals để giao tiếp thread-safe giữa worker threads và GUI thread.

Worker thread (PacketSniffer, WhitelistManager, …) phát signal → event queue → GUI thread xử lý queue mỗi 500ms → callback cập nhật UI an toàn (không gọi widget từ worker thread).
## 3.4 Agent lifecycle
Khởi động (lifecycle.py):
register_agent(config) — đăng ký với Server, lấy agent_id + JWT.
init TokenManager — auto-refresh JWT.
init WhitelistManager + sync ngay (trước khi bật Firewall).
Auto-install WinPcap/Npcap nếu cần.
init FirewallManager — chụp snapshot pre-SAINT (skip-if-exists).
enable_whitelist_mode — Default Deny + allow rules cho IP whitelist.
start PacketSniffer (port 53/80/443).
start LogSender (batch 100, 2s).
start HeartbeatSender (20s).
main_loop — update stats mỗi 5s.
Shutdown:
stop HeartbeatSender.
stop LogSender (flush logs còn trong queue).
stop PacketSniffer.
cleanup FirewallManager — restore policy gốc, xóa SAINT rules.
save state.
## 3.5 5 GUI views

## 3.6 Firewall management
FirewallManager phối hợp 3 sub-managers:

Chế độ hoạt động:
Agent chỉ hỗ trợ một firewall mode duy nhất: whitelist_only (Default Deny + allow danh sách whitelist). Các mode monitor/blacklist trong các phiên bản trước đã được loại bỏ vì không hữu ích thực tế. Khi user không có quyền Administrator, firewall component sẽ bị disable (rule không apply được), nhưng packet capture và log vẫn chạy.
Lệnh netsh tiêu biểu:
# Bật Default Deny (block outbound mặc định)
netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound

# Tạo rule cho phép 1 IP
netsh advfirewall firewall add rule name="FirewallController_Allow_8.8.8.8" \
  dir=out action=allow remoteip=8.8.8.8 enable=yes

# Khôi phục policy gốc
netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound
## 3.7 Firewall Backup & Restore
Tính năng cho phép khôi phục Windows Firewall về trạng thái trước khi cài SAINT. Snapshot được capture LÚC AGENT START LẦN ĐẦU và chứa JSON gồm policy hiện tại (Default Allow/Deny), trạng thái whitelist_mode, danh sách essential_ips, allowed_ips. File mặc định: profiles/backup.saint-snapshot.json (resolve tuyệt đối từ agent install dir, KHÔNG phụ thuộc cwd).
Đặc tính an toàn:
Skip-if-exists: nếu file đã tồn tại, KHÔNG ghi đè — giữ baseline pre-SAINT thật.
Atomic write: ghi temp file + os.replace() — crash giữa lúc ghi không corrupt file.
Admin guard: Restore yêu cầu Administrator privileges, sẽ báo lỗi rõ ràng nếu thiếu.
Safety net: nếu snapshot ghi nhận mọi profile là block → force Default Allow để tránh lockout.
Restore không re-enable Default Deny dù snapshot ghi whitelist_mode=True (đúng intent revert).
## 3.8 Network monitoring
PacketSniffer (Scapy):
Filter TCP port 80 (HTTP), 443 (HTTPS), 53 (DNS).
Thread riêng, graceful shutdown.
Callback cho mỗi packet bắt được.
Đếm packets + domains detected.
DomainExtractor (capture/extractors.py):

OptimizedDNSResolver:
ThreadPoolExecutor 5–10 workers.
Chunking 20 domains/chunk để cân bằng load.
Dual stack: dnspython (sync) + aiodns (async).
Fallback socket.getaddrinfo().
Trả về DNSRecord(ipv4_tuple, cname, ttl, timestamp).
LRU cache 2000 entries.
## 3.9 Communication protocol
Registration:
POST /api/agents/register
Headers: { X-API-Key: "fwc_..." }
Body: {
  hostname, device_id, ip_address, platform, os_info,
  is_admin, capabilities: [firewall, capture, dns]
}
→ 200 { agent_id, agent_token }
Heartbeat (20s):
POST /api/agents/heartbeat
Headers: { Authorization: "Bearer <jwt>" }
Body: { agent_id, hostname, ip_address, status, metrics, logs[] }
→ 200 { whitelist_version, whitelist_version_changed,
        force_sync, policy_version, policy_changed }
Whitelist sync:
GET /api/whitelist/agent-sync
Headers: { Authorization: "Bearer <jwt>" }
→ 200 {
  whitelist: [{value, type}, ...],
  whitelist_version: 5,
  active_profile: { name, domains: [...] } | null,
  policy: { override_mode, custom_whitelist, override_version }
}
## 3.10 Configuration
Config được load theo thứ tự ưu tiên: env vars → agent_config.json cùng dir agent → cwd → ~/.firewall-controller/ → C:\ProgramData\FirewallController\ → defaults.py.
Default ban đầu (PHÒNG NGỪA leak data):
Server URL mặc định để TRỐNG. Agent sẽ chạy ở chế độ offline cho đến khi user mở Settings và nhập URL. Validator check URL bắt đầu bằng http:// hoặc https:// trước khi save.
Mã hóa config (config/crypto.py):
Mã hóa file config chứa API key, JWT token, agent_token.
Dùng thư viện cryptography (Fernet).
File mã hóa có đuôi .enc — agent_config.json.enc.
## 3.11 Build & packaging
# Build SAINT.exe single-file
pyinstaller FirewallAgent.spec
# Output: dist/SAINT.exe
Spec config chính:
Entry point: agent/agent_gui.py
Hidden imports: customtkinter, scapy, dns, requests, psutil, cryptography, …
Datas: agent/, customtkinter/ assets.
Console=False (không hiện console window).
Icon: agent/miku.ico.
uac_admin=False (không bắt buộc admin để chạy GUI, chỉ cần admin để apply firewall).
## 3.12 Yêu cầu hệ thống


# Chương 4 — Luồng hoạt động chính
## 4.1 Khởi động Agent end-to-end
Khởi động GUI → Register với Server → Sync Whitelist → Apply Firewall
                                                                ↓
                      Gửi Heartbeat ←── Bắt gói tin (Scapy) ←────┘
User mở SAINT.exe → GUI hiển thị.
Nhấn Start Agent → đăng ký với Server qua API Key.
Server trả về agent_id + JWT token.
Agent gọi /api/whitelist/agent-sync để lấy whitelist.
DNS Resolver phân giải toàn bộ domain → IP (parallel).
FirewallManager tạo allow rules cho từng IP.
PacketSniffer bắt đầu capture (port 80/443/53).
HeartbeatSender gửi heartbeat mỗi 20s.
LogSender gửi batch logs mỗi 2s.
## 4.2 Kiểm tra truy cập mạng
Máy truy cập website
      ↓
PacketSniffer bắt packet
      ↓
DomainExtractor lấy domain (DNS / HTTP Host / TLS SNI)
      ↓
Whitelist check: domain hoặc IP có trong whitelist?
      ↓                                  ↓
  ALLOWED                            BLOCKED
  (log INFO)                         (log BLOCKED)
      └──────────────┬─────────────────┘
                     ↓
         LogSender → POST /api/logs → Server lưu DB
## 4.3 Đồng bộ Whitelist (incremental)
Admin/Teacher sửa whitelist qua Web Dashboard → Server cập nhật DB.
Server tăng whitelist_version (collection whitelist_meta).
Heartbeat tiếp theo của Agent: Server response kèm whitelist_version mới + cờ whitelist_version_changed=true.
Agent phát hiện version mới → gọi /api/whitelist/agent-sync.
Server trả full whitelist + active_profile + policy.
Agent: DNS resolve domains → IPs; FirewallManager cập nhật allow rules; cập nhật version local.
Lần heartbeat tiếp theo gửi whitelist_version mới — Server trả up_to_date=true (short-circuit, không gửi lại data).
## 4.4 Xác thực & phân quyền RBAC
Admin/Teacher đăng nhập → POST /api/admin/auth/login
          ↓
Server verify bcrypt password
          ↓
Phát hành JWT (access 24h + refresh 7d) → set httpOnly cookie
          ↓
Mọi API call kế tiếp tự động gửi cookie
          ↓
Middleware rbac.py decode JWT → inject g.current_user
          ↓
Service filter data theo role (teacher chỉ thấy group mình)
          ↓
Controller trả về JSON đã filter
## 4.5 Profile whitelist của Teacher
Teacher có thể tạo nhiều profile whitelist riêng cho từng buổi học. Profile gồm tên + danh sách domain. Khi teacher activate 1 profile, danh sách domain của profile sẽ OVERRIDE group whitelist gốc cho đến khi deactivate.
Teacher tạo profile 'Bài thực hành Web' với 5 domain w3schools.com, developer.mozilla.org, …
Click Activate trên profile → Server set is_active=true + bump group.whitelist_version.
Agent heartbeat phát hiện version đổi → sync.
Server response chứa active_profile.domains thay vì base whitelist.
Agent áp profile vào firewall — học sinh chỉ truy cập được 5 domain trên.
Hết tiết, teacher click Deactivate → Server set is_active=false + bump version → Agent revert về base whitelist.

# Chương 5 — Bảo mật & độ tin cậy
## 5.1 Các tính năng bảo mật

## 5.2 Reliability & resilience
Token auto-refresh: TokenManager tự động refresh JWT trước khi hết hạn; nếu refresh fail → trigger re-registration.
Whitelist incremental sync: chỉ tải lại khi version thay đổi (giảm bandwidth + load server).
DNS resolver fallback: dnspython → aiodns → socket.getaddrinfo.
LogSender queue-based: nếu server down, log nằm trong queue đến khi gửi được; có batch + retry với exponential backoff.
Firewall snapshot skip-if-exists: tránh ghi đè baseline pre-SAINT khi agent restart sau crash.
Atomic JSON write cho snapshot: temp file + os.replace().
Safety net: snapshot all-block → restore Default Allow để tránh network lockout.
Heartbeat 20s + status auto-degrade: active → inactive (5–30 phút) → offline (>30 phút).
## 5.3 Pattern thiết kế sử dụng


# Chương 6 — Triển khai & vận hành
## 6.1 Mô hình triển khai
INTERNET / LAN
│
├── Server (Flask)
│     - Ubuntu/Windows Server
│     - Python 3.8+, Port 5000
│     - MongoDB Atlas (cloud)
│
├── Web Browser (Admin/Teacher) → Dashboard quản lý
│
└── Computer Lab
     ├── PC #1 (SAINT.exe + Windows Firewall)
     ├── PC #2 (SAINT.exe + Windows Firewall)
     └── PC #N (SAINT.exe + Windows Firewall)
## 6.2 Triển khai Server
# 1. Clone repo
git clone <repo-url> firewall-controller
cd firewall-controller/server

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cấu hình .env
cp .env.example .env
# Sửa MONGO_URI, JWT_SECRET_KEY, JWT_REFRESH_SECRET_KEY,
# API_KEY_HMAC_SECRET, ...

# 4. (Tùy chọn) Seed admin user lần đầu
python create_admin.py

# 5. Khởi động
python app.py
# Server lắng nghe http://0.0.0.0:5000
Khuyến nghị production:
Đặt sau reverse proxy (Nginx/Caddy) terminate TLS.
Service-ize bằng systemd hoặc Windows Service.
MongoDB Atlas / replica set với daily backup.
Rotate JWT secrets định kỳ.
Monitor /api/health endpoint.
## 6.3 Triển khai Agent
Build SAINT.exe trên máy dev: pyinstaller FirewallAgent.spec.
Copy dist/SAINT.exe sang máy lab.
Admin tạo API Key mới qua Web Dashboard (/api-keys) — copy key (chỉ hiện 1 lần).
Lần đầu mở SAINT.exe trên máy lab: vào Settings → nhập Server URL + API Key → Save.
Restart agent: agent đăng ký với Server, lấy JWT, sync whitelist, apply firewall.
Trên Web Dashboard → tab Agents: máy mới đăng ký xuất hiện, admin gán vào group lớp tương ứng.
(Tùy chọn) Cài SAINT làm Windows Service để chạy ngầm + tự start cùng OS.
## 6.4 Vận hành hàng ngày — Teacher
Đăng nhập Dashboard bằng tài khoản teacher.
Xem các nhóm/lớp được gán quản lý.
Tạo whitelist profile riêng cho buổi học (chỉ allow domain phù hợp bài tập).
Trước giờ học: Activate profile → toàn bộ máy lớp tự động sync (≤ 20s sau heartbeat tiếp theo).
Trong giờ học: xem tab Logs để giám sát máy nào cố truy cập domain bị block.
Hết giờ: Deactivate profile → máy quay về whitelist gốc của nhóm.
## 6.5 Vận hành hàng ngày — Admin
Quản lý tài khoản Teacher: tạo/xóa/reset password qua tab Users.
Tạo/sửa nhóm (Groups) và gán Teacher vào nhóm.
Cấu hình whitelist toàn cục (Whitelist scope=global) — áp dụng cho mọi nhóm.
Cấp/rotate API Key cho agents mới.
Theo dõi tab Audit → trace mọi hành động Admin/Teacher.
Xem tab Logs để phân tích traffic toàn hệ thống; export CSV nếu cần.
Khi máy lab cần gỡ SAINT: GUI Settings → Restore Firewall (khôi phục pre-SAINT state).

# Chương 7 — Phụ lục
## 7.1 Glossary

## 7.2 Code & file size (tóm tắt)

## 7.3 Câu hỏi thường gặp
Q: Agent có hoạt động khi mất kết nối Server không?
Có. Whitelist cached local; firewall rules đã set vẫn áp dụng. Khi mất kết nối, agent log warning + thử reconnect. Khi reconnect, tự động sync version mới nếu có.
Q: Nếu user gỡ SAINT khỏi máy thì firewall còn block không?
SAINT cleanup_on_exit=True sẽ xóa rules SAINT khi GUI close graceful. Nếu kill process force: rules còn lại, nhưng có thể chạy lại SAINT rồi vào Settings → Restore Firewall, hoặc thủ công xóa qua wf.msc (rule có prefix FirewallController_).
Q: Teacher xóa nhầm whitelist toàn cục được không?
Không. RBAC chặn teacher chỉnh sửa whitelist scope=global. Teacher chỉ thao tác được whitelist scope=group của nhóm mình.
Q: Profile của teacher activate có tác động sang nhóm khác không?
Không. Profile gắn với group_id cụ thể; activate chỉ override whitelist của group đó. Các group khác không bị ảnh hưởng.
Q: Làm sao kiểm tra Agent có đang nhận lệnh từ Server không?
Tab Logs trên Web Dashboard sẽ thấy log ALLOWED/BLOCKED real-time từ agent. Tab Agents sẽ thấy status (active/inactive/offline) + last_heartbeat. Trên Agent GUI: tab Dashboard có card 'Last Sync' và 'Server' status.

--- TABLE 0 ---
Thành phần | Vai trò | Công nghệ
Server | Quản lý tập trung, API, Dashboard, RBAC | Python 3.8+, Flask + SocketIO
Agent | Giám sát mạng, áp dụng firewall, GUI | Python 3.8+, CustomTkinter + Scapy
Database | Lưu trữ persistent data | MongoDB (Atlas)
Web Dashboard | Giao diện quản trị | Bootstrap 5 + Jinja2 templates
--- END TABLE ---


--- TABLE 1 ---
Thành phần | Công nghệ | Mục đích
Web Framework | Flask | REST API + Web Dashboard
Realtime | Flask-SocketIO + Gevent | WebSocket notifications
Database | MongoDB (Atlas) + PyMongo | Lưu trữ dữ liệu
Validation | Pydantic | Data modeling & validation
Auth | PyJWT + bcrypt + HMAC-SHA256 | JWT, API key, password hashing
CORS | Flask-CORS | Cross-origin requests
--- END TABLE ---


--- TABLE 2 ---
Thành phần | Công nghệ | Mục đích
GUI | CustomTkinter | Giao diện người dùng Windows
Packet Capture | Scapy + WinPcap/Npcap | Bắt gói tin mạng
DNS Resolution | dnspython + aiodns | Phân giải domain → IP song song
Firewall | netsh (Windows Firewall CLI) | Tạo/xóa rules tự động
HTTP Client | requests | Giao tiếp với Server
System Monitor | psutil + pywin32 | CPU/memory/uptime
Packaging | PyInstaller | Build SAINT.exe single-file
--- END TABLE ---


--- TABLE 3 ---
Collection | Mục đích
agents | Thông tin các Agent đã đăng ký + heartbeat + metrics.
groups | Nhóm Agent (theo lớp/phòng lab) + whitelist + teacher_ids.
whitelists | Danh sách domain/IP được phép (global hoặc theo group).
logs | Log hoạt động mạng do Agent gửi về (ALLOWED/BLOCKED).
users | Tài khoản Admin/Teacher (bcrypt password, RBAC).
admin_sessions | Phiên đăng nhập Admin/Teacher (JWT JTI tracking).
api_keys | API Key cho Agent đăng ký (HMAC-SHA256 hash).
agent_policies | Chính sách riêng từng Agent (isolate / custom whitelist).
whitelist_profiles | Profile whitelist của Teacher, có thể activate/deactivate.
audit_logs | Lịch sử mọi hành động của Admin/Teacher.
whitelist_meta | Theo dõi version whitelist toàn cục (incremental sync).
revoked_tokens | Token đã thu hồi (TTL index auto-delete).
--- END TABLE ---


--- TABLE 4 ---
Trạng thái | Điều kiện
active | Heartbeat ≤ 5 phút trước.
inactive | Heartbeat từ 5 đến 30 phút trước.
offline | Heartbeat > 30 phút hoặc chưa từng heartbeat.
--- END TABLE ---


--- TABLE 5 ---
Method | Route | Auth | Mô tả
POST | /api/agents/register | API Key | Đăng ký Agent mới, nhận agent_token.
POST | /api/agents/heartbeat | JWT | Heartbeat + logs + metrics.
--- END TABLE ---


--- TABLE 6 ---
Method | Route | Auth | Mô tả
GET | /api/agents | Login | Danh sách (RBAC filter theo teacher group).
GET | /api/agents/<id> | Login | Chi tiết agent.
GET | /api/agents/statistics | Login | Thống kê active/inactive/offline.
PATCH | /api/agents/<id>/display-name | Login | Đổi tên hiển thị.
PATCH | /api/agents/<id>/position | Login | Cập nhật vị trí bản đồ.
PATCH | /api/agents/<id>/group | Login (admin) | Chuyển agent sang nhóm khác.
DELETE | /api/agents/<id> | Admin | Xóa agent.
--- END TABLE ---


--- TABLE 7 ---
Method | Route | Auth | Mô tả
GET | /api/agents/<id>/policy | Login | Xem policy của agent.
PATCH | /api/agents/<id>/policy | Login | Đặt isolate / custom_whitelist.
--- END TABLE ---


--- TABLE 8 ---
Method | Route | Auth | Mô tả
GET | /api/whitelist | Login | Danh sách whitelist (scoped).
POST | /api/whitelist | Login | Thêm entry mới.
DELETE | /api/whitelist/<id> | Login | Xóa entry.
POST | /api/whitelist/bulk | Login | Thêm hàng loạt.
POST | /api/whitelist/bulk-update | Login | Update hàng loạt.
POST | /api/whitelist/bulk-delete | Login | Xóa hàng loạt.
GET | /api/whitelist/agent-sync | JWT | Agent sync whitelist.
GET | /api/whitelist/statistics | Login | Thống kê.
POST | /api/whitelist/import | Login | Import CSV.
GET | /api/whitelist/export | Login | Export CSV.
--- END TABLE ---


--- TABLE 9 ---
Method | Route | Auth | Mô tả
GET | /api/groups | Login | Danh sách nhóm.
POST | /api/groups | Admin | Tạo nhóm mới.
GET | /api/groups/<id> | Login | Chi tiết nhóm.
PATCH | /api/groups/<id> | Login | Cập nhật nhóm.
DELETE | /api/groups/<id> | Admin | Xóa nhóm.
POST | /api/groups/<id>/teachers | Admin | Gán teacher vào nhóm.
--- END TABLE ---


--- TABLE 10 ---
Method | Route | Auth | Mô tả
GET | /api/groups/<id>/profiles | Login | Profile của nhóm.
POST | /api/groups/<id>/profiles | Login | Tạo profile.
PATCH | /api/groups/<id>/profiles/<pid> | Login | Sửa profile.
DELETE | /api/groups/<id>/profiles/<pid> | Login | Xóa profile.
POST | /api/groups/<id>/profiles/<pid>/activate | Login | Kích hoạt profile.
POST | /api/groups/<id>/profiles/<pid>/deactivate | Login | Tắt profile.
--- END TABLE ---


--- TABLE 11 ---
Method | Route | Auth | Mô tả
GET | /api/logs | Login | Danh sách logs (RBAC filter).
POST | /api/logs | JWT | Agent gửi batch logs.
GET | /api/logs/stats | Login | Thống kê allowed/blocked.
DELETE | /api/logs | Admin | Xóa logs theo filter.
DELETE | /api/logs/clear | Admin | Xóa toàn bộ logs.
GET | /api/logs/export | Admin | Export CSV.
--- END TABLE ---


--- TABLE 12 ---
Method | Route | Auth | Mô tả
POST | /api/admin/auth/login | None | Đăng nhập, set httpOnly cookie.
POST | /api/admin/auth/logout | Login | Đăng xuất, revoke token.
GET | /api/admin/auth/me | Login | Thông tin user hiện tại.
POST | /api/admin/auth/refresh | Login | Làm mới access token.
GET | /api/admin/users | Admin | Danh sách users.
POST | /api/admin/users | Admin | Tạo user.
PATCH | /api/admin/users/<id> | Admin | Update user (kể cả is_active).
DELETE | /api/admin/users/<id> | Admin | Xóa user.
POST | /api/admin/users/<id>/reset-password | Admin | Reset password.
--- END TABLE ---


--- TABLE 13 ---
Method | Route | Auth | Mô tả
GET | /api/api-keys | Login | Danh sách keys.
POST | /api/api-keys | Admin | Tạo API key (chỉ hiện 1 lần).
POST | /api/api-keys/<id>/revoke | Admin | Thu hồi key.
GET | /api/admin/audit | Admin | Audit logs.
GET | /api/admin/audit/user/<uid> | Admin | Lịch sử của 1 user.
--- END TABLE ---


--- TABLE 14 ---
Role | Phạm vi
admin | Toàn quyền hệ thống — quản lý users, API keys, audit, mọi group.
teacher | Chỉ thao tác trên nhóm mình tạo hoặc được gán quản lý.
--- END TABLE ---


--- TABLE 15 ---
Event | Khi nào | Dữ liệu
server_message | Client kết nối | Welcome message
agent_registered | Agent mới đăng ký | Agent info
agent_status_changed | Agent đổi active/inactive/offline | agent_id, new_status
whitelist_updated | Whitelist được cập nhật | group_id, version
api_key_created | API key mới được tạo | Key info
api_key_revoked | API key bị thu hồi | Key info
--- END TABLE ---


--- TABLE 16 ---
Biến | Mặc định | Mô tả
MONGO_URI | (bắt buộc) | Connection string MongoDB
MONGO_DBNAME | Monitoring | Tên database
FLASK_ENV | development | Môi trường
DEBUG | True | Debug mode
HOST | 0.0.0.0 | Server host
PORT | 5000 | Server port
JWT_SECRET_KEY | (bắt buộc) | Secret cho JWT access token
JWT_REFRESH_SECRET_KEY | (bắt buộc) | Secret cho refresh token
API_KEY_HMAC_SECRET | (bắt buộc) | Secret hash API key
--- END TABLE ---


--- TABLE 17 ---
Signal | Khi phát | Dữ liệu
status_changed | Agent đổi trạng thái | status string
packet_captured | Bắt được gói tin | packet info
log_received | Có log mới | log entry
error_occurred | Có lỗi xảy ra | error message
stats_updated | Cập nhật thống kê | stats dict
whitelist_synced | Whitelist sync xong | whitelist info
--- END TABLE ---


--- TABLE 18 ---
View | Chức năng
Dashboard | Status cards (Running/Stopped, Whitelist count, Uptime, Packets, Server, Last Sync) + activity log + Start/Stop button. Refresh real-time qua signals.
Firewall | Hiển thị policy hiện tại (Default Deny/Allow), rule count, danh sách rules SAINT đã tạo, refresh button.
Whitelist | Danh sách domain/IP đã sync về local + IP đã resolve. Indicator auto-sync (30s).
Logs | Real-time log streaming + filter theo level (DEBUG/INFO/WARNING/ERROR) + export CSV.
Settings | Cấu hình Server URL, API Key, Heartbeat interval, Sync interval, Firewall backup & restore.
--- END TABLE ---


--- TABLE 19 ---
Manager | Trách nhiệm
PolicyManager | Default Deny/Allow toàn cục qua netsh advfirewall set allprofiles.
RulesManager | Tạo/xóa rules allow cho từng IP có prefix FirewallController_.
FirewallUtils | Wrapper subprocess gọi netsh; check admin privileges.
--- END TABLE ---


--- TABLE 20 ---
Phương pháp | Áp dụng | Cách trích xuất
DNS Query | Port 53 | Đọc domain từ DNS question section.
HTTP Host | Port 80 | Đọc Host header từ HTTP request.
TLS SNI | Port 443 | Đọc Server Name Indication từ TLS ClientHello.
--- END TABLE ---


--- TABLE 21 ---
Yêu cầu | Chi tiết
OS | Windows 10/11
Python | 3.8+ (nếu chạy từ source)
WinPcap/Npcap | Bắt buộc cho packet capture (Agent auto-install)
Quyền Admin | Cần thiết để apply firewall rules
Mạng | TCP outbound đến Server URL
RAM | ~100–200 MB
--- END TABLE ---


--- TABLE 22 ---
Tính năng | Mô tả
API Key authentication | Agent đăng ký bằng API Key, server lưu HMAC-SHA256 hash (không lưu plaintext).
JWT tokens | Access token 24h + Refresh token 7 ngày, JTI tracking để revoke.
Mã hóa mật khẩu | bcrypt với salt tự động sinh.
Chống brute-force | Khóa tài khoản 15 phút sau 5 lần đăng nhập sai.
RBAC chi tiết | Quyền theo resource:action; teacher bị data-filter theo group.
httpOnly cookie | JWT lưu trong cookie không truy cập được từ JavaScript (chống XSS).
Token revocation | Logout revoke token; collection revoked_tokens có TTL auto-cleanup.
Audit trail | Mọi hành động Admin/Teacher đều ghi audit_logs (user/action/resource/IP/timestamp).
Config encryption | Agent config chứa API key được mã hóa Fernet (file .enc).
Server URL trống mặc định | Agent KHÔNG tự kết nối server demo; user phải nhập URL trong Settings.
--- END TABLE ---


--- TABLE 23 ---
Pattern | Áp dụng | Mục đích
Singleton | Agent, AgentController, App | Chỉ một instance trong toàn app.
Observer | AgentSignals | Callback registration/dispatch giữa worker và GUI.
MVP | GUI architecture | Tách View / Presenter / Model.
Thread Pool | DNS Resolver | ThreadPoolExecutor 5–10 workers.
Queue | LogSender, Event queue | Async communication giữa thread.
Lazy Loading | MainWindow views | View chỉ tạo khi truy cập lần đầu.
State Machine | Agent state | STOPPED → STARTING → RUNNING → STOPPING.
MVC | Server architecture | Controller / Service / Model phân tách rõ.
--- END TABLE ---


--- TABLE 24 ---
Thuật ngữ | Định nghĩa
SAINT | Security Agent Integrated Network Tool — tên sản phẩm.
Default Deny | Chính sách firewall mặc định chặn mọi outbound; chỉ cho phép IP có rule allow.
Whitelist | Danh sách domain/IP/pattern được phép truy cập.
Pattern | Wildcard domain dạng *.google.com — match mọi subdomain.
Group | Nhóm Agent (thường tương ứng 1 lớp/phòng lab).
Profile | Bộ whitelist tạm thời của Teacher; activate để override group whitelist.
RBAC | Role-Based Access Control — phân quyền theo vai trò Admin/Teacher.
JTI | JWT ID — định danh duy nhất của 1 token, dùng để revoke.
Snapshot | File JSON lưu trạng thái firewall trước khi SAINT thay đổi.
pseudo-id | ID giả cho whitelist entry thuộc group, format group::<gid>::<type>::<value>.
--- END TABLE ---


--- TABLE 25 ---
Thành phần | File chính | Mô tả
Server entry | server/app.py | Khởi tạo Flask, đăng ký 10 blueprints.
Agent entry | agent/agent_gui.py | Khởi động CustomTkinter GUI.
Lifecycle | agent/core/lifecycle.py | Toàn bộ quy trình khởi tạo & cleanup.
Firewall | agent/firewall/manager.py | FirewallManager + snapshot save/restore.
Whitelist client | agent/whitelist/manager.py | Sync + state thread-safe.
DNS | agent/network/dns_resolver.py | OptimizedDNSResolver parallel.
Sniffer | agent/capture/sniffer.py | PacketSniffer (Scapy).
RBAC | server/middleware/rbac.py | Decorator + data filter.
Build spec | FirewallAgent.spec | PyInstaller config build SAINT.exe.
--- END TABLE ---
