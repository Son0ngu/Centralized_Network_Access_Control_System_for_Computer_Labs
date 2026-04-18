# Hướng dẫn quay Video Demo - SAINT ĐATN

## 1. Tổng quan

**Thời lượng đề xuất:** 5-8 phút
**Mục đích:** Minh họa các tính năng chính của hệ thống SAINT cho hội đồng bảo vệ ĐATN

---

## 2. Chuẩn bị trước khi quay

### 2.1 Phần mềm cần thiết

| Phần mềm | Mục đích | Link |
|-----------|----------|------|
| **OBS Studio** | Quay màn hình (miễn phí) | obsproject.com |
| **Shotcut** hoặc **DaVinci Resolve** | Chỉnh sửa video (miễn phí) | shotcut.org / davinciresolve.com |

### 2.2 Cài đặt OBS Studio

1. **Settings → Video:**
   - Base Resolution: 1920x1080 (Full HD)
   - Output Resolution: 1920x1080
   - FPS: 30

2. **Settings → Output:**
   - Recording Format: MP4
   - Encoder: x264
   - Quality: High Quality
   - Bitrate: 6000 Kbps

3. **Settings → Audio:**
   - Sample Rate: 44.1 kHz
   - Microphone: Chọn mic của bạn (nếu muốn thuyết minh)
   - Desktop Audio: Tắt (không cần tiếng hệ thống)

4. **Sources:**
   - Thêm "Display Capture" hoặc "Window Capture"
   - Nếu dùng 2 màn hình: capture từng window riêng

### 2.3 Chuẩn bị môi trường

**Trước khi quay:**
- [ ] Server đang chạy và hoạt động bình thường
- [ ] MongoDB có dữ liệu test (vài agents, groups, whitelists)
- [ ] Tạo sẵn tài khoản: 1 Admin + 1 Teacher
- [ ] Tạo sẵn 1-2 groups với whitelist
- [ ] SAINT.exe đã build và sẵn sàng
- [ ] Tắt notifications Windows (Focus Assist → Priority Only)
- [ ] Đóng các app không cần thiết
- [ ] Zoom browser 100-125% để text dễ đọc
- [ ] Terminal font size 14-16pt

---

## 3. Kịch bản Demo chi tiết

### PHẦN 1: Giới thiệu & Server (1 phút)

**Mở đầu** (15 giây):
> "Xin chào, đây là demo hệ thống SAINT - Security Agent Integrated Network Tool, hệ thống quản lý bảo mật mạng cho môi trường giáo dục."

**Show Server khởi động** (20 giây):
1. Mở terminal, `cd server`
2. Chạy `python app.py`
3. Show log: "Server running on http://0.0.0.0:5000"
4. Highlight: Flask + SocketIO + MongoDB connected

**Show Web Dashboard** (25 giây):
1. Mở browser → `http://localhost:5000`
2. Đăng nhập Admin (username/password)
3. Show dashboard tổng quan
4. Giới thiệu nhanh: "Đây là giao diện quản trị web cho Admin và Teacher"

---

### PHẦN 2: Agent Registration (1 phút)

**Mở SAINT.exe** (15 giây):
1. Double-click SAINT.exe
2. Show GUI mở lên - giới thiệu giao diện
3. "Đây là Agent chạy trên máy tính học sinh"

**Cấu hình Agent** (15 giây):
1. Mở tab Settings
2. Show Server URL đã cấu hình
3. Show API Key

**Khởi động Agent** (15 giây):
1. Quay lại Dashboard
2. Nhấn "Start Agent"
3. Show status chuyển: Stopped → Starting → Running
4. Show activity log: "Registered with server", "Whitelist synced"

**Verify trên Server** (15 giây):
1. Quay lại browser - Web Dashboard
2. Show agent mới xuất hiện trong danh sách
3. Status: Online/Active
4. "Agent đã tự động đăng ký và hiển thị trên dashboard"

---

### PHẦN 3: Whitelist Management (1.5 phút)

**Tạo Group** (20 giây):
1. Trên Web Dashboard → Groups
2. Tạo group mới: "Phòng Lab A1"
3. Show group được tạo

**Gán Agent vào Group** (15 giây):
1. Chọn agent vừa đăng ký
2. Gán vào "Phòng Lab A1"
3. "Agent giờ thuộc về nhóm này"

**Quản lý Whitelist** (25 giây):
1. Mở Whitelist → chọn group "Phòng Lab A1"
2. Thêm domain: `google.com`, `github.com`, `w3schools.com`
3. Show danh sách whitelist đã thêm
4. "Chỉ những domain này được phép truy cập"

**Agent tự Sync** (20 giây):
1. Quay lại Agent GUI
2. Show tab Whitelist → danh sách domain đã sync
3. Show resolved IPs
4. "Agent tự động đồng bộ whitelist từ server mỗi 30 giây"

**Thêm hàng loạt (Bulk)** (10 giây):
1. Show tính năng Import CSV
2. "Cũng hỗ trợ import/export whitelist từ file CSV"

---

### PHẦN 4: Firewall in Action (1.5 phút)

**Chuyển chế độ Whitelist Only** (15 giây):
1. Show Agent đang chế độ Monitor
2. Giải thích: "Chế độ Monitor chỉ giám sát, không chặn"
3. Chuyển sang Whitelist Only (cần quyền Admin)
4. "Bây giờ firewall sẽ chặn tất cả trừ whitelist"

**Test truy cập ĐƯỢC PHÉP** (20 giây):
1. Mở browser → truy cập `google.com`
2. Website load bình thường
3. Show Agent Dashboard → log: "ALLOWED google.com"
4. "Google.com nằm trong whitelist nên được phép"

