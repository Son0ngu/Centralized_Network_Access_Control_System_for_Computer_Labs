# Database models và MongoDB collections

| Collection | Vai trò | Source tham chiếu |
| --- | --- | --- |
| agents | Thông tin Agent, heartbeat, hostname, group, status. | server/bootstrap/container.py, server/models/agent_model.py, server/controllers/agent_controller.py, server/controllers/log_controller.py |
| agent_policies | Policy runtime theo Agent: isolate/reset/custom whitelist. | server/models/agent_policy_model.py |
| api_keys | API Key hash, quyền, trạng thái, hạn dùng. | server/bootstrap/container.py, server/models/api_key_model.py, server/controllers/api_key_controller.py |
| audit_logs | Audit trail cho thao tác quản trị, gồm `ip_address` lấy từ client IP đã chuẩn hóa. | server/models/audit_model.py, server/services/audit_service.py, server/utils/request_ip.py |
| groups | Nhóm phòng lab/lớp, teacher_ids, whitelist theo nhóm. | server/bootstrap/container.py, server/models/group_model.py, server/controllers/agent_controller.py, server/controllers/group_controller.py |
| logs | Log truy cập mạng do Agent gửi. | server/bootstrap/container.py, server/models/log_model.py, server/controllers/log_controller.py, server/controllers/audit_controller.py |
| admin_sessions | Phiên đăng nhập admin/teacher, JTI access/refresh. | server/models/session_model.py |
| users | Tài khoản Admin/Teacher, role, password hash, lock state. | server/bootstrap/container.py, server/models/user_model.py, server/controllers/audit_controller.py, server/controllers/user_controller.py |
| whitelist | Whitelist global/group: domain, IP, URL, category, active. | server/bootstrap/container.py, server/models/whitelist_model.py, server/controllers/agent_controller.py, server/controllers/group_controller.py |
| whitelist_meta | Global whitelist version metadata. | server/models/whitelist_model.py |
| whitelist_profiles | Profile whitelist theo giáo viên/nhóm/bài học. | server/controllers/whitelist_profile_controller.py, server/models/whitelist_profile_model.py |
| revoked_tokens | Token đã revoke, TTL cleanup. | server/services/jwt_service.py |

## Quan hệ nghiệp vụ chính

- Sau refactor 2026-05-26, controller/service không còn gọi Mongo qua `.collection` trực tiếp. Các truy vấn/update trực tiếp đã được gom vào model methods như `GroupModel.find_accessible_group_ids_for_teacher`, `AgentModel.find_agent_ids_by_group_ids`, `WhitelistModel.find_entry_access_info`, `WhitelistProfileModel.list_by_teacher_groups`.
- `agents.group_id` liên kết Agent với `groups`.
- `groups.teacher_ids` xác định Teacher nào được quản lý group.
- `groups.whitelist[]` vẫn là whitelist nhúng trong group ở giai đoạn rollout, nhưng `GroupModel.create_group` và `GroupModel.update_group` luôn normalize entry thành subdocument có `_id: ObjectId`. Nếu frontend gửi `_id` dạng string, model convert lại thành `ObjectId`; nếu entry thiếu `_id`, model stamp mới. Điều này giữ dotted-path query `whitelist._id` hoạt động ổn định cho update/delete/RBAC.
- `whitelist` chứa entries global hoặc theo group; `whitelist_meta` lưu version global.
- `whitelist_profiles` cho phép Teacher tạo profile whitelist riêng theo group/bài học.
- `logs.agent_id` liên kết log truy cập với Agent.
- `agent_policies.agent_id` override policy theo Agent khi isolate/reset.
- `admin_sessions`, `revoked_tokens` hỗ trợ token revocation và session management.
- `audit_logs.ip_address` và `admin_sessions.ip_address` phản ánh IP client do `get_client_ip()` xác định; log cũ đã lưu trước khi sửa vẫn giữ giá trị cũ trong MongoDB.

## Indexes

Các model trong `server/models/*_model.py` đều có `_setup_indexes()` hoặc `_create_indexes()` để tạo index cho lookup thường dùng như `agent_id`, `device_id`, `group_id`, `username`, `role`, `timestamp`, `key_hash`, `jti`.
