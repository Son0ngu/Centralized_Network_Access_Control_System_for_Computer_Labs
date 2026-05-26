# Công nghệ sử dụng - Agent

| Dependency | Vai trò trong source |
| --- | --- |
| scapy>=2.4.5 | Packet capture và phân tích DNS/HTTP/TLS. |
| Windows Firewall / netsh | Cơ chế enforcement chính: chặn mặc định và cho phép IP whitelist bằng rule hệ thống. |
| dnspython | DNS resolver đồng bộ. |
| aiodns | DNS resolver bất đồng bộ. |
| requests>=2.28.0 | HTTP client Agent -> Server. |
| urllib3>=1.26.0 | HTTP transport dependency. |
| psutil>=5.9.0 | Metrics hệ thống. |
| python-dateutil>=2.8.0 | Xử lý datetime. |
| pywin32 | API Windows/admin/service/firewall helper. |
| requests | HTTP client Agent -> Server. |
| netifaces>=0.11.0 | Thông tin network interface. |
| distro>=1.6.0 | Thông tin OS. |
| PySide6>=6.6.0 | GUI desktop Agent (Qt for Python - LGPL). |
| cryptography | Mã hóa config Agent. |

## Công nghệ theo nhóm chức năng

| Nhóm | Công nghệ | Nơi dùng |
| --- | --- | --- |
| GUI | PySide6 (Qt) | `agent/gui_qt/`, entry `agent/agent_gui.py` |
| Controllers (framework-agnostic) | threading + AgentSignals | `agent/controllers/` (được Qt views sử dụng) |
| Packet capture | Scapy | `agent/capture/sniffer.py`, `agent/capture/extractors.py` |
| DNS | dnspython, aiodns | `agent/network/dns_resolver.py` |
| Firewall Windows | netsh, pywin32 | `agent/firewall/` |
| HTTP client | requests | `agent/core/registry.py`, `agent/whitelist/sync.py`, `agent/services/heartbeat.py`, `agent/logging_module/sender.py` |
| Config security | cryptography | `agent/config/crypto.py` |
| Packaging | PyInstaller | `agent/saint_agent.spec` |

