# Testing và deployment

## Tests hiện có

| Test file | Phạm vi |
| --- | --- |
| `test_agents.py`, `test_agent_full.py` | Agent register, heartbeat, agent APIs. |
| `test_whitelist_and_logs.py` | Whitelist, logs, sync/receive logs. |
| `test_users_auth.py` | User và authentication. |
| `test_teacher_data_filtering.py` | RBAC Teacher filtering. |
| `test_groups.py` | Group CRUD/assignment. |
| `test_audit.py` | Audit logging. |
| `test_request_ip.py` | Chuẩn hóa client IP từ `X-Forwarded-For`, `X-Real-IP`, `remote_addr` và AuditService. |

## Kiểm tra đã chạy sau refactor 2026-05-26

| Lệnh | Kết quả |
| --- | --- |
| `rg -n "\.collection\." server/controllers server/services` | Không còn kết quả; direct collection access đã được dọn khỏi controller/service. |
| `git diff --check` | Pass cho các file đã chạm; chỉ có cảnh báo CRLF theo cấu hình hiện tại. |
| `python -m py_compile` trên các file server đã refactor | Pass. |
| Smoke `from app import create_app`, gọi `create_app()` nhiều lần, kiểm tra `/api/health` | Pass; app được tạo đầy đủ route, không còn nhánh minimal app thiếu blueprint. |
| `pytest server/tests/test_groups.py -q -x --tb=short` | 70 passed. |
| `pytest server/tests/test_teacher_data_filtering.py -q -x --tb=short` | 75 passed. |
| `pytest server/tests/test_whitelist_and_logs.py -q -x --tb=short` | 109 passed. |
| `pytest server/tests/test_request_ip.py server/tests/test_audit.py server/tests/test_users_auth.py::TestAdminAuthController -q -x --tb=short` | 44 passed. |

Chưa chạy toàn bộ test suite trong một lệnh duy nhất sau refactor; các nhóm regression trực tiếp cho app/bootstrap, RBAC, whitelist/logs, audit/IP và admin auth đã pass.

## Deployment source

- `server/Dockerfile`: build image Server.
- `server/docker-compose.yml`: compose service cho Server.
- `server/.env-example`: biến môi trường mẫu, không chứa secret thật.
- `agent/saint_agent.spec`: PyInstaller spec cho Agent executable (Qt frontend, output `dist/SAINT/SAINT.exe`).

## Lưu ý vận hành

- Server cần MongoDB URI, JWT secret và cấu hình production phù hợp.
- Nếu chạy sau nginx/reverse proxy, proxy phải forward `X-Forwarded-For` hoặc `X-Real-IP` để `/admin/audit` hiển thị IP máy client thật thay vì IP proxy/localhost.
- Agent Windows cần quyền Administrator nếu bật `whitelist_only`.
- Trước khi chạy Agent thật cần snapshot firewall policy và có đường phục hồi mạng.

Ví dụ nginx:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```
