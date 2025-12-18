# Firewall Controller Enhanced - Tổng quan Project

## 🎯 Mục đích
Hệ thống quản lý firewall tập trung cho doanh nghiệp, cho phép kiểm soát truy cập mạng theo domain/IP whitelist với chế độ **default-deny**.

---

## 🏗️ Kiến trúc Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Flask Server                          │   │
│  │  • MongoDB (agents, whitelist, logs, groups)            │   │
│  │  • REST API + WebSocket (real-time updates)             │   │
│  │  • JWT Authentication                                    │   │
│  │  • Web Dashboard (Bootstrap + JS)                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    HTTPS/WSS │ (Sync whitelist, logs, heartbeat)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT (Windows Client)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │PacketSniffer │  │ Whitelist    │  │   Firewall Manager   │  │
│  │(Scapy)       │→ │ Manager      │→ │   (netsh advfirewall)│  │
│  │DNS/HTTP/TLS  │  │ (sync+check) │  │   allow/block rules  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  DNS Resolver│  │  Log Sender  │  │  GUI (CustomTkinter) │  │
│  │  (dnspython) │  │  (batch)     │  │  Dashboard + Views   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu trúc Project

### Agent (`/agent`) - Python Desktop App
```
agent/
├── core/               # Lifecycle, Agent state, Token management
│   ├── agent.py        # Agent singleton, device ID, state
│   ├── lifecycle.py    # Init/cleanup components
│   ├── token_manager.py# JWT access/refresh tokens
│   └── handlers.py     # Domain detection handler
│
├── capture/            # Network packet capture
│   ├── sniffer.py      # Scapy packet capture (DNS, HTTP, TLS SNI)
│   ├── extractors.py   # Extract domain from packets
│   └── scapy_config.py # WinPcap/Npcap configuration
│
├── firewall/           # Windows Firewall control
│   ├── manager.py      # High-level: setup whitelist firewall
│   ├── policy.py       # Default-deny policy (block all, allow whitelist)
│   ├── rules.py        # Create/remove netsh rules
│   └── utils.py        # IP validation, essential IPs
│
├── whitelist/          # Whitelist management
│   ├── manager.py      # Sync with server, check allowed
│   ├── state.py        # In-memory state (domains, patterns, IPs)
│   ├── sync.py         # HTTP sync với server
│   └── monitor.py      # Periodic sync monitor
│
├── network/            # DNS utilities
│   └── dns_resolver.py # Async DNS resolution (dnspython, aiodns)
│
├── cache/              # Caching
│   └── lru_cache.py    # DNS cache với TTL
│
├── config/             # Configuration
│   ├── loader.py       # Load from file/env
│   ├── defaults.py     # Default config values
│   └── validator.py    # Validate config
│
├── gui/                # CustomTkinter GUI
│   ├── app.py          # Main app window
│   ├── views/          # Dashboard, Whitelist, Firewall, Logs views
│   └── controllers/    # Agent, Whitelist controllers
│
├── logging_module/     # Log shipping
│   └── sender.py       # Batch send logs to server
│
├── services/           # Background services
│   ├── heartbeat.py    # Heartbeat to server
│   └── windows_service.py # Windows service wrapper
│
└── utils/              # Utilities
    ├── ip_detector.py  # Detect local IP, admin privileges
    └── error_handler.py# Critical error handling
```

### Server (`/server`) - Flask REST API
```
server/
├── app.py              # Flask app factory, routes registration
├── docker-compose.yml  # MongoDB + Server containers
│
├── controllers/        # HTTP endpoints
│   ├── agent_controller.py    # /api/agents/*
│   ├── whitelist_controller.py# /api/whitelist/*
│   ├── log_controller.py      # /api/logs/*
│   ├── group_controller.py    # /api/groups/*
│   └── auth_controller.py     # /api/auth/* (JWT)
│
├── models/             # MongoDB models
│   ├── agent_model.py     # Agent documents
│   ├── whitelist_model.py # Whitelist entries
│   ├── log_model.py       # Traffic logs
│   └── group_model.py     # Agent groups
│
├── services/           # Business logic
│   ├── agent_service.py
│   ├── whitelist_service.py
│   └── auth_service.py
│
├── middleware/         # Auth middleware
│   └── auth.py         # JWT validation decorators
│
└── views/              # Web dashboard
    ├── templates/      # Jinja2 HTML
    └── static/         # CSS, JS
```

---

## 🔄 Luồng Hoạt động Chính

### 1. Agent Startup
```
1. Load config (agent_config.json)
2. Generate device_id (hardware hash)
3. Register với server → nhận agent_id + JWT tokens
4. Initialize components:
   - WhitelistManager (sync từ server)
   - FirewallManager (setup default-deny)
   - PacketSniffer (capture traffic)
   - LogSender (batch logs)
   - Heartbeat service
5. Start GUI (nếu có)
```

