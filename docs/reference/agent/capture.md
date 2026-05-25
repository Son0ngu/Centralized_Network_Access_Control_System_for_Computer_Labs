# `agent/capture` — Packet sniffer + Domain extraction + WinPcap auto-install

## Mục đích
Bắt gói tin outbound trên ports 80/443/53 bằng Scapy → trích xuất domain (HTTP Host, TLS SNI, DNS query) → đẩy record sang callback (thường là `handlers.handle_domain_detection`). Có lớp tự cấu hình Scapy cache (tránh permission error) và lớp tự động download/install WinPcap nếu thiếu driver pcap.

## Public API

### `agent/capture/sniffer.py` — Thread bắt gói

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `PacketSniffer` | `class` | [sniffer.py:24](../../../agent/capture/sniffer.py#L24) | Wrap `scapy.sniff` trong thread daemon `PacketSniffer` |
| `.__init__(callback)` | `(Callable[[Dict], None])` | [sniffer.py:25](../../../agent/capture/sniffer.py#L25) | Callback được gọi cho mỗi packet có domain hoặc port 80/443/53 |
| `.start()` | `() -> None` | [sniffer.py:38](../../../agent/capture/sniffer.py#L38) | Spawn thread, idempotent (skip nếu đã chạy) |
| `.stop()` | `() -> None` | [sniffer.py:56](../../../agent/capture/sniffer.py#L56) | Set `_stop_event`, join timeout 5s |
| `.packet_count` / `.domain_count` | `int` | [sniffer.py:34-35](../../../agent/capture/sniffer.py#L34) | Counters (lock-protected) — đọc cho GUI stats |
| `.running` | `bool` | [sniffer.py:28](../../../agent/capture/sniffer.py#L28) | |
| `._capture_loop()` | `() -> None` | [sniffer.py:75](../../../agent/capture/sniffer.py#L75) | BPF filter cố định: `tcp port 80/443/53 or udp port 53`. Max 3 retry trên OSError; PermissionError thì exit ngay |
| `._process_packet(packet)` | `(Packet) -> None` | [sniffer.py:131](../../../agent/capture/sniffer.py#L131) | Build record dict 9 fields (timestamp, domain, src/dest ip+port, protocol, packet_size, direction) |

**Filter & dispatch** (sniffer.py:155-173):
- TCP/80 → `extract_http_host` → protocol `"HTTP"`
- TCP/443 → `extract_https_sni` → protocol `"HTTPS"`
- UDP/53 → `extract_dns_query` → protocol `"DNS"`
- TCP/khác → `"TCP/{port}"`, không extract domain
- UDP/khác → `"UDP/{port}"`, không extract domain

### `agent/capture/extractors.py` — Domain extractor (static methods)

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `DomainExtractor.extract_http_host(packet)` | `(Packet) -> Optional[str]` | [extractors.py:27](../../../agent/capture/extractors.py#L27) | Thử `HTTPRequest.Host` trước, fallback parse raw payload tìm `b"Host: "` → CRLF |
| `DomainExtractor.extract_https_sni(packet)` | `(Packet) -> Optional[str]` | [extractors.py:62](../../../agent/capture/extractors.py#L62) | Thử `TLSClientHello.ext` rồi tới manual parse TLS record |
| `DomainExtractor.extract_dns_query(packet)` | `(Packet) -> Optional[str]` | [extractors.py:182](../../../agent/capture/extractors.py#L182) | `DNS.qd.qname` decode, strip trailing `.` |
| `DomainExtractor._extract_sni_manual(payload)` | `(bytes) -> Optional[str]` | [extractors.py:98](../../../agent/capture/extractors.py#L98) | Manual TLS handshake parse (record type `0x16`, msg type `0x01`, ext type `0`) |
| `DomainExtractor._is_valid_hostname(hostname)` | `(str) -> bool` | [extractors.py:208](../../../agent/capture/extractors.py#L208) | len≤253, regex `[a-zA-Z0-9.-]+`, có `.`, label không bắt đầu/kết thúc bằng `-` |

### `agent/capture/scapy_config.py` — Scapy environment fix

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `configure_scapy()` | `() -> Optional[str]` | [scapy_config.py:12](../../../agent/capture/scapy_config.py#L12) | Set `SCAPY_CACHE_DIR / SCAPY_CONFIG_DIR / SCAPY_DATA_DIR / XDG_CACHE_HOME / SCAPY_HOME` về `%TEMP%/scapy-cache`. Idempotent (cached `_SCAPY_CACHE_DIR`) |
| `ensure_pcap_driver()` | `() -> bool` | [scapy_config.py:54](../../../agent/capture/scapy_config.py#L54) | Tìm `wpcap.dll` ở 7 vị trí (env vars + System32 + Program Files Npcap/WinPcap), prepend vào `PATH`, gọi `os.add_dll_directory` cho Python 3.8+ |
| `apply_scapy_config()` | `() -> None` | [scapy_config.py:122](../../../agent/capture/scapy_config.py#L122) | **Gọi SAU khi import scapy** để set `scapy.config.conf.cache_dir` |

**Thứ tự bắt buộc** (sniffer.py:9-17):
```
configure_scapy()       # set env vars
ensure_pcap_driver()    # set PATH cho wpcap.dll
from scapy.all import sniff  # giờ mới import được
apply_scapy_config()    # set scapy_conf.cache_dir
```

### `agent/capture/winpcap_installer.py` — Auto-install WinPcap

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `WINPCAP_DOWNLOAD_URL` | `str` const | [winpcap_installer.py:17](../../../agent/capture/winpcap_installer.py#L17) | `https://www.winpcap.org/install/bin/WinPcap_4_1_3.exe` |
| `is_admin()` | `() -> bool` | [winpcap_installer.py:30](../../../agent/capture/winpcap_installer.py#L30) | `ctypes.windll.shell32.IsUserAnAdmin` |
| `is_winpcap_installed()` | `() -> bool` | [winpcap_installer.py:37](../../../agent/capture/winpcap_installer.py#L37) | Check 5 file paths (System32/wpcap.dll, Npcap/wpcap.dll, ...) + registry `HKLM\SOFTWARE\WinPcap` + `\Npcap`. Non-Windows → `True` |
| `download_winpcap(target_dir=None)` | `(Optional[str]) -> Optional[str]` | [winpcap_installer.py:88](../../../agent/capture/winpcap_installer.py#L88) | Tải tới `%TEMP%/WinPcap_4_1_3.exe`. Verify size > 100KB. User-Agent là Mozilla |
| `install_winpcap_silent(installer_path)` | `(str) -> bool` | [winpcap_installer.py:157](../../../agent/capture/winpcap_installer.py#L157) | `[installer, "/S"]`, timeout 120s, `CREATE_NO_WINDOW`. Sleep 3s rồi verify. Set `_winpcap_installed_by_us=True` + `atexit.register(cleanup_winpcap)` |
| `uninstall_winpcap_silent()` | `() -> bool` | [winpcap_installer.py:203](../../../agent/capture/winpcap_installer.py#L203) | Tìm uninstaller ở 3 path + registry `Uninstall\WinPcapInst`. Run `/S` |
| `cleanup_winpcap()` | `() -> None` | [winpcap_installer.py:268](../../../agent/capture/winpcap_installer.py#L268) | Lock-protected. Uninstall **CHỈ KHI** `_winpcap_installed_by_us=True`. Xoá installer file |
| `ensure_winpcap_available()` | `() -> Tuple[bool, str]` | [winpcap_installer.py:292](../../../agent/capture/winpcap_installer.py#L292) | **Entry point cho lifecycle**. Check exist → admin → download → install. Trả `(success, message)` |
| `was_installed_by_us()` | `() -> bool` | [winpcap_installer.py:319](../../../agent/capture/winpcap_installer.py#L319) | Cho lifecycle decide có cleanup hay không |
| `init_winpcap_manager()` | `() -> None` | [winpcap_installer.py:325](../../../agent/capture/winpcap_installer.py#L325) | No-op trên non-Windows. Hiện không có gì để init |

## Ai gọi module này
- `agent/core/lifecycle.py` — `ensure_winpcap_available` (Step 3.1) trước khi tạo `FirewallManager`; `PacketSniffer(callback=domain_handler)` ở Step 7; `cleanup_winpcap` + `was_installed_by_us` trong cleanup
- `agent/firewall/manager.py` — fallback resolve cũng đụng tới `socket.getaddrinfo` không qua capture
- GUI không gọi trực tiếp; đọc stats qua `Agent.sniffer.packet_count/domain_count`

## Module này gọi ra
- `scapy.all`, `scapy.layers.{inet,dns,tls,http}` — packet processing
- `agent/shared/time_utils` — timestamp cho record
- `urllib.request` — download installer
- `subprocess` — chạy installer/uninstaller
- `winreg` — check pcap installed via registry
- `ctypes.windll.shell32` — admin check

## Đã có sẵn — đừng viết lại
- Cần extract domain từ packet bất kỳ? → `DomainExtractor.extract_*` static methods — **đừng** parse raw payload thủ công
- Cần validate hostname dạng FQDN? → `DomainExtractor._is_valid_hostname(s)` — quick check (len, charset, có dot, label hợp lệ)
- Cần check pcap driver tồn tại? → `is_winpcap_installed()` (winpcap_installer) — đã cover cả file paths lẫn registry
- Cần set Scapy chạy được trên Windows? → `configure_scapy() + ensure_pcap_driver()` trước khi import — không tự fix `wpcap.dll PATH` thủ công

## Gotchas
- **Top-level side effects ở sniffer.py:9-17**: `configure_scapy()`, `ensure_pcap_driver()`, `from scapy.all import sniff`, `apply_scapy_config()` chạy NGAY khi import `agent.capture.sniffer`. Nghĩa là chỉ cần `from capture import PacketSniffer` đã trigger toàn bộ — không lazy được. Test cần ý thức (mock scapy hoặc skip module).
- **`apply_scapy_config()` chạy SAU `from scapy.all`** (sniffer.py:17), không phải trước. Lý do: `scapy.config.conf` chỉ tồn tại sau khi scapy được import. Đảo thứ tự ⇒ ImportError ngầm.
- **BPF filter trong `_capture_loop` hard-coded** (sniffer.py:79-82) — không đọc từ config `capture.filter`. Config có entry filter (defaults.py:41) nhưng KHÔNG được dùng. Nếu thấy admin đổi filter trong config mà không có hiệu lực → đây là lý do.
- **`sniff` được gọi với `timeout=2` lặp lại** (sniffer.py:90-96) thay vì 1 lần với `stop_filter` — vì scapy `sniff` chặn thread cho tới khi nhận packet, timeout ngắn cho phép check `_stop_event` định kỳ.
- **`_process_packet` gọi callback ngay trong sniff thread** — nếu callback chậm sẽ drop packet. Hiện callback (handlers) chỉ queue log nên rất nhanh; đừng thêm I/O blocking ở đây.
- **Domain extraction fail-soft**: trả `None` thay vì raise. Caller check `if domain or dst_port in [80,443,53]` ⇒ vẫn log packet kể cả không extract được domain (cho audit).
- **TLS SNI manual parse** (extractors.py:98) tin tưởng client gửi đúng format. Packet phân mảnh (TCP segment > 1 packet) sẽ không bắt được SNI — vì `payload` chỉ là packet đầu. Acceptable tradeoff (không reassemble).
- **WinPcap_4_1_3 đã EOL** từ 2018 — không hoạt động trên Windows 10/11 mới. `ensure_winpcap_available` sẽ tải nó về nhưng install có thể fail trên Win11. Hướng đi đúng: hướng user cài **Npcap** thủ công (free từ nmap.org). Code hiện vẫn check Npcap qua registry và `wpcap.dll` ở `Npcap/`.
- **`atexit.register(cleanup_winpcap)`** chỉ register một lần khi install thành công (winpcap_installer.py:188). Nếu lifecycle.py gọi `cleanup_winpcap()` thủ công trong shutdown, atexit chạy thêm lần nữa nhưng `_winpcap_installed_by_us` đã `False` ⇒ no-op. An toàn.
- **`was_installed_by_us` là module-global** — nếu chạy nhiều instance agent cùng process (test), state share giữa các test. Reset thủ công nếu cần.
- **`download_winpcap` không validate signature/hash** — chỉ check size > 100KB. Nếu lưu lại tệ tải, chấp nhận risk. Đừng kích hoạt auto-install trên môi trường nhạy cảm bảo mật mà không cần.
- **`is_winpcap_installed` trả `True` trên non-Windows** (winpcap_installer.py:38) — code path Linux/Mac sẽ skip cleanup. Hiện agent là Windows-only nên không thành vấn đề.
