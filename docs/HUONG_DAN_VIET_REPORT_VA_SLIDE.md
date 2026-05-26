# HƯỚNG DẪN CHI TIẾT: Viết Report + Làm Slide ĐATN theo Template HUST

> **Template sử dụng:**
> - Report: `SOICT_DATN_Application_ENG_Template.pdf` (LaTeX, chuẩn báo cáo kỹ thuật ISO 7144:1986, 31 trang)
> - Slide: `HUST_PPT_template_2022_RED_4x3.pptx` (13 slides, theme đỏ BKHN, tỉ lệ 4:3)

> **Quan trọng:** Template ghi rõ "Sinh viên viết trực tiếp vào file này, chỉ chỉnh sửa nội dung, và **không viết trên file mới**." Khi paste văn bản từ tài liệu khác, dùng "Copy as Text Only" để giữ format template.

---

# PHẦN 0: QUY ĐỊNH BẮT BUỘC CỦA TEMPLATE

Đây là các quy định bắt buộc lấy từ **Phụ lục A** của template. Vi phạm các quy định này có thể bị trừ điểm hoặc **không được phép bảo vệ**.

## 0.1 Cách hành văn khoa học

**Bắt buộc:**
- Viết thành **đoạn văn liền mạch**, không gạch đầu dòng (bullets), không viết ý lẻ.
- Mỗi đoạn có **một ý chính** và các câu phân tích bổ trợ. Câu sau liên kết câu trước, đoạn sau liên kết đoạn trước.
- Mọi câu phải đầy đủ chủ ngữ, vị ngữ.
- Khi cần liệt kê, dùng **chữ số La Mã**: (i), (ii), (iii), (iv)... Ví dụ: "Đồ án có 3 đóng góp: (i) ..., (ii) ..., và (iii) ...".

**Cấm dùng:**
- Từ trong văn nói, từ phóng đại, thái quá, mang tính cảm xúc cá nhân: "tuyệt vời", "cực hay", "cực kỳ hữu ích", "rất ấn tượng"...
- Câu dài dòng. Mỗi câu cần được tối ưu, "rất khó thêm hoặc bớt đi dù chỉ một từ" (trích template).

**Trường hợp bất khả kháng phải dùng bullet:** thống nhất style cho toàn báo cáo (ví dụ tròn đen cấp 1 thì mọi nơi đều vậy).

## 0.2 Tổng quan + Kết chương (BẮT BUỘC cho CH2–CH6)

Mỗi chương từ Chương 2 trở đi **phải có hai đoạn**:

**Đoạn Tổng quan (đầu chương):**
- Liên kết với chương trước (ví dụ: "Chương 3 đã thảo luận về cơ sở lý thuyết...").
- Nêu lý do có mặt chương này và sự cần thiết của nó.
- Giới thiệu các vấn đề/đề mục lớn sẽ trình bày.

**Đoạn Kết chương (cuối chương):**
- Tóm tắt các kết luận quan trọng của chương.
- Trả lời các vấn đề đã mở ra ở Tổng quan.
- Có câu liên kết tới chương tiếp theo (ví dụ: "...được trình bày trong chương tiếp theo – Chương 5").
- **Không viết Kết chương giống hệt Tổng quan.**

Hai đoạn này dùng định dạng văn bản **Normal**, không in đậm/nghiêng, không đóng khung.

**Lưu ý:** Chương 1 không cần phần mô tả chương trong mục `1.4 Thesis organization` (đã có sẵn ở 1.4).

## 0.3 Tham chiếu chéo bắt buộc

Mọi **hình vẽ, bảng biểu, công thức, tài liệu tham khảo** trong ĐATN **bắt buộc phải được tham chiếu ít nhất một lần** trong phần nội dung.

Ví dụ tham chiếu đúng:
- "Bảng 4.1 liệt kê các công cụ phần mềm được sử dụng..."
- "Hình 4.2 minh hoạ thiết kế gói của module Whitelist..."
- "Theo lý thuyết RBAC [4], phân quyền được tổ chức..."
- "Phương trình (5.1) thể hiện công thức tính checksum của whitelist..."

**Không chấp nhận** hình/bảng "tự xuất hiện" mà không có lời mô tả/giải thích nào trong văn bản.

## 0.4 Cấm đạo văn

- **Tuyệt đối cấm đạo văn.** Bị phát hiện → **không được bảo vệ ĐATN**.
- Ghi rõ nguồn cho **mọi thứ không tự viết/vẽ**: trích dẫn, hình ảnh, bảng biểu, sơ đồ, code snippet...
- Trích dẫn theo IEEE: `[1]`, `[2]`... Chi tiết tại mục `REFERENCE` cuối tài liệu này.

## 0.5 Quy định đóng quyển

- Bìa trước và bìa sau là giấy liền khổ, chế bản theo template.
- Dùng **keo nhiệt** dán gáy, **không dùng băng dính/dập ghim**.
- **Phần gáy** ghi: `Kỳ làm ĐATN - Ngành đào tạo - Họ và tên SV - MSSV`. Ví dụ:
  ```
  2026.1 - KHOA HỌC MÁY TÍNH - NGUYỄN VĂN A - 20210xxx
  ```
- Tên ngành đúng theo khoá học (xem template Phụ lục A.2):
  - K61 trở về trước: **Kỹ thuật phần mềm**
  - K62 trở về sau: **Khoa học máy tính**
  - Cử nhân CNTT: **Công nghệ thông tin**
  - ICT Global: **Information Technology**
  - DS&AI: **Khoa học dữ liệu**

## 0.6 Độ dài từng chương (theo template)

| Chương | Độ dài |
|---|---|
| CH1: Introduction | 3–6 trang |
| CH2: Requirement Survey and Analysis | 9–11 trang |
| CH3: Theoretical Background and Technologies | ≤ 10 trang (vượt thì đưa vào phụ lục) |
| CH4: Design, Implementation, and Evaluation | Không quy định tổng, nhưng: 4.1.1: 1–3 tr, 4.2.1: 2–3 tr, 4.2.2: 3–4 tr, 4.2.3: 2–4 tr, 4.4: 2–3 tr |
| CH5: Solution and Contribution | ≥ 5 trang. **Nếu < 5 trang thì gộp vào CH6**, không tách thành chương riêng |
| CH6: Conclusion and Future Work | Tự cân đối |

---

# PHẦN A: VIẾT BÁO CÁO ĐỒ ÁN TỐT NGHIỆP

Template report yêu cầu cấu trúc 6 chương. Dưới đây là hướng dẫn **nội dung cụ thể** bạn cần viết cho từng phần, áp dụng vào project SAINT.

---

## Trang bìa + Trang phụ

Sửa trực tiếp trên file template:

