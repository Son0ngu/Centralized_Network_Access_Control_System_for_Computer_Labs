# Ghi chú phân tích source

## Phạm vi đã đọc

- Python source trong `agent/` và `server/`.
- `server/requirements.txt`, `agent/requirements.txt`, `server/Dockerfile`, `server/docker-compose.yml`, `server/.env-example`.
- Test source trong `server/tests/` để mô tả phạm vi kiểm thử.

## Phạm vi cố ý không dùng làm nguồn chính

- Không dùng tài liệu cũ trong `docs/` để suy luận kiến trúc hiện tại.
- Không đọc `server/.env` để tránh lộ secret.
- Không chạy `dist/SAINT.exe`, Agent GUI, Server thật, Docker compose, packet capture hoặc lệnh firewall.

## Phương pháp

- Trích route từ `server/controllers/*.py` và prefix `/api` từ `server/app.py`.
- Trích class/function bằng AST Python, không import module.
- Trích collection MongoDB từ `server/models/` và `server/services/jwt_service.py`.
- Trích SocketIO event bằng search pattern `socketio.emit` và `@socketio.on`.

## Thống kê source

| Nhóm | Số module Python |
| --- | ---: |
| Agent | 64 |
| Server, gồm tests | 49 |
| Server API routes | 70 |
