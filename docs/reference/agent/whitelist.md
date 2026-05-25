# `agent/whitelist` — Sync & State quản lý whitelist

## Mục đích
Đồng bộ whitelist (domain + pattern + IP) từ server, lưu state thread-safe, resolve domain → IP qua DNS cache, đẩy danh sách IP sang `FirewallManager` để cập nhật allow rules. Kiến trúc 3 lớp: `WhitelistState` (in-memory, hashable diff) → `WhitelistSyncer` (HTTP client, fallback servers) → `WhitelistManager` (orchestrator: sync loop + DNS refresh loop + firewall link). Có thêm `WhitelistMonitor` là helper monitor đứng riêng (hiện không dùng trong production path — xem Gotchas).

## Public API

### `agent/whitelist/manager.py` — Orchestrator

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistManager` | `class` | [manager.py:16](../../../agent/whitelist/manager.py#L16) | Owns `_state`, `_sync`, `dns_cache` (LRU 2000 entries), `resolver` (5 workers), 2 daemon threads |
| `.__init__(config)` | `(Dict)` | [manager.py:17](../../../agent/whitelist/manager.py#L17) | Build syncer từ `server.urls + server.url`. Default sync_interval=60s, cache_ttl=300s |
| `.on_sync_complete(callback)` | `(Callable[[], None]) -> None` | [manager.py:70](../../../agent/whitelist/manager.py#L70) | Đăng ký callback sau mỗi sync (GUI dùng để refresh) |
| `.set_firewall_manager(fw)` | `(FirewallManager) -> None` | [manager.py:97](../../../agent/whitelist/manager.py#L97) | Liên kết, sau đó mọi sync sẽ trigger `_update_firewall_rules` |
| `.start_sync()` | `() -> None` | [manager.py:102](../../../agent/whitelist/manager.py#L102) | Spawn 2 thread: `WhitelistSync` (loop interval) + `DNSRefresh` (check 10s) |
| `.stop_sync()` / `.stop_periodic_updates()` | `() -> None` | [manager.py:125](../../../agent/whitelist/manager.py#L125) | Join cả 2 thread, timeout 5s mỗi cái |
| `.sync_now()` | `() -> bool` | [manager.py:195](../../../agent/whitelist/manager.py#L195) | Sync 1 lần đồng bộ. Build params: `agent_id`, `global_version`, `group_version`, `group_id`, `policy_mode`. Trả `False` khi offline mode (không spam log) |
| `.force_refresh()` | `() -> bool` | [manager.py:394](../../../agent/whitelist/manager.py#L394) | Alias `sync_now()` |
| `.is_allowed(domain, ip=None)` | `(str, Optional[str]) -> bool` | [manager.py:268](../../../agent/whitelist/manager.py#L268) | **Public check** — tăng stats. Check domain trước, IP sau |
| `.is_ip_allowed(ip)` | `(str) -> bool` | [manager.py:286](../../../agent/whitelist/manager.py#L286) | Delegate `_state.is_ip_allowed` |
| `.remove_ip(ip)` | `(str) -> bool` | [manager.py:290](../../../agent/whitelist/manager.py#L290) | Xoá khỏi state + trigger firewall update |
| `.get_stats()` | `() -> Dict` | [manager.py:367](../../../agent/whitelist/manager.py#L367) | Merge state stats + check counters. `last_sync` dạng ISO VN |
| `.get_cache_info()` | `() -> Dict` | [manager.py:383](../../../agent/whitelist/manager.py#L383) | TTL, age, valid flag |
| `.cleanup()` | `() -> None` | [manager.py:399](../../../agent/whitelist/manager.py#L399) | stop + clear state |
| `._state` | `WhitelistState` | [manager.py:23](../../../agent/whitelist/manager.py#L23) | **Public-ish** — `heartbeat` đọc trực tiếp `_state._version` / `_group_version` để báo cáo |
| `._sync` | `WhitelistSyncer` | [manager.py:28](../../../agent/whitelist/manager.py#L28) | Internal HTTP client |
| `._update_firewall_rules()` | `() -> None` | [manager.py:297](../../../agent/whitelist/manager.py#L297) | **Quan trọng**: gom domains + patterns + server hostname → resolve qua cache → union với IP tĩnh → `firewall_manager.update_whitelist(set(), final_ips)`. Truyền `set()` rỗng cho domains để firewall không resolve lại |
| `._sync_loop()` | `() -> None` | [manager.py:136](../../../agent/whitelist/manager.py#L136) | Initial sync + loop với interruptible sleep |
| `._refresh_dns_loop()` | `() -> None` | [manager.py:153](../../../agent/whitelist/manager.py#L153) | Mỗi 10s: lấy keys sắp hết hạn (60s threshold) → resolve lại → nếu update thì gọi `_update_firewall_rules` |

### `agent/whitelist/state.py` — In-memory state

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistState` | `class` | [state.py:12](../../../agent/whitelist/state.py#L12) | RLock-protected. Holds `_domains`, `_patterns`, `_ips`, version metadata, checksum |
| `.update(data)` | `(Dict) -> bool` | [state.py:65](../../../agent/whitelist/state.py#L65) | Parse server response, detect group change → force re-sync. **Trả `False`** khi `up_to_date` hoặc data trùng → caller (manager) sẽ KHÔNG gọi firewall update |
| `.is_domain_allowed(domain)` | `(str) -> bool` | [state.py:133](../../../agent/whitelist/state.py#L133) | 3 cách match: exact → `fnmatch` pattern → subdomain (parent walk) |
| `.is_ip_allowed(ip)` | `(str) -> bool` | [state.py:157](../../../agent/whitelist/state.py#L157) | Exact set membership |
| `.get_stats()` | `() -> Dict` | [state.py:162](../../../agent/whitelist/state.py#L162) | counts + version + checksum |
| `.get_all_domains()` / `get_all_patterns()` / `get_all_ips()` | `() -> Set[str]` | [state.py:174-184](../../../agent/whitelist/state.py#L174) | Trả **copy** (an toàn dùng ngoài lock) |
| `.remove_ip(ip)` | `(str) -> bool` | [state.py:186](../../../agent/whitelist/state.py#L186) | Idempotent — `False` nếu không có |
| `.clear()` | `() -> None` | [state.py:194](../../../agent/whitelist/state.py#L194) | Reset toàn bộ |
| `._parse_entries(data)` | `(Dict) -> Tuple[Set, Set, Set]` | [state.py:27](../../../agent/whitelist/state.py#L27) | Parse `data["domains"]` (string hoặc dict với `value/type`), `data["ips"]`. Pattern detect: `type=="pattern"` hoặc có `*`/`?` |
| `._calculate_checksum()` | `() -> str` | [state.py:124](../../../agent/whitelist/state.py#L124) | MD5 của sorted JSON — dùng để diff |
| `._version` / `_group_version` / `_group_id` / `_policy_mode` | `str` | [state.py:20-23](../../../agent/whitelist/state.py#L20) | **Đọc trực tiếp** bởi manager & heartbeat |

### `agent/whitelist/sync.py` — HTTP client + fallback servers

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistSyncer` | `class` | [sync.py:12](../../../agent/whitelist/sync.py#L12) | Có fallback server list, exponential backoff, JWT auth |
| `.__init__(server_urls, agent_id, config=None, connect_timeout=10, read_timeout=30, max_retries=3)` | | [sync.py:14](../../../agent/whitelist/sync.py#L14) | Giữ `current_server_index` để dính server đã work |
| `.current_url` | `@property -> str` | [sync.py:31](../../../agent/whitelist/sync.py#L31) | Build URL `/api/whitelist/agent-sync` |
| `.sync_with_server(params)` | `(Dict) -> Dict` | [sync.py:47](../../../agent/whitelist/sync.py#L47) | **Trả format chuẩn**: `{"success": bool, "data": ...}` hoặc `{"success": False, "error": str, "offline": True?}` |
| `.extract_domain_value(domain_data)` | `(str|Dict) -> Optional[str]` | [sync.py:138](../../../agent/whitelist/sync.py#L138) | Helper — nhưng `_state._parse_entries` đã có logic riêng, không dùng |
| `._get_headers()` | `() -> Dict[str, str]` | [sync.py:40](../../../agent/whitelist/sync.py#L40) | Set User-Agent + `get_auth_headers(config)` |
| `._build_sync_url(base)` | `(str) -> str` | [sync.py:37](../../../agent/whitelist/sync.py#L37) | |

**Flow `sync_with_server`** (đáng ghi nhớ):
1. Nếu `server_urls` rỗng → return `{success: False, offline: True}` (caller bỏ qua, không log)
2. Lấy headers. Nếu không có `Authorization` lẫn `X-Agent-Token` → fail fast với error (không phải offline) — caller log warning
3. Loop `max_retries` lần với current server. HTTP 401 → **break** (không retry, đợi token refresh). Lỗi khác → exponential backoff `2**attempt`s
4. Nếu vẫn fail và có server khác → loop qua fallback, server nào OK thì `current_server_index = i` (sticky)

### `agent/whitelist/monitor.py` — Standalone monitor (legacy/optional)

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistMonitor` | `class` | [monitor.py:10](../../../agent/whitelist/monitor.py#L10) | Helper wrapping `sync_callback` thành thread loop. Hiện **không được dùng** ở `lifecycle.py` — `WhitelistManager._sync_loop` đã làm việc tương đương |
| `.start()` / `.stop()` / `.get_status()` | | | API tương tự manager |

## Ai gọi module này
- `agent/core/lifecycle.py` — tạo `WhitelistManager`, gọi `set_firewall_manager`, `sync_now`, `start_sync`, `stop_sync`
- `agent/core/handlers.py` — `whitelist.is_allowed(domain)`, `whitelist.is_ip_allowed(ip)` qua `safe_execute`
- `agent/services/heartbeat.py` — đọc `whitelist._state._version` / `_group_version` qua `get_whitelist_versions` callback
- `agent/gui_qt/views/whitelist.py` + `controllers/whitelist_controller.py` — đọc stats, trigger force_refresh

## Module này gọi ra
- `agent/core/token_manager` — `get_auth_headers` cho sync request
- `agent/cache/lru_cache.LRUCache` — DNS cache 2000 entries, TTL 300s
- `agent/network.OptimizedDNSResolver` — resolve domains parallel
- `agent/firewall` — gọi qua `_firewall_manager.update_whitelist(domains, ips)` (interface lỏng, hasattr check)
- `requests` — HTTP

## Đã có sẵn — đừng viết lại
- Cần check 1 domain có whitelisted không (kể cả wildcard, subdomain)? → `WhitelistManager.is_allowed(domain)` — **đừng** tự lặp pattern match. Logic 3 lớp (exact / fnmatch / parent walk) đã ở `state.is_domain_allowed`
- Cần force resync vì biết server đổi data? → `sync_now()` hoặc `force_refresh()`. Server gửi `force_sync=True` qua heartbeat response sẽ tự trigger
- Cần lấy version để gửi cho server? → `_state._version` (global), `_state._group_version` (group). Heartbeat đã wire qua `get_whitelist_versions` lambda
- Cần fallback giữa nhiều server URLs? → `WhitelistSyncer` đã làm — cứ đưa list vào, nó tự switch & sticky
- Cần resolve domain → IP với cache? → Manager đã sẵn `self.dns_cache` + `self.resolver`. **Đừng** tạo `OptimizedDNSResolver` mới chỉ để resolve 1 domain trong code path đã có whitelist

## Gotchas
- **`set_firewall_manager` mới đăng ký link**, không trigger update ngay. Phải `sync_now()` (hoặc đợi periodic) để firewall thật sự được populate. Lifecycle.py đã sync trước khi link firewall, nên thứ tự đúng.
- **`update` trả `False` khi không thay đổi** (state.py:91-98) — manager dùng tín hiệu này để bỏ qua `_update_firewall_rules`, nhưng vẫn gọi `_notify_sync_complete` để GUI refresh "last sync time". Đảo logic ⇒ firewall update mỗi 60s vô ích.
- **Group change force full sync** (state.py:73-77): nếu admin đổi group cho agent, server vẫn có thể trả `up_to_date=True` (cùng global version). State check `group_id` đổi → coi như changed.
- **`_parse_entries` chấp nhận cả `string` và `dict`** (state.py:33-44). Server cũ trả list[str], server mới trả list[{value,type}]. Mỗi format có path riêng — đổi schema phải test cả 2.
- **Pattern detect ngầm**: nếu value chứa `*` hoặc `?`, **tự động** coi là pattern kể cả khi `type="domain"` (state.py:50). Server không cần báo type cho wildcard.
- **`_update_firewall_rules` pass `domains=set()` rỗng** (manager.py:356): cố ý — manager đã resolve xong, để firewall không resolve lại lần nữa. Nếu sửa, double-resolve sẽ làm chậm và đôi khi out-of-sync.
- **DNS cache TTL không bằng record TTL**: `dns_cache.set(domain, ips, ttl=self._cache_ttl)` (manager.py:344). Manager dùng 1 TTL cố định (300s), bỏ TTL thật của DNS record. Đổi nếu muốn respect record TTL — hiện chấp nhận để cache rule đơn giản.
- **`_refresh_dns_loop` chạy `_update_firewall_rules` ngầm** khi có domain mới resolved (manager.py:188). Cẩn thận debounce — nếu hàng trăm domain refresh cùng lúc sẽ batch update firewall liên tục.
- **`WhitelistMonitor` là dead code đường production**: vẫn có trong `__init__.py` exports. Đừng nhầm đây là cái đang chạy. Nếu chắc chắn không dùng nữa → xoá để giảm noise.
- **Server URLs default `["http://localhost:5000"]`** (manager.py:95, heartbeat.py:57, sender.py:54) khi config rỗng — KHÁC với lifecycle/registry coi rỗng là offline. Khá lệch behavior; muốn align nên empty → empty xuyên suốt.
- **`is_allowed(domain, ip)` đếm vào stats** (manager.py:271-283) — đừng gọi nó cho mục đích "peek". Nếu cần peek không tăng counter, dùng `_state.is_domain_allowed`/`is_ip_allowed` thẳng.
- **`sync_now` build params bằng `_state._version` raw** — nếu version chưa từng có giá trị (`""`), gửi `None`. Server phía whitelist endpoint phải xử lý cả 2.
- **2 thread `WhitelistSync` + `DNSRefresh`** chia sẻ `_running`. Stop sẽ join lần lượt với timeout 5s mỗi cái → tổng cộng có thể tới 10s. Acceptable cho shutdown.
