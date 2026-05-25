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
| connect | server/app.py | Server nhận sự kiện SocketIO từ browser/client. |
| disconnect | server/app.py | Server nhận sự kiện SocketIO từ browser/client. |
| logs_cleared | server/controllers/log_controller.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| new_log | server/services/log_service.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| ping | server/app.py | Server nhận sự kiện SocketIO từ browser/client. |
| pong | server/app.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
| server_message | server/app.py | Server phát sự kiện realtime cho dashboard hoặc client liên quan. |
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

## Ghi chú

Dashboard hiện không phải SPA; Server render HTML bằng Flask template, static JS gọi REST API `/api/*` và nhận SocketIO events.
