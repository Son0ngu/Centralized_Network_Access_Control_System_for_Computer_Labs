# Phase 1: DNS Proxy/Sinkhole Architecture Design

> **Version**: 1.0  
> **Date**: 2025-12-18  
> **Status**: Draft  

---

## 1. Executive Summary

### 1.1 Mục tiêu
Chuyển đổi agent từ mô hình **reactive** (bắt packet → check whitelist) sang **proactive** (kiểm soát DNS → cấp phép IP → cho traffic đi).

### 1.2 Vấn đề cần giải quyết

| Vấn đề | Hiện trạng | Giải pháp |
|--------|------------|-----------|
| Race condition | Packet đi trước, check sau | DNS Proxy chặn từ bước resolve |
| Multi-IP CDN | Firewall rules lỗi thời | Cập nhật IP theo TTL real-time |
| DoH/DoT bypass | Không kiểm soát | Block DoH/DoT, ép DNS về 127.0.0.1 |
| Không biết IP trước | Chỉ thấy sau khi connection | DNS response cung cấp IP trước |

---

## 2. Kiến trúc Tổng quan

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENT (Windows)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     NETWORK MANAGER (MỚI)                           │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │    │
│  │  │   Adapter    │ │     DNS      │ │      Drift Monitor         │ │    │
│  │  │  Detector    │ │ Configurator │ │  (watch DNS changes)       │ │    │
│  │  └──────────────┘ └──────────────┘ └─────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                     Set DNS = 127.0.0.1 for all adapters                    │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       DNS PROXY (MỚI) - Core                        │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │    │
│  │  │   Server     │ │   Handler    │ │      Upstream Resolver     │ │    │
│  │  │ UDP/TCP:53   │→│  Whitelist   │→│    (8.8.8.8, 1.1.1.1)     │ │    │
│  │  │ 127.0.0.1    │ │   Check      │ │                            │ │    │
│  │  └──────────────┘ └──────────────┘ └─────────────────────────────┘ │    │
│  │         │                │                       │                  │    │
│  │         │          ┌─────┴─────┐                 │                  │    │
│  │         │       DENIED      ALLOWED              │                  │    │
│  │         │          │            │                │                  │    │
│  │         │    Return NXDOMAIN    │                │                  │    │
│  │         │                       ▼                ▼                  │    │
│  │         │              ┌─────────────────────────────────┐         │    │
│  │         │              │     Firewall Sync (MỚI)        │         │    │
│  │         │              │  Add IP rule BEFORE response   │         │    │
│  │         │              │  Track TTL → auto remove       │         │    │
│  │         │              └─────────────────────────────────┘         │    │
│  │         │                              │                            │    │
│  │         │              ┌───────────────┘                            │    │
│  │         ▼              ▼                                            │    │
│  │  ┌─────────────────────────────────┐                                │    │
│  │  │         DNS Cache               │                                │    │
│  │  │   domain → IPs + TTL + expiry   │                                │    │
│  │  └─────────────────────────────────┘                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SECURITY MODULE (MỚI)                            │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │    │
│  │  │  DoH/DoT     │ │   Bypass     │ │    Cert Validator          │ │    │
│  │  │  Blocker     │ │  Detector    │ │    (SNI ↔ CN/SAN)         │ │    │
│  │  └──────────────┘ └──────────────┘ └─────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   EXISTING MODULES (Refactored)                     │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────────┐ │    │
│  │  │  Whitelist   │ │  Firewall    │ │    PacketSniffer           │ │    │
│  │  │  Manager     │ │  Manager     │ │    (GIẢM VAI TRÒ)          │ │    │
│  │  │  (giữ nguyên)│ │  (mở rộng)   │ │    → Bypass Detection Only │ │    │
│  │  └──────────────┘ └──────────────┘ └─────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           LUỒNG XỬ LÝ CHÍNH                                  │
└──────────────────────────────────────────────────────────────────────────────┘

[App Request: google.com]
        │
        ▼
