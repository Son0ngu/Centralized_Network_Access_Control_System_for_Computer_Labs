# 🎯 COMPLETE USE CASE DIAGRAM - Firewall Controller System

## Hệ thống Firewall Controller - Use Case Diagram Hoàn Chỉnh

```mermaid
flowchart TB
    subgraph ACTORS["👥 ACTORS"]
        Admin["👨‍💼 Administrator<br/>Quản trị viên hệ thống"]
        EndUser["👤 End User<br/>Người dùng cuối"]
        Agent["🤖 Agent<br/>Phần mềm trên máy client"]
        System["⚙️ System<br/>Tác vụ tự động"]
    end

    subgraph SERVER_SYSTEM["🖥️ SERVER SYSTEM"]
        
        subgraph AUTH["🔐 Authentication & Authorization"]
            UC_S1["UC-S1: Quản lý API Key"]
            UC_S2["UC-S2: Xác thực JWT Token"]
            UC_S3["UC-S3: Phân quyền truy cập"]
        end
        
        subgraph AGENT_MGMT["📡 Agent Management"]
            UC_S4["UC-S4: Đăng ký Agent mới"]
            UC_S5["UC-S5: Xem danh sách Agents"]
            UC_S6["UC-S6: Xem chi tiết Agent"]
            UC_S7["UC-S7: Cập nhật thông tin Agent"]
            UC_S8["UC-S8: Xóa/Vô hiệu hóa Agent"]
            UC_S9["UC-S9: Nhận Heartbeat"]
        end
        
        subgraph WHITELIST_MGMT["📋 Whitelist Management"]
            UC_S10["UC-S10: Tạo Whitelist Entry"]
            UC_S11["UC-S11: Xem Whitelist"]
            UC_S12["UC-S12: Cập nhật Whitelist"]
            UC_S13["UC-S13: Xóa Whitelist Entry"]
            UC_S14["UC-S14: Đồng bộ Whitelist cho Agent"]
        end
        
        subgraph GROUP_MGMT["👥 Group Management"]
            UC_S15["UC-S15: Tạo Group"]
            UC_S16["UC-S16: Gán Agent vào Group"]
            UC_S17["UC-S17: Gán Whitelist cho Group"]
            UC_S18["UC-S18: Xem/Xóa Group"]
        end
        
        subgraph LOG_MGMT["📊 Log Management"]
            UC_S19["UC-S19: Nhận Logs từ Agent"]
            UC_S20["UC-S20: Xem Logs"]
            UC_S21["UC-S21: Lọc/Tìm kiếm Logs"]
            UC_S22["UC-S22: Xuất Logs"]
            UC_S23["UC-S23: Xem Dashboard thống kê"]
        end
        
        subgraph REALTIME["⚡ Real-time Updates"]
            UC_S24["UC-S24: Phát sự kiện Socket.IO"]
            UC_S25["UC-S25: Cập nhật Dashboard live"]
        end
    end

    subgraph AGENT_SYSTEM["🖥️ AGENT SYSTEM"]
        
        subgraph LIFECYCLE["🔄 Agent Lifecycle"]
            UC_A1["UC-A1: Khởi động Agent"]
            UC_A2["UC-A2: Đăng ký với Server"]
            UC_A3["UC-A3: Dừng Agent"]
            UC_A4["UC-A4: Gửi Heartbeat"]
        end
        
        subgraph NETWORK_MON["🌐 Network Monitoring"]
            UC_A5["UC-A5: Bắt gói tin mạng"]
            UC_A6["UC-A6: Trích xuất Domain/IP"]
            UC_A7["UC-A7: Phân giải DNS"]
        end
        
        subgraph FIREWALL_CTRL["🛡️ Firewall Control"]
            UC_A8["UC-A8: Kiểm tra Whitelist"]
            UC_A9["UC-A9: Áp dụng Firewall Mode"]
            UC_A10["UC-A10: Tạo Rule cho phép"]
            UC_A11["UC-A11: Chặn kết nối"]
            UC_A12["UC-A12: Bật Default Deny Policy"]
        end
        
        subgraph SYNC_OPS["🔄 Synchronization"]
            UC_A13["UC-A13: Đồng bộ Whitelist"]
            UC_A14["UC-A14: Gửi Logs lên Server"]
            UC_A15["UC-A15: Cập nhật cấu hình"]
        end
        
        subgraph GUI_OPS["🖼️ GUI Operations"]
            UC_A16["UC-A16: Xem trạng thái Agent"]
            UC_A17["UC-A17: Thay đổi Firewall Mode"]
            UC_A18["UC-A18: Xem Logs local"]
            UC_A19["UC-A19: Cấu hình kết nối Server"]
        end
    end

    %% Admin interactions with Server
    Admin --> UC_S1
    Admin --> UC_S5
    Admin --> UC_S6
    Admin --> UC_S7
    Admin --> UC_S8
    Admin --> UC_S10
    Admin --> UC_S11
    Admin --> UC_S12
    Admin --> UC_S13
    Admin --> UC_S15
    Admin --> UC_S16
    Admin --> UC_S17
    Admin --> UC_S18
    Admin --> UC_S20
    Admin --> UC_S21
    Admin --> UC_S22
    Admin --> UC_S23

    %% End User interactions with Agent GUI
    EndUser --> UC_A16
    EndUser --> UC_A17
    EndUser --> UC_A18
    EndUser --> UC_A19

    %% Agent interactions with Server
    Agent --> UC_S4
    Agent --> UC_S9
    Agent --> UC_S14
    Agent --> UC_S19

    %% System automatic interactions
    System --> UC_S24
    System --> UC_S25
    System --> UC_A4
    System --> UC_A5
    System --> UC_A13
    System --> UC_A14

    %% Internal relationships
    UC_S4 -.->|includes| UC_S2
    UC_S9 -.->|includes| UC_S2
    UC_S14 -.->|includes| UC_S2
    UC_S19 -.->|includes| UC_S2
    
    UC_A1 -.->|includes| UC_A2
    UC_A2 -.->|includes| UC_A13
    UC_A5 -.->|includes| UC_A6
    UC_A6 -.->|includes| UC_A7
    UC_A6 -.->|includes| UC_A8
    UC_A8 -.->|includes| UC_A9
    UC_A9 -.->|extends| UC_A10
    UC_A9 -.->|extends| UC_A11

    classDef actorStyle fill:#E1F5FE,stroke:#01579B,stroke-width:2px
    classDef serverStyle fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef agentStyle fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    classDef authStyle fill:#FCE4EC,stroke:#880E4F,stroke-width:2px
    
    class Admin,EndUser,Agent,System actorStyle
    class UC_S1,UC_S2,UC_S3 authStyle
```

