# Use Case Diagrams - Firewall Controller Agent

## 1. System Overview Use Case Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FIREWALL CONTROLLER AGENT SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│    ┌─────────┐                                           ┌─────────────┐        │
│    │  Admin  │                                           │   Server    │        │
│    │  User   │                                           │  (Backend)  │        │
│    └────┬────┘                                           └──────┬──────┘        │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │           AGENT MANAGEMENT              │       │               │
│         ├───►│  ○ Start Agent                          │       │               │
│         ├───►│  ○ Stop Agent                           │       │               │
│         ├───►│  ○ Restart Agent                        │       │               │
│         ├───►│  ○ View Agent Status                    │◄──────┤               │
│         │    └─────────────────────────────────────────┘       │               │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │         FIREWALL MANAGEMENT             │       │               │
│         ├───►│  ○ Enable/Disable Firewall              │       │               │
│         ├───►│  ○ View Firewall Rules                  │       │               │
│         ├───►│  ○ View Blocked Connections             │       │               │
│         │    └─────────────────────────────────────────┘       │               │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │         WHITELIST MANAGEMENT            │       │               │
│         ├───►│  ○ Add IP to Whitelist                  │◄──────┤               │
│         ├───►│  ○ Remove IP from Whitelist             │◄──────┤               │
│         ├───►│  ○ View Whitelist                       │◄──────┤               │
│         ├───►│  ○ Sync Whitelist with Server           │◄──────┤               │
│         │    └─────────────────────────────────────────┘       │               │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │           LOG MANAGEMENT                │       │               │
│         ├───►│  ○ View Activity Logs                   │       │               │
│         ├───►│  ○ Filter Logs by Level                 │       │               │
│         ├───►│  ○ Export Logs                          │       │               │
│         ├───►│  ○ Clear Logs                           │       │               │
│         │    └─────────────────────────────────────────┘       │               │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │          SETTINGS MANAGEMENT            │       │               │
│         ├───►│  ○ Configure Server URL                 │       │               │
│         ├───►│  ○ Configure Sync Interval              │       │               │
│         ├───►│  ○ Change Theme (Dark/Light)            │       │               │
│         │    └─────────────────────────────────────────┘       │               │
│         │                                                       │               │
│         │    ┌─────────────────────────────────────────┐       │               │
│         │    │         MONITORING (BACKGROUND)         │       │               │
│         │    │  ○ Capture Network Packets        ◄─────┼───────┤               │
│         │    │  ○ Block Unauthorized Traffic     ◄─────┼───────┤               │
│         │    │  ○ Send Heartbeat to Server       ─────►│       │               │
│         │    │  ○ Send Logs to Server            ─────►│       │               │
│         │    └─────────────────────────────────────────┘       │               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Lifecycle Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│                    AGENT LIFECYCLE USE CASES                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────┐                                                  │
│   │  Admin  │                                                  │
│   └────┬────┘                                                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC1: Start Agent        │                  │
│        │         │  ├─ Load Configuration   │                  │
│        │         │  ├─ Validate Config      │                  │
│        │         │  ├─ Check Admin Rights   │                  │
│        │         │  ├─ Initialize Components│                  │
│        │         │  ├─ Register with Server │                  │
│        │         │  └─ Start Background Jobs│                  │
│        │         └──────────────────────────┘                  │
│        │                      │                                │
│        │                      │ «includes»                     │
│        │                      ▼                                │
│        │         ┌──────────────────────────┐                  │
│        │         │  UC1.1: Initialize       │                  │
│        │         │         Components       │                  │
│        │         │  ├─ Init FirewallManager │                  │
│        │         │  ├─ Init WhitelistManager│                  │
│        │         │  ├─ Init PacketSniffer   │                  │
│        │         │  ├─ Init LogSender       │                  │
│        │         │  └─ Init HeartbeatSender │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC2: Stop Agent         │                  │
│        │         │  ├─ Stop Background Jobs │                  │
│        │         │  ├─ Flush Log Queue      │                  │
│        │         │  ├─ Cleanup Resources    │                  │
│        │         │  └─ Send Shutdown Log    │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC3: View Agent Status  │                  │
│        │         │  ├─ Get Running State    │                  │
│        │         │  ├─ Get Server Connection│                  │
│        │         │  ├─ Get Uptime           │                  │
│        │         │  └─ Get Component Status │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        └────────►│  UC4: Restart Agent      │                  │
│                  │  ├─ «extends» UC2: Stop  │                  │
│                  │  └─ «extends» UC1: Start │                  │
│                  └──────────────────────────┘                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Firewall Management Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│                 FIREWALL MANAGEMENT USE CASES                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────┐                           ┌─────────────┐        │
│   │  Admin  │                           │   Windows   │        │
│   └────┬────┘                           │  Firewall   │        │
│        │                                └──────┬──────┘        │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC5: Enable Firewall    │──┤               │
│        │         │  ├─ Enable Default Deny  │  │               │
│        │         │  ├─ Create Allow Rules   │  │               │
│        │         │  └─ Verify Policy Active │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC6: Disable Firewall   │──┤               │
│        │         │  ├─ Restore Original     │  │               │
│        │         │  │   Policy              │  │               │
│        │         │  └─ Clear Custom Rules   │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC7: View Firewall      │──┤               │
│        │         │       Status             │  │               │
│        │         │  ├─ Get Current Policy   │  │               │
│        │         │  ├─ Get Rule Count       │  │               │
│        │         │  └─ Get Allowed IPs      │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        └────────►│  UC8: Add IP to          │──┘               │
│                  │       Whitelist          │                  │
│                  │  ├─ Validate IP Format   │                  │
│                  │  ├─ Create netsh Rule    │                  │
│                  │  └─ Update Local State   │                  │
│                  └──────────────────────────┘                  │
│                                                                │
│   ┌─────────────┐                                              │
│   │   System    │                                              │
│   │ (Background)│                                              │
│   └──────┬──────┘                                              │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          ├────────►│  UC9: Auto-Block Traffic │                │
│          │         │  ├─ Detect Non-Whitelist │                │
│          │         │  │   Connection          │                │
│          │         │  ├─ Default Deny Blocks  │                │
│          │         │  └─ Log Blocked Traffic  │                │
│          │         └──────────────────────────┘                │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          └────────►│  UC10: Sync Firewall     │                │
│                    │        Rules             │                │
│                    │  ├─ Get Whitelist Changes│                │
│                    │  ├─ Add New Allow Rules  │                │
│                    │  └─ Remove Old Rules     │                │
│                    └──────────────────────────┘                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Whitelist Management Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│                WHITELIST MANAGEMENT USE CASES                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────┐                           ┌─────────────┐        │
│   │  Admin  │                           │   Server    │        │
│   └────┬────┘                           └──────┬──────┘        │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC11: Add IP Manually   │  │               │
│        │         │  ├─ Validate IP Format   │  │               │
│        │         │  │   (IPv4/IPv6/CIDR)    │  │               │
│        │         │  ├─ Check Duplicate      │  │               │
│        │         │  ├─ Add to Local State   │  │               │
│        │         │  ├─ Create Firewall Rule │  │               │
│        │         │  └─ Notify UI Update     │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC12: Remove IP         │  │               │
│        │         │  ├─ Find IP in State     │  │               │
│        │         │  ├─ Remove from State    │  │               │
│        │         │  ├─ Delete Firewall Rule │  │               │
│        │         │  └─ Notify UI Update     │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC13: View Whitelist    │  │               │
│        │         │  ├─ Get All IPs          │  │               │
│        │         │  ├─ Get All Domains      │  │               │
│        │         │  ├─ Get All Patterns     │  │               │
│        │         │  └─ Display in Table     │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC14: Force Sync        │◄─┤               │
│        │         │  ├─ Request Server Data  │  │               │
│        │         │  ├─ Compare with Local   │  │               │
│        │         │  ├─ Update Local State   │  │               │
│        │         │  └─ Update Firewall Rules│  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        └────────►│  UC15: Search/Filter     │  │               │
│                  │  ├─ Filter by IP         │  │               │
│                  │  ├─ Filter by Status     │  │               │
│                  │  └─ Filter by Source     │  │               │
│                  └──────────────────────────┘  │               │
│                                                │               │
│   ┌─────────────┐                              │               │
│   │   System    │                              │               │
│   │ (Background)│                              │               │
│   └──────┬──────┘                              │               │
│          │                                     │               │
│          │         ┌──────────────────────────┐│               │
│          └────────►│  UC16: Auto Sync         ││               │
│                    │  (Periodic)              ├┘               │
│                    │  ├─ Check Sync Interval  │                │
│                    │  ├─ Send Sync Request    │                │
│                    │  ├─ Process Response     │                │
│                    │  └─ Update State         │                │
│                    └──────────────────────────┘                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 5. Network Monitoring Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│               NETWORK MONITORING USE CASES                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────────┐                                              │
│   │   System    │                                              │
│   │ (PacketSniff│                                              │
│   └──────┬──────┘                                              │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          ├────────►│  UC17: Capture DNS       │                │
│          │         │        Packets           │                │
│          │         │  ├─ Listen Port 53       │                │
│          │         │  ├─ Extract Domain Name  │                │
│          │         │  ├─ Check Whitelist      │                │
│          │         │  └─ Log Result           │                │
│          │         └──────────────────────────┘                │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          ├────────►│  UC18: Capture HTTP      │                │
│          │         │        Traffic           │                │
│          │         │  ├─ Listen Port 80       │                │
│          │         │  ├─ Extract Host Header  │                │
│          │         │  ├─ Check Whitelist      │                │
│          │         │  └─ Log Result           │                │
│          │         └──────────────────────────┘                │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          ├────────►│  UC19: Capture HTTPS     │                │
│          │         │        Traffic (SNI)     │                │
│          │         │  ├─ Listen Port 443      │                │
│          │         │  ├─ Extract SNI from TLS │                │
│          │         │  ├─ Check Whitelist      │                │
│          │         │  └─ Log Result           │                │
│          │         └──────────────────────────┘                │
│          │                                                     │
│          │         ┌──────────────────────────┐                │
│          └────────►│  UC20: Process Detected  │                │
│                    │        Domain            │                │
│                    │  ├─ Resolve DNS to IP    │                │
│                    │  ├─ Check Domain/IP      │                │
│                    │  │   Against Whitelist   │                │
│                    │  ├─ If Allowed: Log INFO │                │
│                    │  ├─ If Blocked: Log BLOCK│                │
│                    │  └─ Send Log to Server   │                │
│                    └──────────────────────────┘                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. Log & Communication Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│              LOG & COMMUNICATION USE CASES                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────┐                           ┌─────────────┐        │
│   │  Admin  │                           │   Server    │        │
│   └────┬────┘                           └──────┬──────┘        │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC21: View Logs in GUI  │  │               │
│        │         │  ├─ Display in Console   │  │               │
│        │         │  ├─ Color by Log Level   │  │               │
│        │         │  └─ Auto-scroll          │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC22: Filter Logs       │  │               │
│        │         │  ├─ By Level (DEBUG,     │  │               │
│        │         │  │   INFO, WARNING, ERROR)│  │               │
│        │         │  ├─ By Keyword           │  │               │
│        │         │  └─ By Time Range        │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        ├────────►│  UC23: Export Logs       │  │               │
│        │         │  ├─ Select Format        │  │               │
│        │         │  ├─ Save to File         │  │               │
│        │         │  └─ Confirm Save         │  │               │
│        │         └──────────────────────────┘  │               │
│        │                                       │               │
│        │         ┌──────────────────────────┐  │               │
│        └────────►│  UC24: Clear Logs        │  │               │
│                  │  └─ Reset Console        │  │               │
│                  └──────────────────────────┘  │               │
│                                                │               │
│   ┌─────────────┐                              │               │
│   │   System    │                              │               │
│   └──────┬──────┘                              │               │
│          │                                     │               │
│          │         ┌──────────────────────────┐│               │
│          ├────────►│  UC25: Queue Log         ││               │
│          │         │  ├─ Add to Queue         ├┘               │
│          │         │  ├─ Check Queue Size     │                │
│          │         │  └─ Batch if Full        │                │
│          │         └──────────────────────────┘                │
│          │                                     │               │
│          │         ┌──────────────────────────┐│               │
│          ├────────►│  UC26: Send Logs Batch   ├┘               │
│          │         │  ├─ Serialize Logs       │                │
│          │         │  ├─ HTTP POST to Server  │                │
│          │         │  ├─ Handle Response      │                │
│          │         │  └─ Retry on Failure     │                │
│          │         └──────────────────────────┘                │
│          │                                     │               │
│          │         ┌──────────────────────────┐│               │
│          └────────►│  UC27: Send Heartbeat    ├┘               │
│                    │  ├─ Collect Metrics      │                │
│                    │  ├─ HTTP POST to Server  │                │
│                    │  └─ Update Last Sent     │                │
│                    └──────────────────────────┘                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. GUI Navigation Use Cases

```
┌────────────────────────────────────────────────────────────────┐
│                   GUI NAVIGATION USE CASES                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────┐                                                  │
│   │  Admin  │                                                  │
│   └────┬────┘                                                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC28: Navigate to       │                  │
│        │         │        Dashboard         │                  │
│        │         │  ├─ Click Sidebar Item   │                  │
│        │         │  ├─ Update Active State  │                  │
│        │         │  ├─ Show Dashboard View  │                  │
│        │         │  └─ Display Status Cards │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC29: Navigate to       │                  │
│        │         │        Firewall View     │                  │
│        │         │  ├─ Show Firewall Status │                  │
│        │         │  └─ Show Control Buttons │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC30: Navigate to       │                  │
│        │         │        Whitelist View    │                  │
│        │         │  ├─ Show IP DataTable    │                  │
│        │         │  ├─ Show Add IP Form     │                  │
│        │         │  └─ Show Sync Button     │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        ├────────►│  UC31: Navigate to       │                  │
│        │         │        Logs View         │                  │
│        │         │  ├─ Show Log Console     │                  │
│        │         │  └─ Show Filter Controls │                  │
│        │         └──────────────────────────┘                  │
│        │                                                       │
│        │         ┌──────────────────────────┐                  │
│        └────────►│  UC32: Navigate to       │                  │
│                  │        Settings View     │                  │
│                  │  ├─ Show Config Options  │                  │
│                  │  └─ Show Theme Toggle    │                  │
│                  └──────────────────────────┘                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```