┌───────────────────┐
│ OS DNS Query      │ ──→ DNS được set = 127.0.0.1
│ google.com?       │
└───────────────────┘
        │
        ▼
┌───────────────────┐     ┌─────────────────────────────────────────┐
│ DNS Proxy Server  │     │ BƯỚC 1: Nhận query                      │
│ 127.0.0.1:53      │     │ - Parse DNS packet                      │
└───────────────────┘     │ - Extract domain name                   │
        │                 └─────────────────────────────────────────┘
        ▼
┌───────────────────┐     ┌─────────────────────────────────────────┐
│ Whitelist Check   │     │ BƯỚC 2: Kiểm tra whitelist              │
│ (WhitelistState)  │     │ - Exact match: google.com               │
└───────────────────┘     │ - Pattern: *.google.com                 │
        │                 │ - IP direct (nếu query IP)              │
        │                 └─────────────────────────────────────────┘
        │
   ┌────┴────┐
   │         │
DENIED    ALLOWED
   │         │
   ▼         ▼
┌──────┐  ┌───────────────────┐
│NXDOM │  │Forward to Upstream│  ──→ 8.8.8.8 / 1.1.1.1
│AIN   │  │(configurable)     │
└──────┘  └───────────────────┘
   │              │
   │              ▼
   │      ┌───────────────────┐     ┌─────────────────────────────────────────┐
   │      │ Parse Response    │     │ BƯỚC 3: Nhận response                   │
   │      │ A: 142.250.x.x    │     │ - Extract A/AAAA records                │
   │      │ TTL: 300s         │     │ - Get TTL                               │
   │      └───────────────────┘     └─────────────────────────────────────────┘
   │              │
   │              ▼
   │      ┌───────────────────┐     ┌─────────────────────────────────────────┐
   │      │ BLOCKING CALL:    │     │ BƯỚC 4: Thêm firewall rule              │
   │      │ FirewallSync.add  │     │ - Add allow rule cho từng IP            │
   │      │ (ip, ttl, domain) │     │ - Track TTL để tự xóa sau               │
   │      └───────────────────┘     │ - CHẶN cho đến khi rule được add        │
   │              │                 └─────────────────────────────────────────┘
   │              │
   │              │ ← Rule added thành công
   │              ▼
   │      ┌───────────────────┐     ┌─────────────────────────────────────────┐
   │      │ Return DNS        │     │ BƯỚC 5: Trả response cho client         │
   │      │ Response to App   │     │ - App nhận IP đã được allow             │
   │      └───────────────────┘     │ - Kết nối đến IP → PASS firewall       │
   │              │                 └─────────────────────────────────────────┘
   │              ▼
   ▼      ┌───────────────────┐
