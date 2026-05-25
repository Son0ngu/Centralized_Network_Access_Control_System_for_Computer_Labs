# Bộ report kỹ thuật SAINT

Bộ tài liệu này được tạo từ source code hiện tại trong `agent/` và `server/`, không dựa vào tài liệu cũ trong `docs/` làm nguồn chính.

## Cách đọc nhanh

- `PROJECT_OVERVIEW.md`: bức tranh tổng thể hệ thống.
- `agent/`: kiến trúc, công nghệ, API Agent tiêu thụ, luồng hoạt động, bảo mật/rủi ro.
- `server/`: kiến trúc Flask/MongoDB, API, models/collections, RBAC, SocketIO, testing/deployment.
- `diagrams/`: sơ đồ Mermaid có thể render trong Markdown viewer.

## Cảnh báo vận hành

Không chạy `dist/SAINT.exe`, `agent/agent_gui.py`, hoặc bất kỳ thành phần Agent runtime nào khi chỉ cần đọc tài liệu. Source hiện tại có chế độ `whitelist_only` dùng Default Deny trên Windows Firewall; nếu chạy thật với quyền Administrator và cấu hình không đúng, máy có thể mất kết nối mạng.
