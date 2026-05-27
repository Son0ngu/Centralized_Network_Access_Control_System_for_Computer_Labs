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
| `test_app_factory.py` | Socket.IO async backend fallback khi cấu hình `gevent` nhưng dependency chưa khả dụng. |
| `test_csrf.py` | Double-submit CSRF middleware: safe methods exempt, header/cookie match required cho POST/PUT/PATCH/DELETE; Bearer/X-API-Key/login/refresh bypass; `ENFORCE_CSRF=False` tắt hook; helper mint/set/delete cookie. |
| `tests/e2e/saint-admin-smoke.spec.js` | Playwright browser smoke: login, shared `SaintAPI`/`SaintToast`/`SaintDate` globals, admin page render, profile change-password visual state, và CSRF header qua `SaintAPI`. |

## Kiểm tra đã chạy sau refactor 2026-05-26

| Lệnh | Kết quả |
| --- | --- |
| `rg -n "\.collection\." server/controllers server/services server/middleware` | Không còn kết quả; direct collection access đã được dọn khỏi controller/service/middleware. |
| `git diff --check` | Pass cho các file đã chạm; chỉ có cảnh báo CRLF theo cấu hình hiện tại. |
| `python -m py_compile` trên các file server đã refactor | Pass. |
| Smoke `from app import create_app`, gọi `create_app()` nhiều lần, kiểm tra `/api/health` | Pass; app được tạo đầy đủ route, không còn nhánh minimal app thiếu blueprint. |
| `pytest server/tests/test_groups.py -q -x --tb=short` | 70 passed. |
| `pytest server/tests/test_teacher_data_filtering.py -q -x --tb=short` | 75 passed. |
| `pytest server/tests/test_whitelist_and_logs.py -q -x --tb=short` | 109 passed. |
| `pytest server/tests/test_request_ip.py server/tests/test_audit.py server/tests/test_users_auth.py::TestAdminAuthController -q -x --tb=short` | 44 passed. |
| `pytest server\tests -q --tb=short` | 505 passed, 23 warnings ở mốc sau whitelist ObjectId/RBAC, lifecycle lazy identity và Socket.IO fallback. |
| `python scripts\migrations\2026_backfill_group_whitelist_entry_ids.py --dry-run` | Pass; DB đang cấu hình không còn group whitelist entry cần backfill/normalize. |
| Flask test-client smoke `/api/health`, `/api/config`, `/profile`, `/admin/audit`, `/groups`, `/whitelist`, `/admin/change-password` | Pass; Socket.IO fallback sang `threading` khi `gevent` chưa cài trong Python env. |
| `pytest server\tests\test_app_factory.py -q --tb=short` | 3 passed sau khi thêm check CORS `PATCH` + `X-CSRF-Token`. |
| `pytest server\tests\test_csrf.py -q --tb=short` (sau khi thêm CSRF middleware) | 12 passed. |
| `pytest server\tests -q --tb=line` (đầy đủ sau CSRF + bare-except + atexit + callback boundary) | **517 passed, 0 failed, 23 warnings**. |
| `pytest server\tests\test_app_factory.py server\tests\test_csrf.py server\tests\test_teacher_data_filtering.py server\tests\test_users_auth.py -q --tb=short` (sau CORS/RBAC middleware/API key actor cleanup) | **180 passed, 0 failed, 20 warnings**. |
| `pytest server\tests -q --tb=short` (full regression sau các bản vá cuối) | **519 passed, 0 failed, 23 warnings**. |
| `npm.cmd run e2e` (sau khi cài `@playwright/test` và Chromium bằng `npx.cmd playwright install chromium`) | **4 passed**; Flask server được start qua `tools/e2e-server.js`, dùng admin local cấu hình bởi `E2E_ADMIN_USERNAME`/`E2E_ADMIN_PASSWORD` nếu khác default. |
| `pytest agent\tests\test_lifecycle_components.py -q --tb=short` (sau lifecycle `AgentComponent.start/stop/health`) | **3 passed**; cover start order, reverse stop, cleanup khi start fail, và component-reported failure. |
| `pytest server\tests\test_whitelist_and_logs.py -q -x --tb=short` (sau `whitelist_entries` collection-first dual path) | **115 passed, 3 expected DeprecationWarning** từ legacy `*_domain` API. |
| `pytest server\tests\test_groups.py server\tests\test_teacher_data_filtering.py server\tests\test_app_factory.py -q -x --tb=short` | **153 passed**; group/RBAC/app factory không regression sau schema migration layer. |
| `python server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py --json --fail-on-invalid` | Dry-run pass; `groups_scanned=0`, `embedded_entries_scanned=0`, `entries_existing=0`, `entries_inserted=0`, `entries_skipped_invalid=0`, `invalid_entries=[]`. |
| `rg -n "\.collection\." server/controllers server/services server/middleware` | Không còn kết quả. |

Toàn bộ server test suite đã chạy lại sau các bản vá trực tiếp gần nhất.

## Deployment source

- `server/Dockerfile`: build image Server.
- `server/docker-compose.yml`: compose service cho Server.
- `server/.env-example`: biến môi trường mẫu, không chứa secret thật.
- `agent/saint_agent.spec`: PyInstaller spec cho Agent executable (Qt frontend, output `dist/SAINT/SAINT.exe`).

## Lưu ý vận hành

- Server cần MongoDB URI, JWT secret và cấu hình production phù hợp.
- Production nên cài đúng Socket.IO async backend theo `SOCKETIO_ASYNC_MODE` (ví dụ `gevent`) để đạt hiệu năng tốt. Nếu backend thiếu, app vẫn fallback sang `threading` để không chết lúc boot.
- Browser smoke tests cần Node.js, `npm.cmd install`, và browser binary Playwright (`npm.cmd run e2e:install`). Nếu đã có server đang chạy, có thể set `E2E_SKIP_WEBSERVER=1`; nếu admin local khác default thì set `E2E_ADMIN_USERNAME` và `E2E_ADMIN_PASSWORD`.
- Nếu chạy sau nginx/reverse proxy, proxy phải forward `X-Forwarded-For` hoặc `X-Real-IP` để `/admin/audit` hiển thị IP máy client thật thay vì IP proxy/localhost.
- Agent Windows cần quyền Administrator nếu bật `whitelist_only`.
- Trước khi chạy Agent thật cần snapshot firewall policy và có đường phục hồi mạng.
- Whitelist/firewall operational cutover dùng runbook `docs/runbooks/whitelist-firewall-cutover.md`; không chạy migration `--write` hoặc đổi firewall default nếu chưa có backup/staging/Windows admin canary.

Ví dụ nginx:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```
