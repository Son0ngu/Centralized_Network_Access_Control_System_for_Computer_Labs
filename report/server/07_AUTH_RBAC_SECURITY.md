# Authentication, RBAC và bảo mật Server

## Authentication

| Luồng | Source | Cơ chế |
| --- | --- | --- |
| Agent register | `middleware/auth.py`, `api_key_service.py` | API Key hash/HMAC permission `agent_register`. |
| Agent API | `require_jwt` | JWT Agent cho heartbeat, whitelist sync, logs. |
| Admin/Teacher login | `admin_auth_controller.py`, `admin_auth_service.py` | Username/password bcrypt, token/cookie, session model. |
| Token refresh/revoke | `jwt_service.py`, `session_model.py` | Access/refresh token, JTI, revoked token collection. |

## RBAC

`server/config/rbac_config.py` định nghĩa 2 role:

- `admin`: toàn quyền, kế thừa quyền Teacher và thêm users/api_keys/logs/export/audit/system.
- `teacher`: chỉ đọc/cập nhật tài nguyên trong group được gán, quản lý whitelist profile, xem logs thuộc Agent của group mình.

## Data filtering

`RBACService` tạo query filter cho groups, agents, logs, whitelist. Controller web-facing dùng `inject_current_user()` và service/model chỉ trả dữ liệu đúng phạm vi.

## Brute-force và session

`UserModel` có failed attempts, lock account; `AdminAuthService` xác thực bcrypt và quản lý session/token. `AuditService` ghi log thao tác quan trọng.
