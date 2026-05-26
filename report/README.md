# Bộ report kỹ thuật SAINT

Bộ tài liệu này được tạo từ source code hiện tại trong `agent/` và `server/`, không dựa vào tài liệu cũ trong `docs/` làm nguồn chính.

## Cập nhật 2026-05-26

- Report đã được cập nhật theo refactor mới nhất: `server/app.py` là entrypoint mỏng, phần tạo app/container/startup task/page route/error handler/SocketIO handler đã tách sang `server/bootstrap/` và `server/routes/`.
- Ranh giới tầng server đã được ghi lại theo trạng thái hiện tại: controller/service không còn truy cập Mongo trực tiếp qua `.collection`; các query/update trực tiếp được chuyển xuống model layer.
- Các mục review kiến trúc đã được đánh dấu trạng thái: phần đã fix, phần còn tồn đọng và hướng sửa tiếp theo.

## Cách đọc nhanh

- `PROJECT_OVERVIEW.md`: bức tranh tổng thể hệ thống.
- `agent/`: kiến trúc, công nghệ, API Agent tiêu thụ, luồng hoạt động, bảo mật/rủi ro.
- `server/`: kiến trúc Flask/MongoDB, API, models/collections, RBAC, SocketIO, testing/deployment.
- `diagrams/`: sơ đồ Mermaid có thể render trong Markdown viewer.

## Cảnh báo vận hành

Không chạy `dist/SAINT/SAINT.exe`, `agent/agent_gui.py`, hoặc bất kỳ thành phần Agent runtime nào khi chỉ cần đọc tài liệu. Source hiện tại có chế độ `whitelist_only` dùng Default Deny trên Windows Firewall; nếu chạy thật với quyền Administrator và cấu hình không đúng, máy có thể mất kết nối mạng.