### 2. Traffic Flow (Hiện tại - CÓ VẤN ĐỀ RACE CONDITION)
```
[App] → [Internet]
           ↓
    PacketSniffer bắt packet
           ↓
    Extract domain từ DNS/HTTP/SNI
           ↓
    Check WhitelistState
    ┌──────┴──────┐
 ALLOWED       BLOCKED
    ↓              ↓
 (đã đi rồi)   Log + Alert
```

**Vấn đề**: Packet đã đi qua rồi mới check → không chặn được thực sự.

### 3. Whitelist Sync
```
Agent                           Server
  │                               │
  │── GET /api/whitelist/agent-sync ──→│
  │   (JWT token, since_datetime) │
  │                               │
  │←── domains[], ips[], patterns[] ──│
  │                               │
  ├─ Update WhitelistState        │
  └─ Update Firewall Rules        │
```

---

## 🔐 Authentication Flow

```
1. Agent Register:
   POST /api/agents/register
   Body: {hostname, device_id, os_info}
   Response: {agent_id, access_token, refresh_token}

2. API Calls:
   Header: Authorization: Bearer <access_token>

3. Token Refresh:
   POST /api/auth/refresh
   Body: {refresh_token}
   Response: {access_token, refresh_token}
```

---

## 📊 Data Models

### Whitelist Entry
```json
{
  "type": "domain|ip|url|port|process",
  "value": "*.example.com",
  "category": "productivity|social|...",
  "priority": "high|normal|low",
  "scope": "global|group",
  "group_id": "...",
  "is_active": true,
  "added_date": "2025-12-18T10:00:00+07:00",
  "expiry_date": null
}
```

### Agent
```json
{
  "agent_id": "uuid",
  "hostname": "PC-001",
  "device_id": "hardware-hash",
  "status": "online|offline",
  "last_heartbeat": "...",
  "group_id": "...",
  "os_info": {...}
}
```

---

## ⚠️ Vấn đề Hiện tại & Giải pháp DNS Proxy

### Vấn đề:
1. **Race condition**: Traffic đi trước, check sau
2. **Multi-IP domains**: CDN trả IP khác nhau, firewall rules lỗi thời
3. **DoH/DoT bypass**: User có thể dùng DNS over HTTPS
4. **Không kiểm soát DNS**: Không biết IP nào sẽ được truy cập

### Giải pháp (DNS Proxy/Sinkhole):
```
[App] → DNS Query → [127.0.0.1:53 - Agent DNS Proxy]
                           ↓
                    Check Whitelist
                    ┌──────┴──────┐
                 ALLOWED        DENIED
                    ↓              ↓
            Forward upstream   NXDOMAIN
                    ↓
            Get A/AAAA records
                    ↓
            Add IP → Firewall (BLOCKING)
                    ↓
            Return DNS response
                    ↓
            [App] connect to IP (đã được allow)
```

**Ưu điểm**:
- Chặn từ bước DNS (không có race condition)
- Biết chính xác IP nào sẽ được truy cập
- Quản lý TTL tự động
- Block DoH/DoT bypass

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Agent | Python 3.10+, CustomTkinter, Scapy, dnspython |
| Server | Flask, MongoDB, Flask-SocketIO, PyJWT |
| Web UI | Bootstrap 5, Vanilla JS |
| Firewall | Windows netsh advfirewall |
| Packaging | PyInstaller |

---

## 📋 Config Example (`agent_config.json`)
```json
{
  "server": {
    "url": "https://firewall-server.local:5000",
    "connect_timeout": 10,
    "read_timeout": 30
  },
  "firewall": {
    "enabled": true,
    "mode": "whitelist",
    "rule_prefix": "FirewallController"
  },
  "whitelist": {
    "sync_interval": 60,
    "cache_ttl": 300
  },
  "logging": {
    "level": "INFO",
    "batch_size": 100,
    "send_interval": 5
  }
}
```

---

## 📈 Roadmap (DNS Proxy Refactor)

| Phase | Mô tả | Ưu tiên |
|-------|-------|---------|
| 1 | Architecture Design | ✅ Đang làm |
| 2 | DNS Proxy Core (listener, handler, cache) | High |
| 3 | Network Manager (auto DNS config) | High |
| 4 | DoH/DoT Blocking | High |
| 5 | Integration với existing code | Medium |
| 6 | GUI Updates | Medium |
| 7 | Server API Updates | Low |
| 8 | Testing | High |

---

## 📝 Key Files để đọc hiểu project

1. **Entry points**: `agent/agent_gui.py`, `server/app.py`
2. **Core logic**: `agent/core/lifecycle.py`, `agent/whitelist/manager.py`
3. **Firewall**: `agent/firewall/manager.py`, `agent/firewall/policy.py`
4. **Packet capture**: `agent/capture/sniffer.py`
5. **Config**: `agent/config/loader.py`, `agent_config.json`
6. **API**: `server/controllers/whitelist_controller.py`
