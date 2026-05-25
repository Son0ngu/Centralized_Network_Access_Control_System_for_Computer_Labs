
SAINT — UML Diagrams
Use Case Diagram · Class Diagrams · Sequence Diagram


Tài liệu sơ đồ UML đầy đủ cho hệ thống Centralized Network Access Control System for Computer Labs

# 1. Use Case Diagram
Sơ đồ use case mô tả các chức năng chính của hệ thống SAINT từ góc nhìn của 3 actor: Admin (quản trị viên), Teacher (giáo viên) và Agent (phần mềm chạy trên máy Windows). Hệ thống được chia thành 8 nhóm chức năng (package): Authentication, User Management, Group Management, Whitelist Management, Network Monitoring, Firewall Control, API Key Management và Audit.

Hình 1.1 — Use Case Diagram tổng quát của SAINT
## 1.1 Actor

## 1.2 Các use case theo nhóm chức năng
Authentication
Login / Logout (cả Admin và Teacher)
Change Password
Register Agent — Agent đăng ký lần đầu bằng API Key
User Management (Admin-only)
Create / Update / Delete / List User
Reset Password
Group Management
Create / Update / Delete / List Group (Admin)
Assign Teachers to Group (Admin)
Assign Agents to Group (Admin/Teacher)
Teacher chỉ thao tác được nhóm mình tạo hoặc được gán
Whitelist Management
Add / Delete Domain / IP
Import / Export Whitelist (CSV)
Manage Whitelist Profile (Teacher tạo profile tạm thời)
Sync Whitelist (Agent gọi)
Network Monitoring
Capture Packets (Agent dùng Scapy)
Extract Domains từ DNS / HTTP Host / TLS SNI
Send Logs to Server (batch 100, 2 giây)
View / Export Logs (Admin/Teacher)
Firewall Control
Apply Firewall Rules (Agent tạo netsh rules)
Set Agent Policy (isolate / custom_whitelist)
Send Heartbeat (20 giây)
Restore Firewall (revert pre-SAINT state)
API Key Management (Admin-only)
Create / Revoke / List API Key
Validate Key (server-side check)
Audit (Admin-only)
View Audit Logs (toàn bộ hành động)
View User Activity (lọc theo user)
## 1.3 Quan hệ <<include>>
Hai quan hệ include chính trong hệ thống:
Capture Packets <<include>> Extract Domains — mỗi packet bắt được đều phải đi qua bước extract domain (DNS/HTTP/SNI) để check whitelist.
Sync Whitelist <<include>> Apply Firewall Rules — sau khi sync xong whitelist từ Server, Agent luôn áp dụng lại firewall rules dựa trên dữ liệu mới.

# 2. Class Diagram — Server
Server SAINT theo kiến trúc 3 tầng MVC: Controller (REST API) → Service (Business Logic) → Model (MongoDB CRUD). Tầng middleware (auth + RBAC) xử lý xác thực và phân quyền trước khi request đi vào Controller. Mỗi tầng có ~10 class chính, tổng cộng khoảng 30 class tham gia luồng xử lý chính.

Hình 2.1 — Class Diagram của SAINT Server
## 2.1 Tầng Controller
Mỗi Controller đăng ký Flask blueprint phục vụ 1 nhóm route. Controller chỉ làm validate input + delegate sang Service, không chứa business logic.

## 2.2 Tầng Service
Service tập trung business logic: validate ngữ nghĩa, phối hợp nhiều Model, gọi RBACService để filter dữ liệu theo role, ghi audit trail.

## 2.3 Tầng Model
Model là wrapper mỏng quanh PyMongo collection — chỉ thao tác CRUD. 12 collection được map tương ứng:


# 3. Class Diagram — Agent
Agent SAINT.exe có kiến trúc MVP (Model-View-Presenter) với 6 package chính: Core (lifecycle), GUI (CustomTkinter views), Firewall (Windows Firewall qua netsh), Whitelist (state + sync), Capture (Scapy sniffer + DNS), Services (heartbeat + log sender). Tất cả background work chạy trong worker thread; GUI thread chỉ render và xử lý event qua hệ thống Signals (queue 500ms).

Hình 3.1 — Class Diagram của SAINT Agent
## 3.1 Core layer

