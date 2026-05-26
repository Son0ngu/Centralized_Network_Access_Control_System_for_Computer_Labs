# `agent/controllers` - GUI Controllers & Worker Bridge

## Mục đích
Tầng controller không phụ thuộc framework UI. Package này giữ lifecycle worker, signal queue, snapshot status/stats cho dashboard, và adapter whitelist state sang dữ liệu bảng. PySide6 view layer nằm ở [`agent/gui_qt`](gui_qt.md); controller vẫn không import widget Qt.

## Public API

### `agent/controllers/agent_controller.py` - Agent lifecycle presenter

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `AgentStatus` | `Enum` | [agent_controller.py:11](../../../agent/controllers/agent_controller.py#L11) | `STOPPED / STARTING / RUNNING / DEGRADED / STOPPING / ERROR`. `DEGRADED` vẫn được coi là running. |
| `AgentEvent` | `@dataclass` | [agent_controller.py:24](../../../agent/controllers/agent_controller.py#L24) | Queue payload: `event_type`, `data`, `timestamp`. |
| `AgentSignals` | `class` | [agent_controller.py:31](../../../agent/controllers/agent_controller.py#L31) | Pub-sub thread-safe trên queue Python; Qt drain qua `QtSignalBridge`. |
| `AgentSignals.connect(signal, callback)` | `(str, Callable) -> bool` | [agent_controller.py:45](../../../agent/controllers/agent_controller.py#L45) | Đăng ký callback cho signal name hợp lệ. |
| `AgentSignals.disconnect(signal, callback)` | `(str, Callable) -> bool` | [agent_controller.py:53](../../../agent/controllers/agent_controller.py#L53) | Gỡ callback nếu đang có. |
| `AgentSignals.emit(signal, data=None)` | `(str, Any) -> None` | [agent_controller.py:61](../../../agent/controllers/agent_controller.py#L61) | Push event vào queue; không gọi callback trực tiếp từ worker thread. |
| `AgentSignals.DRAIN_INTERVAL_MS` | `50` | [agent_controller.py](../../../agent/controllers/agent_controller.py) | Tick drain. Mirror sang `QtSignalBridge` — đổi đồng thời cả 2 chỗ. |
| `AgentSignals.MAX_EVENTS_PER_TICK` | `100` | [agent_controller.py](../../../agent/controllers/agent_controller.py) | Soft cap tránh block GUI khi packet burst. |
| _`AgentSignals.process_events(root)`_ | _removed_ | _was Tk hook_ | Đã xóa. Qt frontends drain queue qua `QtSignalBridge` (`agent/gui_qt/signal_bridge.py`); không có caller nào khác. |
| `AgentController(runtime=None)` | `class` singleton | [agent_controller.py:123](../../../agent/controllers/agent_controller.py#L123) | Owner của worker thread, `_runtime`, `_config`, `_stats`, `signals`. Singleton qua `__new__`, nhưng accept injected `AgentRuntime` qua constructor — test pass `runtime=make_runtime()`. |
| `AgentController.reset_for_test()` | `@classmethod -> None` | [agent_controller.py:134](../../../agent/controllers/agent_controller.py#L134) | Drop singleton + stop running worker. Tests gọi giữa cases để có instance mới. |
| `.status` | `@property -> AgentStatus` | [agent_controller.py](../../../agent/controllers/agent_controller.py) | Status hiện tại. |
| `.is_running` | `@property -> bool` | [agent_controller.py](../../../agent/controllers/agent_controller.py) | `RUNNING` hoặc `DEGRADED`. |
| `.stats` | `@property -> Dict` | [agent_controller.py](../../../agent/controllers/agent_controller.py) | Copy snapshot `_stats`. |
| _`.set_root(root)`_ | _removed_ | _was Tk hook_ | Đã xóa. Qt frontends construct `QtSignalBridge(self.signals)` thẳng — controller không cần biết về toolkit. |
| `.start_agent()` | `() -> bool` | [agent_controller.py:190](../../../agent/controllers/agent_controller.py#L190) | Spawn `AgentWorker-{id}`; trả ngay, status gửi qua `signals`. |
| `.stop_agent()` | `() -> bool` | [agent_controller.py:250](../../../agent/controllers/agent_controller.py#L250) | Set stop event, gọi `Agent.stop()`, để worker cleanup lifecycle. |
| `._agent_worker(worker_id=0)` | `(int) -> None` | [agent_controller.py:269](../../../agent/controllers/agent_controller.py#L269) | Reload config, force whitelist mode, init components, wire `WhitelistController`, emit status/stats, cleanup ở `finally`. |
| `._update_stats()` | `() -> None` | [agent_controller.py:443](../../../agent/controllers/agent_controller.py#L443) | Pull whitelist/sniffer/log_sender stats vào snapshot. |
| `.get_agent_info()` | `() -> Dict` | [agent_controller.py:473](../../../agent/controllers/agent_controller.py#L473) | Status + hostname/device_id/agent_id/firewall flags cho dashboard. |
| `.get_stats()` | `() -> Dict` | [agent_controller.py:496](../../../agent/controllers/agent_controller.py#L496) | Copy `_stats` dưới lock. |
| `.force_whitelist_sync()` | `() -> bool` | [agent_controller.py:501](../../../agent/controllers/agent_controller.py#L501) | Trigger `agent.whitelist.sync_now()` khi agent đang chạy. |
| `get_agent_controller()` | `() -> AgentController` | [agent_controller.py:520](../../../agent/controllers/agent_controller.py#L520) | Singleton accessor. |

### `agent/controllers/whitelist_controller.py` - Whitelist UI data bridge

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WhitelistController` | `class` singleton | [whitelist_controller.py:8](../../../agent/controllers/whitelist_controller.py#L8) | Maintains UI-friendly `_local_ips` từ `WhitelistManager._state`. |
| `.set_whitelist_manager(manager)` | `(manager) -> None` | [whitelist_controller.py:40](../../../agent/controllers/whitelist_controller.py#L40) | Wire `on_sync_complete`, sync cached state, rồi trigger server sync background. |
| `._on_manager_sync_complete()` | `() -> None` | [whitelist_controller.py:57](../../../agent/controllers/whitelist_controller.py#L57) | Callback sau periodic sync của manager; rebuild local list. |
| `._trigger_server_sync()` | `() -> None` | [whitelist_controller.py:62](../../../agent/controllers/whitelist_controller.py#L62) | Thread `ImmediateWhitelistSync` để không block UI. |
| `._sync_from_manager()` | `() -> None` | [whitelist_controller.py:84](../../../agent/controllers/whitelist_controller.py#L84) | Rebuild entries từ domains/patterns/ips trong `WhitelistState`; source=`Server`. |
| `.on_data_changed(callback)` | `(Callable[[List[Dict]], None]) -> None` | [whitelist_controller.py:140](../../../agent/controllers/whitelist_controller.py#L140) | Subscribe data list refresh. |
| `.on_error(callback)` | `(Callable[[str], None]) -> None` | [whitelist_controller.py:145](../../../agent/controllers/whitelist_controller.py#L145) | Subscribe error message. |
| `.on_success(callback)` | `(Callable[[str], None]) -> None` | [whitelist_controller.py:150](../../../agent/controllers/whitelist_controller.py#L150) | Subscribe success message. |
| `.remove_ip(ip)` | `(str) -> bool` | [whitelist_controller.py:180](../../../agent/controllers/whitelist_controller.py#L180) | Spawn worker xoá entry local và gọi `WhitelistManager.remove_ip` nếu có. |
| `.get_all_ips()` | `() -> List[Dict]` | [whitelist_controller.py:220](../../../agent/controllers/whitelist_controller.py#L220) | Snapshot list cho table. |
| `.refresh()` | `() -> None` | [whitelist_controller.py:225](../../../agent/controllers/whitelist_controller.py#L225) | Background `force_refresh`/`sync_now`, rebuild local state, emit success/error. |
| `.get_stats()` | `() -> Dict` | [whitelist_controller.py:249](../../../agent/controllers/whitelist_controller.py#L249) | Counts theo type/source/status + `sync_count` từ manager. |
| `get_whitelist_controller()` | `() -> WhitelistController` | [whitelist_controller.py:279](../../../agent/controllers/whitelist_controller.py#L279) | Singleton accessor. |

## Ai gọi module này
- [`agent/agent_gui.py`](../../../agent/agent_gui.py) → [`gui_qt.app.run`](../../../agent/gui_qt/app.py) import `AgentController`.
- [`agent/gui_qt/signal_bridge.py`](../../../agent/gui_qt/signal_bridge.py) drain `AgentSignals._event_queue` và re-emit Qt signals.
- [`agent/gui_qt/main_window.py`](../../../agent/gui_qt/main_window.py) truyền controller vào `DashboardView`, lấy `get_whitelist_controller` cho `WhitelistView`.
- [`agent/core/lifecycle.py`](../../../agent/core/lifecycle.py) không gọi controller; controller mới là caller của lifecycle.

## Module này gọi ra
- `agent/config` - `reload_config()` lúc start worker.
- `agent/core` - `get_agent()` (singleton), `make_runtime()` (test/multi-tenant), `initialize_components(config, runtime=None)`, `cleanup(config, runtime=None)`, `DeviceIdentityProvider.get_device_id()`.
- `agent/utils` - `check_admin_privileges()`.
- `agent/shared` - time helpers cho timestamp/uptime/sleep.
- `agent/whitelist` - qua `Agent.whitelist` manager instance.

## Đã có sẵn - đừng viết lại
- Cần start/stop agent từ UI? → `AgentController.start_agent()` / `stop_agent()`.
- Cần signal worker → GUI? → `AgentController.signals.emit(...)`, rồi Qt nhận qua `QtSignalBridge`.
- Cần whitelist table data? → `WhitelistController.get_all_ips()` hoặc callback `on_data_changed`.
- Cần force whitelist sync? → `AgentController.force_whitelist_sync()` nếu đang chạy, hoặc `WhitelistController.refresh()` cho view whitelist.

## Gotchas
- `AgentController` là singleton và `Agent` trong `core` cũng là singleton. Tests dùng `AgentController.reset_for_test()` + `Agent.reset_for_test()` (kèm `DeviceIdentityProvider.reset()` nếu mock identity) thay vì tự touch `_instance`/`_initialized` từ bên ngoài. Start quá nhanh sau Stop có guard bằng `_worker_id` + join ngắn; không bypass bằng cách tự spawn worker khác.
- `DEGRADED` vẫn là running. UI nên dùng `.is_running` cho toggle Start/Stop, còn nếu cần strict healthy thì so sánh `.status == AgentStatus.RUNNING`.
- `AgentSignals.process_events(root)` (Tk-style) **đã bị xóa**. Qt path đọc thẳng queue qua `QtSignalBridge`; đừng tái tạo Tk hook.
- `AgentController(runtime=...)` accept injected runtime, nhưng singleton vẫn enforce — pass runtime ở lần `__init__` đầu tiên hoặc gọi `reset_for_test()` rồi construct lại.
- `WhitelistController._sync_from_manager()` xoá/rebuild toàn bộ server entries. Nếu thêm local-only entry sau này, phải giữ `source != "Server"` như logic hiện tại.
- Controller import theo top-level package (`from config`, `from core`) dựa vào `agent/agent_gui.py` thêm `agent/` vào `sys.path`. Khi đổi entry point hoặc spec, phải giữ invariant này.