```
HANOI UNIVERSITY OF SCIENCE AND TECHNOLOGY
GRADUATION THESIS

Thesis title: BUILDING A DISTRIBUTED NETWORK SECURITY
MANAGEMENT SYSTEM FOR EDUCATIONAL ENVIRONMENTS

[Họ tên SV]
[Email @sis.hust.edu.vn]
Program: [Tên chương trình]
Supervisor: [Tên GVHD]
Department: Computer Engineering
School: School of Information and Communications Technology
HANOI, [tháng/năm]
```

---

## ACKNOWLEDGMENTS (100-150 từ)

Viết lời cảm ơn đến GVHD, gia đình, bạn bè. Ví dụ gợi ý:

```
Tôi xin gửi lời cảm ơn chân thành đến [Tên GVHD] đã tận tình
hướng dẫn trong suốt quá trình thực hiện đồ án. Xin cảm ơn gia đình
đã luôn động viên, hỗ trợ. Cảm ơn các bạn trong lớp đã cùng trao đổi
và góp ý. Đồ án này là kết quả của quá trình nghiên cứu và phát triển
không ngừng, giúp tôi nâng cao kiến thức về bảo mật mạng, kiến trúc
phần mềm phân tán, và phát triển ứng dụng thực tế.
```

---

## ABSTRACT (200-350 từ, viết thành đoạn văn)

**Trình tự bắt buộc:** (i) Vấn đề → (ii) Hướng tiếp cận → (iii) Giải pháp → (iv) Đóng góp & kết quả

Bạn viết **thành đoạn văn liền mạch**, KHÔNG gạch đầu dòng:

```
Gợi ý nội dung:

(i) Vấn đề: Trong môi trường giáo dục, việc quản lý truy cập mạng
của học sinh/sinh viên là một thách thức lớn. Các giải pháp hiện tại
như proxy server hoặc cấu hình firewall thủ công đòi hỏi chuyên môn
IT cao và khó triển khai trên quy mô lớn. Giáo viên không có khả
năng kiểm soát truy cập mạng theo lớp/nhóm trong giờ giảng dạy.

(ii) Hướng tiếp cận: Đồ án lựa chọn kiến trúc Client-Server phân
tán với cơ chế whitelist-based firewall, cho phép quản lý tập trung
thông qua REST API và phân quyền RBAC.

(iii) Giải pháp: Đồ án xây dựng hệ thống SAINT gồm Server (Flask +
MongoDB) cung cấp API và Web Dashboard, và Agent (Python +
PySide6/Qt) cài trên máy tính Windows để giám sát mạng, đồng bộ
whitelist, và tự động áp dụng firewall rules.

(iv) Đóng góp & kết quả: Hệ thống hoạt động ổn định với ~50 API
endpoints, 12 MongoDB collections, packet capture (Scapy), DNS
resolution parallel, RBAC 2 roles, audit trail, và JWT authentication
đa lớp. Agent được đóng gói thành SAINT.exe có thể triển khai
không cần cài đặt Python.
```

---

## TABLE OF CONTENTS

Template tự sinh mục lục. Bạn chỉ cần cập nhật mục lục sau khi viết xong toàn bộ.

---

## LIST OF ABBREVIATIONS

| Viết tắt | Giải thích |
|----------|-----------|
| SAINT | Security Agent Integrated Network Tool |
| API | Application Programming Interface |
| REST | Representational State Transfer |
| JWT | JSON Web Token |
| RBAC | Role-Based Access Control |
| CRUD | Create, Read, Update, Delete |
| MVC | Model-View-Controller |
| MVP | Model-View-Presenter |
| DNS | Domain Name System |
| SNI | Server Name Indication |
| TLS | Transport Layer Security |
| HMAC | Hash-based Message Authentication Code |
| GUI | Graphical User Interface |
| LRU | Least Recently Used |
| CLI | Command Line Interface |

---

## CHAPTER 1: INTRODUCTION (3-6 trang)

### 1.1 Motivation (Đặt vấn đề)

**Chỉ nêu vấn đề, TUYỆT ĐỐI KHÔNG nêu giải pháp.**

Nội dung cần viết (thành đoạn văn):

```
Đoạn 1: Thực trạng
- Trong trường học, học sinh thường truy cập các trang web không
  phù hợp (mạng xã hội, game, nội dung tiêu cực) trong giờ học
- Ảnh hưởng đến chất lượng giảng dạy và học tập
- Số liệu minh chứng nếu có (khảo sát, thống kê)

Đoạn 2: Các giải pháp hiện có và hạn chế
- Proxy server (Squid, pfSense): phức tạp, cần chuyên môn IT cao
- Firewall thủ công: tốn thời gian, không linh hoạt
- Phần mềm quản lý (NetSupport, LanSchool): tốn phí, phụ thuộc
  vendor, không tùy biến được
- Các giải pháp này KHÔNG cho phép giáo viên tự quản lý theo lớp

Đoạn 3: Tầm quan trọng
- Nhu cầu quản lý mạng trong giáo dục ngày càng tăng
- Cần giải pháp đơn giản, giáo viên có thể tự sử dụng
- Cần hệ thống giám sát real-time, có audit trail
```

### 1.2 Objectives and scope (Mục tiêu và phạm vi)

**Tổng quan các sản phẩm/nghiên cứu hiện tại → So sánh → Xác định hạn chế → Đề ra mục tiêu**

```
Đoạn 1: Tổng quan sản phẩm tương tự
- NetSupport School: quản lý lớp học, có giám sát screen nhưng
  tốn phí, không open-source, không tùy biến
- OpenDNS/Cisco Umbrella: filter DNS nhưng cần cấu hình router,
  không phân quyền theo giáo viên
- Pi-hole: DNS sinkhole, chỉ chặn DNS, không giám sát traffic

Đoạn 2: So sánh và đánh giá
- Lập bảng so sánh (tính năng, giá, open-source, RBAC, real-time)

Đoạn 3: Mục tiêu cụ thể
- Xây dựng hệ thống Client-Server quản lý truy cập mạng
- Agent tự động trên Windows với whitelist-based firewall
- Server REST API + Web Dashboard
- RBAC Admin/Teacher
- Giám sát real-time, audit trail

Đoạn 4: Phạm vi
- Hỗ trợ Windows 10/11
- Mạng LAN/Internet
- Whitelist-based (chặn mặc định, chỉ cho phép danh sách trắng)
```

### 1.3 Tentative solution (Định hướng giải pháp)

**Ngắn gọn: (i) Hướng → (ii) Giải pháp → (iii) Đóng góp**

```
(i) Hướng: Kiến trúc Client-Server phân tán, sử dụng Flask
(Python) cho Server, PySide6/Qt cho Agent GUI, MongoDB cho
database, JWT + API Key cho authentication.

(ii) Giải pháp: SAINT gồm 2 thành phần chính:
- Server: Flask REST API + WebSocket + MongoDB + RBAC
- Agent: GUI application capture packets bằng Scapy, quản lý
  Windows Firewall bằng netsh, đồng bộ whitelist từ Server

(iii) Đóng góp:
- Hệ thống whitelist-based firewall tự động
- RBAC cho phép giáo viên tự quản lý lớp
- Packet capture + domain extraction (DNS/HTTP/SNI)
- Whitelist Profile cho phép teacher tạo bộ whitelist riêng
```

