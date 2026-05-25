# `agent/network` — DNS Resolver (parallel, IPv4-only)

## Mục đích
Resolve domain → IP với `dnspython` (sync) và `aiodns` (async). Có thread pool để resolve nhiều domain song song (chunked để không quá tải máy yếu). Trả `DNSRecord` (có TTL chính xác từ response — quan trọng cho cache). Fallback về `socket.getaddrinfo` khi cả hai stack fail.

Module 1 file (`dns_resolver.py`). IPv4 only — không query AAAA, không trả IPv6. Có nguyên do: firewall agent IPv4-only (xem [firewall.md](firewall.md) Gotchas).

## Public API

### `agent/network/dns_resolver.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `OptimizedDNSResolver` | `class` | [dns_resolver.py:48](../../../agent/network/dns_resolver.py#L48) | Holds `dns.resolver.Resolver` + `ThreadPoolExecutor` (named `DNSResolver`). Auto `atexit.register(self.shutdown)` |
| `.__init__(max_workers=10, timeout=10.0)` | `(int, float)` | [dns_resolver.py:51](../../../agent/network/dns_resolver.py#L51) | resolver.timeout=`timeout`, resolver.lifetime=`timeout*2`. Dùng system nameservers (Machine DNS) |
| `.resolve_domain_sync(domain)` | `(str) -> DNSRecord` | [dns_resolver.py:72](../../../agent/network/dns_resolver.py#L72) | Query A → CNAME nếu rỗng → fallback `socket`. TTL = min của tất cả RRsets trong chain |
| `.resolve_domain_async(domain)` | `async (str) -> DNSRecord` | [dns_resolver.py:120](../../../agent/network/dns_resolver.py#L120) | `aiodns` parallel A query. Tạo resolver mới mỗi call (gắn loop hiện tại) — tránh "attached to different loop" |
| `.resolve_multiple_parallel(domains)` | `(List[str]) -> Dict[str, DNSRecord]` | [dns_resolver.py:187](../../../agent/network/dns_resolver.py#L187) | **Chunked**: 20 domain/chunk, timeout = `self.timeout * 4` per chunk, sleep 0.5s giữa các chunk. Domain miss → fallback record |
| `.resolve_multiple_async(domains)` | `async (List[str]) -> Dict[str, DNSRecord]` | [dns_resolver.py:236](../../../agent/network/dns_resolver.py#L236) | `asyncio.gather` tất cả, exception → fallback |
| `.shutdown()` | `() -> None` | [dns_resolver.py:310](../../../agent/network/dns_resolver.py#L310) | Idempotent. `executor.shutdown(wait=True)`. Đã auto register atexit |
| `._query_aiodns(domain, record_type)` | `async` | [dns_resolver.py:169](../../../agent/network/dns_resolver.py#L169) | Internal. Tạo `aiodns.DNSResolver(loop=current_loop)` mỗi call |
| `._fallback_resolve(domain)` | `(str) -> DNSRecord` | [dns_resolver.py:264](../../../agent/network/dns_resolver.py#L264) | `socket.getaddrinfo(AF_INET, SOCK_STREAM)`. Nếu input đã là IP, trả thẳng (ttl=300). IPv6 input → trả empty IPs |
| `._async_fallback_resolve(domain)` | `async` | [dns_resolver.py:296](../../../agent/network/dns_resolver.py#L296) | Chạy `_fallback_resolve` trong executor |
| `._is_ip_address(s)` | `(str) -> bool` | [dns_resolver.py:303](../../../agent/network/dns_resolver.py#L303) | `ipaddress.ip_address` |
| `_min_ttl_dnspython(answer)` | `(Answer) -> Optional[int]` | [dns_resolver.py:23](../../../agent/network/dns_resolver.py#L23) | **Quan trọng**: lấy min TTL từ **tất cả RRsets** trong response (bao gồm CNAME chain) — vì dnspython tự follow CNAME khi query A |

`DNSRecord` được định nghĩa ở [agent/cache/lru_cache.py:13](../../../agent/cache/lru_cache.py#L13) — xem [cache.md](cache.md).

## Ai gọi module này
- `agent/whitelist/manager.py` — owner chính, dùng cả `resolve_domain_sync` (DNS refresh loop) lẫn `resolve_multiple_parallel` (sync update)
- `agent/firewall/manager.py` — lazy import `OptimizedDNSResolver` trong `_resolve_domains_to_ips` (manager.py:485) khi cần resolve trực tiếp ở firewall layer

## Module này gọi ra
- `dnspython` (`dns.resolver`) — sync queries
- `aiodns` — async queries
- `concurrent.futures.ThreadPoolExecutor` — parallel sync
- `socket.getaddrinfo` — fallback
- `agent/shared/time_utils.now` — set `resolved_at`
- `agent/cache/lru_cache.DNSRecord` — return type

## Đã có sẵn — đừng viết lại
- Cần resolve 1 domain? → `resolver.resolve_domain_sync(d)` — đã có CNAME chain, TTL accurate, fallback socket
- Cần resolve nhiều domain? → `resolver.resolve_multiple_parallel(list)` — đã chunk, có timeout protection, không gây spike CPU
- Cần TTL chính xác từ dns response? → `_min_ttl_dnspython(answer)` — **đừng** dùng `answer.ttl` raw (sẽ miss TTL của CNAME records trong chain)
- Cần resolve trong async context? → `resolve_domain_async` hoặc `resolve_multiple_async`

## Gotchas
- **`sys.path.insert` ở top** (dns_resolver.py:14): chèn parent dir vào path để `from shared.time_utils` work khi run module độc lập. Side effect ở import time — ảnh hưởng cả process. Hơi bẩn nhưng được dùng cho test/standalone scripts.
- **IPv4-only**: chỉ query A records (dns_resolver.py:84), AAAA bị bỏ. Fallback cũng `AF_INET` (dns_resolver.py:284). Nếu admin muốn IPv6 — phải sửa cả 3 chỗ.
- **CNAME được follow ngầm bởi dnspython**: query A thường trả về IP của hostname cuối chain. Code chỉ resolve CNAME riêng (line 95) khi A rỗng. Trường hợp này hiếm (server thường có A đầu chain), nhưng cần thiết cho domain dạng `*.cloudfront.net`.
- **TTL min từ chain**: `_min_ttl_dnspython` (dns_resolver.py:23) đảm bảo cache hết hạn cùng record ngắn nhất. Nếu chỉ lấy `answer.ttl` ⇒ cache lâu hơn CNAME upstream cho phép.
- **`aiodns` resolver tạo mới mỗi call** (dns_resolver.py:176): vì instance gắn cứng với event loop khởi tạo. Nếu cache resolver thì sẽ raise `attached to a different loop` khi gọi từ loop khác. Cost: tạo resolver mỗi call (~ms) — acceptable.
- **Chunked parallel có `time.sleep(0.5)`** (dns_resolver.py:223) giữa các chunk — không phải `shared.sleep`. Cố ý dùng `time.sleep` raw để không phụ thuộc shared module trong path performance.
- **`resolve_multiple_parallel` luôn trả đủ keys** (dns_resolver.py:230-232) — nếu chunk timeout, missing domain sẽ được fill bằng fallback record (có thể trả empty `ipv4=()`). Caller không cần check key missing — chỉ check `record.ipv4` rỗng.
- **`shutdown()` đã register atexit** (line 70). Manager nào tạo resolver mới (vd firewall.manager._resolve_domains_to_ips) cũng register thêm 1 atexit handler nữa ⇒ chồng nhau. Hiện chấp nhận; tránh tạo `OptimizedDNSResolver` trong loop.
- **`_shutdown` flag check trước mỗi resolve**: nếu đã shutdown, trả thẳng fallback record (có thể là empty). Caller không bị crash nhưng dữ liệu sai sau atexit.
- **System nameservers** dùng từ `dns.resolver.Resolver()` mặc định — đọc từ `/etc/resolv.conf` (POSIX) hoặc IPHelper API (Windows). Nếu máy bị thay đổi nameserver runtime, resolver KHÔNG tự reload — phải restart agent. Hiếm gặp.
