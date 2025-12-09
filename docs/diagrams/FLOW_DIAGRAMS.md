# 🔥 Firewall Controller - Flow Diagrams

> Complete system flow diagrams for Agent and Server components

---

## Table of Contents

- [🔥 Firewall Controller - Flow Diagrams](#-firewall-controller---flow-diagrams)
  - [Table of Contents](#-table-of-contents)
  - [1. System Overview](#1-system-overview)
  - [2. Agent Startup Flow](#2-agent-startup-flow)
  - [3. Agent Main Loop](#3-agent-main-loop)
  - [4. Packet Detection \& Processing](#4-packet-detection--processing)
  - [5. Firewall Mode Decision Logic](#5-firewall-mode-decision-logic)
  - [6. Whitelist Synchronization](#6-whitelist-synchronization)
  - [7. Server API Flow](#7-server-api-flow)
  - [8. Authentication Flow](#8-authentication-flow)
  - [9. Heartbeat \& Status Flow](#9-heartbeat--status-flow)
  - [10. Agent Shutdown Flow](#10-agent-shutdown-flow)
  - [11. GUI Event Flow](#11-gui-event-flow)
  - [12. Complete System Interaction](#12-complete-system-interaction)
  - [📊 Mode Comparison Table](#-mode-comparison-table)
  - [🔧 Component Dependencies](#-component-dependencies)

---

## 1. System Overview

```mermaid
flowchart TB
    subgraph "🖥️ Agent Side"
        GUI[/"🖼️ Agent GUI<br/>(CustomTkinter)"/]
        AGENT["🤖 Agent Core"]
        SNIFFER["📡 Packet Sniffer<br/>(Scapy)"]
        FIREWALL["🛡 Firewall Manager<br/>(Windows Firewall)"]
        WHITELIST["Whitelist Manager"]
        LOGSENDER["📤 Log Sender"]
        HEARTBEAT["💓 Heartbeat Sender"]
    end

    subgraph "☁️ Server Side"
        FLASK["🌐 Flask Server"]
        API["REST API"]
        MONGODB[("🗄️ MongoDB")]
        SOCKETIO["Socket.IO"]
        WEBUI[/"🖥️ Web Dashboard"/]
    end

    subgraph "👤 Users"
        ADMIN["👨‍💼 Administrator"]
        ENDUSER["👤 End User"]
    end

    ADMIN --> WEBUI
    ENDUSER --> GUI
    
    GUI <--> AGENT
    AGENT --> SNIFFER
    AGENT --> FIREWALL
    AGENT --> WHITELIST
    AGENT --> LOGSENDER
    AGENT --> HEARTBEAT
    
    LOGSENDER --> API
    HEARTBEAT --> API
    WHITELIST --> API
    
    FLASK --> API
    FLASK --> SOCKETIO
    API <--> MONGODB
    SOCKETIO --> WEBUI
    
    style GUI fill:#4CAF50,color:#fff
    style WEBUI fill:#2196F3,color:#fff
    style MONGODB fill:#4DB33D,color:#fff
    style FIREWALL fill:#FF5722,color:#fff
```

---

## 2. Agent Startup Flow

```mermaid
flowchart TD
    START([Agent Start]) --> LOAD_CONFIG["📄 Load Configuration<br/>(agent_config.json)"]
    
    LOAD_CONFIG --> VALIDATE["Validate Configuration"]
    VALIDATE --> |Invalid| ERROR_CONFIG["Log Error & Exit"]
    VALIDATE --> |Valid| CHECK_ADMIN{"🔐 Check Admin<br/>Privileges?"}
    
    CHECK_ADMIN --> |No Admin| WARN_ADMIN["⚠️ Warning: Limited Mode"]
    CHECK_ADMIN --> |Has Admin| INIT_COMPONENTS["🔧 Initialize Components"]
    WARN_ADMIN --> INIT_COMPONENTS
    
    subgraph "🔧 Component Initialization"
        INIT_COMPONENTS --> INIT_TOKEN["🔑 Init Token Manager"]
        INIT_TOKEN --> INIT_WHITELIST["Init Whitelist Manager"]
        INIT_WHITELIST --> INIT_FIREWALL{"🛡 Firewall Enabled?"}
        
        INIT_FIREWALL --> |Yes| SETUP_FW["Setup Firewall Rules"]
        INIT_FIREWALL --> |No| SKIP_FW["Skip Firewall Setup"]
        
        SETUP_FW --> INIT_SNIFFER
        SKIP_FW --> INIT_SNIFFER["📡 Init Packet Sniffer"]
        
        INIT_SNIFFER --> INIT_LOGSENDER["📤 Init Log Sender"]
        INIT_LOGSENDER --> INIT_HEARTBEAT["💓 Init Heartbeat Sender"]
    end
    
    INIT_HEARTBEAT --> REGISTER["Register with Server"]
    
    REGISTER --> |Success| SYNC_WL["Sync Whitelist"]
    REGISTER --> |Fail| RETRY_REG{"🔁 Retry?"}
    
    RETRY_REG --> |Yes| REGISTER
    RETRY_REG --> |Max Retries| OFFLINE_MODE["📴 Offline Mode"]
    
    SYNC_WL --> START_SERVICES["▶️ Start All Services"]
    OFFLINE_MODE --> START_SERVICES
    
    subgraph "▶️ Start Services"
        START_SERVICES --> SVC_SNIFFER["Start Sniffer Thread"]
        SVC_SNIFFER --> SVC_LOGSENDER["Start Log Sender Thread"]
        SVC_LOGSENDER --> SVC_HEARTBEAT["Start Heartbeat Thread"]
        SVC_HEARTBEAT --> SVC_WHITELIST["Start Whitelist Sync Thread"]
    end
    
    SVC_WHITELIST --> SEND_STARTUP["📤 Send Startup Log"]
    SEND_STARTUP --> RUNNING([🟢 Agent Running])
    
    style START fill:#4CAF50,color:#fff
    style RUNNING fill:#4CAF50,color:#fff
    style ERROR_CONFIG fill:#f44336,color:#fff
    style OFFLINE_MODE fill:#FF9800,color:#fff
```

---

## 3. Agent Main Loop

```mermaid
flowchart TD
    RUNNING([🟢 Agent Running]) --> MAIN_LOOP{"Main Loop"}
    
    MAIN_LOOP --> CHECK_STOP{"🛑 Stop Signal?"}
    CHECK_STOP --> |Yes| SHUTDOWN["🔴 Initiate Shutdown"]
    CHECK_STOP --> |No| PROCESS_EVENTS
    
    subgraph "📨 Event Processing"
        PROCESS_EVENTS["Process Pending Events"]
        PROCESS_EVENTS --> CHECK_PACKETS{"📦 New Packets?"}
        CHECK_PACKETS --> |Yes| HANDLE_PACKET["Handle Packet"]
        CHECK_PACKETS --> |No| CHECK_LOGS
        
        HANDLE_PACKET --> CHECK_LOGS{"Logs to Send?"}
        CHECK_LOGS --> |Yes| SEND_LOGS["Send Log Batch"]
        CHECK_LOGS --> |No| CHECK_HB
        
        SEND_LOGS --> CHECK_HB{"💓 Heartbeat Due?"}
        CHECK_HB --> |Yes| SEND_HB["Send Heartbeat"]
        CHECK_HB --> |No| CHECK_SYNC
        
        SEND_HB --> CHECK_SYNC{"Sync Due?"}
        CHECK_SYNC --> |Yes| SYNC_WL["Sync Whitelist"]
        CHECK_SYNC --> |No| SLEEP
        
        SYNC_WL --> SLEEP["😴 Sleep 100ms"]
    end
    
    SLEEP --> MAIN_LOOP
    
    SHUTDOWN --> CLEANUP["Cleanup Resources"]
    CLEANUP --> SEND_SHUTDOWN["📤 Send Shutdown Log"]
    SEND_SHUTDOWN --> STOPPED([🔴 Agent Stopped])
    
    style RUNNING fill:#4CAF50,color:#fff
    style STOPPED fill:#f44336,color:#fff
    style MAIN_LOOP fill:#2196F3,color:#fff
```

---

## 4. Packet Detection & Processing

```mermaid
flowchart TD
    CAPTURE([📡 Packet Captured]) --> PARSE["Parse Packet"]
    
    PARSE --> GET_LAYERS["Extract Layers<br/>(IP, TCP, UDP)"]
    GET_LAYERS --> CHECK_TYPE{"Packet Type?"}
    
    CHECK_TYPE --> |DNS| EXTRACT_DNS["Extract DNS Query"]
    CHECK_TYPE --> |HTTP| EXTRACT_HTTP["Extract HTTP Host"]
    CHECK_TYPE --> |HTTPS| EXTRACT_SNI["Extract TLS SNI"]
    CHECK_TYPE --> |Other| SKIP["Skip Packet"]
    
    EXTRACT_DNS --> BUILD_RECORD
    EXTRACT_HTTP --> BUILD_RECORD
    EXTRACT_SNI --> BUILD_RECORD
    
    subgraph "Build Detection Record"
        BUILD_RECORD["Create Record"]
        BUILD_RECORD --> |domain| DOMAIN["domain: example.com"]
        BUILD_RECORD --> |dest_ip| DESTIP["dest_ip: 1.2.3.4"]
        BUILD_RECORD --> |src_ip| SRCIP["src_ip: 192.168.1.100"]
        BUILD_RECORD --> |protocol| PROTO["protocol: HTTPS"]
        BUILD_RECORD --> |port| PORT["port: 443"]
    end
    
    DOMAIN --> HANDLER["🎯 Domain Handler"]
    DESTIP --> HANDLER
    SRCIP --> HANDLER
    PROTO --> HANDLER
    PORT --> HANDLER
    
    HANDLER --> CHECK_WL{"Check Whitelist"}
    
    CHECK_WL --> DOMAIN_CHECK["Check Domain"]
    CHECK_WL --> IP_CHECK["Check IP"]
    
    DOMAIN_CHECK --> |Allowed| WL_ALLOWED["domain_allowed = true"]
    DOMAIN_CHECK --> |Not Found| WL_DOMAIN_DENY["domain_allowed = false"]
    
    IP_CHECK --> |Allowed| IP_ALLOWED["ip_allowed = true"]
    IP_CHECK --> |Not Found| IP_DENY["ip_allowed = false"]
    
    WL_ALLOWED --> DETERMINE_ACTION
    WL_DOMAIN_DENY --> DETERMINE_ACTION
    IP_ALLOWED --> DETERMINE_ACTION
    IP_DENY --> DETERMINE_ACTION
    
    DETERMINE_ACTION["🎯 Determine Action<br/>(Based on Mode)"]
    DETERMINE_ACTION --> LOG_ENTRY["Create Log Entry"]
    LOG_ENTRY --> QUEUE_LOG["📤 Queue for Sending"]
    QUEUE_LOG --> DONE([Processing Complete])
    
    SKIP --> DONE
    
    style CAPTURE fill:#9C27B0,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style WL_ALLOWED fill:#4CAF50,color:#fff
    style WL_DOMAIN_DENY fill:#f44336,color:#fff
```

---

## 5. Firewall Mode Decision Logic

```mermaid
flowchart TD
    START([🎯 Determine Action]) --> CHECK_ENABLED{"🛡 Firewall<br/>Enabled?"}
    
    CHECK_ENABLED --> |No| MONITOR_MODE["action = MONITORED<br/>level = INFO/WARNING"]
    CHECK_ENABLED --> |Yes| CHECK_MODE{"Firewall Mode?"}
    
    subgraph "Mode: MONITOR"
        CHECK_MODE --> |monitor| M_ACTION["action = MONITORED"]
        M_ACTION --> M_LEVEL{"Whitelisted?"}
        M_LEVEL --> |Yes| M_INFO["level = INFO"]
        M_LEVEL --> |No| M_WARN["level = WARNING"]
    end
    
    subgraph "🛡 Mode: WHITELIST_ONLY"
        CHECK_MODE --> |whitelist_only| WO_CHECK{"Whitelisted?"}
        WO_CHECK --> |Yes| WO_ALLOW["action = ALLOWED<br/>level = INFO"]
        WO_CHECK --> |No| WO_BLOCK["action = BLOCKED<br/>level = BLOCKED"]
    end
    
    subgraph "🚫 Mode: BLOCK"
        CHECK_MODE --> |block| B_CHECK{"Whitelisted?"}
        B_CHECK --> |Yes| B_ALLOW["action = ALLOWED<br/>level = INFO"]
        B_CHECK --> |No| B_BLOCK["action = BLOCKED<br/>level = BLOCKED"]
    end
    
    subgraph "⚠️ Mode: WARN"
        CHECK_MODE --> |warn| W_CHECK{"Whitelisted?"}
        W_CHECK --> |Yes| W_ALLOW["action = ALLOWED<br/>level = INFO"]
        W_CHECK --> |No| W_WARN["action = WARNING<br/>level = WARNING"]
    end
    
    MONITOR_MODE --> CREATE_LOG
    M_INFO --> CREATE_LOG
    M_WARN --> CREATE_LOG
    WO_ALLOW --> CREATE_LOG
    WO_BLOCK --> CREATE_LOG
    B_ALLOW --> CREATE_LOG
    B_BLOCK --> CREATE_LOG
    W_ALLOW --> CREATE_LOG
    W_WARN --> CREATE_LOG
    
    CREATE_LOG["Create Enhanced Log Record"]
    CREATE_LOG --> QUEUE["📤 Queue Log"]
    QUEUE --> END([Done])
    
    style START fill:#2196F3,color:#fff
    style END fill:#4CAF50,color:#fff
    style WO_BLOCK fill:#f44336,color:#fff
    style B_BLOCK fill:#f44336,color:#fff
    style WO_ALLOW fill:#4CAF50,color:#fff
    style B_ALLOW fill:#4CAF50,color:#fff
```

---

## 6. Whitelist Synchronization

```mermaid
flowchart TD
    TRIGGER([Sync Trigger]) --> CHECK_INTERVAL{"Sync Interval<br/>Elapsed?"}
    
    CHECK_INTERVAL --> |No| SKIP_SYNC["Skip Sync"]
    CHECK_INTERVAL --> |Yes| BUILD_REQUEST
    
    subgraph "📤 Build Sync Request"
        BUILD_REQUEST["Build Request Params"]
        BUILD_REQUEST --> AGENT_ID["agent_id"]
        BUILD_REQUEST --> CHECKSUM["current_checksum"]
        BUILD_REQUEST --> VERSION["current_version"]
    end
    
    AGENT_ID --> SEND_REQUEST
    CHECKSUM --> SEND_REQUEST
    VERSION --> SEND_REQUEST
    
    SEND_REQUEST["📡 Send to Server<br/>/api/whitelist/agent-sync"]
    
    SEND_REQUEST --> |Success| CHECK_RESPONSE{"Response?"}
    SEND_REQUEST --> |Fail| RETRY{"🔁 Retry?"}
    
    RETRY --> |Yes| SEND_REQUEST
    RETRY --> |Max| SYNC_FAIL["Sync Failed"]
    
    CHECK_RESPONSE --> |No Changes| NO_UPDATE["No Update Needed"]
    CHECK_RESPONSE --> |Has Changes| PARSE_DATA
    
    subgraph "📥 Parse Whitelist Data"
        PARSE_DATA["Parse Response"]
        PARSE_DATA --> DOMAINS["Extract Domains"]
        PARSE_DATA --> PATTERNS["🔤 Extract Patterns"]
        PARSE_DATA --> IPS["🌐 Extract IPs"]
    end
    
    DOMAINS --> UPDATE_STATE
    PATTERNS --> UPDATE_STATE
    IPS --> UPDATE_STATE
    
    UPDATE_STATE["💾 Update Whitelist State"]
    UPDATE_STATE --> CALC_CHECKSUM["🔢 Calculate New Checksum"]
    
    CALC_CHECKSUM --> CHECK_FW{"🛡 Firewall<br/>Enabled?"}
    CHECK_FW --> |Yes| SYNC_FW["Sync Firewall Rules"]
    CHECK_FW --> |No| SYNC_COMPLETE
    
    SYNC_FW --> SYNC_COMPLETE["Sync Complete"]
    
    NO_UPDATE --> DONE([Next Sync])
    SYNC_COMPLETE --> DONE
    SYNC_FAIL --> DONE
    SKIP_SYNC --> DONE
    
    style TRIGGER fill:#2196F3,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style SYNC_FAIL fill:#f44336,color:#fff
```

---

## 7. Server API Flow

```mermaid
flowchart TD
    REQUEST([📥 API Request]) --> MIDDLEWARE["🔐 Auth Middleware"]
    
    MIDDLEWARE --> CHECK_AUTH{"🔑 Auth Method?"}
    
    CHECK_AUTH --> |API Key| VALIDATE_KEY["Validate API Key"]
    CHECK_AUTH --> |JWT| VALIDATE_JWT["Validate JWT Token"]
    CHECK_AUTH --> |None| CHECK_PUBLIC{"Public Endpoint?"}
    
    VALIDATE_KEY --> |Valid| ROUTE
    VALIDATE_KEY --> |Invalid| AUTH_FAIL["401 Unauthorized"]
    
    VALIDATE_JWT --> |Valid| ROUTE
    VALIDATE_JWT --> |Expired| AUTH_FAIL
    VALIDATE_JWT --> |Invalid| AUTH_FAIL
    
    CHECK_PUBLIC --> |Yes| ROUTE
    CHECK_PUBLIC --> |No| AUTH_FAIL
    
    ROUTE["🔀 Route to Controller"]
    
    subgraph "Controllers"
        ROUTE --> |/agents/*| AGENT_CTRL["Agent Controller"]
        ROUTE --> |/logs/*| LOG_CTRL["Log Controller"]
        ROUTE --> |/whitelist/*| WL_CTRL["Whitelist Controller"]
        ROUTE --> |/groups/*| GROUP_CTRL["Group Controller"]
        ROUTE --> |/api-keys/*| KEY_CTRL["API Key Controller"]
    end
    
    AGENT_CTRL --> SERVICE["🔧 Service Layer"]
    LOG_CTRL --> SERVICE
    WL_CTRL --> SERVICE
    GROUP_CTRL --> SERVICE
    KEY_CTRL --> SERVICE
    
    SERVICE --> MODEL["📊 Model Layer"]
    MODEL --> MONGODB[("🗄️ MongoDB")]
    
    MONGODB --> |Result| FORMAT["Format Response"]
    FORMAT --> EMIT_WS{"📡 Emit WebSocket?"}
    
    EMIT_WS --> |Yes| SOCKETIO["Socket.IO Broadcast"]
    EMIT_WS --> |No| RESPONSE
    
    SOCKETIO --> RESPONSE["📤 JSON Response"]
    RESPONSE --> END([Response Sent])
    
    AUTH_FAIL --> END
    
    style REQUEST fill:#2196F3,color:#fff
    style END fill:#4CAF50,color:#fff
    style AUTH_FAIL fill:#f44336,color:#fff
    style MONGODB fill:#4DB33D,color:#fff
```

---

## 8. Authentication Flow

```mermaid
flowchart TD
    subgraph "🔐 Agent Registration"
        REG_START([Agent Start]) --> BUILD_INFO["Build Agent Info"]
        BUILD_INFO --> SEND_REG["POST /api/agents/register"]
        SEND_REG --> REG_CHECK{"Response?"}
        
        REG_CHECK --> |Success| STORE_TOKEN["Store JWT Token"]
        REG_CHECK --> |Fail| REG_RETRY["Retry Registration"]
        
        STORE_TOKEN --> USE_TOKEN["Use Token for API Calls"]
    end
    
    subgraph "🔑 API Key Authentication"
        API_REQ([API Request]) --> ADD_HEADER["Add X-API-Key Header"]
        ADD_HEADER --> SEND_API["Send Request"]
        SEND_API --> KEY_CHECK{"Valid Key?"}
        
        KEY_CHECK --> |Yes| PROCESS["Process Request"]
        KEY_CHECK --> |No| REJECT["401 Unauthorized"]
    end
    
    subgraph "🎫 JWT Token Flow"
        JWT_REQ([Authenticated Request]) --> CHECK_EXPIRY{"Token Expired?"}
        CHECK_EXPIRY --> |No| USE_JWT["Use Current Token"]
        CHECK_EXPIRY --> |Yes| REFRESH["POST /api/auth/refresh"]
        
        REFRESH --> REF_CHECK{"Refresh OK?"}
        REF_CHECK --> |Yes| NEW_TOKEN["Store New Token"]
        REF_CHECK --> |No| RE_LOGIN["Re-register Agent"]
        
        NEW_TOKEN --> USE_JWT
        RE_LOGIN --> REG_START
    end
    
    subgraph "🛡 Token Manager"
        USE_JWT --> TM_GET["TokenManager.get_auth_headers()"]
        TM_GET --> TM_CHECK{"Token Valid?"}
        TM_CHECK --> |Yes| RETURN_HEADERS["Return Authorization Header"]
        TM_CHECK --> |No| TM_REFRESH["Auto Refresh Token"]
        TM_REFRESH --> RETURN_HEADERS
    end
    
    style REG_START fill:#4CAF50,color:#fff
    style API_REQ fill:#2196F3,color:#fff
    style JWT_REQ fill:#9C27B0,color:#fff
    style REJECT fill:#f44336,color:#fff
```

---

## 9. Heartbeat & Status Flow

```mermaid
flowchart TD
    subgraph "💓 Agent Heartbeat"
        HB_TRIGGER([Heartbeat Timer]) --> COLLECT_METRICS
        
        COLLECT_METRICS["📊 Collect Metrics"]
        COLLECT_METRICS --> CPU["CPU Usage"]
        COLLECT_METRICS --> MEM["Memory Usage"]
        COLLECT_METRICS --> UPTIME["Agent Uptime"]
        COLLECT_METRICS --> STATS["Packet Stats"]
        
        CPU --> BUILD_HB
        MEM --> BUILD_HB
        UPTIME --> BUILD_HB
        STATS --> BUILD_HB
        
        BUILD_HB["🔨 Build Heartbeat Payload"]
        BUILD_HB --> SEND_HB["📤 POST /api/agents/heartbeat"]
        
        SEND_HB --> HB_RESP{"Response?"}
        HB_RESP --> |Success| UPDATE_LAST["Update Last Heartbeat"]
        HB_RESP --> |Fail| INCREMENT_FAIL["Increment Failure Count"]
        
        INCREMENT_FAIL --> CHECK_MAX{"Max Failures?"}
        CHECK_MAX --> |No| WAIT_RETRY["Wait & Retry"]
        CHECK_MAX --> |Yes| RECONNECT["⚠️ Attempt Reconnect"]
    end
    
    subgraph "📊 Server Status Tracking"
        RECV_HB([📥 Receive Heartbeat]) --> PARSE_HB["Parse Heartbeat"]
        PARSE_HB --> UPDATE_DB["Update Agent in DB"]
        UPDATE_DB --> CALC_STATUS["Calculate Status"]
        
        CALC_STATUS --> TIME_DIFF["Calculate Time Difference"]
        TIME_DIFF --> STATUS_CHECK{"Time Since<br/>Last Heartbeat?"}
        
        STATUS_CHECK --> |≤ 5 min| ACTIVE["🟢 ACTIVE"]
        STATUS_CHECK --> |≤ 30 min| INACTIVE["🟡 INACTIVE"]
        STATUS_CHECK --> |> 30 min| OFFLINE["🔴 OFFLINE"]
        
        ACTIVE --> EMIT_STATUS
        INACTIVE --> EMIT_STATUS
        OFFLINE --> EMIT_STATUS
        
        EMIT_STATUS["Emit Status Update"]
        EMIT_STATUS --> WEBUI["📺 Update Web Dashboard"]
    end
    
    style HB_TRIGGER fill:#E91E63,color:#fff
    style RECV_HB fill:#2196F3,color:#fff
    style ACTIVE fill:#4CAF50,color:#fff
    style INACTIVE fill:#FF9800,color:#fff
    style OFFLINE fill:#f44336,color:#fff
```

---

## 10. Agent Shutdown Flow

```mermaid
flowchart TD
    TRIGGER([🛑 Shutdown Trigger]) --> SIGNAL_TYPE{"Signal Type?"}
    
    SIGNAL_TYPE --> |GUI Button| GUI_STOP["GUI Stop Request"]
    SIGNAL_TYPE --> |SIGTERM| SIG_STOP["Signal Handler"]
    SIGNAL_TYPE --> |SIGINT| SIG_STOP
    SIGNAL_TYPE --> |Service Stop| SVC_STOP["Service Manager"]
    
    GUI_STOP --> SET_FLAG
    SIG_STOP --> SET_FLAG
    SVC_STOP --> SET_FLAG
    
    SET_FLAG["🚩 Set Stop Flag"]
    SET_FLAG --> STOP_SNIFFER["🛑 Stop Packet Sniffer"]
    
    subgraph "Cleanup Sequence"
        STOP_SNIFFER --> STOP_HEARTBEAT["🛑 Stop Heartbeat Sender"]
        STOP_HEARTBEAT --> STOP_WHITELIST["🛑 Stop Whitelist Sync"]
        STOP_WHITELIST --> FLUSH_LOGS["📤 Flush Pending Logs"]
        FLUSH_LOGS --> STOP_LOGSENDER["🛑 Stop Log Sender"]
    end
    
    STOP_LOGSENDER --> CHECK_FW{"🛡 Firewall<br/>Cleanup?"}
    
    CHECK_FW --> |Yes| CLEANUP_FW["Cleanup Firewall Rules"]
    CHECK_FW --> |No| BUILD_SHUTDOWN
    
    CLEANUP_FW --> RESTORE_POLICY["↩️ Restore Original Policy"]
    RESTORE_POLICY --> BUILD_SHUTDOWN
    
    BUILD_SHUTDOWN["Build Shutdown Log"]
    BUILD_SHUTDOWN --> |event_type| EVT["agent_shutdown"]
    BUILD_SHUTDOWN --> |uptime| UPT["uptime string"]
    BUILD_SHUTDOWN --> |message| MSG["Agent shutdown"]
    
    EVT --> SEND_SHUTDOWN
    UPT --> SEND_SHUTDOWN
    MSG --> SEND_SHUTDOWN
    
    SEND_SHUTDOWN["📤 Send Shutdown Log"]
    SEND_SHUTDOWN --> WAIT_SEND["⏳ Wait for Send (5s)"]
    
    WAIT_SEND --> CLOSE_CONNECTIONS["Close Connections"]
    CLOSE_CONNECTIONS --> LOG_FINAL["Final Local Log"]
    LOG_FINAL --> EXIT([🔴 Exit Process])
    
    style TRIGGER fill:#f44336,color:#fff
    style EXIT fill:#f44336,color:#fff
    style CLEANUP_FW fill:#FF9800,color:#fff
```

---

## 11. GUI Event Flow

```mermaid
flowchart TD
    subgraph "🖼️ GUI Application"
        APP_START([GUI Start]) --> INIT_CTK["Init CustomTkinter"]
        INIT_CTK --> LOAD_VIEWS["Load Views"]
        LOAD_VIEWS --> CONNECT_CTRL["Connect Controllers"]
        CONNECT_CTRL --> MAIN_WINDOW["Show Main Window"]
    end
    
    subgraph "📊 Dashboard View"
        MAIN_WINDOW --> DASHBOARD["Dashboard View"]
        DASHBOARD --> STATUS_CARDS["Status Cards"]
        DASHBOARD --> ACTIVITY_LOG["Activity Log"]
        DASHBOARD --> START_BTN["Start/Stop Button"]
    end
    
    subgraph "🎮 User Actions"
        START_BTN --> |Click| CHECK_STATE{"Agent State?"}
        CHECK_STATE --> |Stopped| START_AGENT["▶️ Start Agent"]
        CHECK_STATE --> |Running| STOP_AGENT["⏹️ Stop Agent"]
        
        START_AGENT --> EMIT_START["Emit 'agent_start'"]
        STOP_AGENT --> EMIT_STOP["Emit 'agent_stop'"]
    end
    
    subgraph "🔔 Signal System"
        EMIT_START --> AGENT_CTRL["AgentController"]
        EMIT_STOP --> AGENT_CTRL
        
        AGENT_CTRL --> PROCESS_CMD["Process Command"]
        PROCESS_CMD --> UPDATE_STATE["Update Agent State"]
        
        UPDATE_STATE --> EMIT_SIGNAL["Emit Signal"]
        EMIT_SIGNAL --> |status_changed| ON_STATUS["on_status_changed()"]
        EMIT_SIGNAL --> |stats_updated| ON_STATS["on_stats_updated()"]
        EMIT_SIGNAL --> |error_occurred| ON_ERROR["on_error()"]
    end
    
    subgraph "UI Updates"
        ON_STATUS --> UPDATE_CARDS["Update Status Cards"]
        ON_STATS --> UPDATE_METRICS["Update Metrics"]
        ON_ERROR --> SHOW_ERROR["Show Error Message"]
        
        UPDATE_CARDS --> REFRESH_UI["Refresh UI"]
        UPDATE_METRICS --> REFRESH_UI
        SHOW_ERROR --> REFRESH_UI
    end
    
    style APP_START fill:#4CAF50,color:#fff
    style START_AGENT fill:#4CAF50,color:#fff
    style STOP_AGENT fill:#f44336,color:#fff
```

---

## 12. Complete System Interaction

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant GUI as 🖼️ Agent GUI
    participant A as 🤖 Agent Core
    participant S as 📡 Sniffer
    participant WL as Whitelist
    participant FW as 🛡 Firewall
    participant LS as 📤 LogSender
    participant HB as 💓 Heartbeat
    participant API as 🌐 Server API
    participant DB as 🗄️ MongoDB
    participant WS as Socket.IO
    participant WEB as 🖥️ Web UI

    Note over U,WEB: STARTUP PHASE
    U->>GUI: Click Start
    GUI->>A: start_agent()
    A->>A: load_config()
    A->>A: validate_config()
    A->>WL: initialize()
    A->>FW: initialize()
    A->>S: initialize()
    A->>LS: initialize()
    A->>HB: initialize()
    
    A->>API: POST /agents/register
    API->>DB: Insert/Update Agent
    DB-->>API: Success
    API-->>A: {agent_id, token}
    
    A->>WL: sync_now()
    WL->>API: GET /whitelist/agent-sync
    API->>DB: Query Whitelist
    DB-->>API: Whitelist Data
    API-->>WL: {domains, patterns, ips}
    WL->>FW: sync_firewall_rules()
    
    A->>LS: start()
    A->>HB: start()
    A->>S: start()
    
    A->>LS: queue_log(startup_log)
    LS->>API: POST /logs
    API->>DB: Insert Logs
    API->>WS: emit('new_log')
    WS->>WEB: Update Dashboard

    Note over U,WEB: RUNNING PHASE
    
    loop Every Packet
        S->>S: capture_packet()
        S->>A: callback(packet_info)
        A->>WL: is_allowed(domain)
        WL-->>A: true/false
        A->>A: determine_action()
        A->>LS: queue_log(detection_log)
    end
    
    loop Every 2 seconds
        LS->>API: POST /logs (batch)
        API->>DB: Insert Logs
        API->>WS: emit('new_log')
        WS->>WEB: Real-time Update
    end
    
    loop Every 20 seconds
        HB->>HB: collect_metrics()
        HB->>API: POST /agents/heartbeat
        API->>DB: Update Agent Status
        API->>WS: emit('agent_status')
        WS->>WEB: Update Agent Card
    end
    
    loop Every 60 seconds
        WL->>API: GET /whitelist/agent-sync
        API-->>WL: Updated Whitelist
        WL->>FW: sync_changes()
    end

    Note over U,WEB: 🛑 SHUTDOWN PHASE
    U->>GUI: Click Stop
    GUI->>A: stop_agent()
    A->>S: stop()
    A->>HB: stop()
    A->>WL: stop_sync()
    A->>LS: flush_queue()
    A->>FW: cleanup_rules()
    A->>LS: queue_log(shutdown_log)
    LS->>API: POST /logs
    API->>DB: Insert Shutdown Log
    API->>WS: emit('new_log')
    WS->>WEB: Show Shutdown Event
    A->>LS: stop()
    A-->>GUI: agent_stopped
    GUI->>GUI: update_ui()
```

---

## 📊 Mode Comparison Table

| Mode | Icon | Action on Whitelist | Action on Non-Whitelist | Real Blocking | Use Case |
|------|------|--------------------|-----------------------|---------------|----------|
| `monitor` | 👁️ | MONITORED | MONITORED (WARNING) | No | Testing, Learning |
| `whitelist_only` | 🛡 | ALLOWED | BLOCKED | Yes | Production |
| `block` | 🚫 | ALLOWED | BLOCKED | Yes | Strict Security |
| `warn` | ⚠️ | ALLOWED | WARNING | No | Soft Enforcement |

---

## 🔧 Component Dependencies

```mermaid
flowchart LR
    subgraph "📦 Agent Modules"
        CONFIG[config] --> SHARED[shared]
        CORE[core] --> CONFIG
        CORE --> SHARED
        CORE --> UTILS[utils]
        
        FIREWALL[firewall] --> SHARED
        CAPTURE[capture] --> SHARED
        WHITELIST[whitelist] --> SHARED
        WHITELIST --> CORE
        
        SERVICES[services] --> SHARED
        SERVICES --> CORE
        
        LOGGING[logging_module] --> SHARED
        LOGGING --> CORE
        
        GUI[gui] --> CORE
        GUI --> CONFIG
    end
    
    subgraph "📦 Server Modules"
        APP[app] --> CTRL[controllers]
        CTRL --> SVC[services]
        SVC --> MDL[models]
        MDL --> DBCFG[database]
        
        MW[middleware] --> SVC
        VIEWS[views] --> CTRL
    end
    
    style CONFIG fill:#E91E63,color:#fff
    style CORE fill:#9C27B0,color:#fff
    style APP fill:#2196F3,color:#fff
```

---

*Generated: December 1, 2025*
*Firewall Controller v2.2 - Modular Architecture*
