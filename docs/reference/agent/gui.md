# `agent/gui` - Legacy compatibility note

## Mục đích
`agent/gui` không còn là source GUI hiện tại. Package GUI cũ đã được tách bỏ; runtime hiện tại đi qua:

- [`agent/controllers`](controllers.md) - controller/presenter không phụ thuộc framework, quản lý worker thread, signal queue, whitelist bridge.
- [`agent/gui_qt`](gui_qt.md) - view layer PySide6, `QApplication`, `MainWindow`, views, components, QSS styles.

Giữ file reference này để người đọc tài liệu cũ có điểm chuyển tiếp. Không thêm code mới vào package `agent/gui`.

## Mapping migration

| Nhu cầu cũ | Nơi hiện tại |
|---|---|
| Start/stop agent từ UI, đọc status/stats | [`agent/controllers/agent_controller.py`](../../../agent/controllers/agent_controller.py) |
| Bridge whitelist state sang bảng UI | [`agent/controllers/whitelist_controller.py`](../../../agent/controllers/whitelist_controller.py) |
| Entry point GUI | [`agent/agent_gui.py`](../../../agent/agent_gui.py) → [`agent/gui_qt/app.py`](../../../agent/gui_qt/app.py) |
| Cửa sổ chính, sidebar, router view | [`agent/gui_qt/main_window.py`](../../../agent/gui_qt/main_window.py) |
| Dashboard | [`agent/gui_qt/views/dashboard.py`](../../../agent/gui_qt/views/dashboard.py) |
| Firewall rules view | [`agent/gui_qt/views/firewall.py`](../../../agent/gui_qt/views/firewall.py) |
| Whitelist view | [`agent/gui_qt/views/whitelist.py`](../../../agent/gui_qt/views/whitelist.py) |
| Logs view + local logging handler | [`agent/gui_qt/views/logs.py`](../../../agent/gui_qt/views/logs.py), [`agent/gui_qt/components/log_console.py`](../../../agent/gui_qt/components/log_console.py) |
| Settings save/restore | [`agent/gui_qt/views/settings.py`](../../../agent/gui_qt/views/settings.py) |
| Table/card/log visual components | [`agent/gui_qt/components/`](../../../agent/gui_qt/components/) |
| Theme/style tokens | [`agent/gui_qt/styles.py`](../../../agent/gui_qt/styles.py) |

## Quy ước mới
- View code chỉ nên gọi controller API hoặc nhận Qt signals qua `QtSignalBridge`; không gọi trực tiếp lifecycle/firewall từ nhiều nơi.
- Controller vẫn dùng absolute imports theo `agent/agent_gui.py` sys.path setup để chạy được cả source mode và PyInstaller bundle.
- Spec hiện tại là [`agent/saint_agent.spec`](../../../agent/saint_agent.spec) cho bundle chính.