---

## 📋 Chi tiết từng Use Case

### 🖥️ SERVER USE CASES

```mermaid
flowchart LR
    subgraph UC_S1_DETAIL["UC-S1: Quản lý API Key"]
        direction TB
        S1_1["1. Admin truy cập trang API Keys"]
        S1_2["2. Tạo API Key mới với tên và permissions"]
        S1_3["3. Server sinh key: fc_<random_hex>"]
        S1_4["4. Lưu hash SHA-256 vào MongoDB"]
        S1_5["5. Trả về plaintext key (chỉ 1 lần)"]
        S1_6["6. Admin copy và cấu hình cho Agent"]
        
        S1_1 --> S1_2 --> S1_3 --> S1_4 --> S1_5 --> S1_6
    end
```

```mermaid
flowchart LR
    subgraph UC_S4_DETAIL["UC-S4: Đăng ký Agent mới"]
        direction TB
        S4_1["1. Agent gửi POST /api/agents/register"]
        S4_2["2. Middleware kiểm tra X-API-Key header"]
        S4_3["3. Validate API Key trong database"]
        S4_4["4. Kiểm tra permission 'register'"]
        S4_5["5. Tạo/Cập nhật Agent trong MongoDB"]
        S4_6["6. Sinh JWT tokens (access + refresh)"]
        S4_7["7. Trả về agent_id và JWT tokens"]
        S4_8["8. Emit socket event 'agent_registered'"]
        
        S4_1 --> S4_2 --> S4_3 --> S4_4 --> S4_5 --> S4_6 --> S4_7 --> S4_8
    end
```