**Test truy cập BỊ CHẶN** (20 giây):
1. Mở browser → truy cập `facebook.com`
2. Website KHÔNG load được
3. Show Agent Dashboard → log: "BLOCKED facebook.com"
4. "Facebook không trong whitelist nên bị chặn bởi firewall"

**Show Firewall Rules** (15 giây):
1. Mở tab Firewall trên Agent
2. Show danh sách rules SAINT_ALLOW_xxx
3. "Mỗi IP được phép có 1 rule riêng trong Windows Firewall"

**Show Logs trên Server** (20 giây):
1. Quay lại Web Dashboard → Logs
2. Show logs ALLOWED và BLOCKED từ agent
3. Show filter by action, domain, thời gian
4. "Tất cả hoạt động mạng được ghi log và gửi về server"

---

### PHẦN 5: RBAC Demo (1 phút)

**Tạo tài khoản Teacher** (15 giây):
1. Admin → Users → Create User
2. Tạo teacher account: "gv_nguyen"
3. Gán vào group "Phòng Lab A1"

**Đăng nhập Teacher** (15 giây):
1. Logout Admin
2. Đăng nhập bằng tài khoản Teacher
3. Show dashboard

**So sánh quyền hạn** (30 giây):
1. Teacher chỉ thấy group "Phòng Lab A1" (không thấy group khác)
2. Không có menu Users, API Keys, Audit
3. "Teacher chỉ quản lý được nhóm mình phụ trách"
4. Teacher vẫn có thể quản lý whitelist của group mình
5. "Đây là cơ chế RBAC - phân quyền theo vai trò"

---

### PHẦN 6: Whitelist Profile (45 giây)

**Tạo Profile** (20 giây):
1. Teacher → chọn group → Profiles
2. Tạo profile "Bài thực hành Web"
3. Thêm domains: `developer.mozilla.org`, `codepen.io`
4. "Profile cho phép teacher tạo bộ whitelist riêng cho bài học"

**Kích hoạt Profile** (15 giây):
1. Click "Activate" trên profile
2. Show agent sync lại whitelist mới
3. "Khi kích hoạt, whitelist của profile sẽ override whitelist nhóm"

**Tắt Profile** (10 giây):
1. Click "Deactivate"
2. "Hết giờ học, teacher tắt profile, whitelist trở về mặc định"

---

### PHẦN 7: Real-time Monitoring (45 giây)

**Agent Dashboard** (20 giây):
1. Show Agent Dashboard với status cards animated
2. Packets count đang tăng
3. Domains detected
4. Uptime ticking
5. "Dashboard cập nhật real-time mỗi giây"

**Log Streaming** (15 giây):
1. Mở tab Logs trên Agent
2. Show logs chạy real-time khi browse web
3. Show filter by level: ERROR, WARNING, INFO

**Server Realtime** (10 giây):
1. Show Web Dashboard cập nhật agent status
2. "Server nhận heartbeat từ agent mỗi 20 giây"

---

### PHẦN 8: Kết thúc (15 giây)

> "Đây là toàn bộ demo hệ thống SAINT. Hệ thống cho phép quản lý truy cập mạng tập trung, phân quyền cho giáo viên, và giám sát real-time. Cảm ơn đã theo dõi."

---

## 4. Tips quay video chuyên nghiệp

### Trước khi quay
1. **Chạy thử 1 lần** trước khi quay chính thức
2. **Chuẩn bị dữ liệu test** sẵn (không để hội đồng chờ tạo data)
3. **Tắt antivirus** nếu nó chặn Scapy/WinPcap
4. **Restart server** để log sạch
5. **Clear browser cache** để demo sạch

### Khi quay
1. **Di chuột chậm** để người xem theo kịp
2. **Pause 2-3 giây** sau mỗi thao tác quan trọng
3. **Zoom vào** text nhỏ (Ctrl + Scroll)
4. **Nói rõ ràng** nếu thuyết minh bằng giọng
5. **Không lúng túng** - nếu sai, dừng và quay lại đoạn đó

### Sau khi quay
1. **Cắt** các đoạn thừa, im lặng dài
2. **Thêm text overlay** cho mỗi phần (Phần 1, Phần 2...)
3. **Tốc độ**: Có thể tăng 1.5x cho đoạn chờ loading
4. **Thêm nhạc nền** nhẹ nhàng (không bắt buộc)

---

## 5. Hậu kỳ cơ bản (Shotcut)

### Cắt ghép
1. Import video vào Shotcut
2. Kéo vào Timeline
3. Dùng "Split" (S) để cắt tại vị trí cần
4. Xóa đoạn thừa

### Thêm tiêu đề
1. Open Other → Text → nhập tiêu đề
2. Kéo vào timeline phía trên video
3. Chỉnh duration 3-5 giây

### Export
1. File → Export Video
2. Preset: YouTube (H.264, 1080p)
3. Quality: 70-80%
4. Export

---

## 6. Checklist cuối cùng

- [ ] Video dài 5-8 phút
- [ ] Mỗi phần chức năng đều được demo
- [ ] Không có lỗi/crash trong video
- [ ] Text đủ lớn để đọc được
- [ ] Có thuyết minh hoặc text overlay giải thích
- [ ] Video export Full HD (1920x1080)
- [ ] File size hợp lý (< 500MB)
- [ ] Đã test play trên máy khác

---

## 7. Phương án dự phòng

Nếu demo live bị lỗi:
1. **Chuẩn bị video backup** - quay sẵn, phát nếu demo live fail
2. **Screenshots** - nếu cả video lẫn live đều fail, show screenshots
3. **Postman** - show API hoạt động trực tiếp qua Postman
4. **Logs** - show terminal logs để chứng minh hệ thống hoạt động