┌──────┐  │ App connects to   │
│ LOG  │  │ 142.250.x.x:443   │ ──→ Firewall ALLOW (rule đã có)
│Event │  │ (HTTPS)           │
└──────┘  └───────────────────┘
```

---

## 3. Module Specifications

### 3.1 DNS Proxy Module (`agent/dns_proxy/`)

#### 3.1.1 Cấu trúc thư mục

```
agent/dns_proxy/
├── __init__.py
├── server.py           # DNS server listener (UDP/TCP 53)
├── handler.py          # Query processing + whitelist check
├── resolver.py         # Upstream resolver với failover
├── cache.py            # DNS cache với TTL tracking
├── firewall_sync.py    # Đồng bộ DNS → Firewall (blocking)
└── config.py           # DNS Proxy configuration
```

#### 3.1.2 Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DNSProxyServer                          │
├─────────────────────────────────────────────────────────────────┤
│ - bind_address: str = "127.0.0.1"                               │
│ - port: int = 53                                                │
│ - handler: DNSQueryHandler                                      │
│ - udp_socket: socket                                            │
│ - tcp_socket: socket                                            │
│ - running: bool                                                 │
│ - thread_pool: ThreadPoolExecutor                               │
├─────────────────────────────────────────────────────────────────┤
│ + start() → None                                                │
│ + stop() → None                                                 │
│ + handle_udp_request(data, addr) → bytes                        │
│ + handle_tcp_request(conn) → None                               │
│ + get_stats() → Dict                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DNSQueryHandler                          │
├─────────────────────────────────────────────────────────────────┤
│ - whitelist_state: WhitelistState                               │
│ - upstream_resolver: UpstreamResolver                           │
│ - firewall_sync: FirewallDNSSync                                │
│ - cache: DNSCache                                               │
│ - firewall_timeout: float = 5.0                                 │
├─────────────────────────────────────────────────────────────────┤
│ + handle(query: bytes) → bytes                                  │
│ + check_whitelist(domain: str) → bool                           │
│ + forward_and_process(domain: str) → DNSResponse                │
│ + build_nxdomain_response(query) → bytes                        │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│UpstreamResolver │ │    DNSCache     │ │   FirewallDNSSync       │
├─────────────────┤ ├─────────────────┤ ├─────────────────────────┤
│- resolvers[]    │ │- entries: Dict  │ │- firewall_manager       │
│- timeout: float │ │- lock: RLock    │ │- ip_ttl_tracker: Dict   │
│- current_idx    │ │- min_ttl: int   │ │- cleanup_thread         │
├─────────────────┤ ├─────────────────┤ ├─────────────────────────┤
│+ resolve(domain)│ │+ get(domain)    │ │+ add_ips(domain, ips,   │
│+ health_check() │ │+ set(domain,..) │ │         ttl) → bool     │
│                 │ │+ cleanup()      │ │+ remove_expired()       │
└─────────────────┘ └─────────────────┘ └─────────────────────────┘
```

#### 3.1.3 Sequence Diagram - DNS Query Flow

```
┌───────┐     ┌───────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│ App   │     │DNSProxy   │    │Handler  │    │Whitelist │    │Upstream  │    │FWSync     │
└───┬───┘     └─────┬─────┘    └────┬────┘    └────┬─────┘    └────┬─────┘    └─────┬─────┘
    │               │               │              │               │                │
    │ DNS Query     │               │              │               │                │
    │──────────────>│               │              │               │                │
    │               │ handle(query) │              │               │                │
    │               │──────────────>│              │               │                │
    │               │               │ check_domain │              │                │
    │               │               │─────────────>│              │                │
    │               │               │              │              │                │
    │               │               │<── allowed ──│              │                │
    │               │               │              │              │                │
    │               │               │        forward(domain)      │                │
    │               │               │─────────────────────────────>│                │
    │               │               │              │              │                │
    │               │               │<── A records + TTL ─────────│                │
    │               │               │              │              │                │
    │               │               │              │   add_ips(domain, ips, ttl)   │
    │               │               │──────────────────────────────────────────────>│
    │               │               │              │              │                │
    │               │               │              │              │     BLOCKING   │
    │               │               │              │              │     Add rules  │
    │               │               │              │              │                │
    │               │               │<─────────────── success ─────────────────────│
    │               │               │              │               │                │
    │               │<── response ──│              │               │                │
    │               │               │              │               │                │
    │<── DNS resp ──│               │               │               │                │
    │               │               │               │               │                │
    │ Connect IP    │               │               │               │                │
    │═══════════════════════════════════════════════════════════════>│ ALLOWED      │
    │               │               │               │               │                │
```

### 3.2 Network Manager Module (`agent/network_manager/`)

#### 3.2.1 Cấu trúc thư mục

```
agent/network_manager/
├── __init__.py
├── adapter_detector.py    # Phát hiện tất cả network adapters
├── dns_configurator.py    # Set DNS = 127.0.0.1
├── drift_monitor.py       # Monitor DNS changes
├── restore_manager.py     # Backup/Restore DNS settings
└── config.py              # Network manager config
```