## 3.2 Firewall package
FirewallManager là orchestrator phối hợp 2 sub-managers:
PolicyManager — quản lý Default Allow/Deny qua netsh advfirewall set allprofiles.
RulesManager — tạo/xóa rule cho từng IP với prefix FirewallController_<IP>.
Ngoài ra FirewallManager phụ trách Backup/Restore: save_snapshot() lưu JSON chứa policy hiện tại + whitelist_mode + essential_ips với skip-if-exists guard; restore_snapshot() khôi phục policy gốc, có admin guard và safety-net tránh lockout mạng.
## 3.3 Whitelist package

## 3.4 Capture & DNS package

## 3.5 Background services

## 3.6 GUI views


# 4. Sequence Diagram — Whitelist Sync
Sơ đồ tuần tự minh họa luồng đồng bộ whitelist incremental giữa Agent và Server. Đây là một trong các luồng quan trọng nhất của hệ thống vì nó quyết định tốc độ phản hồi khi Teacher thay đổi whitelist trên Dashboard.

Hình 4.1 — Sequence Diagram: Whitelist Sync giữa Agent và Server
## 4.1 Mô tả từng bước
1. Heartbeat tick (20s)
Agent GUI báo cho WhitelistManager rằng đến hạn heartbeat tiếp theo.
2. POST /api/agents/heartbeat
Agent gửi heartbeat lên Server với agent_id, metrics và whitelist_version hiện tại đang nắm giữ.
3. Server forward heartbeat
WhitelistController nhận request, gọi WhitelistService để xử lý.
4. compare whitelist_version
WhitelistService truy vấn MongoDB collection whitelist_meta để đọc version mới nhất.
5. version mismatch
MongoDB trả về version mới (ví dụ: server=v6, agent đang v5) → có thay đổi.
6. response{version_changed:true}
Service trả response chứa whitelist_version mới + cờ whitelist_version_changed=true + force_sync flag (nếu có).
7. HTTP 200 + version_changed
Server response 200 OK với body chứa cờ. Agent đọc cờ này từ heartbeat response.
8. GET /api/whitelist/agent-sync
WhitelistManager phát hiện cờ → gọi endpoint sync để lấy whitelist mới.
9. get_agent_sync_data()
Service build payload: whitelist entries (merge global + group), active_profile (nếu có), policy override.
10. Response payload
Server trả về JSON: { whitelist[], active_profile, policy, whitelist_version }.
11. DNS resolve + apply firewall
Agent dùng OptimizedDNSResolver resolve toàn bộ domain → IPs (parallel), sau đó gọi FirewallManager.update_whitelist() để tạo/xóa netsh rules tương ứng. State local được cập nhật version mới.
## 4.2 Tối ưu hóa: short-circuit khi up-to-date
Nếu ở bước 4 Service phát hiện whitelist_version của agent BẰNG version trên Server, response sẽ chỉ chứa { up_to_date: true } mà KHÔNG gửi lại whitelist data. Agent skip toàn bộ bước 8-11. Đây là cơ chế quan trọng giúp hệ thống scale: dù có 100 agent, Server cũng không phải gửi đi cả 100 lần whitelist nếu nội dung không thay đổi.
Khi nào version tăng?
Admin/Teacher thêm/sửa/xóa entry trong whitelist của group → service tự bump group whitelist_version.
Teacher activate/deactivate whitelist profile → bump group whitelist_version.
Admin set agent policy (isolate / custom_whitelist) → bump agent_policy override_version (kênh thông báo riêng qua field policy_changed).

--- TABLE 0 ---
Actor | Vai trò | Phương thức xác thực
Admin | Quản trị toàn hệ thống: tạo user, group, API key, xem audit | Username + Password → JWT cookie
Teacher | Quản lý nhóm/lớp được gán: whitelist, profile, xem logs | Username + Password → JWT cookie
Agent | Phần mềm trên máy Windows: tự động sync, monitor, apply firewall | API Key → đổi sang JWT agent token
--- END TABLE ---