### 1.4 Thesis organization (Bố cục đồ án)

Viết MÔ TẢ cho từng chương (thành đoạn văn, KHÔNG gạch đầu dòng):

```
Chương 2 trình bày về khảo sát hiện trạng và phân tích yêu cầu
hệ thống SAINT, bao gồm phân tích các hệ thống tương tự, biểu
đồ use case tổng quan và chi tiết, đặc tả các use case quan trọng,
và các yêu cầu phi chức năng.

Chương 3 giới thiệu các nền tảng lý thuyết và công nghệ sử dụng
trong đồ án, bao gồm kiến trúc Client-Server, Flask framework,
MongoDB, JWT authentication, packet capture với Scapy, và cơ chế
RBAC.

Chương 4 trình bày chi tiết thiết kế, cài đặt và đánh giá hệ
thống SAINT, từ lựa chọn kiến trúc phần mềm MVC/MVP, thiết kế
database 12 collections, thiết kế giao diện, đến kết quả cài đặt
và kiểm thử.

Chương 5 trình bày đóng góp chính của đồ án, bao gồm giải pháp
whitelist-based firewall tự động, cơ chế đồng bộ whitelist với
DNS resolution parallel, hệ thống RBAC Teacher data filtering,
và Whitelist Profile cho quản lý bài học.

Chương 6 tổng kết kết quả đạt được, phân tích hạn chế, và đề
xuất hướng phát triển trong tương lai.
```

---

## CHAPTER 2: REQUIREMENT SURVEY AND ANALYSIS (9-11 trang)

> **Bắt buộc**: Đầu chương có đoạn **Tổng quan** liên kết với Chương 1 và giới thiệu nội dung sẽ trình bày. Cuối chương có đoạn **Kết chương** tóm tắt và liên kết tới Chương 3. Xem mục 0.2.

> **Phương pháp**: Template mặc định dùng **biểu đồ use case** (OOAD). Nếu chọn phương pháp khác (ví dụ Agile + User Story), trao đổi với GVHD để đổi tên đề mục.

### 2.1 Status survey (Khảo sát hiện trạng)

**Phân tích, so sánh các sản phẩm tương tự:**

```
Lập bảng so sánh:

| Tiêu chí         | NetSupport | OpenDNS | Pi-hole | SAINT |
|-------------------|-----------|---------|---------|-------|
| Open-source       | Không     | Không   | Có      | Có    |
| Whitelist firewall| Không     | Có      | Một phần| Có    |
| RBAC Teacher      | Không     | Không   | Không   | Có    |
| Real-time monitor | Có        | Không   | Không   | Có    |
| Packet capture    | Có        | Không   | Không   | Có    |
| Web Dashboard     | Có        | Có      | Có      | Có    |
| Agent GUI         | Có        | Không   | Không   | Có    |
| Audit trail       | Không     | Có      | Không   | Có    |
| Free              | Không     | Không   | Có      | Có    |

Phân tích ưu/nhược điểm từng sản phẩm, kết luận cần phát triển
SAINT với các tính năng: whitelist firewall, RBAC, packet capture,
audit trail, open-source.
```

### 2.2 Functional Overview

#### 2.2.1 General use case diagram

Vẽ biểu đồ use case tổng quan với **3 tác nhân**:

```
Tác nhân:
1. Agent (máy tính) - tự động đăng ký, heartbeat, sync, capture
2. Admin - toàn quyền quản lý hệ thống
3. Teacher - quản lý nhóm được gán

Use cases tổng quan:
- Quản lý Agent (Agent Management)
- Quản lý Whitelist (Whitelist Management)
- Quản lý nhóm (Group Management)
- Quản lý người dùng (User Management)
- Xác thực & Phân quyền (Authentication & Authorization)
- Giám sát & Log (Monitoring & Logging)
- Quản lý API Key (API Key Management)
```

#### 2.2.2 Detailed use case diagram

Phân rã từng use case tổng quan. Ví dụ:

```
Use case "Quản lý Whitelist" phân rã:
- Thêm domain/IP vào whitelist
- Xóa domain/IP khỏi whitelist
- Import whitelist từ CSV
- Export whitelist ra CSV
- Bulk add/update/delete
- Sync whitelist cho Agent
- Quản lý Whitelist Profile
- Kích hoạt/tắt Profile
```

#### 2.2.3 Business process

Vẽ biểu đồ hoạt động cho quy trình chính:

```
Quy trình 1: Quản lý truy cập mạng trong giờ học
Teacher đăng nhập → Chọn nhóm/lớp → Tạo hoặc chọn Whitelist
Profile → Kích hoạt Profile → Agent tự sync → Firewall áp dụng
→ Học sinh chỉ truy cập được whitelist → Hết giờ → Teacher tắt
Profile → Whitelist về mặc định

Quy trình 2: Đăng ký và quản lý Agent
Admin tạo API Key → Cài SAINT.exe trên PC → Agent đăng ký với
Server → Admin gán Agent vào Group → Agent sync whitelist →
Agent bắt đầu capture + heartbeat
```

### 2.3 Functional description

**Chọn 4-7 use case quan trọng nhất để đặc tả chi tiết.**

Đề xuất 5 use cases:

```
UC1: Đăng ký Agent (Agent Registration)
- Tiền điều kiện: API Key hợp lệ, Agent chưa đăng ký
- Luồng chính: Agent gửi POST /register với API Key và device_id
  → Server tạo record → Trả về agent_id + JWT token
- Luồng phát sinh: API Key hết hạn, device_id đã tồn tại
- Hậu điều kiện: Agent có agent_id và JWT token

UC2: Đồng bộ Whitelist (Whitelist Sync)
- Tiền điều kiện: Agent đã đăng ký, JWT hợp lệ
- Luồng chính: Agent gửi GET /whitelist/agent-sync → Server
  trả danh sách domain/IP + profile active → Agent cập nhật
  WhitelistState → DNS resolve → Firewall update rules
- Luồng phát sinh: Server offline → dùng cache, Token hết hạn
  → auto-refresh
- Hậu điều kiện: Whitelist và Firewall rules đã cập nhật

UC3: Quản lý Whitelist Profile (Whitelist Profile Management)
- Tiền điều kiện: Teacher đăng nhập, có group được gán
- Luồng chính: Teacher tạo Profile với tên + danh sách domain
  → Kích hoạt Profile → Server cập nhật version → Agent sync
- Luồng phát sinh: Profile trùng tên, domain không hợp lệ
- Hậu điều kiện: Profile active, Agent đã sync whitelist mới

UC4: Xác thực và phân quyền RBAC (Authentication & RBAC)
- Tiền điều kiện: Tài khoản đã được tạo bởi Admin
- Luồng chính: User nhập username/password → Server verify
  bcrypt → Tạo JWT cookie → Middleware kiểm tra role → Filter
  data theo ownership
- Luồng phát sinh: Sai mật khẩu 5 lần → khóa 15 phút
- Hậu điều kiện: User đăng nhập, chỉ thấy data mình quản lý

UC5: Giám sát hoạt động mạng (Network Monitoring)
- Tiền điều kiện: Agent đang chạy, PacketSniffer hoạt động
- Luồng chính: Scapy bắt packet → DomainExtractor trích xuất
  domain → WhitelistManager check → Log ALLOWED/BLOCKED →
  LogSender gửi batch về Server → Server lưu MongoDB
- Luồng phát sinh: WinPcap chưa cài, lỗi mạng
- Hậu điều kiện: Logs lưu trên Server, hiển thị Dashboard
```