#### 3.2.2 Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       NetworkManager                            │
├─────────────────────────────────────────────────────────────────┤
│ - adapter_detector: AdapterDetector                             │
│ - dns_configurator: DNSConfigurator                             │
│ - drift_monitor: DriftMonitor                                   │
│ - restore_manager: RestoreManager                               │
│ - config: Dict                                                  │
├─────────────────────────────────────────────────────────────────┤
│ + initialize() → bool                                           │
│ + apply_dns_config() → bool                                     │
│ + restore_dns_config() → bool                                   │
│ + start_monitoring() → None                                     │
│ + stop_monitoring() → None                                      │
│ + get_status() → Dict                                           │
│ + on_adapter_change(callback) → None                            │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│AdapterDetector  │ │DNSConfigurator  │ │    DriftMonitor         │
├─────────────────┤ ├─────────────────┤ ├─────────────────────────┤
│                 │ │- backup_path    │ │- check_interval: int    │
├─────────────────┤ ├─────────────────┤ │- running: bool          │
│+ get_all()      │ │+ backup()       │ ├─────────────────────────┤
│+ get_active()   │ │+ set_dns()      │ │+ start()                │
│+ get_primary()  │ │+ restore()      │ │+ stop()                 │
│+ watch_changes()│ │+ verify()       │ │+ check_drift()          │
└─────────────────┘ └─────────────────┘ └─────────────────────────┘
```

#### 3.2.3 Adapter Detection Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-ADAPTER HANDLING                               │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │     AdapterDetector.get_all()   │
                    └─────────────────────────────────┘
                                    │
                    PowerShell: Get-NetAdapter | Where Status -eq 'Up'
                                    │
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │                   Adapter List                         │
        │  ┌─────────────────────────────────────────────────┐  │
        │  │ Ethernet: 192.168.1.100 (default route) ★      │  │
        │  │ Wi-Fi: 10.0.0.50                                │  │
        │  │ VPN: 172.16.0.1                                 │  │
        │  │ VMware: 192.168.56.1                            │  │
        │  └─────────────────────────────────────────────────┘  │
        └───────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │              DNSConfigurator.apply_all()               │
        │                                                        │
        │  FOR EACH adapter:                                     │
        │    1. Backup current DNS settings                      │
        │    2. Set DNS = 127.0.0.1 (IPv4)                      │
        │    3. Set DNS = ::1 (IPv6 if enabled)                 │
        │    4. Verify settings applied                          │
        │    5. Log result                                       │
        └───────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │                 DriftMonitor.start()                   │
        │                                                        │
        │  EVERY 30 seconds:                                     │
        │    - Check DNS for all adapters                        │
        │    - If DNS != 127.0.0.1:                             │
        │        - Log WARNING: "DNS drift detected"             │
        │        - Re-apply DNS settings                         │
        │        - Alert admin                                   │
        │                                                        │
        │  ON adapter change event:                              │
        │    - New adapter UP → Apply DNS 127.0.0.1             │
        │    - VPN connected → Apply DNS 127.0.0.1              │
        └───────────────────────────────────────────────────────┘
```

### 3.3 Security Module (`agent/security/`)

#### 3.3.1 Cấu trúc thư mục

```
agent/security/
├── __init__.py
├── doh_blocker.py        # Block DoH/DoT traffic
├── bypass_detector.py    # Detect DNS bypass attempts
├── cert_validator.py     # Validate SNI ↔ Certificate
└── providers.py          # DoH provider database
```

