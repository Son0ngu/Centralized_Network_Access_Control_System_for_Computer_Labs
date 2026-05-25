# `server/app.py` + `server/time_utils.py` — Bootstrap + Time helpers

## Mục đích
- `app.py`: Entry point Flask. Wire toàn bộ DI chain (models → services → controllers), register blueprints, register web routes (HTML templates), error handlers, Socket.IO events. Chạy SocketIO server bằng `gevent`.
- `time_utils.py`: Helpers timezone Việt Nam **độc lập với agent/shared/time_utils** — đừng nhầm. Server có file riêng vì server không import `agent/*`.

## Public API

### `server/app.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `create_app()` | `() -> (Flask, SocketIO)` | [app.py:68](../../../server/app.py#L68) | Single-shot factory. Idempotent qua `_app_initialized` flag (cho Werkzeug reloader). Validate config → CORS → SocketIO → connect Mongo → init indexes → `register_controllers` → main routes → error handlers → SocketIO events. Lưu services lên `app` |
| `initialize_database_indexes(app, db)` | | [app.py:169](../../../server/app.py#L169) | Construct mọi Model class một lần để trigger `_setup_indexes()` của từng model |
| `register_controllers(app, socketio, db)` | `→ (log, agent, group, api_key, user)` | [app.py:194](../../../server/app.py#L194) | **Trái tim của DI**: tạo theo thứ tự models → jwt_service → services → middleware init → controllers → blueprints. Trả 5 service ref dùng tiếp ở `register_main_routes` |
| `register_main_routes(app, log_service, agent_service)` | | [app.py:318](../../../server/app.py#L318) | Render HTML pages: `/`, `/agents`, `/groups`, `/groups/<id>`, `/whitelist`, `/logs`, `/api-keys`, `/login`, `/admin/users`, `/admin/audit`, `/profile`. Plus health: `/api/health`, `/api/config` |
| `register_error_handlers(app)` | | [app.py:447](../../../server/app.py#L447) | 404/500 → JSON nếu path bắt đầu `/api/`, ngược lại render `404.html`/`500.html` |
| `register_socketio_events(socketio)` | | [app.py:469](../../../server/app.py#L469) | `connect`, `disconnect`, `ping` |
| `format_datetime_filter(dt, format)` | template filter | [app.py:93](../../../server/app.py#L93) | Đăng ký Jinja filter `format_datetime` — parse ISO via `parse_agent_timestamp` rồi format |

**Top-level monkey patch** (app.py:1-3): `gevent.monkey.patch_all()` PHẢI chạy đầu tiên trước mọi import — nếu không socket/SSL sẽ blocking thread.

**`sys.path.insert(0, ...)`** (app.py:9): cho phép `from models.X` không cần prefix `server.`.

### `server/time_utils.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `VIETNAM_TZ` | `ZoneInfo("Asia/Ho_Chi_Minh")` | [time_utils.py:26](../../../server/time_utils.py#L26) | Constant |
| `FUTURE_DRIFT_TOLERANCE` | `timedelta(minutes=5)` | [time_utils.py:27](../../../server/time_utils.py#L27) | Ngưỡng "timestamp tương lai bất thường" |
| `now_vietnam()` | `() -> datetime` | [time_utils.py:33](../../../server/time_utils.py#L33) | `datetime.now(VIETNAM_TZ)` (aware) |
| `now_iso()` | `() -> str` | [time_utils.py:37](../../../server/time_utils.py#L37) | ISO 8601 VN |
| `to_vietnam(dt)` | `(Optional[datetime]) -> Optional[datetime]` | [time_utils.py:41](../../../server/time_utils.py#L41) | Naive → gắn tz VN. Aware → convert. None → None |
| `parse_agent_timestamp(value)` | `(Any) -> datetime` | [time_utils.py:123](../../../server/time_utils.py#L123) | **Sponge function**: nhận `datetime`/`int`/`float`/`str`. Hỗ trợ ISO + 3 format strftime. Bất kỳ giá trị nào không parse được → `now_vietnam()`. Áp dụng `_normalise_future_timestamp` để clamp |
| `format_datetime(value, fmt="%Y-%m-%d %H:%M:%S")` | `(Any, str) -> str` | [time_utils.py:164](../../../server/time_utils.py#L164) | None → `"N/A"`. Parse rồi strftime |
| `calculate_age_seconds(value)` | `(Any) -> float` | [time_utils.py:185](../../../server/time_utils.py#L185) | `(now_vietnam() - dt).total_seconds()` |
| `get_time_ago_string(value)` | `(Any) -> str` | [time_utils.py:195](../../../server/time_utils.py#L195) | `"5 minutes ago"` / `"2 hours ago"` / ... |
| `_normalise_future_timestamp(dt, reference=None)` | | [time_utils.py:53](../../../server/time_utils.py#L53) | **Quan trọng**: nếu `dt` xa hơn reference > 5 phút, thử trừ UTC offset (sửa double-conversion legacy bugs) hoặc clamp về reference. Log warning |
| `_parse_with_known_formats(value)` | | [time_utils.py:104](../../../server/time_utils.py#L104) | Fallback parse 3 format string |

## Ai gọi module này

`app.py`:
- Bản thân là entry. Chạy bằng `python app.py` từ `server/`. Production deploy thường wrap qua gunicorn/uvicorn nhưng repo này dùng `socketio.run` trực tiếp với gevent.

`time_utils.py`:
- Mọi model, service, controller server-side — gần như **tất cả file `.py` trong `server/`**
- Tests import `now_vietnam` để dựng fixture

## Module này gọi ra
- `flask`, `flask_socketio`, `flask_cors`
- `pymongo` (gián tiếp qua `database.config`)
- `gevent.monkey` cho async
- stdlib `datetime`, `zoneinfo`

## Đã có sẵn — đừng viết lại
- Cần ISO timestamp gửi client? → `time_utils.now_iso()` — **đừng** dùng `datetime.now().isoformat()` (mất tz)
- Cần parse timestamp lạ (agent gửi format khác nhau)? → `parse_agent_timestamp(value)` — đã handle datetime/int/float/str ISO/strftime + clamp drift
- Cần format datetime cho template? → đã register filter `{{ dt|format_datetime }}` — không tự strftime
- Cần "5 minutes ago"? → `get_time_ago_string(value)`
- Cần Mongo db? → `database.config.get_database(config)` — **đừng** `MongoClient(...)` thẳng (xem [database.md](database.md))
- Cần auth header check? → middleware decorator (xem [middleware.md](middleware.md))
- Cần lifecycle log entry chuẩn? → ở server log nhận agent record, không có helper riêng — agent có `build_lifecycle_log`

## Gotchas

### App bootstrap
- **Monkey patch ở line 1-3 PHẢI là đầu tiên** — bất kỳ `import socket` nào trước đó (kể cả gián tiếp) sẽ làm `ssl` & `requests` chạy blocking. Đừng đặt logging/dotenv lên trên.
- **`_app_initialized` flag** (app.py:66-80): tránh re-init khi Werkzeug reloader chạy. Production dùng `use_reloader=False` (line 515) nên không quan trọng, nhưng dev mode cần flag này.
- **Hai chuỗi controller registration cho RBAC** (app.py:138 cho 5 service core + 226-244 cho RBAC service chain): nếu thêm controller mới, đảm bảo register cả 5 trả về phù hợp `register_main_routes` signature.
- **`whitelist_profile_model.collection.delete_many({"is_default": True})`** (app.py:279) — startup cleanup legacy default profiles. Idempotent nhưng chạy mỗi lần boot. Nếu schema thay đổi, đảm bảo không xoá nhầm.
- **Default API key auto-tạo lần đầu** (app.py:252-257): log warning ra console với key plaintext. **CHỈ SHOW 1 LẦN** — production deploy phải copy ngay hoặc check `api_keys` collection cũ.
- **Default admin user auto-tạo** (app.py:248): `user_service.ensure_default_admin()` chỉ tạo nếu chưa có admin nào. Username/password mặc định `admin/admin123456` — đổi ngay sau lần login đầu.
- **`gevent` async mode** trên SocketIO (app.py:79, 122): tránh dùng blocking I/O trong controller — sẽ block toàn bộ worker. Nếu cần CPU-heavy, dùng `flask_executor` hoặc background task.
- **CORS allow `*`** (app.py:112): chấp nhận mọi origin. Cho dev tốt, production nên restrict.

### Time utils
- **Server `time_utils.py` ≠ Agent `shared/time_utils.py`**: 2 file độc lập, có overlap chức năng (`now_vietnam`, `now_iso`, `parse_agent_timestamp`). Agent có thêm uptime, cache helpers; server có thêm `parse_agent_timestamp` lượng dữ liệu lớn hơn (handles datetime/int/float/str) + `format_datetime` + drift normalisation.
- **`parse_agent_timestamp` rất khoan dung**: input không hợp lệ → return `now_vietnam()`, không raise. Caller không phải try-except. Nhưng cũng nghĩa là silent data corruption nếu agent gửi sai format — kiểm log warning.
- **Drift normalisation logic**: timestamp > 5 phút tương lai → thử `dt - dt.utcoffset()` (sửa lỗi UTC convert 2 lần) → nếu vẫn lệch thì clamp về `reference_time`. Hiện hữu cho heartbeat của các agent legacy có bug timezone.
- **Default fallback `now_vietnam()` cho mọi unknown input** — không ý thức được sẽ overwrite ngầm. Nếu thấy log "Unrecognised timestamp" hay "ahead of reference", agent đang bug.
- **Format strftime 3 dạng** (`%Y-%m-%d %H:%M:%S.%f / %Y-%m-%d %H:%M:%S / %Y/%m/%d %H:%M:%S`): nếu format khác (DD/MM/YYYY) sẽ fail và rơi vào fallback `now_vietnam()`. Đừng thêm format mới bừa — agent phải gửi ISO.
- **Codec options `tz_aware=True, tzinfo=VIETNAM_TZ`** (database/config.py:24): mọi datetime đọc từ Mongo **đã gắn tz VN**. Đừng `to_vietnam()` lại trừ khi giá trị đến từ source khác (string từ JSON).

### Web routes
- **Dashboard stats fake 0** (app.py:326-331): server-side template render `total_logs=0` để tránh leak global stats cho teacher trước khi JS fetch và áp RBAC filter. Đừng "fix" bằng cách pass stats thật vào template.
- **`/groups/<group_id>` dùng `app.group_service`** (app.py:366): truy cập service qua app object, không qua DI. OK vì singleton, nhưng test cần wire `app.group_service` thủ công.
- **Page routes có cả pre-login pages** (`/login`) và **các page mà auth check do JS làm** (`/admin/users`, `/admin/audit`) — Flask không kiểm token. JS gọi `/api/admin/auth/me` rồi redirect nếu fail. Nếu user disable JS, trang vẫn render nhưng API call sẽ 401. Acceptable tradeoff cho SPA-lite.