### 2.4 Non-functional requirement

```
1. Hiệu năng:
   - Agent heartbeat mỗi 20 giây, không ảnh hưởng hiệu năng PC
   - DNS resolve parallel (5-10 workers) hoàn thành < 5 giây
   - LogSender batch 100 logs/request, không tắc nghẽn

2. Bảo mật:
   - JWT tokens với JTI tracking, auto-revoke
   - API Key hash HMAC-SHA256
   - bcrypt password hashing
   - Chống brute-force (khóa 15 phút sau 5 lần sai)
   - httpOnly Cookie

3. Độ tin cậy:
   - Agent hoạt động offline (cache whitelist)
   - Fallback server URLs
   - Retry logic với exponential backoff

4. Tính dễ dùng:
   - Agent GUI trực quan (PySide6/Qt)
   - Web Dashboard responsive
   - Teacher không cần kiến thức IT

5. Kỹ thuật:
   - Database: MongoDB Atlas (NoSQL)
   - Agent: Windows 10/11
   - Server: Python 3.8+, Flask
```

---

## CHAPTER 3: THEORETICAL BACKGROUND AND TECHNOLOGIES (≤ 10 trang)

> **Bắt buộc**: Có Tổng quan + Kết chương. Tổng quan liên kết với CH2 ("Sau khi đã phân tích yêu cầu ở Chương 2, Chương 3 trình bày các nền tảng công nghệ được dùng để hiện thực hoá các yêu cầu đó..."). Kết chương liên kết với CH4.

> **Quy định template**:
> - **Mỗi công nghệ/lý thuyết phải có 3 phần**: (i) giải quyết vấn đề/yêu cầu cụ thể nào ở CH2, (ii) các alternative có thể thay thế, (iii) lý do chọn phương án này.
> - **Trích nguồn**: kiến thức thu thập từ đâu phải có citation [n] đến mục REFERENCE.
> - **Không trình bày dài dòng chi tiết**. Đây là kiến thức có sẵn, chỉ tóm tắt và phân tích.
> - Nếu cần > 10 trang, đưa phần dư vào **Phụ lục**.
> - Công nghệ trong CH3 phải khớp với phần **Tentative solution (1.3)** ở CH1.

**Mỗi công nghệ phải nêu: dùng để giải quyết vấn đề gì ở Chương 2, tại sao chọn nó thay vì alternative.**

```
3.1 Kiến trúc Client-Server phân tán
- Giải quyết: yêu cầu quản lý tập trung + client tự động
- Tại sao không dùng P2P: cần central management
- Mô tả ngắn: Server trung tâm, nhiều Agent client

3.2 Flask Web Framework
- Giải quyết: cần REST API + web dashboard
- So sánh: Django (quá nặng), FastAPI (thiếu template engine)
- Mô tả: lightweight, extensible, large ecosystem

3.3 Flask-SocketIO (WebSocket)
- Giải quyết: cần real-time notifications cho dashboard
- So sánh: polling (tốn bandwidth), SSE (one-way)
- Mô tả: full-duplex, event-driven

3.4 MongoDB (NoSQL)
- Giải quyết: cần flexible schema cho logs, agents, whitelist
- So sánh: PostgreSQL (rigid schema), Redis (memory-only)
- Mô tả: document-based, Atlas cloud

3.5 JWT Authentication
- Giải quyết: xác thực agent + admin stateless
- So sánh: Session-based (không scale), OAuth2 (quá phức tạp)
- Mô tả: stateless, JTI revocation

3.6 RBAC (Role-Based Access Control)
- Giải quyết: phân quyền Admin/Teacher
- So sánh: ABAC (quá phức tạp cho 2 roles), ACL (khó quản lý)
- Mô tả: resource:action permissions

3.7 Scapy (Packet Capture)
- Giải quyết: giám sát traffic mạng real-time
- So sánh: Wireshark (GUI only), tcpdump (Linux only)
- Mô tả: Python-based, cross-protocol

3.8 PySide6 (Qt for Python)
- Giải quyết: GUI Agent trên Windows
- So sánh: PyQt (license thương mại/GPL), Electron (bundle lớn)
- Mô tả: Qt bindings chính thức cho Python, native widgets, signal/slot thread-safe

3.9 dnspython + aiodns
- Giải quyết: phân giải domain → IP cho whitelist
- Mô tả: parallel resolution, async support

3.10 Windows Firewall (netsh)
- Giải quyết: chặn/cho phép traffic theo IP
- Mô tả: built-in Windows, command-line interface
```

---

## CHAPTER 4: DESIGN, IMPLEMENTATION, AND EVALUATION

> **Bắt buộc**: Có Tổng quan + Kết chương. Tổng quan liên kết với CH3, Kết chương liên kết với CH5.

> **Lưu ý template**: Tránh trình bày trùng lặp với **CH5 (Solution and Contribution)**. Những nội dung mang tính đóng góp/giải pháp chỉ **tóm lược** ở CH4, sau đó dùng tham chiếu chéo: *"Chi tiết về kiến trúc/giải pháp này được trình bày trong phần 5.x"*. Chi tiết đầy đủ đặt ở CH5.

### 4.1 Architecture design

#### 4.1.1 Software architecture selection (1-3 trang)

```
Server: MVC Pattern
- Model: MongoDB CRUD operations (PyMongo)
- View: Jinja2 templates + Static files
- Controller: Flask route handlers
- Thêm: Service layer (business logic), Middleware layer (auth)
→ Giải thích: MVC chuẩn + Service layer để tách business logic
  khỏi controller, giúp code testable và maintainable

Agent: MVP + Observer (Signals)
- Model: Agent core components (Firewall, Whitelist, Sniffer)
- View: PySide6 GUI views (`agent/gui_qt`)
- Presenter: AgentController (singleton, background thread)
- Observer: AgentSignals (event queue, callbacks)
→ Giải thích: MVP tách biệt GUI thread và worker thread,
  Signals đảm bảo thread-safe communication
```

#### 4.1.2 Overall design (Biểu đồ gói UML)

Vẽ **Package Diagram** cho cả Server và Agent:

```
SERVER PACKAGES (phân tầng rõ ràng):

┌─────────────────────────────────┐
│         Middleware Layer         │  ← auth.py, rbac.py
├─────────────────────────────────┤
│         Controller Layer         │  ← *_controller.py
├─────────────────────────────────┤
│          Service Layer           │  ← *_service.py
├─────────────────────────────────┤
│           Model Layer            │  ← *_model.py
├─────────────────────────────────┤
│         Database Layer           │  ← config.py (MongoDB)
└─────────────────────────────────┘

Dependencies: Middleware → Controller → Service → Model → Database
(Tầng trên phụ thuộc tầng dưới, KHÔNG ngược lại)


AGENT PACKAGES:

┌─────────────────────────────────┐
│           GUI Layer              │  ← views/, controllers/
├─────────────────────────────────┤
│          Core Layer              │  ← core/ (agent, lifecycle)
├──────────┬──────────┬───────────┤
│ Firewall │Whitelist │ Capture   │  ← Functional packages
├──────────┴──────────┴───────────┤
│         Services Layer           │  ← heartbeat, log sender
├─────────────────────────────────┤
│      Infrastructure Layer        │  ← config, network, cache
└─────────────────────────────────┘
```

#### 4.1.3 Detailed package design

Vẽ biểu đồ lớp cho từng package quan trọng:

```
Package Firewall:
  FirewallManager ──uses──▶ PolicyManager
  FirewallManager ──uses──▶ RulesManager
  FirewallManager ──uses──▶ FirewallUtils

Package Whitelist:
  WhitelistManager ──uses──▶ WhitelistSyncer
  WhitelistManager ──uses──▶ WhitelistState
  WhitelistManager ──uses──▶ OptimizedDNSResolver
  WhitelistManager ──uses──▶ LRUCache

Package Core:
  Agent (singleton)
  AgentController ──creates──▶ AgentSignals
  AgentController ──manages──▶ Agent
```

### 4.2 Detailed design

#### 4.2.1 User interface design (2-3 trang)

```
Mô tả:
- Độ phân giải: 1280x720 (tối thiểu)
- Theme: Dark Fusion style + QSS (`agent/gui_qt/styles.py`)
- Navigation: Sidebar với icons

Screenshots thiết kế (mockup hoặc thật) cho:
1. Dashboard View - 8 status cards + activity log
2. Firewall View - policy + rules table
3. Whitelist View - domain list
4. Logs View - console + filter
5. Settings View - config form
6. Web Dashboard - agent list, whitelist management
```

#### 4.2.2 Layer design (3-4 trang)

Chọn 2-3 lớp quan trọng, vẽ thuộc tính + phương thức:

```
Lớp 1: WhitelistManager
- Thuộc tính: state, syncer, dns_resolver, cache, lock
- Phương thức: sync_now(), is_allowed(), is_ip_allowed(), get_stats()

Lớp 2: AgentController (singleton)
- Thuộc tính: agent, signals, worker_thread, stats
- Phương thức: start_agent(), stop_agent(), _agent_worker()

Lớp 3: FirewallManager
- Thuộc tính: policy_manager, rules_manager, mode
- Phương thức: setup(), cleanup(), update_rules()

Vẽ Sequence Diagram cho 2-3 use case:
- UC1: Agent Registration sequence
- UC2: Whitelist Sync sequence
- UC5: Packet Detection sequence
```

#### 4.2.3 Database design (2-4 trang)

```
Vẽ E-R Diagram cho 12 collections:

Quan hệ chính:
- Agent → Group (N:1) qua group_id
- Group → User/Teacher (N:M) qua teacher_ids
- Whitelist → Group (N:1) qua group_id
- Log → Agent (N:1) qua agent_id
- AgentPolicy → Agent (1:1) qua agent_id
- WhitelistProfile → Group + Teacher (N:1) qua group_id, teacher_id
- AuditLog → User (N:1) qua user_id
- Session → User (N:1) qua user_id

Mô tả chi tiết 5-6 collections quan trọng nhất
(agents, whitelists, groups, logs, users)
→ Tham khảo file docs/SERVER_DOCUMENTATION.md mục 3
```

### 4.3 Application Building

#### 4.3.1 Libraries and Tools

Lập bảng:

```
| Mục đích          | Công cụ/Thư viện    | Phiên bản | URL |
|--------------------|---------------------|-----------|-----|
| IDE                | VS Code             | latest    | ... |
| Server Framework   | Flask               | 3.x       | ... |
| WebSocket          | Flask-SocketIO      | 5.x       | ... |
| Database           | MongoDB Atlas       | 7.x       | ... |
| MongoDB Driver     | PyMongo             | 4.x       | ... |
| JWT                | PyJWT               | 2.x       | ... |
| Password Hash      | bcrypt              | 4.x       | ... |
| GUI Framework      | PySide6             | >=6.6     | ... |
| Packet Capture     | Scapy               | 2.5+      | ... |
| DNS Resolution     | dnspython           | 2.x       | ... |
| System Monitor     | psutil              | 5.9+      | ... |
| Build Tool         | PyInstaller         | 6.x       | ... |
| Testing            | pytest              | 7.x       | ... |
| Version Control    | Git                 | 2.x       | ... |
```

#### 4.3.2 Achievement

```
Thống kê:
- Server: ~XX files Python, ~XXXX dòng code
- Agent: ~XX files Python, ~XXXX dòng code
- ~50 REST API endpoints
- 12 MongoDB collections
- 7 test files (pytest)
- Sản phẩm đóng gói: SAINT.exe (~50MB)
- Dung lượng mã nguồn: ~XXX KB

(Chạy lệnh để đếm: find . -name "*.py" | xargs wc -l)
```

#### 4.3.3 Illustration of main functions

```
Chụp screenshots thật + giải thích:

1. Agent Dashboard - hiển thị status cards, activity log
2. Agent Firewall - rules đang hoạt động
3. Agent Whitelist - domains đã sync + resolved IPs
4. Web Dashboard - danh sách agents online/offline
5. Web Whitelist Management - CRUD whitelist entries
6. Web RBAC - Teacher view vs Admin view
7. Web Logs - filtered logs từ agents
```

### 4.4 Testing (2-3 trang)

```
Sử dụng pytest, 7 test files:

Kỹ thuật kiểm thử:
- Unit testing cho services
- Integration testing cho API endpoints
- Data filtering testing cho RBAC

Thiết kế test cases cho 2-3 chức năng:

TC1: Agent Registration
| # | Input | Expected | Actual | Pass? |
|---|-------|----------|--------|-------|
| 1 | Valid API key + device_id | 200 + agent_id | ... | ... |
| 2 | Invalid API key | 401 Unauthorized | ... | ... |
| 3 | Duplicate device_id | 200 (update) | ... | ... |

TC2: RBAC Teacher Filtering
| # | Input | Expected | Actual | Pass? |
|---|-------|----------|--------|-------|
| 1 | Teacher xem group mình | 200 + data | ... | ... |
| 2 | Teacher xem group khác | 403 Forbidden | ... | ... |
| 3 | Admin xem tất cả | 200 + all data | ... | ... |

Tổng kết: XX test cases, XX passed, XX failed
```

