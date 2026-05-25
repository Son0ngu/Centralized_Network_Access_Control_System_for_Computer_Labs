# Database models và MongoDB collections

| Collection | Vai trò | Source tham chiếu |
| --- | --- | --- |
| agents | Thông tin Agent, heartbeat, hostname, group, status. | server/app.py, server/config/rbac_config.py, server/controllers/agent_controller.py, server/controllers/log_controller.py |
| agent_policies | Policy runtime theo Agent: isolate/reset/custom whitelist. | server/models/agent_policy_model.py |
| api_keys | API Key hash, quyền, trạng thái, hạn dùng. | server/app.py, server/config/rbac_config.py, server/controllers/api_key_controller.py, server/models/api_key_model.py |
| audit_logs | Audit trail cho thao tác quản trị. | server/models/audit_model.py |
| groups | Nhóm phòng lab/lớp, teacher_ids, whitelist theo nhóm. | server/app.py, server/config/rbac_config.py, server/controllers/agent_controller.py, server/controllers/group_controller.py |
| logs | Log truy cập mạng do Agent gửi. | server/app.py, server/config/rbac_config.py, server/controllers/api_key_controller.py, server/controllers/audit_controller.py |
| admin_sessions | Phiên đăng nhập admin/teacher, JTI access/refresh. | server/models/session_model.py |
| users | Tài khoản Admin/Teacher, role, password hash, lock state. | server/app.py, server/config/rbac_config.py, server/controllers/audit_controller.py, server/controllers/user_controller.py |
| whitelist | Whitelist global/group: domain, IP, URL, category, active. | server/app.py, server/config/rbac_config.py, server/controllers/agent_controller.py, server/controllers/group_controller.py |
| whitelist_meta | Global whitelist version metadata. | server/models/whitelist_model.py |
| whitelist_profiles | Profile whitelist theo giáo viên/nhóm/bài học. | server/controllers/whitelist_profile_controller.py, server/models/whitelist_profile_model.py |
| revoked_tokens | Token đã revoke, TTL cleanup. | server/services/jwt_service.py |

## Quan hệ nghiệp vụ chính

- `agents.group_id` liên kết Agent với `groups`.
- `groups.teacher_ids` xác định Teacher nào được quản lý group.
- `whitelist` chứa entries global hoặc theo group; `whitelist_meta` lưu version global.
- `whitelist_profiles` cho phép Teacher tạo profile whitelist riêng theo group/bài học.
- `logs.agent_id` liên kết log truy cập với Agent.
- `agent_policies.agent_id` override policy theo Agent khi isolate/reset.
- `admin_sessions`, `revoked_tokens` hỗ trợ token revocation và session management.

## Indexes

Các model trong `server/models/*_model.py` đều có `_setup_indexes()` hoặc `_create_indexes()` để tạo index cho lookup thường dùng như `agent_id`, `device_id`, `group_id`, `username`, `role`, `timestamp`, `key_hash`, `jti`.