```mermaid
flowchart LR
    subgraph UC_S14_DETAIL["UC-S14: Đồng bộ Whitelist cho Agent"]
        direction TB
        S14_1["1. Agent gửi GET /api/whitelist/agent-sync"]
        S14_2["2. Server xác thực JWT token"]
        S14_3["3. Lấy group_id của Agent"]
        S14_4["4. Query whitelist entries của group"]
        S14_5["5. Format response với domains, IPs, patterns"]
        S14_6["6. Trả về whitelist data + checksum"]
        
        S14_1 --> S14_2 --> S14_3 --> S14_4 --> S14_5 --> S14_6
    end
```

```mermaid
flowchart LR
    subgraph UC_S19_DETAIL["UC-S19: Nhận Logs từ Agent"]
        direction TB
        S19_1["1. Agent gửi POST /api/logs/receive"]
        S19_2["2. Server xác thực JWT token"]
        S19_3["3. Parse batch logs từ request body"]
        S19_4["4. Validate và enrich log data"]
        S19_5["5. Insert vào MongoDB collection"]
        S19_6["6. Emit socket event 'new_logs'"]
        S19_7["7. Cập nhật dashboard statistics"]
        
        S19_1 --> S19_2 --> S19_3 --> S19_4 --> S19_5 --> S19_6 --> S19_7
    end
```

---

### 🤖 AGENT USE CASES

```mermaid
flowchart LR
    subgraph UC_A1_DETAIL["UC-A1: Khởi động Agent"]
        direction TB
        A1_1["1. Load config từ agent_config.json"]
        A1_2["2. Validate configuration"]
        A1_3["3. Kiểm tra Admin privileges"]
        A1_4["4. Initialize components:<br/>- TokenManager<br/>- LogSender<br/>- WhitelistManager<br/>- FirewallManager<br/>- PacketSniffer<br/>- HeartbeatSender"]
        A1_5["5. Đăng ký với Server"]
        A1_6["6. Đồng bộ Whitelist lần đầu"]
        A1_7["7. Bắt đầu capture packets"]
        A1_8["8. Gửi lifecycle log 'STARTUP'"]
        
        A1_1 --> A1_2 --> A1_3 --> A1_4 --> A1_5 --> A1_6 --> A1_7 --> A1_8
    end
```

```mermaid
flowchart LR
    subgraph UC_A5_DETAIL["UC-A5: Bắt gói tin mạng"]
        direction TB
        A5_1["1. PacketSniffer chạy trên background thread"]
        A5_2["2. Scapy sniff với filter:<br/>port 80, 443, 53"]
        A5_3["3. Với mỗi packet, gọi callback"]
        A5_4["4. Trích xuất thông tin:<br/>- HTTP Host header<br/>- HTTPS SNI<br/>- DNS Query"]
        A5_5["5. Resolve DNS nếu cần"]
        A5_6["6. Gửi record đến handler"]
        
        A5_1 --> A5_2 --> A5_3 --> A5_4 --> A5_5 --> A5_6
    end
```

```mermaid
flowchart LR
    subgraph UC_A9_DETAIL["UC-A9: Áp dụng Firewall Mode"]
        direction TB
        A9_1["1. Nhận domain/IP từ packet handler"]
        A9_2["2. Kiểm tra trong whitelist"]
        A9_3{"3. Mode hiện tại?"}
        
        A9_4["MONITOR:<br/>Log only, không block"]
        A9_5["WHITELIST_ONLY:<br/>Allow nếu trong whitelist<br/>Block nếu không"]
        A9_6["BLOCK:<br/>Block tất cả không trong whitelist"]
        A9_7["WARN:<br/>Allow nhưng log warning"]
        
        A9_8["4. Thực thi action tương ứng"]
        A9_9["5. Gửi log lên Server"]
        
        A9_1 --> A9_2 --> A9_3
        A9_3 -->|monitor| A9_4
        A9_3 -->|whitelist_only| A9_5
        A9_3 -->|block| A9_6
        A9_3 -->|warn| A9_7
        A9_4 --> A9_8
        A9_5 --> A9_8
        A9_6 --> A9_8
        A9_7 --> A9_8
        A9_8 --> A9_9
    end
```