--- TABLE 1 ---
Class | Routes phụ trách | Service dùng
AgentController | /api/agents/* | AgentService
GroupController | /api/groups/* | GroupService
WhitelistController | /api/whitelist/* | WhitelistService
LogController | /api/logs/* | LogService
AdminAuthController | /api/admin/auth/* | AdminAuthService
UserController | /api/admin/users/* | UserService
APIKeyController | /api/api-keys/* | APIKeyService
AuditController | /api/admin/audit/* | AuditService
WhitelistProfileController | /api/groups/<id>/profiles/* | WhitelistProfileService
--- END TABLE ---


--- TABLE 2 ---
Class | Trách nhiệm chính
UserService | CRUD user + bcrypt password hashing + lockout sau 5 lần fail.
AgentService | Đăng ký agent, cập nhật status, scoped listing theo group.
GroupService | CRUD group + teacher assignment.
WhitelistService | Add/update/delete domain, tính scoped whitelist cho UI, build agent sync payload.
LogService | Nhận logs từ agent, query với pagination.
AdminAuthService | Đăng nhập, refresh token, change password, brute-force protection.
JWTService | Tạo + verify JWT (access 24h + refresh 7d), JTI tracking để revoke.
APIKeyService | Sinh API key + lưu HMAC-SHA256 hash, validate khi agent register.
RBACService | Check permission resource:action, filter dữ liệu theo group ownership cho teacher.
AuditService | Ghi mọi hành động Admin/Teacher kèm user/action/resource/IP.
WhitelistProfileService | CRUD profile + activate/deactivate (override whitelist tạm thời).
--- END TABLE ---


--- TABLE 3 ---
Model | Collection
UserModel | users
AgentModel | agents
GroupModel | groups
WhitelistModel | whitelists + whitelist_meta
LogModel | logs
AuditModel | audit_logs
APIKeyModel | api_keys
SessionModel | admin_sessions + revoked_tokens
WhitelistProfileModel | whitelist_profiles
AgentPolicyModel | agent_policies
--- END TABLE ---


--- TABLE 4 ---
Class | Pattern | Trách nhiệm
Agent | Singleton | Singleton trung tâm, lưu reference đến mọi component (firewall, whitelist, sniffer, log_sender, heartbeat, token_manager).
AgentController | Presenter | Bridge giữa GUI và Agent. Khi user click Start/Stop, controller gọi lifecycle functions trong background thread, signal kết quả ngược lên GUI.
Lifecycle (module) | Module | Hàm initialize_components(config) và cleanup_components() — orchestrator toàn bộ flow khởi động/dừng agent.
TokenManager | Background thread | Auto-refresh JWT trước khi hết hạn; callback re-registration nếu refresh fail.
--- END TABLE ---


--- TABLE 5 ---
Class | Trách nhiệm
WhitelistManager | API public: sync_now(), is_allowed(), is_ip_allowed(). Phối hợp state + syncer + DNS resolver. Khi sync xong, gọi firewall.update_whitelist().
WhitelistState | Thread-safe storage với RLock. Lưu domains, patterns (*.x.com), IPs, version.
WhitelistSyncer | HTTP client gọi GET /api/whitelist/agent-sync. Retry + fallback URL + JWT auth.
WhitelistMonitor | Periodic syncer chạy mỗi 30 giây (background thread).
--- END TABLE ---


--- TABLE 6 ---
Class | Trách nhiệm
PacketSniffer | Scapy-based sniffer. Filter TCP port 53/80/443. Chạy thread riêng, graceful shutdown qua _stop_event.
DomainExtractor | Stateless utility: extract domain từ DNS question / HTTP Host header / TLS SNI ClientHello.
OptimizedDNSResolver | Parallel DNS resolver. ThreadPool 5–10 workers, chunking 20 domain/chunk, dual stack dnspython + aiodns, LRU cache 2000 entries.
--- END TABLE ---


--- TABLE 7 ---
Class | Interval | Endpoint
HeartbeatSender | 20 giây | POST /api/agents/heartbeat — gửi status + metrics, nhận whitelist_version + force_sync flag
LogSender | 2 giây (batch 100) | POST /api/logs — queue-based, exponential backoff khi server lỗi
--- END TABLE ---


--- TABLE 8 ---
View | Chức năng
DashboardView | Status cards real-time (Running/Stopped, Uptime, Packets, Whitelist count, Server status).
FirewallView | Hiển thị policy hiện tại, danh sách rules SAINT đã tạo.
WhitelistView | Danh sách domain/IP đã sync + IP đã resolve.
LogsView | Real-time log streaming + filter level + export CSV.
SettingsView | Cấu hình Server URL, API Key, Heartbeat/Sync interval, Firewall backup/restore.
--- END TABLE ---
