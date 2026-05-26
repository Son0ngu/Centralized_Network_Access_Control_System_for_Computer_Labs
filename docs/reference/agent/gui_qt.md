# `agent/gui_qt` - PySide6 GUI

## Mục đích
View layer hiện tại của agent. Package này chỉ chứa UI PySide6: app bootstrap, main window, Qt signal bridge, views, reusable components, và QSS style. Agent lifecycle/worker thread nằm ở [`agent/controllers`](controllers.md).

## Public API

### Entry point & shell

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `app.run()` | `() -> int` | [app.py:19](../../../agent/gui_qt/app.py#L19) | Tạo/reuse `QApplication`, apply `GLOBAL_QSS`, set icon, tạo `AgentController`, `QtSignalBridge`, `MainWindow`, rồi `app.exec()`. |
| `MainWindow` | `class(QMainWindow)` | [main_window.py:33](../../../agent/gui_qt/main_window.py#L33) | Sidebar nav + `QStackedWidget`; owns all five views. |
| `MainWindow._build_ui()` | `() -> None` | [main_window.py:45](../../../agent/gui_qt/main_window.py#L45) | Build sidebar, instantiate dashboard/whitelist/firewall/logs/settings, wire cross-view signals. |
| `MainWindow._on_status_changed(data)` | `(dict) -> None` | [main_window.py:125](../../../agent/gui_qt/main_window.py#L125) | Khi agent running/degraded, hand live `FirewallManager` sang `FirewallView`. |
| `MainWindow._on_whitelist_synced(data)` | `(dict) -> None` | [main_window.py:139](../../../agent/gui_qt/main_window.py#L139) | Khi controller emit `agent_ready`, bật auto-sync cho `WhitelistView`. |
| `MainWindow._show_view(view_id)` | `(str) -> None` | [main_window.py:160](../../../agent/gui_qt/main_window.py#L160) | Switch stacked widget và checked nav button. |
| `MainWindow.closeEvent(event)` | `(event) -> None` | [main_window.py:173](../../../agent/gui_qt/main_window.py#L173) | Confirm nếu agent đang chạy, stop agent, cleanup logs handler, stop signal bridge. |

### `agent/gui_qt/signal_bridge.py` - Queue → Qt signals

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `QtSignalBridge` | `class(QObject)` | [signal_bridge.py:19](../../../agent/gui_qt/signal_bridge.py#L19) | Poll `AgentSignals._event_queue` bằng `QTimer`, emit Qt signals trên GUI thread. |
| `status_changed / stats_updated / packet_captured / log_received / error_occurred / whitelist_synced` | `Signal(dict)` | [signal_bridge.py:22](../../../agent/gui_qt/signal_bridge.py#L22) | Typed Qt signals map 1-1 với controller signal names. |
| `.__init__(agent_signals, parent=None)` | | [signal_bridge.py:29](../../../agent/gui_qt/signal_bridge.py#L29) | Start timer 50ms và build `_signal_map`. |
| `._drain()` | `() -> None` | [signal_bridge.py:46](../../../agent/gui_qt/signal_bridge.py#L46) | Drain tối đa 100 events/tick; nếu còn backlog thì `QTimer.singleShot(0, ...)`. |
| `._dispatch(event)` | `(AgentEvent) -> None` | [signal_bridge.py:65](../../../agent/gui_qt/signal_bridge.py#L65) | Emit Qt signal tương ứng, ignore unknown event. |
| `.stop()` | `() -> None` | [signal_bridge.py:74](../../../agent/gui_qt/signal_bridge.py#L74) | Stop timer khi đóng app. |

### Views

| View | Vị trí | Trách nhiệm | Notes |
|---|---|---|---|
| `DashboardView` | [dashboard.py:165](../../../agent/gui_qt/views/dashboard.py#L165) | Dashboard signal-driven: status pill, metric cards, server/firewall panels, activity log, Start/Stop, Sync Now. | Nhận `AgentController` + `QtSignalBridge`; không poll controller mỗi giây như GUI cũ. |
| `FirewallView` | [firewall.py:40](../../../agent/gui_qt/views/firewall.py#L40) | Hiển thị policy/mode/rule count + table rules. | `set_firewall_manager()` khi agent running; fallback đọc `netsh` khi chưa có manager. |
| `WhitelistView` | [whitelist.py:42](../../../agent/gui_qt/views/whitelist.py#L42) | Table whitelist, search, toggle resolved IPs, Refresh/Sync. | Nhận `controller_get`; đăng ký callback với `WhitelistController`; auto-sync sau `set_agent_ready(True)`. |
| `LogsView` | [logs.py:39](../../../agent/gui_qt/views/logs.py#L39) | Log console, level filter, search, export CSV, clear. | Mount `GUILogHandler` vào root logger; `cleanup()` gỡ handler khi đóng app. |
| `SettingsView` | [settings.py:28](../../../agent/gui_qt/views/settings.py#L28) | Form API key/server/firewall/logging, encrypted save, manual restore snapshot, clear rules. | Save bằng `config.crypto.encrypt_config`; restore ưu tiên `FirewallManager.restore_snapshot`, có fallback netsh thủ công. |

### Components

| Symbol | Vị trí | Mô tả |
|---|---|---|
| `StatusCard` | [status_card.py:13](../../../agent/gui_qt/components/status_card.py#L13) | Reusable `QFrame` metric card với title/value/icon/subtitle và dynamic color. |
| `Sparkline` | [sparkline.py:18](../../../agent/gui_qt/components/sparkline.py#L18) | Lightweight custom-painted line chart; `push`, `set_values`, `clear`. |
| `DictTableModel` | [data_table.py:40](../../../agent/gui_qt/components/data_table.py#L40) | `QAbstractTableModel` cho list dict + column descriptors. |
| `DataTable` | [data_table.py:126](../../../agent/gui_qt/components/data_table.py#L126) | Widget wrapper quanh `QTableView`, `set_data`, `get_data`, `clear`, `row_count`. |
| `LogConsole` | [log_console.py:44](../../../agent/gui_qt/components/log_console.py#L44) | Console frame có toolbar pause/clear/copy, history, level filter, thread-safe append qua Qt signal. |
| `GUILogHandler` | [log_console.py:217](../../../agent/gui_qt/components/log_console.py#L217) | `logging.Handler` bridge Python logging → `LogConsole.append_log`. |
| `GLOBAL_QSS` + palette constants | [styles.py:8](../../../agent/gui_qt/styles.py#L8) | Central QSS + color tokens cho views/components. |

## Ai gọi module này
- [`agent/agent_gui.py`](../../../agent/agent_gui.py) gọi `gui_qt.app.run()` khi chạy source hoặc bundle.
- [`agent/saint_agent.spec`](../../../agent/saint_agent.spec) đóng gói `agent/agent_gui.py` và hiddenimports PySide6/controller modules.
- `MainWindow` là owner của views; views gọi controller APIs thay vì gọi trực tiếp `core.lifecycle`.

## Module này gọi ra
- `agent/controllers` - `AgentController`, `get_whitelist_controller`, `AgentSignals`.
- `agent/config` - Settings view load/save encrypted config.
- `agent/firewall` - Settings restore fallback và FirewallView manager/netsh state.
- `agent/network` - WhitelistView resolve domains khi bật resolved IPs.
- `PySide6` - Qt widgets/core/gui.

## Đã có sẵn - đừng viết lại
- Cần thêm màn hình mới? → thêm view widget vào `agent/gui_qt/views/`, khai báo nav item và `_views` trong `MainWindow`.
- Cần nhận event từ agent worker? → thêm signal name ở `AgentSignals` và map ở `QtSignalBridge`.
- Cần table list dict? → dùng `DataTable`/`DictTableModel`.
- Cần log local trong UI? → dùng `LogConsole` + `GUILogHandler`; server upload vẫn đi qua `logging_module.LogSender`.
- Cần chỉnh theme? → sửa `styles.py` để QSS/constants giữ nhất quán.

## Gotchas
- `QtSignalBridge` đọc trực tiếp `_event_queue` của `AgentSignals`. Không chạy thêm legacy queue drain đồng thời.
- `MainWindow` instantiate tất cả views ngay trong `_build_ui()`. Nếu view mới nặng hoặc cần network, hãy defer work tới `showEvent`/button action.
- `LogsView.cleanup()` quan trọng: root logger giữ handler global, nếu không gỡ trước khi Qt destroy widget thì log sau đó có thể đụng object đã bị xoá.
- `FirewallView` có hai nguồn dữ liệu: live `FirewallManager` sau khi agent running, và `netsh` fallback trước đó. Khi sửa rule display, test cả hai path.
- `SettingsView` tự tìm config path và encrypt khi save. Không ghi plaintext config từ view khác.
