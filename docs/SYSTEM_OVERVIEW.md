# SAINT - Tổng Quan Hệ Thống

## 1. Giới thiệu

**SAINT** (Security Agent Integrated Network Tool) là hệ thống quản lý bảo mật mạng phân tán, được thiết kế cho môi trường giáo dục. Hệ thống cho phép quản trị viên và giáo viên giám sát, kiểm soát truy cập mạng của các máy tính trong phòng lab/lớp học thông qua cơ chế whitelist và firewall tự động.

### Vấn đề cần giải quyết
- Học sinh/sinh viên truy cập các trang web không phù hợp trong giờ học
- Thiếu công cụ quản lý mạng tập trung cho môi trường giáo dục
- Giáo viên không có khả năng kiểm soát truy cập mạng theo lớp/nhóm
- Không có hệ thống giám sát real-time hoạt động mạng

### Giải pháp
SAINT cung cấp hệ thống Client-Server với:
- **Agent** cài đặt trên máy tính học sinh, tự động đồng bộ whitelist và áp dụng firewall
- **Server** quản lý tập trung, cung cấp dashboard web và REST API
- **RBAC** phân quyền Admin/Teacher để giáo viên tự quản lý lớp của mình

---

## 2. Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────────┐
│                    QUẢN TRỊ VIÊN / GIÁO VIÊN                 │
│              (Web Browser - Dashboard)                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP/HTTPS + WebSocket
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                     SERVER (Flask)                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Controllers  │  │  Services    │  │    Middleware       │  │
│  │ (API Routes) │→ │ (Logic)      │  │ (Auth + RBAC)      │  │
│  └─────────────┘  └──────┬───────┘  └────────────────────┘  │
│                          │                                    │
│  ┌──────────────┐  ┌─────▼──────┐  ┌────────────────────┐   │
│  │ Flask-SocketIO│  │  Models    │  │   JWT Service      │   │
│  │ (Real-time)  │  │ (MongoDB)  │  │ (Token mgmt)       │   │
│  └──────────────┘  └─────┬──────┘  └────────────────────┘   │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │   MongoDB      │
                   │   (Atlas)      │
                   │   12 Collections│
                   └────────────────┘
                            ▲
              REST API      │      REST API
         (JWT Auth)         │     (JWT Auth)
         ┌──────────────────┼──────────────────┐
         │                  │                  │
┌────────▼───────┐ ┌───────▼────────┐ ┌───────▼────────┐
│   AGENT #1     │ │   AGENT #2     │ │   AGENT #N     │
│  (Windows PC)  │ │  (Windows PC)  │ │  (Windows PC)  │
│                │ │                │ │                │
│ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │
│ │ GUI (Qt)   │ │ │ │ GUI (Qt)   │ │ │ │ GUI (Qt)   │ │
│ ├────────────┤ │ │ ├────────────┤ │ │ ├────────────┤ │
│ │ Firewall   │ │ │ │ Firewall   │ │ │ │ Firewall   │ │
│ │ Manager    │ │ │ │ Manager    │ │ │ │ Manager    │ │
│ ├────────────┤ │ │ ├────────────┤ │ │ ├────────────┤ │
│ │ Packet     │ │ │ │ Packet     │ │ │ │ Packet     │ │
│ │ Sniffer    │ │ │ │ Sniffer    │ │ │ │ Sniffer    │ │
│ ├────────────┤ │ │ ├────────────┤ │ │ ├────────────┤ │
│ │ Whitelist  │ │ │ │ Whitelist  │ │ │ │ Whitelist  │ │
│ │ Manager    │ │ │ │ Manager    │ │ │ │ Manager    │ │
│ └────────────┘ │ │ └────────────┘ │ │ └────────────┘ │
└────────────────┘ └────────────────┘ └────────────────┘
```

---

## 3. Technology Stack

### Server
| Thành phần | Công nghệ | Mục đích |
|-----------|-----------|----------|
| Web Framework | Flask | REST API + Web Dashboard |
| Real-time | Flask-SocketIO + Gevent | WebSocket notifications |
| Database | MongoDB (Atlas) | Lưu trữ dữ liệu |
| ORM/ODM | PyMongo + Pydantic | Data modeling & validation |
| Authentication | PyJWT + bcrypt | JWT tokens + password hashing |
| CORS | Flask-CORS | Cross-origin requests |

### Agent
| Thành phần | Công nghệ | Mục đích |
|-----------|-----------|----------|
| GUI | PySide6/Qt | Giao diện người dùng Windows |
| Packet Capture | Scapy | Bắt gói tin mạng |
| DNS Resolution | dnspython + aiodns | Phân giải domain → IP |
| Firewall | netsh (Windows) | Quản lý Windows Firewall |
| HTTP Client | requests | Giao tiếp với Server |
| System Monitor | psutil + pywin32 | Thông tin hệ thống |
| Packaging | PyInstaller | Build SAINT.exe |

---

## 4. Luồng hoạt động chính

### 4.1 Luồng khởi động Agent

```
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌───────────┐
│ Khởi    │     │ Đăng ký  │     │ Sync     │     │ Áp dụng   │
│ động    │────▶│ với      │────▶│ Whitelist│────▶│ Firewall  │
│ GUI     │     │ Server   │     │ từ Server│     │ Rules     │
└─────────┘     └──────────┘     └──────────┘     └───────────┘
                                                        │
                ┌──────────┐     ┌──────────┐           │
                │ Gửi      │     │ Bắt gói  │           │
                │ Heartbeat│◀────│ tin mạng │◀──────────┘
                │ định kỳ  │     │ (Scapy)  │
                └──────────┘     └──────────┘
