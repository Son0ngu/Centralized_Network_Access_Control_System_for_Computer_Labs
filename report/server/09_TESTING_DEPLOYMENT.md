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

## Deployment source

- `server/Dockerfile`: build image Server.
- `server/docker-compose.yml`: compose service cho Server.
- `server/.env-example`: biến môi trường mẫu, không chứa secret thật.
- `agent/saint_agent.spec`: PyInstaller spec cho Agent executable (Qt frontend, output `dist/SAINT-Agent.exe`).

## Lưu ý vận hành

- Server cần MongoDB URI, JWT secret và cấu hình production phù hợp.
- Agent Windows cần quyền Administrator nếu bật `whitelist_only`.
- Trước khi chạy Agent thật cần snapshot firewall policy và có đường phục hồi mạng.