```mermaid
flowchart LR
    subgraph UC_A13_DETAIL["UC-A13: Đồng bộ Whitelist"]
        direction TB
        A13_1["1. WhitelistMonitor trigger sync"]
        A13_2["2. Build request với agent_id"]
        A13_3["3. Gọi GET /api/whitelist/agent-sync"]
        A13_4["4. So sánh checksum với local"]
        A13_5{"5. Có thay đổi?"}
        A13_6["6a. Cập nhật WhitelistState"]
        A13_7["6b. Cập nhật Firewall rules"]
        A13_8["Skip - không có thay đổi"]
        
        A13_1 --> A13_2 --> A13_3 --> A13_4 --> A13_5
        A13_5 -->|Yes| A13_6 --> A13_7
        A13_5 -->|No| A13_8
    end
```

---

## 🔄 Complete Interaction Flow

```mermaid
sequenceDiagram
    autonumber
    
    box rgb(230, 245, 255) CLIENT SIDE
        participant User as 👤 End User
        participant GUI as 🖼️ Agent GUI
        participant Agent as 🤖 Agent Core
        participant Sniffer as 📡 Packet Sniffer
        participant FW as 🛡️ Firewall Manager
    end
    
    box rgb(255, 243, 224) SERVER SIDE
        participant API as 🌐 Flask API
        participant Auth as 🔐 Auth Middleware
        participant DB as 🗄️ MongoDB
        participant Socket as ⚡ Socket.IO
    end
    
    box rgb(232, 245, 233) ADMIN SIDE
        participant Admin as 👨‍💼 Administrator
        participant Web as 🖥️ Web Dashboard
    end

    Note over Admin, Web: === PHASE 1: SETUP ===
    
    Admin->>Web: Truy cập Server Dashboard
    Admin->>Web: Tạo API Key mới
    Web->>API: POST /api-keys
    API->>DB: Lưu hash(api_key)
    API-->>Web: Trả về plaintext key
    Admin->>Admin: Copy API Key

    Note over User, FW: === PHASE 2: AGENT STARTUP ===
    
    User->>GUI: Khởi động Agent
    GUI->>Agent: main()
    Agent->>Agent: Load config (api_key trong config)
    Agent->>Agent: Validate configuration
    Agent->>Agent: Initialize components
    
    Agent->>API: POST /api/agents/register<br/>Header: X-API-Key
    API->>Auth: Validate API Key
    Auth->>DB: Find by hash(api_key)
    DB-->>Auth: Key document
    Auth->>Auth: Check permissions
    Auth-->>API: Valid ✓
    API->>DB: Create/Update Agent
    API->>API: Generate JWT tokens
    API-->>Agent: {agent_id, jwt_tokens}
    API->>Socket: Emit 'agent_registered'
    Socket-->>Web: Real-time update
    
    Agent->>API: GET /api/whitelist/agent-sync<br/>Header: Authorization: Bearer JWT
    API->>Auth: Validate JWT
    Auth-->>API: Valid ✓
    API->>DB: Query whitelist for agent's group
    API-->>Agent: {domains, ips, patterns}
    Agent->>FW: Setup firewall rules
    
    Agent->>Sniffer: Start packet capture

    Note over User, FW: === PHASE 3: RUNTIME OPERATION ===
    
    loop Mỗi 20 giây
        Agent->>API: POST /api/agents/heartbeat<br/>Header: Authorization: Bearer JWT
        API->>DB: Update last_seen
        API-->>Agent: OK
        API->>Socket: Emit 'agent_heartbeat'
        Socket-->>Web: Update agent status
    end
    
    loop Mỗi 60 giây
        Agent->>API: GET /api/whitelist/agent-sync
        API-->>Agent: Whitelist data
        Agent->>FW: Sync firewall rules nếu có thay đổi
    end
    
    Note over User, FW: === PHASE 4: TRAFFIC DETECTION ===
    
    User->>User: Truy cập google.com
    Sniffer->>Sniffer: Capture DNS query
    Sniffer->>Agent: {domain: "google.com", dest_ip: "142.250.x.x"}
    Agent->>Agent: Check whitelist
    
    alt Domain trong Whitelist
        Agent->>Agent: action = ALLOWED
        Agent->>FW: Ensure allow rule exists
    else Domain KHÔNG trong Whitelist
        alt Mode = monitor
            Agent->>Agent: action = MONITORED
        else Mode = whitelist_only/block
            Agent->>Agent: action = BLOCKED
            Agent->>FW: Block connection (nếu có quyền admin)
        else Mode = warn
            Agent->>Agent: action = WARNING
        end
    end
    
    Agent->>API: POST /api/logs/receive<br/>{domain, action, timestamp, ...}
    API->>DB: Insert log
    API->>Socket: Emit 'new_logs'
    Socket-->>Web: Real-time log update
    
    Note over Admin, Web: === PHASE 5: ADMIN MONITORING ===
    
    Admin->>Web: Xem Dashboard
    Web->>API: GET /api/logs?limit=100
    API->>DB: Query logs
    API-->>Web: Logs data
    Web->>Web: Hiển thị logs real-time
    
    Admin->>Web: Thêm domain vào whitelist
    Web->>API: POST /api/whitelist
    API->>DB: Insert whitelist entry
    API->>Socket: Emit 'whitelist_updated'
    
    Note over User, FW: === PHASE 6: AGENT SHUTDOWN ===
    
    User->>GUI: Tắt Agent
    GUI->>Agent: stop()
    Agent->>Sniffer: Stop capture
    Agent->>FW: Cleanup rules (nếu cấu hình)
    Agent->>API: POST /api/logs/receive<br/>{event_type: "shutdown"}
    API->>Socket: Emit 'agent_offline'
    Socket-->>Web: Update agent status = offline
```