### 4.5 Deployment

```
Mô hình triển khai:
- Server: Ubuntu/Windows Server, Python 3.8+, port 5000
- Database: MongoDB Atlas (cloud)
- Agent: Windows 10/11, SAINT.exe (standalone)

Cách triển khai:
1. Server: pip install → cấu hình .env → python app.py
2. Agent: Copy SAINT.exe → chạy → cấu hình Server URL + API Key

Kết quả thử nghiệm:
- Đã test với X máy tính trong phòng lab
- Agent heartbeat ổn định, whitelist sync < 5 giây
- Firewall rules áp dụng thành công
```

---

## CHAPTER 5: SOLUTION AND CONTRIBUTION (≥ 5 trang, tối đa không giới hạn)

> **Bắt buộc**: Có Tổng quan + Kết chương. Tổng quan liên kết với CH4 ("Sau khi đã trình bày kiến trúc, thiết kế và cài đặt ở Chương 4, Chương 5 này tập trung vào các giải pháp và đóng góp nổi bật...").

> **Quan trọng - footnote template**: Nếu phần này **dưới 5 trang** thì **gộp vào CH6 (Conclusion)**, **KHÔNG tách thành chương riêng**. Khi gộp, đổi tên CH6 thành "CONCLUSION, CONTRIBUTION, AND FUTURE WORK".

> **Cấu trúc bắt buộc cho mỗi đóng góp**: 3 mục con
> - (i) **Dẫn dắt/giới thiệu** bài toán/vấn đề cụ thể.
> - (ii) **Giải pháp** mà sinh viên đề xuất.
> - (iii) **Kết quả đạt được** (nếu có): số liệu, so sánh, đánh giá.

> **Không trình bày lặp**: CH4 đã có gì thì CH5 không nói lại. Dùng tham chiếu chéo từ CH4 sang CH5.

**Chương QUAN TRỌNG NHẤT - thầy cô đánh giá chủ yếu từ đây.**

```
5.1 Giải pháp Whitelist-based Firewall tự động
(i) Vấn đề: Cần chặn truy cập không phép mà không cần proxy
(ii) Giải pháp: Agent tự tạo Windows Firewall rules (Default Deny
    + Allow whitelist IPs), DNS resolve parallel, LRU cache
(iii) Kết quả: Chặn thành công, < 5s sync, < 100MB RAM

5.2 Cơ chế đồng bộ Whitelist với Version Tracking
(i) Vấn đề: Agent cần biết khi nào whitelist thay đổi
(ii) Giải pháp: Server tăng version khi update → Agent detect
    thay đổi qua heartbeat response → Chỉ sync khi version thay đổi
(iii) Kết quả: Giảm 90% request sync không cần thiết

5.3 RBAC Teacher Data Filtering
(i) Vấn đề: Teacher chỉ nên thấy data nhóm mình
(ii) Giải pháp: Middleware inject current_user → Service filter
    by created_by/teacher_ids → Teacher chỉ thấy data liên quan
(iii) Kết quả: Hoàn toàn isolated, đã test 7 test files

5.4 Whitelist Profile cho quản lý bài học
(i) Vấn đề: Teacher cần whitelist khác nhau cho mỗi bài học
(ii) Giải pháp: Profile system - tạo, kích hoạt, tắt - override
    whitelist nhóm mà không ảnh hưởng whitelist gốc
(iii) Kết quả: Teacher tự quản lý linh hoạt, Agent sync tự động

5.5 Packet Capture và Domain Extraction đa phương thức
(i) Vấn đề: Cần trích xuất domain từ cả HTTP, HTTPS, DNS
(ii) Giải pháp: Scapy capture TCP 80/443/53 → Extract bằng 3
    phương pháp: DNS Query parsing, HTTP Host header, TLS SNI
(iii) Kết quả: Detect được 95%+ domain truy cập
```

---

## CHAPTER 6: CONCLUSION AND FUTURE WORK

> **Bắt buộc**: Có Tổng quan đầu chương ngắn gọn liên kết với CH5. Không cần Kết chương (vì là chương cuối).

> **Lưu ý**: Nếu CH5 < 5 trang, gộp vào đây và đổi tiêu đề thành "CONCLUSION, CONTRIBUTION, AND FUTURE WORK".

### 6.1 Conclusion

```
So sánh với sản phẩm tương tự:
- SAINT vs NetSupport: open-source, free, có RBAC Teacher
- SAINT vs Pi-hole: có packet capture, GUI agent, RBAC
- SAINT vs OpenDNS: không cần thay đổi DNS router

Đã làm được:
- Hệ thống Client-Server hoạt động ổn định
- ~50 API endpoints, 12 collections
- RBAC 2 roles, audit trail
- Agent GUI 5 views, whitelist firewall tự động
- Build SAINT.exe standalone

Chưa làm được:
- Chỉ hỗ trợ Windows
- Web UI chưa là SPA (vẫn dùng server-side rendering)
- Chưa containerize

Bài học kinh nghiệm:
- Thread-safe communication quan trọng trong GUI app
- JWT + RBAC cần thiết kế cẩn thận từ đầu
- MongoDB flexible nhưng cần đánh index đúng cách
```

### 6.2 Future work

```
Hoàn thiện:
- Hỗ trợ Linux/macOS Agent
- Xây dựng React/Vue SPA frontend
- Docker containerization + CI/CD

Nâng cấp:
- Machine Learning phát hiện truy cập bất thường
- Mobile app cho Teacher
- Dashboard analytics nâng cao (biểu đồ, thống kê)
- TLS inspection cho HTTPS content filtering
```

---

## REFERENCE (IEEE format)

> **Quy định nghiêm ngặt từ template:**
> - **Tối thiểu 10–15 tài liệu** tham khảo.
> - **CẤM**: bài giảng/slide, Wikipedia, blog cá nhân, các trang web thông thường.
> - **Cho phép**: trang web nếu là công bố chính thống của tổ chức (W3C, IETF RFC, ISO, vendor docs chính thức).
> - **Chỉ tài liệu được trích dẫn `[n]` trong văn bản** mới xuất hiện trong danh sách REFERENCE.
> - Hạn chế trích từ website, ưu tiên sách + bài báo hội nghị/tạp chí.

### 5 loại tài liệu tham khảo theo IEEE

**Loại 1 - Bài báo tạp chí khoa học:** *Tên tác giả, "tên bài báo", tên tạp chí, vol., no., pp. trang–trang, NXB, năm.*
```
[1] E. H. Hovy, "Automated discourse generation using discourse
    structure relations," Artificial Intelligence, vol. 63,
    no. 1-2, pp. 341–385, 1993.
```

**Loại 2 - Sách:** *Tên tác giả, tên sách, edition. NXB, năm.*
```
[2] L. L. Peterson and B. S. Davie, Computer Networks: A Systems
    Approach. Elsevier, 2007.
[3] M. Grinberg, Flask Web Development, 2nd ed. O'Reilly, 2018.
```

