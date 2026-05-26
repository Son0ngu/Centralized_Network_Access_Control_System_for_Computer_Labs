# SocketIO, realtime và frontend dashboard

## SocketIO events trong source

| Event | Source | Ý nghĩa |
| --- | --- | --- |
| admin_login | server/services/admin_auth_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_deleted | server/controllers/agent_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_deleted | server/services/agent_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_group_updated | server/controllers/agent_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_heartbeat | server/controllers/agent_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_heartbeat | server/services/agent_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_logout | server/controllers/auth_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_policy_changed | server/services/agent_policy_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_registered | server/controllers/agent_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| agent_registered | server/services/agent_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| api_key_created | server/services/api_key_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| api_key_revoked | server/services/api_key_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| connect | server/routes/socketio_events.py | Server nhận sự kiện SocketIO từ browser/client. |
| disconnect | server/routes/socketio_events.py | Server nhận sự kiện SocketIO từ browser/client. |
| logs_cleared | server/controllers/log_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| new_log | server/services/log_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| ping | server/routes/socketio_events.py | Server nhận sự kiện SocketIO từ browser/client. |
| pong | server/routes/socketio_events.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| server_message | server/routes/socketio_events.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| token_refreshed | server/controllers/auth_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| user_created | server/services/user_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_added | server/services/whitelist_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_bulk_added | server/services/whitelist_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_deleted | server/services/whitelist_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_updated | server/controllers/whitelist_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_updated | server/controllers/whitelist_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_updated | server/controllers/whitelist_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_updated | server/services/whitelist_profile_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| whitelist_updated | server/services/whitelist_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |

## Frontend server-rendered

| Page/template | JS/CSS liên quan | Chức năng |
| --- | --- | --- |
| `dashboard.html` | `dashboard.js`, `dashboard.css` | Tổng quan agents/logs/realtime. |
| `agents.html` | `agents.js`, `agents.css` | Quản lý Agent, group, display name, policy. |
| `groups.html`, `group_detail.html` | `groups.js`, `group_detail.js` | Quản lý group, assign Agent/Teacher. |
| `whitelist.html` | `whitelist.js`, `whitelist.css` | CRUD/import/export/bulk whitelist. |
| `logs.html` | `logs.js`, `logs.css` | Filter/export/clear logs. |
| `admin_users.html`, `admin_audit.html` | `admin_users.js`, CSS | User management và audit log. |
| `profile.html` | `profile.css` | Thông tin tài khoản và đổi mật khẩu. |

## Ghi chú

Dashboard hiện không phải SPA; Server render HTML bằng Flask template, static JS gọi REST API `/api/*` và nhận SocketIO events.

Trang `profile.html` dùng class riêng `profile-change-password-btn` cho nút đổi mật khẩu. Nút này có nền vàng nhạt và chữ nâu ở trạng thái thường, hover/focus/disabled đều giữ màu tương phản; không còn phụ thuộc vào `text-white` hoặc chỉ hiện chữ khi hover trên `.btn-warning`.

## Logs page - Details rendering

Agent gửi log với `message` mặc định là `"Log entry"` khi nó không gắn mô tả riêng (xem `agent/logging_module/sender.py:135` và `agent/core/handlers.py::handle_domain_detection` - handler không set `message`). Trước đây UI hiển thị thẳng chuỗi `"Log entry"` ở khung Details, gần như vô dụng.

Hiện tại `server/views/static/js/logs.js` có ba helper:

- `escapeHtml(text)` - escape ký tự HTML trước khi nhúng vào `innerHTML`, chống XSS từ field do packet sniffer trích (TLS SNI, HTTP Host).
- `buildLogDescription(log)` - dựng câu mô tả từ các field có sẵn trong log document: `action` (`BLOCKED` / `ALLOWED` / `ALLOWED_BY_IP` / `OBSERVED`), `domain`, `source_ip`, `dest_ip`, `protocol` (đặc biệt `DNS`), `port`, `firewall_mode`, và hai cờ `domain_allowed` / `ip_allowed` để gắn lý do (ví dụ `"domain not in whitelist"`, `"IP whitelisted but SNI/Host is not - possible CDN co-tenant"`).
- `getLogDetailText(log)` - wrapper: dùng `log.message` nếu là chuỗi tùy chỉnh, fallback sang `buildLogDescription(log)` khi message rỗng hoặc bằng placeholder `"Log entry"`.

Cả `renderLogs()` (list view) lẫn `showLogDetails()` (modal View Details) đều gọi `getLogDetailText` và escape output trước khi nhúng vào `innerHTML`. Trường `dataset.search` cho client-side filter cũng dùng `detailText` để search theo description.

Lợi ích: cải tiến chỉ touch frontend nên có hiệu lực ngay với cả log cũ đã lưu trong MongoDB; không cần redeploy Agent ra từng máy Windows phòng lab.