---

## 📊 Use Case Matrix

| ID | Use Case | Actor | Server/Agent | Priority |
|----|----------|-------|--------------|----------|
| **UC-S1** | Quản lý API Key | Admin | Server | High |
| **UC-S2** | Xác thực JWT Token | System | Server | High |
| **UC-S3** | Phân quyền truy cập | System | Server | High |
| **UC-S4** | Đăng ký Agent mới | Agent | Server | High |
| **UC-S5** | Xem danh sách Agents | Admin | Server | Medium |
| **UC-S6** | Xem chi tiết Agent | Admin | Server | Medium |
| **UC-S7** | Cập nhật thông tin Agent | Admin | Server | Low |
| **UC-S8** | Xóa/Vô hiệu hóa Agent | Admin | Server | Low |
| **UC-S9** | Nhận Heartbeat | Agent | Server | High |
| **UC-S10** | Tạo Whitelist Entry | Admin | Server | High |
| **UC-S11** | Xem Whitelist | Admin | Server | Medium |
| **UC-S12** | Cập nhật Whitelist | Admin | Server | Medium |
| **UC-S13** | Xóa Whitelist Entry | Admin | Server | Medium |
| **UC-S14** | Đồng bộ Whitelist cho Agent | Agent | Server | High |
| **UC-S15** | Tạo Group | Admin | Server | Medium |
| **UC-S16** | Gán Agent vào Group | Admin | Server | Medium |
| **UC-S17** | Gán Whitelist cho Group | Admin | Server | Medium |
| **UC-S18** | Xem/Xóa Group | Admin | Server | Low |
| **UC-S19** | Nhận Logs từ Agent | Agent | Server | High |
| **UC-S20** | Xem Logs | Admin | Server | High |
| **UC-S21** | Lọc/Tìm kiếm Logs | Admin | Server | Medium |
| **UC-S22** | Xuất Logs | Admin | Server | Low |
| **UC-S23** | Xem Dashboard thống kê | Admin | Server | High |
| **UC-S24** | Phát sự kiện Socket.IO | System | Server | High |
| **UC-S25** | Cập nhật Dashboard live | System | Server | Medium |
| **UC-A1** | Khởi động Agent | User/System | Agent | High |
| **UC-A2** | Đăng ký với Server | Agent | Agent | High |
| **UC-A3** | Dừng Agent | User | Agent | High |
| **UC-A4** | Gửi Heartbeat | System | Agent | High |
| **UC-A5** | Bắt gói tin mạng | System | Agent | High |
| **UC-A6** | Trích xuất Domain/IP | System | Agent | High |
| **UC-A7** | Phân giải DNS | System | Agent | Medium |
| **UC-A8** | Kiểm tra Whitelist | System | Agent | High |
| **UC-A9** | Áp dụng Firewall Mode | System | Agent | High |
| **UC-A10** | Tạo Rule cho phép | System | Agent | High |
| **UC-A11** | Chặn kết nối | System | Agent | High |
| **UC-A12** | Bật Default Deny Policy | System | Agent | Medium |
| **UC-A13** | Đồng bộ Whitelist | System | Agent | High |
| **UC-A14** | Gửi Logs lên Server | System | Agent | High |
| **UC-A15** | Cập nhật cấu hình | User | Agent | Low |
| **UC-A16** | Xem trạng thái Agent | User | Agent | Medium |
| **UC-A17** | Thay đổi Firewall Mode | User | Agent | Medium |
| **UC-A18** | Xem Logs local | User | Agent | Medium |
| **UC-A19** | Cấu hình kết nối Server | User | Agent | Medium |