**Loại 3 - Báo cáo hội nghị:** *Tên tác giả, "tên báo cáo", in tên hội nghị, địa điểm, năm, pp. trang–trang.*
```
[4] M. Poesio and B. Di Eugenio, "Discourse structure and
    anaphoric accessibility," in ESSLLI workshop on information
    structure, discourse structure and discourse semantics,
    Copenhagen, Denmark, 2001, pp. 129–143.
[5] D. F. Ferraiolo and R. Kuhn, "Role-based access controls,"
    in Proc. 15th NIST-NCSC National Computer Security Conf.,
    Baltimore, USA, 1992, pp. 554–563.
```

**Loại 4 - Luận văn/Đồ án/Luận án:** *Tên tác giả, "tên luận văn", loại luận văn, tên trường, địa điểm, năm.*
```
[6] A. Knott, "A data-driven methodology for motivating a set
    of coherence relations," Ph.D. dissertation, The University
    of Edinburgh, UK, 1996.
```

**Loại 5 - Tài liệu Internet (chính thống):** *Tên tác giả/tổ chức, tên tài liệu. [Online]. Available: URL (visited on dd/mm/yyyy).*
```
[7] M. Jones, JSON Web Token (JWT), RFC 7519, IETF, 2015.
    [Online]. Available: https://datatracker.ietf.org/doc/
    html/rfc7519 (visited on 05/2026).
[8] P. Biondi, Scapy documentation. [Online]. Available:
    https://scapy.readthedocs.io/ (visited on 05/2026).
```

### Gợi ý nguồn cho project SAINT

| Chủ đề | Nguồn đáng tin cậy |
|---|---|
| RBAC | Ferraiolo & Kuhn (1992), NIST RBAC standard |
| JWT | RFC 7519 (IETF) |
| Flask | "Flask Web Development" - M. Grinberg, O'Reilly |
| MongoDB | "MongoDB: The Definitive Guide" - K. Chodorow, O'Reilly |
| Scapy | P. Biondi, official documentation |
| TLS SNI | RFC 6066 (IETF) |
| DNS | RFC 1035 (IETF) |
| HTTP Host header | RFC 7230 (IETF) |
| bcrypt | Provos & Mazières (1999), USENIX paper |
| Windows Firewall netsh | Microsoft Docs (docs.microsoft.com) |

---

## APPENDIX A: THESIS WRITING GUIDELINE

Phần này template đã có sẵn (Phụ lục A từ A.1 đến A.8), bao gồm:
- A.1 General Regulations (đã trình bày ở **Phần 0** của file hướng dẫn này)
- A.2 Majoring (ghi đúng tên ngành, xem mục 0.5)
- A.3 Bulleting and Numbering (cú pháp LaTeX `\begin{itemize}`, `\begin{enumerate}`)
- A.4 Table insertion (mọi bảng phải có caption + được tham chiếu trong văn bản)
- A.5 Figure Insertion (mọi hình phải có caption ở dưới + được tham chiếu)
- A.6 Reference (IEEE format, xem section REFERENCE ở trên)
- A.7 Equations (gói `amsmath`, `amssymb`, `amsfonts` đã sẵn trong template)
- A.8 Qui cách đóng quyển (xem mục 0.5)

**Sinh viên KHÔNG sửa Phụ lục A** (template đã viết sẵn các hướng dẫn này).

---

## APPENDIX B: USE CASE DESCRIPTIONS (nếu cần)

Template cung cấp Phụ lục B để chứa đặc tả use case **overflow** từ Chương 2 nếu CH2 không đủ chỗ.

**Khi nào dùng:**
- CH2 mục 2.3 chỉ đặc tả 4-7 UC quan trọng nhất.
- Các UC còn lại (nếu muốn đặc tả) đặt vào Phụ lục B.

**Đặc tả mỗi UC phải có:**
- (i) Tên use case
- (ii) Tác nhân tham gia
- (iii) Tiền điều kiện
- (iv) Luồng sự kiện chính
- (v) Luồng sự kiện phát sinh (ngoại lệ)
- (vi) Hậu điều kiện
- (vii) (Tuỳ chọn) Biểu đồ hoạt động nếu UC phức tạp

**Áp dụng cho SAINT** - các UC có thể đẩy xuống Phụ lục B nếu CH2 hết chỗ:

```
B.1 Đặc tả use case "Quản lý API Key"
B.2 Đặc tả use case "Bulk import/export Whitelist"
B.3 Đặc tả use case "Audit log viewing"
B.4 Đặc tả use case "Reset password người dùng"
B.5 Đặc tả use case "Set Agent Policy (isolate/reset/custom)"
```

---

# PHẦN B: LÀM SLIDE THEO TEMPLATE HUST

## Phân tích Template HUST

Template `HUST_PPT_template_2022_RED_4x3.pptx` có **13 slides**:

| Slide | Layout | Dùng làm gì |
|-------|--------|-------------|
| 1 | Trang bìa (background đỏ BKHN) | Bìa |
| 2 | Section divider (đỏ) | Chia section |
| 3 | Title slide (có logo BKHN + title + subtitle) | Trang mở đầu |
| 4-12 | Content slides (title + content placeholder) | Nội dung |
| 13 | Thank You slide | Kết thúc |

### Cách làm slide theo template

**Bước 1:** Mở file `HUST_PPT_template_2022_RED_4x3.pptx` trong PowerPoint

**Bước 2:** Duplicate slides nội dung (slide 4) cho đủ ~15-18 content slides

**Bước 3:** Điền nội dung theo cấu trúc bên dưới

### Cấu trúc slide đề xuất (18-20 slides)

