# API Agent sử dụng và giải thích

Agent không expose HTTP API nội bộ. Agent là client gọi REST API của Server.

| Method | Server API | Module Agent gọi | Auth | Mục đích | Output chính |
| --- | --- | --- | --- | --- | --- |
| POST | /api/agents/register | core.registry.register_agent / try_register_with_server | API Key | Đăng ký Agent, gửi hostname/device_id/IP/OS. | `agent_id`, access/refresh token. |
| POST | /api/agents/heartbeat | services.heartbeat.HeartbeatSender._send_heartbeat | JWT Agent | Gửi trạng thái, metrics, version và nhận chỉ thị force sync. | Kết quả heartbeat, policy/sync flags. |
| GET | /api/whitelist/agent-sync | whitelist.sync.WhitelistSyncer.sync_with_server | JWT Agent | Kéo whitelist scoped theo Agent/group/profile/policy. | Whitelist entries, versions, policy mode. |
| POST | /api/logs | logging_module.sender.LogSender._send_batch | JWT Agent | Gửi batch log ALLOWED/BLOCKED/OBSERVED. | Số log nhận/lưu hoặc lỗi. |
| POST | /api/auth/refresh | core.token_manager.TokenManager._do_refresh | Refresh token | Làm mới access token khi gần hết hạn. | Token mới hoặc yêu cầu đăng ký lại. |
| POST | /api/auth/logout | core.token_manager / cleanup flow nếu dùng | JWT/refresh token | Thu hồi token khi Agent dừng hoặc đăng xuất. | Trạng thái revoke. |

## Luồng kết nối

1. `register_agent()` thu thập thông tin máy và gọi `/api/agents/register` bằng API Key.
2. Token nhận được được quản lý bởi `TokenManager`.
3. `HeartbeatSender` gửi `/api/agents/heartbeat` định kỳ.
4. `WhitelistSyncer` gọi `/api/whitelist/agent-sync` khi cần đồng bộ.
5. `LogSender` gom log thành batch và gửi `/api/logs`.