---

## 🎯 Actor Descriptions

| Actor | Type | Description |
|-------|------|-------------|
| **👨‍💼 Administrator** | Human | Quản trị viên hệ thống, truy cập Server Dashboard để quản lý agents, whitelist, xem logs |
| **👤 End User** | Human | Người dùng cuối sử dụng máy tính có cài Agent, tương tác qua Agent GUI |
| **🤖 Agent** | System | Phần mềm chạy trên máy client, tự động thực hiện các tác vụ bảo mật |
| **⚙️ System** | System | Các tác vụ tự động chạy theo lịch (heartbeat, sync, packet capture) |

---

## 🔗 Use Case Relationships

```mermaid
flowchart TB
    subgraph INCLUDES["«includes» Relationships"]
        UC_A1["UC-A1: Khởi động Agent"] -->|includes| UC_A2["UC-A2: Đăng ký với Server"]
        UC_A2 -->|includes| UC_A13["UC-A13: Đồng bộ Whitelist"]
        UC_A5["UC-A5: Bắt gói tin"] -->|includes| UC_A6["UC-A6: Trích xuất Domain"]
        UC_A6 -->|includes| UC_A8["UC-A8: Kiểm tra Whitelist"]
        UC_S4["UC-S4: Đăng ký Agent"] -->|includes| UC_S2["UC-S2: Xác thực JWT"]
    end
    
    subgraph EXTENDS["«extends» Relationships"]
        UC_A9["UC-A9: Áp dụng Mode"] -.->|extends| UC_A10["UC-A10: Tạo Rule cho phép"]
        UC_A9 -.->|extends| UC_A11["UC-A11: Chặn kết nối"]
        UC_S20["UC-S20: Xem Logs"] -.->|extends| UC_S21["UC-S21: Lọc Logs"]
        UC_S20 -.->|extends| UC_S22["UC-S22: Xuất Logs"]
    end
```

---

## 📝 Preconditions & Postconditions

### UC-S4: Đăng ký Agent mới

| Aspect | Description |
|--------|-------------|
| **Preconditions** | - Server đang chạy<br/>- API Key hợp lệ đã được tạo<br/>- Agent có kết nối mạng đến Server |
| **Main Flow** | 1. Agent gửi thông tin đăng ký<br/>2. Server xác thực API Key<br/>3. Server tạo/cập nhật Agent record<br/>4. Server trả về JWT tokens |
| **Postconditions** | - Agent có agent_id và JWT tokens<br/>- Agent hiển thị trong danh sách trên Server<br/>- Agent có thể gọi các API khác |
| **Exceptions** | - API Key không hợp lệ → 401 Unauthorized<br/>- Server không khả dụng → Retry với exponential backoff |

### UC-A9: Áp dụng Firewall Mode

| Aspect | Description |
|--------|-------------|
| **Preconditions** | - Agent đã khởi động thành công<br/>- Whitelist đã được đồng bộ<br/>- Firewall mode đã được cấu hình |
| **Main Flow** | 1. Nhận domain/IP từ packet<br/>2. Kiểm tra trong whitelist<br/>3. Xác định action theo mode<br/>4. Thực thi action<br/>5. Gửi log |
| **Postconditions** | - Traffic được xử lý theo policy<br/>- Log được gửi lên Server<br/>- Firewall rules được cập nhật (nếu cần) |
| **Exceptions** | - Không có quyền admin → Chỉ log, không block<br/>- Server không khả dụng → Queue logs locally |

---

*Document generated: December 2025*
*System: Firewall Controller Enhanced v2.2*