```

**Chi tiết:**
1. Người dùng mở SAINT.exe → GUI hiển thị
2. Nhấn "Start Agent" → Agent đăng ký với Server qua API Key
3. Server trả về `agent_id` + JWT token
4. Agent gọi `/api/whitelist/agent-sync` để lấy danh sách whitelist
5. DNS Resolver phân giải tất cả domain → IP
6. FirewallManager tạo rules cho phép các IP trong whitelist
7. PacketSniffer bắt đầu capture traffic (TCP 80, 443, 53)
8. HeartbeatSender gửi heartbeat mỗi 20 giây
9. LogSender gửi batch logs mỗi 2 giây

### 4.2 Luồng kiểm tra truy cập mạng (Preventive + Detective)

```
┌──────────┐     ┌───────────────────────────────┐
│ Máy tính │     │ Layer 3: Windows Firewall     │
│ truy cập │────▶│ Default Deny + allow IPs      │
│ website  │     │ Self-allow program=SAINT.exe  │
└──────────┘     └───────────┬───────────────────┘
                             │
                ┌────────────┼───────────────┐
                ▼ pass (IP   ▼ drop          ▼ agent's own
                  in WL)      (no rule)         outbound
            ┌─────────┐  ┌─────────┐      ┌──────────────┐
            │ NIC out │  │ DROPPED │      │ Server, DNS  │
            └────┬────┘  │ silent  │      └──────────────┘
                 │        └─────────┘
                 ▼
┌────────────────────────────────────────────────────────┐
│ Layer 7: Scapy Sniffer (passive copy at NIC)           │
│   DomainExtractor: DNS query / HTTP Host / TLS SNI     │
│   Whitelist check by domain + IP                       │
└─────────────────────────┬──────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌──────────┐  ┌──────────────────┐  ┌──────────┐
   │ ALLOWED  │  │ ALLOWED_BY_IP    │  │ BLOCKED  │
   │ INFO     │  │ WARNING          │  │ (record) │
   │          │  │ (CDN bleed-thru) │  │          │
   └─────┬────┘  └────────┬─────────┘  └─────┬────┘
         └────────────────┼──────────────────┘
                          ▼
              ┌──────────────────────┐
              │ LogSender batch 100  │
              │ → POST /api/logs     │
              │ → MongoDB logs[]     │
              └──────────────────────┘
```

**Key insight về `ALLOWED_BY_IP`**: khi user vào `phimlau.com` mà domain này
host trên cùng Cloudflare IP với `portal.edu.vn` (đã whitelist), Layer 3
cho qua vì IP match. Layer 7 thấy SNI = `phimlau.com` không nằm trong
whitelist → log WARNING. Admin xem dashboard sẽ thấy event này và có thể
quyết định: tighten policy, gọi học sinh, hoặc whitelist thêm domain hợp pháp.

### 4.3 Luồng đồng bộ Whitelist

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│ Admin/   │     │ Server    │     │ Version  │     │ Agent    │
│ Teacher  │────▶│ cập nhật  │────▶│ tăng lên │────▶│ phát hiện│
│ sửa WL  │     │ whitelist │     │          │     │ thay đổi │
└──────────┘     └───────────┘     └──────────┘     └────┬─────┘
                                                          │
                 ┌───────────┐     ┌──────────┐           │
                 │ Firewall  │     │ DNS      │           │
                 │ cập nhật  │◀────│ resolve  │◀──────────┘
                 │ rules     │     │ domains  │
                 └───────────┘     └──────────┘
```

### 4.4 Luồng xác thực & phân quyền RBAC

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│ Admin/   │     │ POST      │     │ Verify   │     │ Tạo JWT  │
│ Teacher  │────▶│ /login    │────▶│ bcrypt   │────▶│ cookie   │
│ đăng nhập│     │ user+pass │     │ password │     │ httpOnly │
└──────────┘     └───────────┘     └──────────┘     └────┬─────┘
                                                          │
                 ┌───────────┐     ┌──────────┐           │
                 │ Trả về    │     │ RBAC     │           │
                 │ data đã   │◀────│ filter   │◀──────────┘
                 │ filter    │     │ theo role │
                 └───────────┘     └──────────┘
