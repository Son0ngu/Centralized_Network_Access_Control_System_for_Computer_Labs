# `agent/cache` — LRU Cache + `DNSRecord` dataclass

## Mục đích
Cache LRU thread-safe với TTL per-entry, dùng chủ yếu cho DNS lookup nhưng generic — value `Any`. Cùng module định nghĩa `DNSRecord` dataclass (return type của DNS resolver).

Module 1 file (`lru_cache.py`).

## Public API

### `agent/cache/lru_cache.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `DNSRecord` | `@dataclass` | [lru_cache.py:13](../../../agent/cache/lru_cache.py#L13) | `ipv4: Tuple[str,...]`, `cname: Optional[str]`, `ttl: int`, `resolved_at: float` |
| `CacheValue` | `@dataclass` | [lru_cache.py:20](../../../agent/cache/lru_cache.py#L20) | Generic wrapper. **Hiện không dùng** — `LRUCache` lưu raw value thay vì wrap. Để lại làm fixture |
| `LRUCache` | `class` | [lru_cache.py:26](../../../agent/cache/lru_cache.py#L26) | RLock-protected. `OrderedDict` + 2 dict song song (`_timestamps`, `_ttls`) |
| `.__init__(max_size=1000, default_ttl=300.0)` | `(int, float)` | [lru_cache.py:27](../../../agent/cache/lru_cache.py#L27) | |
| `.get(key)` | `(str) -> Optional[Any]` | [lru_cache.py:43](../../../agent/cache/lru_cache.py#L43) | **Side effects**: nếu expired → xoá, `_misses++`; nếu hit → `move_to_end`, `_hits++`; miss → `_misses++`. Trả `None` cả khi key thật sự là `None` (cẩn thận) |
| `.set(key, value, ttl=None)` | `(str, Any, Optional[float]) -> None` | [lru_cache.py:62](../../../agent/cache/lru_cache.py#L62) | Idempotent (remove rồi add lại → reset position). Evict oldest khi full |
| `.delete(key)` | `(str) -> bool` | [lru_cache.py:82](../../../agent/cache/lru_cache.py#L82) | `False` nếu key không có |
| `.clear()` | `() -> None` | [lru_cache.py:90](../../../agent/cache/lru_cache.py#L90) | Reset toàn bộ |
| `.cleanup_expired()` | `() -> int` | [lru_cache.py:97](../../../agent/cache/lru_cache.py#L97) | Xoá entries hết hạn. Trả số entries xoá. Không tự gọi — caller phải schedule |
| `.get_expiring_keys(threshold_seconds=60.0)` | `(float) -> list[str]` | [lru_cache.py:112](../../../agent/cache/lru_cache.py#L112) | List key sắp/đã hết hạn trong vòng `threshold` giây. **Dùng bởi `WhitelistManager._refresh_dns_loop`** để pre-refresh trước khi expire |
| `.get_stats()` | `() -> Dict` | [lru_cache.py:134](../../../agent/cache/lru_cache.py#L134) | size, max_size, hits, misses, hit_rate (%) |
| `.__len__()` / `.__contains__(key)` | | [lru_cache.py:147-151](../../../agent/cache/lru_cache.py#L147) | `in` operator gọi `.get(key) is not None` ⇒ tăng hit/miss counter. **Cẩn thận** |
| `HighPerformanceLRUCache` | `= LRUCache` (alias) | [lru_cache.py:154](../../../agent/cache/lru_cache.py#L154) | Tương thích code cũ |
| `._remove(key)` | `(str) -> None` | [lru_cache.py:76](../../../agent/cache/lru_cache.py#L76) | Pop 3 dict song song |

## Ai gọi module này
- `agent/whitelist/manager.py` — `LRUCache(max_size=2000, default_ttl=300)` cho DNS cache
- `agent/network/dns_resolver.py` — import `DNSRecord` làm return type
- `agent/cache/__init__` re-export — không có caller ngoài DNS path

## Module này gọi ra
- `agent/shared/time_utils` — `now`, `is_cache_valid`
- stdlib: `collections.OrderedDict`, `threading.RLock`, `dataclasses`

## Đã có sẵn — đừng viết lại
- Cần thread-safe LRU với TTL? → dùng cái này — **đừng** wrap `functools.lru_cache` (không có TTL) hay `cachetools.TTLCache` (thêm dep)
- Cần biết key nào sắp expire? → `get_expiring_keys(threshold)` — handy cho pre-refresh, **đừng** iterate `.cache` để tự tính
- Cần wipe expired periodically? → `cleanup_expired()` — nhớ schedule, không tự gọi
- Cần đo hit rate? → `get_stats()` trả `hit_rate` (%)

## Gotchas
- **`__contains__` đếm hit/miss** (lru_cache.py:150): `if key in cache` thay đổi statistics. Nếu muốn check tồn tại mà không đếm — phải dùng `cache._cache.__contains__(key)` raw. Hiện không ai cần.
- **`get(key)` trả `None` khả nghi**: nếu app cache value `None` chính thức, không phân biệt được với "miss" hay "expired". Hiện DNS cache lưu `set` IP nên không xảy ra. Nếu cache `None` được, dùng sentinel object riêng.
- **3 dict song song** (`_cache`, `_timestamps`, `_ttls`): nếu thread bị kill giữa `set` (khả năng cực thấp vì RLock + GIL), có thể desync. Hiện chấp nhận.
- **Eviction policy `while len >= max_size`** (lru_cache.py:68): evict cho tới khi có chỗ. Trong điều kiện bình thường evict 1 entry/lần. Nếu `max_size` bị thay đổi runtime (không có API public), có thể evict nhiều.
- **`get_expiring_keys` lấy cả keys ĐÃ expired** (threshold ≥ 0). Nếu chỉ muốn keys "sắp hết" (chưa expire), filter thêm. Tài liệu docstring có nhắc.
- **`CacheValue` dataclass dead code** — chỉ định nghĩa, không dùng. Nếu muốn rewrite cache với metadata gắn giá trị, dùng `CacheValue`; hiện 2 dict song song hoạt động OK.
- **`HighPerformanceLRUCache` chỉ là alias** — đừng tưởng là implementation khác. Tên gây hiểu nhầm; tránh dùng tên này trong code mới.
- **Không persist**: cache mất khi agent restart. DNS lookups phải resolve lại lần đầu — chấp nhận trade-off.
- **`max_size` không là `maxsize` quan trọng** — chỉ là hint. Memory thực tế bị chiếm bởi values (set of IP strings ~ vài KB/entry). 2000 entries × ~1KB = ~2MB ⇒ OK.
- **Thread-safety chỉ cho cache ops**, không cho value bên trong. Nếu value là mutable (vd `set`), caller mutate sau `get` mà không lock → race condition. Whitelist manager dùng `set(...)` copy khi gọi `dns_cache.get(domain)`. Pattern an toàn.
