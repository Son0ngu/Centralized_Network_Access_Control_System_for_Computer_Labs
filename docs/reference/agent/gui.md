# `agent/gui` — Entry point, App, Controllers, Views, Components, Styles, Resources

## Mục đích
Toàn bộ tầng UI (CustomTkinter). Kiến trúc **MVP + Signals**:
- **Models**: `core/Agent`, `whitelist/state`, `firewall/manager` — không thuộc gui
- **Views**: `gui/views/*.py` — passive, gọi controller
- **Presenters/Controllers**: `gui/controllers/{agent,whitelist}_controller.py` — singleton, chạy agent ở worker thread
- **Signals**: `AgentSignals` (queue + 500ms tick) — bridge **thread agent worker → thread GUI** thread-safe

Cộng thêm: **lazy view creation** (view tạo lần đầu user click sidebar), **theme system** (3 palette + WidgetStyles), **icon set** (emoji).

Cấu trúc:
```
agent_gui.py               entry — chạy FirewallControllerApp().run()
gui/
├── app.py                 FirewallControllerApp (singleton, owns root window)
├── controllers/
│   ├── agent_controller.py     AgentController + AgentSignals (Singleton + event queue)
│   └── whitelist_controller.py WhitelistController (bridge whitelist state → UI)
├── views/
│   ├── main_window.py     MainWindow (sidebar + content area, view router)
│   ├── dashboard_view.py
│   ├── firewall_view.py
│   ├── whitelist_view.py
│   ├── logs_view.py
│   ├── settings_view.py
│   └── components/
│       ├── status_card.py   StatusCard, AnimatedStatusCard, StatusCardGrid
│       ├── data_table.py    DataTable, SearchableDataTable
│       └── log_console.py   LogConsole, GUILogHandler, QueueLogHandler
├── styles/
│   ├── colors.py          ColorPalette + 3 palettes + helpers
│   ├── themes.py          Theme + ThemeManager singleton
│   └── stylesheet.py      WidgetStyles (preset cho button/input/card/...)
└── resources/
    └── icons.py           ICONS (IconSet) + MENU_ICONS + STATUS_ICONS + ASCII_LOGO
```

## Public API

### Entry: `agent/agent_gui.py`