```

---

## 5. Các tính năng bảo mật

| Tính năng | Mô tả |
|-----------|--------|
| **API Key Authentication** | Agent đăng ký bằng API Key (HMAC-SHA256 hash) |
| **JWT Tokens** | Access token (24h) + Refresh token (7 ngày), JTI tracking |
| **Mã hóa mật khẩu** | bcrypt với salt tự động |
| **Chống brute-force** | Khóa tài khoản sau 5 lần đăng nhập sai (15 phút) |
| **RBAC** | Phân quyền chi tiết Admin/Teacher theo resource:action |
| **httpOnly Cookie** | JWT lưu trong cookie không truy cập được từ JavaScript |
| **Token Revocation** | Thu hồi token khi logout, TTL auto-cleanup |
| **Audit Trail** | Ghi log tất cả hành động của Admin/Teacher |
| **Config Encryption** | Mã hóa file cấu hình Agent chứa thông tin nhạy cảm |
| **Session Management** | Quản lý phiên đăng nhập, hết hạn tự động |

---

## 5b. Mô hình Defense in Depth (Preventive + Detective)

Hệ thống áp dụng 2 lớp control bổ trợ nhau, mỗi lớp giải quyết một class of attacks:

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3 - PREVENTIVE CONTROL (Windows Firewall)                 │
│  - Default Deny outbound trên cả 3 profile domain/private/public │
│  - Allow rules theo IP cho whitelist đã resolve                  │
│  - Self-allow rule theo program path (SAINT.exe) cho 443/53      │
│  → Chặn ≥99% non-whitelisted traffic ngay ở kernel               │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                (Traffic vào IP whitelisted lọt qua)
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Layer 7 - DETECTIVE CONTROL (Scapy Passive Sniffer)             │
│  - Bắt TCP 80/443, UDP 53 (passive, không inject)                │
│  - Trích xuất domain qua DNS query / HTTP Host / TLS SNI         │
│  - Phân loại event thành 4 cấp compliance:                       │
│      ALLOWED        - domain match explicit whitelist            │
│      ALLOWED_BY_IP  - IP whitelisted, domain KHÔNG có (WARNING)  │
│      BLOCKED        - không match cả domain lẫn IP               │
│      OBSERVED       - passive mode (không có admin để enforce)   │
│  → Admin review WARNING để phát hiện CDN bleed-through           │
└──────────────────────────────────────────────────────────────────┘
```

**Vì sao không active blocking ở Layer 7:**

Các kỹ thuật active enforcement ở Layer 7 (TCP RST injection, DNS hijack với
local sinkhole, browser policy modification qua registry) đều bị Defender,
CrowdStrike, SentinelOne flag là malicious behavior. SAINT thiết kế để
**không có hành vi malware-like**, phù hợp deploy chung với EDR ở môi trường
enterprise/giáo dục có IT policy strict. Trade-off: chấp nhận giới hạn fine-grained
ở Layer 7, bù lại bằng detective control để admin có visibility và iterate policy.

---

## 6. Mô hình triển khai

```
┌─────────────────────────────────────────────┐
│              INTERNET / LAN                  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │         Server (Flask)                 │  │
│  │    - Ubuntu/Windows Server             │  │
│  │    - Python 3.8+                       │  │
│  │    - Port 5000                         │  │
│  │    - MongoDB Atlas (cloud)             │  │
│  └────────────────────────────────────────┘  │
│                    │                         │
│       ┌────────────┼────────────┐            │
│       │            │            │            │
│  ┌────▼────┐  ┌────▼────┐  ┌───▼─────┐      │
│  │ PC #1   │  │ PC #2   │  │ PC #N   │      │
│  │SAINT.exe│  │SAINT.exe│  │SAINT.exe│      │
│  │Windows  │  │Windows  │  │Windows  │      │
│  └─────────┘  └─────────┘  └─────────┘      │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │   Web Browser (Admin/Teacher)          │  │
│  │   Truy cập Dashboard quản lý          │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 7. Tóm tắt các thành phần

| Thành phần | Vai trò | Ngôn ngữ | Framework |
|-----------|---------|----------|-----------|
| Server | Quản lý tập trung, API, Dashboard | Python 3.8+ | Flask + SocketIO |
| Agent | Giám sát mạng, Firewall, GUI | Python 3.8+ | PySide6/Qt + Scapy + netsh |
| Database | Lưu trữ dữ liệu | - | MongoDB Atlas |
| Web Dashboard | Giao diện quản trị | HTML/CSS/JS | Flask Templates |

### Số liệu dự án
- **~50 API endpoints** phục vụ Agent và Web Dashboard
- **12 MongoDB collections** lưu trữ dữ liệu
- **2 roles RBAC** (Admin, Teacher) với hệ thống permission chi tiết
- **5 GUI views** trên Agent (Dashboard, Firewall, Whitelist, Logs, Settings)
- **7 test files** kiểm thử Server
