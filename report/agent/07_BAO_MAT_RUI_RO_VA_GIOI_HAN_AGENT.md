# Bảo mật, rủi ro và giới hạn của Agent

## Cơ chế bảo mật

| Cơ chế | Source | Ý nghĩa |
| --- | --- | --- |
| API Key khi đăng ký | `agent/core/registry.py` | Agent không tự đăng ký nếu thiếu credential hợp lệ. |
| JWT access/refresh | `agent/core/token_manager.py` | Gọi API sau đăng ký bằng token, có auto refresh. |
| Config encryption | `agent/config/crypto.py` | Mã hóa file config chứa thông tin nhạy cảm theo machine key. |
| Whitelist-only | `agent/firewall/manager.py` | Default Deny outbound, chỉ allow whitelist/server/DNS. |
| Snapshot/restore | `agent/firewall/manager.py`, `agent/gui_qt/views/settings.py` | Giảm rủi ro khi cần phục hồi policy. |

## Rủi ro ngắt mạng

`whitelist_only` có thể làm máy mất kết nối nếu:

- Chưa allow IP Server hoặc DNS trước khi bật Default Deny.
- Domain whitelist không resolve được.
- Agent chạy với quyền Administrator trên máy thật nhưng cấu hình sai.
- Cleanup/restore thất bại sau khi tạo rules.

## Giảm rủi ro đã có trong code

- `create_self_allow_rules()` allow chương trình Agent.
- `_resolve_server_urls()` resolve và allow Server URL trước khi bật policy.
- `shared/server_urls.py::collect_server_urls(config, allow_dev_default=False)` là resolver URL Server chung; khi chưa cấu hình Server, Agent ở first-run offline mode thay vì tự fallback về `http://localhost:5000`.
- `PolicyManager.backup_current_policy()` và restore policy.
- `RulesManager.clear_all_rules()` dọn rule theo prefix.
- Settings view có thao tác restore/clear rule thủ công.

## Giới hạn

- Tập trung Windows; dùng `netsh`, pywin32, Scapy/driver packet capture.
- Layer 7 chỉ quan sát DNS/HTTP/SNI, không decrypt HTTPS.
- Nếu CDN/shared IP làm IP được whitelist nhưng domain khác đi qua, hệ thống ghi warning thay vì luôn chặn chính xác ở domain-level.