| Symbol | Vị trí | Mô tả |
|---|---|---|
| `main()` | [agent_gui.py:11](../../../agent/agent_gui.py#L11) | Insert sys.path → `FirewallControllerApp().run()` |
| Top-level `sys.path.insert` | [agent_gui.py:5-6](../../../agent/agent_gui.py#L5) | Cho phép `from shared.X` không cần `agent.` prefix |

### `agent/gui/app.py` — Application root

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `FirewallControllerApp` | `class` (Singleton) | [app.py:8](../../../agent/gui/app.py#L8) | Owns `_root` (CTk), `_main_window`, `_controller`. Hard-code light mode + blue theme khi init |
| `.run()` | `() -> None` | [app.py:31](../../../agent/gui/app.py#L31) | Tạo root, set icon `miku.ico`, title `"SAINT - Security Agent Integrated Network Tool"`, 1200×800, min 900×600. Wire `WM_DELETE_WINDOW` → `_on_close`. `mainloop()` |
| `._on_close()` | | [app.py:84](../../../agent/gui/app.py#L84) | Nếu agent đang chạy → confirm dialog → `stop_agent()` → đợi 1.5s rồi `_do_quit` (cho cleanup firewall) |
| `.quit()` | | [app.py:109](../../../agent/gui/app.py#L109) | Public alias `_on_close` |
| `._center_window()` | | [app.py:68](../../../agent/gui/app.py#L68) | Center on screen |

### `agent/gui/controllers/agent_controller.py` — Presenter chính

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `AgentStatus` | `Enum` | [agent_controller.py:11](../../../agent/gui/controllers/agent_controller.py#L11) | `STOPPED / STARTING / RUNNING / STOPPING / ERROR` |
| `AgentEvent` | `@dataclass` | [agent_controller.py:20](../../../agent/gui/controllers/agent_controller.py#L20) | `event_type: str`, `data: Dict`, `timestamp: float` — bọc payload trong queue |
| `AgentSignals` | `class` | [agent_controller.py:28](../../../agent/gui/controllers/agent_controller.py#L28) | Pub-sub trên 6 signal: `status_changed`, `packet_captured`, `log_received`, `error_occurred`, `stats_updated`, `whitelist_synced` |
| `AgentSignals.connect(signal, callback)` | `(str, Callable) -> bool` | [agent_controller.py:42](../../../agent/gui/controllers/agent_controller.py#L42) | `False` nếu signal name không có trong list |
| `AgentSignals.disconnect(signal, callback)` | `(str, Callable) -> bool` | [agent_controller.py:50](../../../agent/gui/controllers/agent_controller.py#L50) | |
| `AgentSignals.emit(signal, data=None)` | `(str, Any) -> None` | [agent_controller.py:58](../../../agent/gui/controllers/agent_controller.py#L58) | **Thread-safe**. Push vào queue, KHÔNG gọi callback ở đây |
| `AgentSignals.process_events(root)` | `(CTk) -> None` | [agent_controller.py:70](../../../agent/gui/controllers/agent_controller.py#L70) | Drain queue → dispatch callbacks ở GUI thread. Self-reschedule mỗi 500ms qua `root.after` |
| `AgentController` | `class` (Singleton) | [agent_controller.py:107](../../../agent/gui/controllers/agent_controller.py#L107) | Holds `signals`, `_agent` (Agent ref sau init), `_config`, `_worker_thread`, `_stop_event`, `_stats` |
| `.status` | `@property -> AgentStatus` | [agent_controller.py:147](../../../agent/gui/controllers/agent_controller.py#L147) | |
| `.is_running` | `@property -> bool` | [agent_controller.py:151](../../../agent/gui/controllers/agent_controller.py#L151) | |
| `.stats` | `@property -> Dict` | [agent_controller.py:155](../../../agent/gui/controllers/agent_controller.py#L155) | Copy của `_stats` |
| `.set_root(root)` | `(CTk) -> None` | [agent_controller.py:159](../../../agent/gui/controllers/agent_controller.py#L159) | Cần gọi trước `mainloop` để start `process_events` ticking |
| `.start_agent()` | `() -> bool` | [agent_controller.py:165](../../../agent/gui/controllers/agent_controller.py#L165) | Spawn thread `AgentWorker`. Trả ngay, status qua signals |
| `.stop_agent()` | `() -> bool` | [agent_controller.py:191](../../../agent/gui/controllers/agent_controller.py#L191) | Set `_stop_event` + `agent.stop()`. Thread tự cleanup |
| `._agent_worker()` | `() -> None` | [agent_controller.py:210](../../../agent/gui/controllers/agent_controller.py#L210) | **Heart of controller**: reload config → set device_id → coerce mode/enabled theo admin → `initialize_components` → wire `WhitelistController` → main loop sleep(1) + update stats. `finally`: `cleanup()` + emit `stopped` |
| `._update_stats()` | `() -> None` | [agent_controller.py:319](../../../agent/gui/controllers/agent_controller.py#L319) | Đọc từ `agent.whitelist._state` (domains/patterns/ips count), `sniffer.packet_count`, `log_sender.get_status` |
| `.get_agent_info()` | `() -> Dict` | [agent_controller.py:349](../../../agent/gui/controllers/agent_controller.py#L349) | Cho dashboard: status, stats, hostname, device_id, agent_id, is_registered, firewall_mode, firewall_enabled |
| `.get_stats()` | `() -> Dict` | [agent_controller.py:372](../../../agent/gui/controllers/agent_controller.py#L372) | Copy `_stats` |
| `.force_whitelist_sync()` | `() -> bool` | [agent_controller.py:377](../../../agent/gui/controllers/agent_controller.py#L377) | Manual sync trigger, emit `whitelist_synced` |
| `get_agent_controller()` | `() -> AgentController` | [agent_controller.py:396](../../../agent/gui/controllers/agent_controller.py#L396) | Singleton accessor (= `AgentController()`) |

### `agent/gui/controllers/whitelist_controller.py` — Bridge state → UI list

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistController` | `class` (Singleton, thread-safe `__new__`) | [whitelist_controller.py:8](../../../agent/gui/controllers/whitelist_controller.py#L8) | Owns `_local_ips: Dict[str, Dict]` — UI-friendly format (ip/type/status/source). Refs `_whitelist_manager` |
| `.set_whitelist_manager(manager)` | | [whitelist_controller.py:40](../../../agent/gui/controllers/whitelist_controller.py#L40) | Wire `on_sync_complete` callback, initial sync, trigger server sync ở background thread |
| `.on_data_changed(callback)` | `(Callable[[List[Dict]], None]) -> None` | [whitelist_controller.py:140](../../../agent/gui/controllers/whitelist_controller.py#L140) | Đăng ký callback cho UI refresh |
| `.on_error(callback)` / `.on_success(callback)` | | [whitelist_controller.py:145-150](../../../agent/gui/controllers/whitelist_controller.py#L145) | Status bar messages |
| `.remove_ip(ip)` | `(str) -> bool` | [whitelist_controller.py:180](../../../agent/gui/controllers/whitelist_controller.py#L180) | Spawn worker thread → xoá khỏi local + manager state |
| `.get_all_ips()` | `() -> List[Dict]` | [whitelist_controller.py:220](../../../agent/gui/controllers/whitelist_controller.py#L220) | Snapshot `_local_ips.values()` |
| `.refresh()` | `() -> None` | [whitelist_controller.py:225](../../../agent/gui/controllers/whitelist_controller.py#L225) | Background `force_refresh` (server sync) + `_sync_from_manager` |
| `.get_stats()` | `() -> Dict` | [whitelist_controller.py:249](../../../agent/gui/controllers/whitelist_controller.py#L249) | Counts theo type/status/source + merge manager stats |
| `._sync_from_manager()` | `() -> None` | [whitelist_controller.py:84](../../../agent/gui/controllers/whitelist_controller.py#L84) | **Wipe + rebuild `_local_ips`** từ `manager._state` (domains + patterns + ips), giữ entry source="Local" |
| `get_whitelist_controller()` | `() -> WhitelistController` | [whitelist_controller.py:279](../../../agent/gui/controllers/whitelist_controller.py#L279) | Singleton accessor |

### `agent/gui/views/main_window.py` — Sidebar + content area router

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `MainWindow` | `class(CTkFrame)` | [main_window.py:8](../../../agent/gui/views/main_window.py#L8) | Holds `_views` (instantiated), `_view_classes` (lazy), `_menu_buttons` |
| `.__init__(parent)` | | [main_window.py:11](../../../agent/gui/views/main_window.py#L11) | Setup UI → register view classes → show "dashboard" |
| `._create_views()` | | [main_window.py:126](../../../agent/gui/views/main_window.py#L126) | **Map only**, không instantiate. Wire `AgentSignals` cho `whitelist_synced`, `status_changed` |
| `._get_view(view_name)` | | [main_window.py:148](../../../agent/gui/views/main_window.py#L148) | Lazy create — cls() chỉ khi user click lần đầu |
| `._show_view(view_name)` | | [main_window.py:178](../../../agent/gui/views/main_window.py#L178) | Hide current (call `.on_hide()` nếu có), grid new (call `.on_show()`). Update menu button states |
| `._on_status_changed(data)` | | [main_window.py:157](../../../agent/gui/views/main_window.py#L157) | Khi status="running" → wire firewall manager vào FirewallView (nếu view đã tạo) |
| `._on_agent_ready(data)` | | [main_window.py:171](../../../agent/gui/views/main_window.py#L171) | Notify WhitelistView → `set_agent_ready(True)` |

### Views — common pattern

Tất cả các view kế thừa `ctk.CTkFrame` với `fg_color="transparent"`, hỗ trợ optional `on_show()` / `on_hide()` / `destroy()` để cleanup periodic update khi user switch tab.

| View | Vị trí | Mô tả ngắn | Điểm đáng chú ý |
|---|---|---|---|
| `DashboardView` | [dashboard_view.py:7](../../../agent/gui/views/dashboard_view.py#L7) | 8 status cards (2 hàng × 4 cột) + Activity Log + Start/Stop button | `STATS_REFRESH_INTERVAL = 1000ms`. Listen 5 signals: status_changed/stats_updated/error/packet_captured/whitelist_synced. ASCII banner cho start/stop/shutdown. `_format_uptime` riêng (xem Gotchas) |
| `FirewallView` | [firewall_view.py:8](../../../agent/gui/views/firewall_view.py#L8) | Policy/rule count/mode + DataTable rules | `REFRESH_INTERVAL = 5000ms`. Fallback `_get_rules_from_netsh` nếu chưa wire `firewall_manager`. Show "Whitelist Only (idle)" khi không admin |
| `WhitelistView` | [whitelist_view.py:10](../../../agent/gui/views/whitelist_view.py#L10) | DataTable + filter + toggle "Resolved IPs" + Sync/Refresh buttons | **Tạo riêng** `OptimizedDNSResolver()` (whitelist_view.py:23). Auto-sync 30s. `set_agent_ready(True)` từ MainWindow để bắt đầu sync |
| `LogsView` | [logs_view.py:10](../../../agent/gui/views/logs_view.py#L10) | LogConsole + filter level + search + Export CSV/Clear | **Mount `GUILogHandler` vào root logger** (logs_view.py:160) — bắt mọi `logger.info` toàn agent. Export CSV qua `LogConsole.get_history()` |
| `SettingsView` | [settings_view.py:8](../../../agent/gui/views/settings_view.py#L8) | API key, server URL, intervals, log level, Restore button | Save → `config.crypto.encrypt_config` (settings_view.py:97). Restore: ưu tiên `agent.firewall.restore_snapshot`, fallback netsh thủ công. Validate URL required + scheme |

### `agent/gui/views/components/status_card.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `StatusCard` | `class(CTkFrame)` | [status_card.py:5](../../../agent/gui/views/components/status_card.py#L5) | Card với icon + title + giá trị to + subtitle. `width=200, height=120` mặc định |
| `.set_value(value) / set_title / set_icon / set_color / set_subtitle` | `(str) -> None` | [status_card.py:93-117](../../../agent/gui/views/components/status_card.py#L93) | Setters cập nhật UI immediately |
| `.set_status(status, color)` | | [status_card.py:123](../../../agent/gui/views/components/status_card.py#L123) | Convenience: set value + color cùng lúc |
| `.get_value()` | `() -> str` | [status_card.py:119](../../../agent/gui/views/components/status_card.py#L119) | Current value |
| `AnimatedStatusCard(StatusCard)` | | [status_card.py:129](../../../agent/gui/views/components/status_card.py#L129) | Extends với `show_trend` (↑/↓/→) + `animate`. **Animation hiện đã bị bypass** (xem Gotchas) |
| `AnimatedStatusCard.pulse()` | | [status_card.py:222](../../../agent/gui/views/components/status_card.py#L222) | Flash white 150ms rồi restore color |
| `StatusCardGrid` | `class(CTkFrame)` | [status_card.py:234](../../../agent/gui/views/components/status_card.py#L234) | Helper builder. `add_card(id, ...)` auto-place vào grid `columns × N`. Hiện **không dùng** ở views nào — views tự `grid()` thủ công |

### `agent/gui/views/components/data_table.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `DataTable` | `class(CTkFrame)` | [data_table.py:6](../../../agent/gui/views/components/data_table.py#L6) | Scrollable table. Columns config: `{key, title, width, weight, type?}` |
| `.set_data(data)` | `(List[Dict]) -> None` | [data_table.py:82](../../../agent/gui/views/components/data_table.py#L82) | Replace toàn bộ. Refresh qua `after_idle` |
| `.add_row(row)` / `.remove_row(idx)` / `.remove_row_by_key(k, v)` | | [data_table.py:91-110](../../../agent/gui/views/components/data_table.py#L91) | |
| `.get_data()` / `.clear()` / `.get_row_count()` | | [data_table.py:113-245](../../../agent/gui/views/components/data_table.py#L113) | |
| `._format_value(value, type)` | | [data_table.py:220](../../../agent/gui/views/components/data_table.py#L220) | `type="datetime"|"date"` → format `datetime.fromtimestamp(value)` |
| Status-cell coloring | [data_table.py:160-166](../../../agent/gui/views/components/data_table.py#L160) | Tự color cột `status`: active/allowed/online → xanh, blocked/denied/offline → đỏ, pending/syncing → cam |
| `SearchableDataTable` | `class(CTkFrame)` | [data_table.py:248](../../../agent/gui/views/components/data_table.py#L248) | Wraps DataTable + search bar + clear button + count. Hiện **không dùng** ở views nào |

### `agent/gui/views/components/log_console.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `LogConsole` | `class(CTkFrame)` | [log_console.py:9](../../../agent/gui/views/components/log_console.py#L9) | Console với queue processor (200ms batch 100). `max_lines=1000` mặc định, history list cho export |
| `LEVEL_COLORS / LEVEL_ICONS` | class consts | [log_console.py:12-41](../../../agent/gui/views/components/log_console.py#L12) | Map level/event → màu/emoji (DEBUG/INFO/WARNING/ERROR/CRITICAL + BLOCK/ALLOW/PACKET/SYNC/STARTUP/SHUTDOWN/SUCCESS) |
| `.append_log(message, level="INFO", timestamp=None)` | | [log_console.py:220](../../../agent/gui/views/components/log_console.py#L220) | **Thread-safe** — push vào queue |
| `.set_filter_level(level)` | `("ALL"|"DEBUG"|...) -> None` | [log_console.py:157](../../../agent/gui/views/components/log_console.py#L157) | Rebuild console từ history |
| `.clear()` | | [log_console.py:277](../../../agent/gui/views/components/log_console.py#L277) | Clear console + history |
| `.get_history()` | `() -> List[Dict]` | [log_console.py:290](../../../agent/gui/views/components/log_console.py#L290) | Copy history cho export. Mỗi entry: `{timestamp, level, message}` |
| `.write(message) / .flush()` | | [log_console.py:294-301](../../../agent/gui/views/components/log_console.py#L294) | File-like API cho redirect stdout |
| `._toggle_pause()` | | [log_console.py:145](../../../agent/gui/views/components/log_console.py#L145) | Pause queue processor (vẫn queue, không append) |
| `GUILogHandler(logging.Handler)` | | [log_console.py:304](../../../agent/gui/views/components/log_console.py#L304) | Bắc cầu Python `logging` → `LogConsole.append_log` |
| `QueueLogHandler(logging.Handler)` | | [log_console.py:328](../../../agent/gui/views/components/log_console.py#L328) | Alt: emit vào generic `queue.Queue`. Hiện **không dùng** ở views nào |

### `agent/gui/styles/colors.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `ColorPalette` | `@dataclass(frozen=True)` | [colors.py:5](../../../agent/gui/styles/colors.py#L5) | ~50 màu hex chia nhóm (bg/accent/status/text/border/sidebar/chart/console) |
| `DARK_PALETTE`, `LIGHT_PALETTE`, `HIGH_CONTRAST_PALETTE` | const | [colors.py:88-146](../../../agent/gui/styles/colors.py#L88) | 3 palette predefined |
| `STATUS_COLORS` | `Dict[str, str]` | [colors.py:198](../../../agent/gui/styles/colors.py#L198) | Map status name → dark palette color |
| `get_status_color(status)` | `(str) -> str` | [colors.py:231](../../../agent/gui/styles/colors.py#L231) | Lookup, fallback `text_muted` |
| `hex_to_rgb / rgb_to_hex / lighten_color / darken_color / with_alpha / get_contrast_text` | | [colors.py:151-193](../../../agent/gui/styles/colors.py#L151) | Color math helpers |

### `agent/gui/styles/themes.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `ThemeMode` | `Enum` | [themes.py:19](../../../agent/gui/styles/themes.py#L19) | `DARK / LIGHT / HIGH_CONTRAST / SYSTEM` |
| `FontConfig / SpacingConfig / BorderConfig` | `@dataclass` | [themes.py:27-96](../../../agent/gui/styles/themes.py#L27) | Token systems (xs/sm/md/lg/xl/2xl/3xl/4xl) |
| `Theme` | `class` | [themes.py:99](../../../agent/gui/styles/themes.py#L99) | Container: name + mode + colors + fonts + spacing + borders. Plus `get_button_style(variant)` cho 7 variant (primary/secondary/success/danger/warning/ghost/outline) |
| `DARK_THEME / LIGHT_THEME / HIGH_CONTRAST_THEME` | const | [themes.py:210-226](../../../agent/gui/styles/themes.py#L210) | |
| `ThemeManager` | `class` (Singleton) | [themes.py:229](../../../agent/gui/styles/themes.py#L229) | Default `LIGHT_THEME`. `set_theme(name)` apply + notify callbacks. Auto-apply tới CTk appearance |
| `.colors / .fonts / .spacing / .borders` | shortcuts | [themes.py:266-282](../../../agent/gui/styles/themes.py#L266) | Truy cập property của current theme |
| `.font(size, weight, mono)` | `(str, str, bool) -> CTkFont` | [themes.py:368](../../../agent/gui/styles/themes.py#L368) | Sizes: xs/sm/md/lg/xl/2xl/3xl/4xl |
| `.button(variant) / .input() / .card() / .sidebar() / .label(variant)` | | [themes.py:347-365](../../../agent/gui/styles/themes.py#L347) | Convenience accessors |
| `.on_theme_change(callback)` | | [themes.py:315](../../../agent/gui/styles/themes.py#L315) | Subscribe cho dynamic re-skin |
| `get_theme()` | `() -> ThemeManager` | [themes.py:374](../../../agent/gui/styles/themes.py#L374) | Singleton accessor |

### `agent/gui/styles/stylesheet.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WidgetStyles` | namespace với static methods | [stylesheet.py:8](../../../agent/gui/styles/stylesheet.py#L8) | Preset kwargs cho CTk widgets. Mọi method **đọc `get_theme()` mỗi lần call** ⇒ tự respect theme change |
| Buttons | `primary_button / secondary_button / success_button / danger_button / icon_button` | [stylesheet.py:17-84](../../../agent/gui/styles/stylesheet.py#L17) | Trả dict spread vào `CTkButton(**...)` |
| Inputs | `text_input / search_input` | [stylesheet.py:89-116](../../../agent/gui/styles/stylesheet.py#L89) | |
| Cards | `card / elevated_card / status_card("success"|"error"|...)` | [stylesheet.py:121-153](../../../agent/gui/styles/stylesheet.py#L121) | |
| Labels | `title_label / heading_label / body_label / muted_label / status_label(status)` | [stylesheet.py:159-203](../../../agent/gui/styles/stylesheet.py#L159) | |
| Misc | `dropdown / console_textbox / table_header / table_row(index) / sidebar / sidebar_item(active) / progress_bar / switch` | [stylesheet.py:208-302](../../../agent/gui/styles/stylesheet.py#L208) | |
| `apply_style(widget, style)` | `(Widget, Dict) -> None` | [stylesheet.py:307](../../../agent/gui/styles/stylesheet.py#L307) | `widget.configure(**style)` swallowing errors |
| `create_styled_button(parent, text, variant="primary", command=None, **kw)` | | [stylesheet.py:321](../../../agent/gui/styles/stylesheet.py#L321) | Factory shortcut |
| `create_styled_input(parent, placeholder="", variant="text", **kw)` | | [stylesheet.py:355](../../../agent/gui/styles/stylesheet.py#L355) | |
| `create_styled_card(parent, **kw)` | | [stylesheet.py:385](../../../agent/gui/styles/stylesheet.py#L385) | |

### `agent/gui/resources/icons.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `IconSet` | `@dataclass(frozen=True)` | [icons.py:6](../../../agent/gui/resources/icons.py#L6) | ~80 emoji constants chia nhóm: nav/status/action/security/network/system/file/user/info/console/theme/chart/app |
| `ICONS` | instance | [icons.py:117](../../../agent/gui/resources/icons.py#L117) | Truy cập: `ICONS.shield`, `ICONS.dashboard`, ... |
| `MENU_ICONS / STATUS_ICONS / ACTION_ICONS` | `Dict[str, str]` | [icons.py:122-160](../../../agent/gui/resources/icons.py#L122) | Lookup map |
| `get_icon(name, fallback="•")` | `(str, str) -> str` | [icons.py:163](../../../agent/gui/resources/icons.py#L163) | Lookup attr trên ICONS rồi tới các dict |
| `get_status_icon / get_menu_icon / get_action_icon` | | [icons.py:190-202](../../../agent/gui/resources/icons.py#L190) | Helper riêng từng dict |
| `ASCII_LOGO / ASCII_LOGO_SMALL / SPLASH_LOGO` | str const | [icons.py:207-229](../../../agent/gui/resources/icons.py#L207) | Banner cho console/log |

## Ai gọi module này
- `agent/agent_gui.py` — entry point khởi tạo `FirewallControllerApp().run()`
- Bên trong gui: views → controllers, controllers → core/whitelist/firewall, components → views

Bên ngoài gui **không** import vào — gui là leaf consumer của các module khác.

## Module này gọi ra
- `customtkinter` — toàn bộ UI
- `agent/core` — `get_agent`, `initialize_components`, `cleanup`, `AGENT_DEVICE_ID`
- `agent/config` — `reload_config`, `decrypt_config`, `encrypt_config`
- `agent/whitelist` — qua `agent.whitelist` ref
- `agent/firewall` — qua `agent.firewall` ref + `_resolve_snapshot_path`, `FirewallUtils`
- `agent/network` — `OptimizedDNSResolver` (whitelist view tạo riêng)
- `agent/utils` — `check_admin_privileges`
- `agent/shared` — `now_vietnam`, `uptime_string`, etc.
- stdlib: `tkinter.filedialog`, `tkinter.messagebox`, `csv`, `logging`, `queue`, `threading`

## Đã có sẵn — đừng viết lại
- Cần singleton truy cập agent từ UI? → `AgentController()` (hoặc `get_agent_controller()`) — **đừng** dựng `Agent()` trực tiếp ở view
- Cần emit event từ worker thread sang GUI? → `agent_ctrl.signals.emit('signal_name', data)` — **đừng** `root.after` trực tiếp từ thread khác
- Cần thread-safe append vào log console? → `log_console.append_log(msg, level)` — đã có internal queue
- Cần ICONS? → `from ..resources import ICONS` rồi `ICONS.shield` — **đừng** hardcode emoji rải rác (xem dashboard_view dùng `"📊"` raw — đó là tech debt)
- Cần style button/input/card đồng bộ? → `WidgetStyles.primary_button()`, `create_styled_button(...)`, `theme.button("primary")` — **đừng** lặp `fg_color="#0077cc"` 50 chỗ (xem Gotchas)
- Cần lookup màu theo status string ("running"/"blocked"/...)? → `get_status_color(status)`
- Cần ColorPalette/font/spacing/border tokens? → `get_theme().colors / .fonts / .spacing / .borders` thay vì hardcode
- Cần lazy view tạo theo click sidebar? → đã có pattern ở `MainWindow._get_view`
- Cần auto-mount Python logging vào GUI? → `GUILogHandler(log_console)` — `LogsView` đã setup root logger
- Cần convert hex color? → `hex_to_rgb / rgb_to_hex / lighten_color / darken_color` (styles/colors.py)
- Cần generic data table? → `DataTable(columns=[{key,title,width,weight}], on_delete=...)` — không phải `Treeview` thủ công
- Cần searchable table? → `SearchableDataTable` (hiện chưa ai dùng — có thể là chỗ tốt để gom)

## Gotchas

### Threading / Signals
- **2 thread model**: GUI thread (CTk mainloop) + worker thread (AgentWorker). Mọi `tk.Widget.configure` phải chạy ở GUI thread. `AgentSignals` (queue + 500ms tick) là cách duy nhất worker → GUI. **Đừng** gọi `widget.configure` trực tiếp từ worker.
- **`process_events` reschedule mọi 500ms** (agent_controller.py:84). Latency tối đa giữa emit và callback: 500ms. Đủ cho UI, đừng dựa vào để timing-sensitive logic.
- **`AgentSignals._callbacks` dict cứng 6 signal** (agent_controller.py:31). Thêm signal mới phải sửa cả `connect` (line 45 check `in self._callbacks`) — nó refuse signal không có sẵn.
- **`_dispatch_event` copy callbacks list trước khi gọi** (line 89) — an toàn unsubscribe trong callback. **Đừng** clear callbacks rồi expect callback đó sẽ không chạy lần này.

### Singletons
- **4 Singleton chính**: `FirewallControllerApp`, `AgentController`, `WhitelistController`, `ThemeManager`. Tất cả dùng `_instance` + `_initialized` pattern → `__init__` chỉ chạy 1 lần. Test cần reset `Cls._instance = None`.
- **`WhitelistController.__new__` có `_lock`** (whitelist_controller.py:14) — thread-safe khởi tạo. Cái khác không có. Hiện không có race vì lifecycle chạy từ main thread, nhưng nếu future tạo từ worker, cẩn thận.

### Lazy view creation
- **Views khởi tạo ở lần đầu user click sidebar** (main_window.py:148-155). Lần đầu vào "Firewall" có thể 200-500ms khởi tạo (subprocess `netsh` ở FirewallView). UX OK vì user click trước đợi sau.
- **`set_firewall_manager` chỉ gọi khi view đã tồn tại** (main_window.py:166): nếu user chưa từng vào FirewallView, manager không được wire ngay khi agent start. Lần đầu vào view sẽ thấy "rules empty" cho tới khi `_refresh_rules` chạy hoặc `_on_status_changed` re-trigger.

### Theming inconsistency
- **App hard-code `ctk.set_appearance_mode("light")`** trong `FirewallControllerApp.__init__` (app.py:28), bypass `ThemeManager`. Đổi theme runtime qua ThemeManager nhưng `app` đã set light → không khớp.
- **Dashboard/Firewall/Whitelist/Logs/Settings hardcode hex colors** (`"#0077cc"`, `"#00ff88"`, `"#ff4444"`) thay vì dùng `WidgetStyles`/`ThemeManager`. Nếu đổi theme runtime, các view này KHÔNG re-skin. WidgetStyles là dead-ish code — chỉ MainWindow dùng `get_theme()` thực sự.
- **Default theme là LIGHT** (themes.py:247) nhưng `DARK_PALETTE` được khai báo trước → confusing. Nếu future muốn switch sang Dark default, đổi `_current_theme = LIGHT_THEME` thành `DARK_THEME`.

### Animation
- **`AnimatedStatusCard._animate_value_change` đã bypass animation** (status_card.py:204-212): comment "Skip animation to improve performance" — set ngay end value. `_animation_id` cancel logic thừa. Nếu cần animation lại, chỉ cần thay implementation; signature giữ nguyên.
- **`AnimatedStatusCard` được DashboardView dùng cho status/domains/ips/packets cards** (dashboard_view.py:112+) — vẫn alias `set_value` nên hoạt động OK kể cả không animation.

### Worker thread quirks
- **`_agent_worker` force `firewall.mode = "whitelist_only"`** (agent_controller.py:237) sau khi reload config. Nếu admin sửa config thành mode khác, sẽ bị overwrite. Cố ý — agent chỉ hỗ trợ 1 mode.
- **`firewall.enabled = bool(admin_status)`** (agent_controller.py:238): admin → enable, không admin → disable enforcement nhưng vẫn observe. Nếu user nâng quyền giữa session, phải restart agent (cached admin status — xem [utils.md](utils.md)).
- **`cleanup` trong `finally` của worker** (line 305-309): nếu init fail, vẫn gọi cleanup. Cleanup phải idempotent với state chưa init (`hasattr(agent, 'firewall')` check trong [core.lifecycle](core.md)).

### Settings save flow
- **Settings save → `encrypt_config(self._config, self._config_path)`** (settings_view.py:97). Sau save, **không trigger reload trong worker** — config thay đổi chỉ active khi agent restart (start/stop từ dashboard). Nếu user save URL mới khi agent đang chạy, agent vẫn dùng URL cũ.
- **`server.urls` được set thành `[url_value]`** sau save (settings_view.py:77) — đồng nhất với loader.py logic. Đừng thêm logic ghép list cũ + url mới.

### Logs view ⇄ Python logging
- **`LogsView._setup_logging` mount handler vào root logger + nhiều named loggers** (logs_view.py:160-179). Khi user navigate sang LogsView, log từ trước cũng đã được capture bởi handler trong khi view còn chưa visible (vì view tạo lazy lần đầu click). Có nghĩa: log trước khi mở LogsView lần đầu sẽ KHÔNG xuất hiện ở console (vì handler chưa có).
- **`GUILogHandler.emit` không thread-safe ở logging side** nhưng `LogConsole.append_log` push vào queue thread-safe ⇒ OK kể cả nhiều thread log cùng lúc.
- **Logger names** mount cứng (`"agent", "core.agent", "firewall", "whitelist", "capture", "heartbeat", "gui"`). Logger mới (vd `services.heartbeat` thật ra) propagate qua root vẫn bắt được, nhưng named list bị stale — đừng tin nó liệt kê đầy đủ.

### Whitelist view DNS resolver duplication
- **WhitelistView tự tạo `OptimizedDNSResolver()` riêng** (whitelist_view.py:23) — không share với `agent.whitelist.resolver`. Hậu quả: 2 thread pool, 2 atexit handler, 2 system DNS cache. Acceptable nhưng nếu thấy hot path nên reuse.
- **`_resolve_domains_to_ips` có `print()` debug** (whitelist_view.py:364, 368, 370, 382, 391) — đường dev, không qua logger. Sẽ in ra stdout console khi chạy GUI. Nếu chạy GUI từ shortcut Windows (không có console), `print` no-op nhưng vẫn không qua log file.
- **`_resolve_queued_domains` chỉ giữ 1 request gần nhất** (whitelist_view.py:313): nếu user toggle nhanh, chỉ resolve set domains cuối cùng. OK behavior.

### Restore button trong Settings
- **2 đường restore**: agent đang chạy → `agent.firewall.restore_snapshot()` (preferred). Không chạy → netsh trực tiếp. Logic gần trùng `firewall/manager.restore_snapshot`. Nếu sửa logic restore, đảm bảo cả 2 path đồng bộ.
- **Admin guard ở cả 2 path** (settings_view.py:395) — netsh silent fail nếu không admin ⇒ phải check explicit.

### Misc
- **Font `Segoe UI`** mặc định (themes.py:30). Trên máy hệ không có Segoe (Linux chẳng hạn), CTk fallback. Hiện Windows-only ⇒ OK.
- **`ASCII_LOGO` trong icons.py có lỗi format** (icons.py:212) — text "Education Security Management Edition" bị xuống dòng giữa khung. Hiển thị xấu khi print, nhưng không break.
- **`miku.ico`** ở `agent/miku.ico` — không phải resource standard, đặt cạnh `agent_gui.py`. App load qua `os.path.join(...)` (app.py:39). Tên file hơi vui, không liên quan SAINT — đổi tên cẩn thận update `app.py:39`.
- **`MainWindow._update_menu_states` dùng `accent_primary` cho active button text** — light theme accent = `"#0077cc"`. Nếu future muốn dark theme default, đảm bảo contrast vẫn đủ với `sidebar_item_active`.
