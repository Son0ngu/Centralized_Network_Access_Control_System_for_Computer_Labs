# `agent/shared` - Tiện ích dùng chung toàn agent

## Mục đích
Helpers không phụ thuộc business logic: thời gian theo timezone Việt Nam, đo uptime, đọc thông tin OS. Là module **được import nhiều nhất** trong agent (22/60 file). Trước khi viết bất kỳ helper time hoặc os nào - check ở đây.

## Public API

### `agent/shared/time_utils.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `VIETNAM_TZ` | `tzinfo` (constant) | [time_utils.py:24](../../../agent/shared/time_utils.py#L24) | Timezone Asia/Ho_Chi_Minh, fallback UTC+7 nếu thiếu `tzdata` |
| `now()` | `() -> float` | [time_utils.py:34](../../../agent/shared/time_utils.py#L34) | Unix timestamp hiện tại - alias `cache_time` |
| `now_vietnam()` | `() -> datetime` | [time_utils.py:44](../../../agent/shared/time_utils.py#L44) | `datetime` aware theo VN tz |
| `now_iso()` | `() -> str` | [time_utils.py:54](../../../agent/shared/time_utils.py#L54) | ISO 8601 string VN tz - alias `agent_time`. **Dùng cái này khi gửi server.** |
| `now_server_compatible(ts=None)` | `(Optional[float]) -> str` | [time_utils.py:64](../../../agent/shared/time_utils.py#L64) | Convert Unix ts → ISO VN. None ⇒ now |
| `sleep(duration)` | `(float) -> None` | [time_utils.py:79](../../../agent/shared/time_utils.py#L79) | `time.sleep` no-op khi `duration<=0` |
| `is_cache_valid(ts, ttl)` | `(float, float) -> bool` | [time_utils.py:94](../../../agent/shared/time_utils.py#L94) | Check cache còn hạn |
| `cache_age(ts)` | `(float) -> float` | [time_utils.py:108](../../../agent/shared/time_utils.py#L108) | Tuổi cache (giây) |
| `uptime()` | `() -> float` | [time_utils.py:125](../../../agent/shared/time_utils.py#L125) | Uptime agent từ lúc import module |
| `uptime_string()` | `() -> str` | [time_utils.py:135](../../../agent/shared/time_utils.py#L135) | Định dạng `"2h 30m 15s"` |
| `reset_uptime()` | `() -> None` | [time_utils.py:149](../../../agent/shared/time_utils.py#L149) | Chỉ dùng trong test |
| `debug_time_info()` | `() -> dict` | [time_utils.py:159](../../../agent/shared/time_utils.py#L159) | Snapshot debug (unix/iso/uptime/tz) |

**Aliases (giữ tương thích code cũ):** `agent_time` = `now_iso`, `cache_time` = `now`.

### `agent/shared/os_info.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `get_os_details()` | `() -> Dict[str, str]` | [os_info.py:55](../../../agent/shared/os_info.py#L55) | Trả `{platform, name, version, arch}`. Windows: tự detect Win11 qua build ≥ 22000 |

### `agent/shared/server_urls.py` - Resolver server URL chung

Single source of truth cho mọi component cần list server URL (registration, whitelist sync, heartbeat, log sender). Trước đây mỗi component tự fallback hardcode `http://localhost:5000` hoặc Render production URL — đã thống nhất ở đây (P0.5).

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `DEV_DEFAULT_URL` | `"http://localhost:5000"` | [server_urls.py:18](../../../agent/shared/server_urls.py#L18) | Constant chỉ dùng khi caller opt-in `allow_dev_default=True`. |
| `collect_server_urls(config, allow_dev_default=False)` | `(Optional[Dict], bool) -> List[str]` | [server_urls.py:21](../../../agent/shared/server_urls.py#L21) | Gom `config.server.urls + config.server.url + config.server_url`, strip whitespace, dedupe giữ thứ tự. Empty config + `allow_dev_default=False` ⇒ `[]` (caller phải xử lý OFFLINE mode). |

**Quy tắc**: production caller LUÔN dùng `allow_dev_default=False`. Empty list = OFFLINE = component skip silently. Chỉ test/dev script được set `True`.

## Ai gọi module này
Hầu hết các package agent: `core`, `firewall`, `whitelist`, `services`, `logging_module`, `capture`, `network`, `cache`, `config`, `utils`, `gui` (22/60 file). Là leaf module - sửa API ở đây ảnh hưởng toàn agent.

## Đã có sẵn - đừng viết lại
- Cần timestamp gửi server? → `now_iso()`
- Cần `datetime` để format/parse? → `now_vietnam()`
- Cần TTL check? → `is_cache_valid(ts, ttl)` - **đừng** viết `time.time() - ts > ttl` rải rác
- Cần tên OS Windows chính xác (kể cả Win11)? → `get_os_details()` - **đừng** dùng thẳng `platform.system()`

## Gotchas
- `_start_time` được set ở **import time** (line 27). Nếu module được import lazily, uptime sẽ tính từ thời điểm import đầu tiên, không phải lúc agent start. Hiện tại OK vì `time_utils` được import sớm trong `agent_gui.py` chain.
- `ZoneInfo("Asia/Ho_Chi_Minh")` fail khi build PyInstaller thiếu `tzdata` → fallback fixed offset UTC+7 (line 17). Không có DST nên không sai, nhưng log warning sẽ xuất hiện 1 lần khi khởi động.
- `winreg` chỉ import khi `sys.platform == "win32"` (os_info.py:8) - code này **không chạy được** trên Linux/Mac, sẽ raise `NameError` ở `_detect_windows_info`. Hiện chấp nhận được vì agent là Windows-only.
- Server có file `server/time_utils.py` **độc lập** (không share). Nếu sửa logic timezone, nhớ đồng bộ cả 2 - xem `docs/reference/server/...` (TBD).
