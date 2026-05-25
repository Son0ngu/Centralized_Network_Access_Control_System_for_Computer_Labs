# Hướng dẫn làm Slide bảo vệ Đồ Án Tốt Nghiệp - SAINT

## 1. Cấu trúc slide đề xuất (20-25 slides)

### Slide 1: Trang bìa
```
TRƯỜNG ĐẠI HỌC [TÊN TRƯỜNG]
KHOA [TÊN KHOA]

ĐỒ ÁN TỐT NGHIỆP

Đề tài: XÂY DỰNG HỆ THỐNG QUẢN LÝ BẢO MẬT MẠNG
PHÂN TÁN CHO MÔI TRƯỜNG GIÁO DỤC (SAINT)

GVHD: [Tên giảng viên]
SVTH: [Tên sinh viên]
MSSV: [Mã số]
Lớp: [Tên lớp]

Năm 2026
```

---

### Slide 2: Mục lục
```
1. Đặt vấn đề
2. Mục tiêu đề tài
3. Tổng quan hệ thống
4. Công nghệ sử dụng
5. Thiết kế Server
6. Thiết kế Agent
7. Luồng hoạt động
8. Bảo mật hệ thống
9. Kết quả & Demo
10. Kết luận & Hướng phát triển
```

---

### Slide 3: Đặt vấn đề
**Nội dung trình bày:**
- Thực trạng: Học sinh truy cập web không phù hợp trong giờ học
- Thiếu công cụ quản lý mạng tập trung cho trường học
- Giáo viên không kiểm soát được mạng theo lớp/nhóm
- Các giải pháp hiện tại (proxy, manual firewall) quá phức tạp

**Tips:** Dùng bullet points ngắn gọn, có thể thêm 1 hình minh họa về phòng lab.

---

### Slide 4: Mục tiêu đề tài
**Nội dung:**
- Xây dựng hệ thống Client-Server quản lý truy cập mạng
- Agent tự động trên máy tính Windows (whitelist-based firewall)
- Server quản lý tập trung với Web Dashboard
- Phân quyền RBAC cho Admin và Teacher
- Giám sát real-time hoạt động mạng
- Ghi log và audit trail đầy đủ

---

### Slide 5: Tổng quan kiến trúc hệ thống
**Nội dung:** Sơ đồ kiến trúc Client-Server

```
Nên vẽ sơ đồ gồm:
- Server (trung tâm) kết nối MongoDB
- Nhiều Agent (máy tính) kết nối Server qua REST API
- Web Browser (Admin/Teacher) kết nối Server
- Mũi tên chỉ hướng giao tiếp

Dùng shapes trong PowerPoint:
- Rectangle cho Server, Agent
- Cylinder cho Database
- Cloud cho Internet/LAN
- Arrows cho kết nối
```

**Tips:** Slide này RẤT QUAN TRỌNG - hội đồng thường hỏi về kiến trúc. Vẽ rõ ràng, dùng màu phân biệt Server (xanh), Agent (cam), Database (tím).

---

### Slide 6: Kiến trúc chi tiết
**Nội dung:** Sơ đồ MVC/layers cho cả Server và Agent

```
Server (Flask MVC):
Controller → Service → Model → MongoDB

Agent (MVP + Signals):
GUI Views ← Signals ← AgentController → Components
                                         (Firewall, Sniffer, Whitelist)
```

---

### Slide 7: Công nghệ sử dụng - Server
**Nội dung:** Bảng công nghệ

| Thành phần | Công nghệ |
|-----------|-----------|
| Web Framework | Flask + Flask-SocketIO |
| Database | MongoDB Atlas |
| Auth | JWT + API Key + bcrypt |
| Real-time | WebSocket (SocketIO) |
| Validation | Pydantic |

**Tips:** Dùng icons/logo cho mỗi công nghệ sẽ đẹp hơn.

---

### Slide 8: Công nghệ sử dụng - Agent
**Nội dung:**

| Thành phần | Công nghệ |
|-----------|-----------|
| GUI | CustomTkinter |
| Packet Capture | Scapy + WinPcap |
| DNS | dnspython + aiodns |
| Firewall | netsh (Windows) |
| Build | PyInstaller → SAINT.exe |

---

### Slide 9: Thiết kế Database
**Nội dung:** ERD hoặc bảng collections

Highlight 4-5 collections chính:
- `agents` - Thông tin agent
- `whitelists` - Domain/IP cho phép
- `groups` - Nhóm agent
- `logs` - Logs hoạt động mạng
- `users` - Tài khoản Admin/Teacher

