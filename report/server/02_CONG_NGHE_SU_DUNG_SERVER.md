# Công nghệ sử dụng - Server

| Dependency | Vai trò trong source |
| --- | --- |
| pymongo | MongoDB driver. |
| pydantic | Validate/schema dữ liệu. |
| flask | Web framework cho REST API và server-rendered dashboard. |
| flask-socketio | WebSocket/SocketIO để đẩy trạng thái real-time. |
| flask-cors | CORS cho API. |
| python-dotenv | Nạp biến môi trường từ `.env`. |
| pyjwt | JWT access/refresh token. |
| bcrypt | Hash mật khẩu. |
| email_validator | Validate email user. |
| gevent | Async worker cho SocketIO. |
| gevent-websocket | WebSocket transport cho gevent. |
| tzdata | Thư viện hỗ trợ runtime. |
| python-snappy | Nén dữ liệu MongoDB/network nếu driver dùng. |

## Runtime và triển khai

| Thành phần | Source | Vai trò |
| --- | --- | --- |
| Flask app factory | `server/app.py` | Khởi tạo app, CORS, SocketIO, DB, route. |
| MongoDB config | `server/database/config.py` | Kết nối MongoDB, config theo env. |
| Docker | `server/Dockerfile`, `server/docker-compose.yml` | Đóng gói/deploy Server. |
| Server templates | `server/views/templates/` | Dashboard/admin pages server-rendered. |
| Static JS/CSS | `server/views/static/` | Tương tác dashboard, table, auth, SocketIO client. |