```
Slide 1:  [Template slide 3] Trang bìa
          Title: XÂY DỰNG HỆ THỐNG QUẢN LÝ BẢO MẬT MẠNG
                 PHÂN TÁN CHO MÔI TRƯỜNG GIÁO DỤC (SAINT)
          Subtitle: GVHD: [tên] | SVTH: [tên] | MSSV: [mã]

Slide 2:  [Template slide 4] Mục lục
          1. Đặt vấn đề  2. Mục tiêu  3. Kiến trúc  4. Công nghệ
          5. Thiết kế  6. Kết quả  7. Demo  8. Kết luận

Slide 3:  [Duplicate slide 4] ĐẶT VẤN ĐỀ
          • Học sinh truy cập web không phù hợp
          • Thiếu công cụ quản lý mạng tập trung
          • Giáo viên không kiểm soát được
          • Proxy/firewall thủ công quá phức tạp

Slide 4:  [Duplicate slide 4] MỤC TIÊU
          • Client-Server quản lý truy cập mạng
          • Whitelist-based firewall tự động
          • RBAC Admin/Teacher
          • Giám sát real-time + Audit trail

Slide 5:  [Duplicate slide 4] KIẾN TRÚC TỔNG THỂ
          Vẽ sơ đồ: Server ← REST API → Agents
                     Server ← WebSocket → Browser
                     Server → MongoDB
          (Vẽ bằng PowerPoint shapes hoặc paste hình từ draw.io)

Slide 6:  [Duplicate slide 4] KIẾN TRÚC CHI TIẾT
          Server: MVC (Controller → Service → Model → MongoDB)
          Agent: MVP + Signals (GUI ← Controller → Components)

Slide 7:  [Duplicate slide 4] CÔNG NGHỆ - SERVER
          Bảng: Flask, MongoDB, JWT, SocketIO, Pydantic, bcrypt

Slide 8:  [Duplicate slide 4] CÔNG NGHỆ - AGENT
          Bảng: PySide6, Scapy, dnspython, netsh, PyInstaller

Slide 9:  [Duplicate slide 4] THIẾT KẾ DATABASE
          Bảng 5-6 collections chính
          (agents, whitelists, groups, logs, users)

Slide 10: [Duplicate slide 4] THIẾT KẾ API
          ~50 endpoints, chia nhóm:
          Agent (3), Whitelist (10), Group (6), Auth (6)...

Slide 11: [Duplicate slide 4] AGENT GUI
          Screenshots 5 views
          (Dashboard, Firewall, Whitelist, Logs, Settings)

Slide 12: [Duplicate slide 4] LUỒNG HOẠT ĐỘNG
          Sequence: Register → Sync → Firewall → Capture → Heartbeat

Slide 13: [Duplicate slide 4] BẢO MẬT
          8 lớp: API Key, JWT, bcrypt, brute-force, httpOnly,
          RBAC, Audit Trail, Token Revocation

Slide 14: [Duplicate slide 4] RBAC PHÂN QUYỀN
          Bảng so sánh Admin vs Teacher

Slide 15: [Duplicate slide 4] KẾT QUẢ
          • ~50 API endpoints
          • 12 MongoDB collections
          • Agent 5 views, SAINT.exe
          • 7 test files passed

Slide 16: [Duplicate slide 4] DEMO
          Screenshots / video demo
          (hoặc demo live nếu được phép)

Slide 17: [Duplicate slide 4] KẾT LUẬN
          Đạt được | Hạn chế | Hướng phát triển

Slide 18: [Template slide 13] THANK YOU / Q&A
```

### Tips khi dùng template HUST

1. **Giữ nguyên background/header** - đừng xóa logo BKHN, thanh đỏ
2. **Font**: Dùng font có sẵn trong template (thường Calibri/Arial)
3. **Bảng biểu**: Dùng table style phù hợp màu đỏ BKHN
4. **Sơ đồ**: Vẽ bằng PowerPoint shapes hoặc paste hình từ draw.io/Lucidchart
5. **Screenshots**: Resize vừa slide, có thể thêm border/shadow
6. **Tỉ lệ 4:3**: Template này là 4:3, KHÔNG phải 16:9 - sắp xếp nội dung phù hợp
7. **Slide number**: Template đã có sẵn số trang tự động

---

# PHẦN C: CHECKLIST TRƯỚC KHI NỘP

## Report - Nội dung

- [ ] Trang bìa + trang phụ đúng format (tên trường, đề tài, GVHD, SVTH, signature)
- [ ] Acknowledgments **100–150 từ** (đếm thật)
- [ ] Abstract **200–350 từ**, viết đoạn văn liền mạch theo trình tự (i)(ii)(iii)(iv)
- [ ] Mục lục, List of Figures, List of Tables, List of Abbreviations cập nhật
- [ ] Chương 1 - **3–6 trang**, đủ 4 mục: Motivation, Objectives & scope, Tentative solution, Thesis organization
- [ ] Chương 2 - **9–11 trang**, đủ 4 mục: Status survey, Functional Overview (3 sub), Functional description (4–7 UC), Non-functional requirement
- [ ] Chương 3 - **≤ 10 trang**, mỗi công nghệ có (i) giải quyết vấn đề gì ở CH2, (ii) alternative, (iii) lý do chọn
- [ ] Chương 4 - đủ Architecture (4.1) + Detailed design (4.2) + App Building (4.3) + Testing (4.4) + Deployment (4.5)
- [ ] Chương 5 - **≥ 5 trang**, mỗi đóng góp có 3 mục con (dẫn dắt / giải pháp / kết quả). Nếu < 5 trang → gộp CH6.
- [ ] Chương 6 - đủ Conclusion + Future work
- [ ] Tài liệu tham khảo ≥ 10 mục, đúng IEEE format, **đủ ít nhất 3 trong 5 loại** (sách / tạp chí / hội nghị / luận văn / internet chính thống)
- [ ] Phụ lục A (template tự viết, không sửa)
- [ ] Phụ lục B (Use Case Descriptions) - nếu CH2 không đủ chỗ

## Report - Quy định format (Phần 0)

- [ ] **KHÔNG** gạch đầu dòng / viết ý. Phải viết đoạn văn.
- [ ] Khi liệt kê: dùng (i), (ii), (iii), (iv) - không dùng "•", "*", "-"
- [ ] **KHÔNG** từ phóng đại: "tuyệt vời", "cực hay", "cực kỳ", "rất ấn tượng"...
- [ ] Mỗi đoạn có **một ý chính** + câu phân tích. Đoạn không quá dài.
- [ ] **Mỗi chương CH2–CH5 có Tổng quan đầu chương + Kết chương** (Normal text, không in đậm/khung)
- [ ] **Mọi hình, bảng, công thức được tham chiếu ít nhất 1 lần** trong văn bản
- [ ] Mọi hình/bảng/code không tự viết → ghi nguồn `[n]` đầy đủ
- [ ] **KHÔNG** Wikipedia, slide, blog làm tài liệu tham khảo
- [ ] Citation IEEE `[n]` xuất hiện trong văn bản trước khi vào REFERENCE
- [ ] Format thống nhất toàn báo cáo (font, margin, page numbering từ template)

## Report - Đóng quyển

- [ ] Bìa trước + bìa sau giấy liền khổ, chế bản theo template
- [ ] Dùng **keo nhiệt** dán gáy (không băng dính/dập ghim)
- [ ] **Gáy ĐATN** ghi đúng: `Kỳ ĐATN - Ngành - Họ tên SV - MSSV` (ví dụ: `2026.1 - KHOA HỌC MÁY TÍNH - NGUYỄN VĂN A - 20210xxx`)
- [ ] Tên ngành đúng khoá học (K61 KTPM / K62+ KHMT / cử nhân CNTT / ICT Global / DS&AI)

## Slide
- [ ] Dùng đúng template HUST
- [ ] 18-20 slides
- [ ] Logo BKHN giữ nguyên
- [ ] Font đọc được (≥ 18pt cho nội dung)
- [ ] Có sơ đồ kiến trúc
- [ ] Có screenshots thật
- [ ] Slide cuối: Thank You / Q&A
- [ ] Thời gian trình bày ~25-30 phút