**Tips:** Không cần show hết 12 collections - chỉ show những cái quan trọng nhất.

---

### Slide 10: Thiết kế API
**Nội dung:** Tổng quan API endpoints

Chia theo nhóm:
- Agent API: register, heartbeat, sync (3 endpoints)
- Whitelist API: CRUD + bulk + import/export (10 endpoints)
- Group API: CRUD + assign teachers (6 endpoints)
- Auth API: login, logout, refresh (6 endpoints)
- User/Audit API: CRUD + audit trail (10 endpoints)

**Tổng: ~50 REST API endpoints**

**Tips:** Không liệt kê hết - dùng bảng tổng hợp, chi tiết để trong demo.

---

### Slide 11: Thiết kế Agent - GUI
**Nội dung:** Screenshots của 5 views

- Dashboard: Status cards + Activity log
- Firewall: Rules table
- Whitelist: Domain list + auto-sync
- Logs: Real-time log console
- Settings: Server config

**Tips:** Chụp screenshots thật, resize đẹp. Có thể xếp 2-3 screenshots/slide.

---

### Slide 12: Thiết kế Agent - Core Components
**Nội dung:** Sơ đồ components

```
Agent Core
├── PacketSniffer (Scapy) → Bắt gói tin TCP 80/443/53
├── DomainExtractor → Trích xuất domain (DNS/HTTP/SNI)
├── FirewallManager → Tạo/xóa Windows Firewall rules
├── WhitelistManager → Đồng bộ whitelist từ Server
├── HeartbeatSender → Gửi heartbeat 20s
└── LogSender → Gửi batch logs 2s
```

---

### Slide 13: Luồng đăng ký Agent
**Nội dung:** Sequence diagram

```
Agent          Server         MongoDB
  │               │               │
  │ POST /register│               │
  │──────────────▶│               │
  │ (API Key)     │ Save agent    │
  │               │──────────────▶│
  │               │               │
  │ {agent_id,    │               │
  │  jwt_token}   │               │
  │◀──────────────│               │
  │               │               │
  │ GET /whitelist│               │
  │──────────────▶│ Query WL      │
  │ (JWT)         │──────────────▶│
  │               │               │
  │ {domains,IPs} │               │
  │◀──────────────│               │
```

---

### Slide 14: Luồng kiểm tra truy cập
**Nội dung:** Flowchart

```
Packet bắt được → Extract Domain → Trong Whitelist?
                                    ├── Có → ALLOWED (log)
                                    └── Không → BLOCKED (log + firewall chặn)
```

---

### Slide 15: Hệ thống bảo mật
**Nội dung:** Các lớp bảo mật

1. **API Key + HMAC-SHA256** - Đăng ký agent an toàn
2. **JWT Tokens** - Access (24h) + Refresh (7 ngày)
3. **bcrypt** - Hash mật khẩu với salt
4. **Chống brute-force** - Khóa 15 phút sau 5 lần sai
5. **httpOnly Cookie** - JWT không truy cập từ JS
6. **RBAC** - Phân quyền Admin/Teacher chi tiết
7. **Audit Trail** - Ghi log mọi hành động
8. **Token Revocation** - Thu hồi token khi logout

---

### Slide 16: RBAC - Phân quyền
**Nội dung:** So sánh quyền Admin vs Teacher

| Chức năng | Admin | Teacher |
|-----------|-------|---------|
| Quản lý users | V | X |
| Quản lý groups | V (tất cả) | V (chỉ nhóm mình) |
| Quản lý agents | V (tất cả) | V (chỉ nhóm mình) |
| Whitelist | V (tất cả) | V (chỉ nhóm mình) |
| Xem logs | V (tất cả) | V (chỉ nhóm mình) |
| API Keys | V | X |
| Audit logs | V | X |

---

### Slide 17: Kết quả đạt được
**Nội dung:** Tóm tắt thành tựu

- Hoàn thành hệ thống Client-Server đầy đủ
- ~50 API endpoints phục vụ Agent và Web Dashboard
- 12 MongoDB collections
- RBAC 2 roles với hệ thống permission chi tiết
- Agent GUI 5 views với real-time monitoring
- Whitelist-based firewall tự động
- Packet capture và domain extraction (DNS/HTTP/SNI)
- Audit trail và session management
- Build executable SAINT.exe

---