#### 3.3.2 DoH/DoT Blocking Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DoH/DoT BLOCKING RULES                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ RULE 1: Block DNS to non-localhost                               │
│ ─────────────────────────────────────────────────────────────── │
│ Action: BLOCK                                                    │
│ Direction: Outbound                                              │
│ Protocol: UDP/TCP                                                │
│ Port: 53                                                         │
│ RemoteAddress: NOT 127.0.0.1 AND NOT [upstream_resolvers]       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ RULE 2: Block DoT (DNS over TLS)                                 │
│ ─────────────────────────────────────────────────────────────── │
│ Action: BLOCK                                                    │
│ Direction: Outbound                                              │
│ Protocol: TCP                                                    │
│ Port: 853                                                        │
│ RemoteAddress: ANY                                               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ RULE 3: Block DoH providers (HTTPS port 443)                     │
│ ─────────────────────────────────────────────────────────────── │
│ Action: BLOCK                                                    │
│ Direction: Outbound                                              │
│ Protocol: TCP                                                    │
│ Port: 443                                                        │
│ RemoteAddress: [DOH_PROVIDER_IPS]                               │
│                                                                  │
│ Known DoH Providers:                                             │
│   • dns.google (8.8.8.8, 8.8.4.4)                               │
│   • cloudflare-dns.com (1.1.1.1, 1.0.0.1)                       │
│   • dns.quad9.net (9.9.9.9, 149.112.112.112)                    │
│   • doh.opendns.com (208.67.222.222, 208.67.220.220)            │
│   • dns.nextdns.io                                               │
│   • dns.adguard.com                                              │
│   • doh.cleanbrowsing.org                                        │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ RULE 4: Allow upstream resolvers (DNS only)                      │
│ ─────────────────────────────────────────────────────────────── │
│ Action: ALLOW                                                    │
│ Direction: Outbound                                              │
│ Protocol: UDP/TCP                                                │
│ Port: 53                                                         │
│ RemoteAddress: [configured_upstream_resolvers]                   │
│                                                                  │
│ Priority: HIGHER than block rules                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Role Transition

### 4.1 PacketSniffer - Vai trò mới

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PACKETSNIFFER ROLE TRANSITION                            │
└─────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════╗
║                           HIỆN TẠI (v1.x)                                  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  PacketSniffer:                                                            ║
║    ┌────────────────────────────────────────────────────────────────────┐ ║
║    │ ✗ PRIMARY: Whitelist decision (allow/block)                        │ ║
║    │ ✗ Capture ALL traffic                                              │ ║
║    │ ✗ Extract domain → check whitelist → decide                        │ ║
║    │ ✗ Race condition: packet đã đi rồi                                 │ ║
║    └────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                    │
                                    ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                           SAU REFACTOR (v2.x)                              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  DNS Proxy (PRIMARY):                                                      ║
║    ┌────────────────────────────────────────────────────────────────────┐ ║
║    │ ✓ ALL whitelist decisions go through DNS                           │ ║
║    │ ✓ Block at DNS level (before traffic)                              │ ║
║    │ ✓ Add firewall rule before returning IP                            │ ║
║    │ ✓ No race condition                                                 │ ║
║    └────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║  PacketSniffer (SECONDARY - Optional):                                     ║
║    ┌────────────────────────────────────────────────────────────────────┐ ║
║    │ ○ BYPASS DETECTION ONLY                                             │ ║
║    │ ○ Detect direct IP connections (no DNS)                             │ ║
║    │ ○ Detect DoH traffic patterns                                       │ ║
║    │ ○ SNI validation (domain ↔ cert)                                    │ ║
║    │ ○ Logging & alerting only - NO blocking decision                    │ ║
║    └────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

### 4.2 Decision Priority Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DECISION PRIORITY HIERARCHY                            │
└─────────────────────────────────────────────────────────────────────────────┘

   Priority 1 (Highest): DNS Proxy
   ─────────────────────────────────
   • ALL traffic phải đi qua DNS (đã ép về 127.0.0.1)
   • Whitelist check xảy ra TẠI ĐÂY
   • Firewall rule được add TRƯỚC KHI trả response
   • Không có quyết định nào bypass được layer này

   Priority 2: Firewall (Default-Deny)
   ─────────────────────────────────────
   • Default: BLOCK ALL outbound
   • ALLOW rules chỉ được add bởi DNS Proxy
   • Essential IPs (localhost, DNS upstream) pre-allowed
   • Rules có TTL, tự xóa khi hết hạn

   Priority 3 (Lowest): PacketSniffer - Bypass Detection
   ────────────────────────────────────────────────────────
   • KHÔNG có quyền allow/block
   • Chỉ DETECT và LOG:
       - Direct IP connections (không qua DNS)
       - DoH/DoT attempts
       - SNI mismatch
   • Alert admin khi detect bypass
   • Optional: có thể disable hoàn toàn

   ┌────────────────────────────────────────────────────────────────────┐
   │  QUY TẮC VÀNG: Chỉ DNS Proxy được quyết định allow/block          │
   │                PacketSniffer chỉ quan sát và cảnh báo              │
   └────────────────────────────────────────────────────────────────────┘
