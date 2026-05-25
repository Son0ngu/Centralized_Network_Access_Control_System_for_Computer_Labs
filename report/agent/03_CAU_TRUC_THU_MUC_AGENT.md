# Cấu trúc thư mục Agent

```text
agent/
├── cache/
│   ├── __init__.py
│   └── lru_cache.py
├── capture/
│   ├── __init__.py
│   ├── extractors.py
│   ├── scapy_config.py
│   ├── sniffer.py
│   └── winpcap_installer.py
├── config/
│   ├── __init__.py
│   ├── crypto.py
│   ├── defaults.py
│   ├── loader.py
│   └── validator.py
├── controllers/                       # controller dùng chung, không phụ thuộc GUI framework
│   ├── __init__.py
│   ├── agent_controller.py
│   └── whitelist_controller.py
├── core/
│   ├── __init__.py
│   ├── agent.py
│   ├── handlers.py
│   ├── lifecycle.py
│   ├── registry.py
│   └── token_manager.py
├── firewall/
│   ├── __init__.py
│   ├── manager.py
│   ├── policy.py
│   ├── rules.py
│   └── utils.py
├── gui_qt/                            # PySide6 frontend (toàn bộ view)
│   ├── __init__.py
│   ├── app.py                         # `run()` — khởi tạo QApplication, MainWindow
│   ├── main_window.py                 # QMainWindow + sidebar + QStackedWidget
│   ├── signal_bridge.py               # AgentSignals queue → Qt signals
│   ├── styles.py                      # QSS global + palette constants
│   ├── components/
│   │   ├── __init__.py
│   │   ├── data_table.py              # QTableView + DictTableModel
│   │   ├── log_console.py             # QPlainTextEdit + GUILogHandler
│   │   ├── sparkline.py               # QPainter line chart
│   │   └── status_card.py
│   └── views/
│       ├── __init__.py
│       ├── dashboard.py
│       ├── firewall.py
│       ├── logs.py
│       ├── settings.py
│       └── whitelist.py
├── logging_module/
│   ├── __init__.py
│   └── sender.py
├── network/
│   ├── __init__.py
│   └── dns_resolver.py
├── services/
│   ├── __init__.py
│   └── heartbeat.py
├── shared/
│   ├── __init__.py
│   ├── os_info.py
│   └── time_utils.py
├── utils/
│   ├── __init__.py
│   ├── error_handler.py
│   ├── ip_detector.py
│   └── validators.py
├── whitelist/
│   ├── __init__.py
│   ├── manager.py
│   ├── monitor.py
│   ├── state.py
│   └── sync.py
├── agent_gui.py                       # Qt entry point (đầu vào của PyInstaller)
├── saint_agent.spec                   # PyInstaller spec build .exe
├── miku.ico
├── README.md
└── requirements.txt
```

## Ý nghĩa các package chính

| Package | Vai trò |
| --- | --- |
| `agent/core` | Singleton Agent, lifecycle, register, token manager, handler domain detection. |
| `agent/firewall` | Quản lý Windows Firewall policy/rules/default-deny. |
| `agent/whitelist` | State whitelist, sync với Server, update firewall rules. |
| `agent/capture` | Cấu hình Scapy, packet sniffer, extract DNS/HTTP/TLS SNI. |
| `agent/controllers` | Framework-agnostic controller package: `AgentController` + `WhitelistController`, quản lý worker thread, signal queue và dữ liệu whitelist cho Qt views. |
| `agent/gui_qt` | PySide6 frontend đầy đủ: app entry, MainWindow + sidebar, views (Dashboard, Whitelist, Firewall, Logs, Settings), components reusable (DataTable, StatusCard, LogConsole, Sparkline). |
| `agent/config` | Default config, load env/file, validate, encrypt/decrypt. |
| `agent/services` | Heartbeat sender. |
| `agent/logging_module` | Queue và gửi logs batch về Server. |

