# Tổng quan dự án SAINT

## Mục tiêu hệ thống

SAINT là hệ thống quản lý truy cập mạng tập trung cho phòng máy/lab giáo dục. Hệ thống gồm Server trung tâm, Web Dashboard cho Admin/Teacher và Agent chạy trên máy Windows của học sinh/sinh viên. Mục tiêu chính là cho phép quản lý whitelist domain/IP theo nhóm, giám sát truy cập mạng, ghi log và phân quyền theo vai trò.

## Thành phần chính

| Thành phần | Vai trò | Source chính |
| --- | --- | --- |
| Server Flask | REST API, Web Dashboard, SocketIO realtime, auth/RBAC | `server/app.py`, `server/controllers/`, `server/services/` |
| MongoDB | Lưu agents, users, groups, whitelist, logs, sessions, audit | `server/models/` |
| Agent Core | Đăng ký Agent, heartbeat, token, lifecycle | `agent/core/`, `agent/services/` |
| Agent Enforcement | Whitelist sync, DNS resolve, Windows Firewall rules | `agent/whitelist/`, `agent/network/`, `agent/firewall/` |
| Agent Monitoring | Scapy sniffer, domain extraction, log sender | `agent/capture/`, `agent/logging_module/` |
| Agent GUI | PySide6 (Qt) dashboard / settings / logs / firewall / whitelist views | `agent/gui_qt/` + `agent/controllers/` |

## Sơ đồ tổng thể

```mermaid
%% xem thêm: diagrams/system_architecture.mmd
flowchart TB
  Browser["Admin/Teacher Browser"] -->|"HTTP + SocketIO"| Server["Flask Server"]
  Server --> Mongo[("MongoDB")]
  Agent["Windows Agent"] -->|"REST API + JWT"| Server
  Agent --> Firewall["Windows Firewall"]
  Agent --> Sniffer["Scapy Packet Sniffer"]
```

## Khác biệt cần lưu ý so với tài liệu cũ

- Source hiện tại có Dockerfile/docker-compose cho Server.
- Server dùng Flask app factory, SocketIO async mode `gevent`, controller/service/model tách lớp rõ hơn.
- Agent requirements có `pydivert`, `scapy`, `pywin32`, `netifaces`, `PySide6`, `cryptography`; enforcement chính trong source là `whitelist_only`.
- RBAC chỉ có 2 role chính: `admin` và `teacher`; Teacher bị filter theo group ownership.
- Agent không expose HTTP API nội bộ; Agent là client gọi Server API.