### Slide 18-19: Demo Screenshots
**Nội dung:** Screenshots thực tế

- Web Dashboard: Danh sách agents online/offline
- Agent GUI: Dashboard với status cards
- Firewall rules đang hoạt động
- Logs real-time
- RBAC: Teacher view vs Admin view

**Tips:** Có thể thay bằng video demo nếu được phép.

---

### Slide 20: Kết luận
**Nội dung:**

**Đã đạt được:**
- Hệ thống hoạt động ổn định
- Giải quyết bài toán quản lý mạng trong giáo dục
- Áp dụng các kỹ thuật bảo mật hiện đại

**Hạn chế:**
- Chỉ hỗ trợ Windows
- Chưa có web UI hiện đại (SPA)
- Chưa containerize (Docker)

**Hướng phát triển:**
- Hỗ trợ Linux/macOS
- Xây dựng React/Vue frontend
- Deploy Docker + CI/CD
- Machine learning phát hiện bất thường
- Mobile app cho giáo viên

---

### Slide 21: Q&A
```
CẢM ƠN HỘI ĐỒNG ĐÃ LẮNG NGHE!

Q & A
```

---

## 2. Tips thiết kế slide chuyên nghiệp

### Màu sắc
- **Màu chính**: Xanh dương đậm (#1a365d) - chuyên nghiệp, tin cậy
- **Màu phụ**: Xanh lá (#38a169) cho highlight
- **Nền**: Trắng hoặc xám nhạt
- **Text**: Đen hoặc xám đậm
- **Tránh**: Quá nhiều màu, gradient sặc sỡ

### Font chữ
- **Tiêu đề**: Bold, 28-36pt
- **Nội dung**: Regular, 18-24pt
- **Font đề xuất**: Segoe UI, Arial, Calibri
- **Tránh**: Font chữ viết tay, Comic Sans

### Layout
- **1 ý chính/slide** - không nhồi nhét quá nhiều
- **Bullet points**: Tối đa 6-7 dòng/slide
- **Hình ảnh/sơ đồ**: Chiếm ít nhất 40% diện tích slide
- **Whitespace**: Để trống đủ, đừng kín hết

### Sơ đồ
- Vẽ bằng **PowerPoint shapes** (không paste hình text)
- Hoặc dùng **draw.io** rồi export PNG
- Dùng **Lucidchart** hoặc **Mermaid** cho sequence diagram
- Sử dụng **màu phân biệt** cho các thành phần khác nhau

### Nội dung
- **NÊN**: Bullet points ngắn, keywords, sơ đồ, bảng
- **KHÔNG NÊN**: Đoạn văn dài, copy code, quá nhiều chi tiết kỹ thuật
- **Chi tiết kỹ thuật** → để trong báo cáo, slide chỉ show overview
- **Mỗi slide nói trong 1-2 phút** → 20 slides ≈ 20-30 phút trình bày

---

## 3. Câu hỏi hội đồng thường hỏi

Chuẩn bị trước các câu hỏi:

### Kiến trúc
- Tại sao chọn Client-Server thay vì kiến trúc khác?
- Tại sao dùng MongoDB thay vì SQL?
- Agent giao tiếp với Server như thế nào?

### Bảo mật
- JWT có ưu điểm gì so với session-based auth?
- Nếu token bị đánh cắp thì sao?
- RBAC hoạt động thế nào khi teacher quản lý nhiều nhóm?

### Kỹ thuật
- Scapy bắt gói tin như thế nào? Hiệu năng ra sao?
- Whitelist sync mechanism hoạt động thế nào?
- Agent chạy không có quyền Admin thì sao?

### Triển khai
- Deploy thực tế như thế nào?
- Hệ thống scale được bao nhiêu agent?
- Có test chưa? Test như thế nào?

---

## 4. Thời lượng trình bày đề xuất

| Phần | Slides | Thời gian |
|------|--------|-----------|
| Đặt vấn đề & Mục tiêu | 2-3 | 3 phút |
| Kiến trúc & Công nghệ | 3-4 | 5 phút |
| Thiết kế Server | 2-3 | 4 phút |
| Thiết kế Agent | 2-3 | 4 phút |
| Luồng hoạt động | 2 | 3 phút |
| Bảo mật | 2 | 3 phút |
| Demo/Kết quả | 2-3 | 5 phút |
| Kết luận | 1-2 | 2 phút |
| **Tổng** | **~20** | **~30 phút** |