```

### 4.3 Module Communication

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MODULE COMMUNICATION MAP                             │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────┐
                    │      Agent Core         │
                    │   (lifecycle.py)        │
                    └───────────┬─────────────┘
                                │ initializes
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│  NetworkManager   │ │   DNSProxy      │ │   SecurityModule    │
└─────────┬─────────┘ └────────┬────────┘ └──────────┬──────────┘
          │                    │                      │
          │ on_adapter_change  │                      │
          │───────────────────>│                      │
          │                    │                      │
          │                    │ check_whitelist      │
          │                    │<─────────────────────│
          │                    │     │                │
          │                    │     ▼                │
          │                    │  ┌──────────────┐    │
          │                    │  │WhitelistState│    │
          │                    │  └──────────────┘    │
          │                    │                      │
          │                    │ add_ip_rule          │
          │                    │─────────────────────>│
          │                    │     │                │
          │                    │     ▼                │
          │                    │  ┌──────────────┐    │
          │                    │  │FirewallMgr   │    │
          │                    │  └──────────────┘    │
          │                    │                      │
          │                    │                      │
          │  ┌─────────────────┼──────────────────────┤
          │  │                 │                      │
          │  ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     PacketSniffer (Optional)                │
│  • Receives: nothing (standalone observer)                  │
│  • Outputs: bypass_detected events → LogSender              │
│  • NO communication with DNS Proxy for decisions            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Configuration Schema

### 5.1 New Config Structure

```json
{
  "dns_proxy": {
    "enabled": true,
    "bind_address": "127.0.0.1",
    "port": 53,
    "ipv6_enabled": true,
    "ipv6_bind_address": "::1",
    
    "upstream_resolvers": [
      {"address": "8.8.8.8", "port": 53, "priority": 1},
      {"address": "1.1.1.1", "port": 53, "priority": 2},
      {"address": "208.67.222.222", "port": 53, "priority": 3}
    ],
    "upstream_timeout": 5.0,
    "upstream_retries": 2,
    
    "cache": {
      "enabled": true,
      "max_entries": 10000,
      "min_ttl": 60,
      "max_ttl": 86400,
      "negative_ttl": 300
    },
    
    "firewall_sync": {
      "timeout": 5.0,
      "retry_on_failure": true,
      "grace_period": 60
    }
  },
  
  "network_manager": {
    "enabled": true,
    "auto_configure_dns": true,
    "monitor_interval": 30,
    "backup_path": "dns_backup.json",
    
    "adapters": {
      "include_virtual": false,
      "include_vpn": true,
      "exclude_patterns": ["VMware*", "VirtualBox*"]
    }
  },
  
  "security": {
    "block_doh": true,
    "block_dot": true,
    "doh_providers_update_url": null,
    
    "bypass_detection": {
      "enabled": true,
      "alert_on_direct_ip": true,
      "alert_on_doh_attempt": true,
      "log_level": "WARNING"
    },
    
    "cert_validation": {
      "enabled": false,
      "strict_mode": false
    }
  },
  
  "packet_sniffer": {
    "enabled": false,
    "mode": "bypass_detection_only",
    "capture_filter": "tcp port 443"
  }
}
```

---

## 6. Migration Strategy

### 6.1 Backward Compatibility

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MIGRATION PHASES                                    │
└─────────────────────────────────────────────────────────────────────────────┘

Phase A: Parallel Mode (Testing)
────────────────────────────────
• DNS Proxy chạy song song với PacketSniffer
• Cả hai đều log decisions
• Compare results để verify DNS Proxy hoạt động đúng
• PacketSniffer vẫn là primary (fallback)
• Duration: 2 tuần

Phase B: DNS Primary (Transition)
──────────────────────────────────
• DNS Proxy trở thành primary
• PacketSniffer chuyển sang bypass detection only
• Firewall rules chỉ được add bởi DNS Proxy
• PacketSniffer không có quyền add rules
• Duration: 2 tuần

Phase C: DNS Only (Production)
───────────────────────────────
• PacketSniffer có thể disable hoàn toàn
• Hoặc giữ lại chỉ cho logging/alerting
• DNS Proxy là single source of truth
• Full production mode
```

### 6.2 Rollback Plan

```python
# Rollback configuration
{
    "dns_proxy": {
        "enabled": false  # Disable DNS Proxy
    },
    "packet_sniffer": {
        "enabled": true,
        "mode": "full"  # Revert to old behavior
    },
    "network_manager": {
        "auto_configure_dns": false  # Don't touch DNS settings
    }
}

# Rollback commands
# 1. Stop agent
# 2. Restore DNS settings: Import-Clixml dns_backup.xml | Set-DnsClientServerAddress
# 3. Update config to rollback values
# 4. Restart agent
```

---

## 7. Testing Requirements

### 7.1 Test Cases

| Test ID | Category | Description | Expected Result |
|---------|----------|-------------|-----------------|
| T01 | DNS Proxy | Query whitelisted domain | Return valid IPs, firewall rule added |
| T02 | DNS Proxy | Query non-whitelisted domain | Return NXDOMAIN, no firewall rule |
| T03 | DNS Proxy | Wildcard match *.google.com | Match and allow |
| T04 | Firewall | IP added before DNS response | Connection succeeds |
| T05 | Firewall | TTL expiry | Rule removed after TTL |
| T06 | Network | DNS drift detection | Auto re-apply DNS |
| T07 | Network | New adapter connected | DNS auto-configured |
| T08 | Security | DoH attempt | Blocked, alert logged |
| T09 | Security | Direct IP connection | Detected, alert logged |
| T10 | Failover | Upstream DNS timeout | Switch to backup resolver |
| T11 | Concurrency | 100 concurrent queries | All processed correctly |
| T12 | Error | Firewall add fails | DNS returns NXDOMAIN or retries |

### 7.2 Performance Benchmarks

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| DNS query latency | < 50ms overhead | Time from query to response |
| Firewall rule add | < 100ms | Time for netsh command |
| Concurrent queries | > 100 qps | Load test with dnspython |
| Memory usage | < 100MB | For 10k cache entries |
| CPU usage | < 5% idle | When only DNS Proxy running |

---

## 8. Appendix

### 8.1 File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `agent/dns_proxy/*` | CREATE | New DNS Proxy module |
| `agent/network_manager/*` | CREATE | New Network Manager module |
| `agent/security/*` | CREATE | New Security module |
| `agent/core/lifecycle.py` | MODIFY | Add new module initialization |
| `agent/firewall/manager.py` | MODIFY | Add TTL-based rule management |
| `agent/capture/sniffer.py` | MODIFY | Change to bypass detection only |
| `agent/config/defaults.py` | MODIFY | Add new config sections |
| `agent_config.json` | MODIFY | Add new configuration options |

### 8.2 Dependencies

```
# New dependencies
dnspython>=2.4.0      # DNS parsing and building
netifaces>=0.11.0     # Network interface detection (optional)
pywin32>=306          # Windows API for adapter management
```

### 8.3 Glossary

| Term | Definition |
|------|------------|
| DNS Proxy | Local DNS server that intercepts and controls DNS queries |
| Sinkhole | DNS server that returns NXDOMAIN for blocked domains |
| DoH | DNS over HTTPS (port 443) |
| DoT | DNS over TLS (port 853) |
| TTL | Time To Live - how long DNS record is valid |
| NXDOMAIN | DNS response indicating domain does not exist |
| SNI | Server Name Indication - domain in TLS handshake |
| Drift | Unintended change to DNS settings |
