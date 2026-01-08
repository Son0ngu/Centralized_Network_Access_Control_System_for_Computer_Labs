import customtkinter as ctk
import threading
from typing import Dict, List, Optional, Set

from ..controllers.whitelist_controller import get_whitelist_controller
from .components.data_table import DataTable
from network.dns_resolver import OptimizedDNSResolver


class WhitelistView(ctk.CTkFrame):
    """Whitelist view for managing allowed domains/IPs."""
    
    # Auto-sync interval in milliseconds (30 seconds)
    AUTO_SYNC_INTERVAL = 30000
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Get controller
        self._controller = get_whitelist_controller()

        # Shared DNS resolver for domain/IP lookups
        self._dns_resolver = OptimizedDNSResolver()
        
         # Resolved IP cache/state
        self._resolved_data: Optional[List[tuple]] = None
        self._last_resolved_domains: Set[str] = set()
        self._resolving_thread: Optional[threading.Thread] = None
        self._resolve_lock = threading.Lock()
        
        # Queue for pending resolve requests
        self._resolve_queued_domains: Optional[List[str]] = None

        # Auto-sync job ID
        self._auto_sync_job = None
        
        # Flag to check if agent is ready for server sync
        self._agent_ready = False
        
        # Setup UI
        self._setup_ui()
        
        # Register callbacks
        self._register_callbacks()
        
        # Initial data load (local only - no server sync yet)
        self.after(500, self._load_data)
        
        # Don't start auto-sync here - wait for agent to be ready
        # Agent controller will call set_agent_ready() when registered
    
    def _setup_ui(self):
        """Setup whitelist UI."""
        # Header
        self._create_header()
        
        # Stats section
        self._create_stats_section()
        
        # DataTable
        self._create_table()
        
        # Status bar
        self._create_status_bar()
    
    def _create_header(self):
        """Create header with title."""
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        
        # Title
        title = ctk.CTkLabel(
            header,
            text="IP Whitelist Manager",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(side="left", anchor="w")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=100,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._on_refresh
        )
        refresh_btn.pack(side="right")
        
        # Sync button
        sync_btn = ctk.CTkButton(
            header,
            text="☁️ Sync Server",
            width=120,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#00d4ff",
            hover_color="#00b8d4",
            text_color="#000000",
            command=self._on_sync
        )
        sync_btn.pack(side="right", padx=(0, 10))
    
    def _create_stats_section(self):
        """Create statistics section."""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        stats_frame.pack(fill="x", pady=(0, 10))
        stats_frame.pack_propagate(False)
        
        # Stats label - wider for more info
        self._stats_label = ctk.CTkLabel(
            stats_frame,
            text="📊 Loading statistics...",
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self._stats_label.pack(side="left", anchor="w", fill="x", expand=True)
        
        # Display mode toggle
        self._show_resolved = ctk.BooleanVar(value=False)
        toggle_switch = ctk.CTkSwitch(
            stats_frame,
            text="Resolved IPs",
            variable=self._show_resolved,
            command=self._on_toggle_resolved,
            font=ctk.CTkFont(size=12)
        )
        toggle_switch.pack(side="right", padx=(10, 5))
        
        # Search entry
        self._search_entry = ctk.CTkEntry(
            stats_frame,
            placeholder_text="Filter IPs...",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12),
            corner_radius=6,
            border_color="#3d3d54",
            fg_color="#0a0a12"
        )
        self._search_entry.pack(side="right")
        self._search_entry.bind("<KeyRelease>", self._on_search)
    
    def _create_table(self):
        """Create data table for IP list."""
        # Table container
        table_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12)
        table_frame.pack(fill="both", expand=True)
        
        # DataTable with IP columns - responsive with larger minsize
        # Weight determines how columns share extra space (higher = more space)
        columns = [
            {"key": "ip", "title": "Domain / IP Address", "width": 400, "weight": 4},
            {"key": "type", "title": "Type", "width": 120, "weight": 1},
            {"key": "status", "title": "Status", "width": 120, "weight": 1},
            {"key": "source", "title": "Source", "width": 120, "weight": 1},
        ]
        
        self._table = DataTable(
            table_frame,
            columns=columns,
            on_delete=None,
            show_actions=False
        )
        self._table.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        status_frame.pack(fill="x", pady=(10, 0))
        status_frame.pack_propagate(False)
        
        self._status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="#00ff88"
        )
        self._status_label.pack(side="left")
    
    def _register_callbacks(self):
        """Register controller callbacks."""
        self._controller.on_data_changed(lambda d: self.after(0, self._update_table, d))
        self._controller.on_error(lambda m: self.after(0, self._show_error, m))
        self._controller.on_success(lambda m: self.after(0, self._show_success, m))
    
    def _load_data(self):
        """Load initial data."""
        data = self._controller.get_all_ips()
        self._update_table(data)
        self._update_stats()
    
    def _update_table(self, data: List[Dict]):
        """Update table with new data."""
        # Get filter text
        filter_text = ""
        if hasattr(self, '_search_entry'):
            filter_text = self._search_entry.get().lower()

        show_resolved = self._show_resolved.get() if hasattr(self, '_show_resolved') else False

        filtered_data: List[Dict] = []

        if show_resolved:
            # Build resolved IP list from domains only (exclude direct IP entries)
            domains = [item.get("ip", "") for item in data if item.get("type", "").lower() == "domain"]

            # If domains changed or we haven't resolved yet, trigger background resolution
            if set(domains) != self._last_resolved_domains or self._resolved_data is None:
                self._last_resolved_domains = set(domains)
                self._resolved_data = None
                self._start_resolve_domains(domains)
                # Keep existing table data while resolving to avoid empty UI
                return

            resolved_ips = self._resolved_data or []

            for ip, domain in resolved_ips:
                if filter_text and filter_text not in ip.lower():
                    continue
                filtered_data.append({
                    "ip": ip,
                    "type": "IP",
                    "status": "Resolved",
                    "source": f"Resolved from {domain}",
                })
        else:
            # Reset resolved cache when switching back to domain view
            self._resolved_data = None
            self._last_resolved_domains = set()

            # Show only domains (hide raw whitelist IPs)
            for ip_data in data:
                ip = ip_data.get("ip", "")
                if ip_data.get("type", "").lower() != "domain":
                    continue
                if filter_text and filter_text not in ip.lower():
                    continue
                filtered_data.append(ip_data)

        # Set data to table
        self._table.set_data(filtered_data)
        
        # Update stats
        self._update_stats()
    
    def _update_stats(self):
        """Update statistics label."""
        stats = self._controller.get_stats()
        
        # Count by type
        domains = stats.get('manager_domains', 0)
        ips = stats.get('manager_ips', 0)
        total = stats.get('total_ips', 0)
        
        stats_text = (
            f"📊 Total: {total}  |  "
            f"🌐 Domains: {domains}  |  "
            f"📍 IPs: {ips}  |  "
            f"Active: {stats.get('active', 0)}"
        )
        
        sync_count = stats.get('sync_count', 0)
        if sync_count > 0:
            stats_text += f"  |  Syncs: {sync_count}"
        
        self._stats_label.configure(text=stats_text)
    
    def _on_delete_row(self, row_data: Dict):
        """Handle delete button click."""
        ip = row_data.get("ip", "")
        
        if ip:
            # Confirm dialog would be nice, but for now just delete
            self._controller.remove_ip(ip)
    
    def _on_refresh(self):
        """Handle refresh button click."""
        self._status_label.configure(text="Refreshing...", text_color="#ffa500")
        self._controller.refresh()
    
    def _on_sync(self):
        """Handle sync button click."""
        # Check if agent is ready (has whitelist manager connected)
        if self._controller._whitelist_manager is None:
            self._show_error("Agent not started - please start agent first")
            return
        
        self._status_label.configure(text="☁️ Syncing with server...", text_color="#00d4ff")
        self._controller.refresh()
    
    def _on_toggle_resolved(self):
        """Handle toggle resolved IPs."""
        if self._show_resolved.get():
            self._status_label.configure(text="Resolving domains...", text_color="#ffa500")
        else:
            self._status_label.configure(text="Showing domains", text_color="#00ff88")
        self._load_data()  # Reload and filter data
    
    def _on_search(self, event=None):
        """Handle search/filter."""
        self._load_data()  # Reload and filter data

    def _start_resolve_domains(self, domains: List[str]):
        """Resolve domains in a background thread to keep UI responsive."""
        # If thread is running, queue this request
        if self._resolving_thread and self._resolving_thread.is_alive():
            self._resolve_queued_domains = domains  # Update pending request
            return
            
        # Clear queue since we are handling it now
        self._resolve_queued_domains = None

        def worker():
            resolved_pairs = []
            try:
                with self._resolve_lock:
                    resolved_pairs = self._resolve_domains_to_ips(domains)
            finally:
                def update_ui():
                    if not self.winfo_exists():
                        return

                    self._resolved_data = resolved_pairs

                    if self._show_resolved.get():
                        # Refresh table now that resolved data is ready
                        self._status_label.configure(
                            text=f"Resolved {len(resolved_pairs)} IPs",
                            text_color="#00ff88"
                        )
                        self._update_table(self._controller.get_all_ips())
                    else:
                        # If user switched views, just reset state
                        self._resolved_data = None
                    
                    # Check if there is a pending request in queue
                    if self._resolve_queued_domains is not None:
                        # Start next resolution with queued domains
                        next_domains = self._resolve_queued_domains
                        self._resolve_queued_domains = None
                        # Don't recurse directly to avoid stack depth, use after
                        self.after(50, lambda: self._start_resolve_domains(next_domains))

                self.after(0, update_ui)

        self._resolving_thread = threading.Thread(target=worker, daemon=True, name="ResolveDomainsThread")
        self._resolving_thread.start()
        
    def _resolve_domains_to_ips(self, domains: List[str]) -> List[tuple]:
        """Resolve domains using the shared DNS resolver with deduplication."""
        if not domains:
            return []

        unique_domains = [d for d in dict.fromkeys(domains) if d]
        seen_ips: Set[str] = set()
        resolved: List[tuple] = []

        try:
            results = self._dns_resolver.resolve_multiple_parallel(unique_domains)
        except Exception:
            return []

        for domain in unique_domains:
            record = results.get(domain)
            if not record:
                continue

            for ip in list(record.ipv4) + list(record.ipv6):
                if ip in seen_ips:
                    continue
                seen_ips.add(ip)
                resolved.append((ip, domain))

        return resolved
    
    def _show_error(self, message: str):
        """Show error message in status bar."""
        self._status_label.configure(text=f"{message}", text_color="#ff4444")
        
        # Reset after 3 seconds
        self.after(3000, lambda: self._status_label.configure(
            text="Ready", text_color="#00ff88"
        ))
    
    def _show_success(self, message: str):
        """Show success message in status bar."""
        self._status_label.configure(text=f"{message}", text_color="#00ff88")
        
        # Update stats
        self._update_stats()
    
    def _start_auto_sync(self):
        """Start auto-sync periodic task."""
        if not self._agent_ready:
            # Agent not ready yet, check again in 5 seconds
            self.after(5000, self._check_and_start_auto_sync)
            return
        self._do_auto_sync()
    
    def _check_and_start_auto_sync(self):
        """Check if agent is ready and start auto-sync."""
        if not self.winfo_exists():
            return
        
        # Check if whitelist manager is connected (agent has started)
        if self._controller._whitelist_manager is not None:
            self._agent_ready = True
            self._do_auto_sync()
        else:
            # Try again in 5 seconds
            self.after(5000, self._check_and_start_auto_sync)
    
    def set_agent_ready(self, ready: bool = True):
        """Set agent ready status and start auto-sync if ready."""
        self._agent_ready = ready
        if ready and self._auto_sync_job is None:
            self._start_auto_sync()
    
    def _do_auto_sync(self):
        """Perform auto-sync and schedule next."""
        try:
            # Check if widget still exists
            if not self.winfo_exists():
                return
            
            # First sync from manager's local state (fast)
            self._controller._sync_from_manager()
            
            # Update table with new data
            data = self._controller.get_all_ips()
            self._update_table(data)
            
            # Update stats
            self._update_stats()
            
        except Exception as e:
            # Silent fail - don't spam logs
            pass
        
        # Schedule next auto-sync
        try:
            if self.winfo_exists():
                self._auto_sync_job = self.after(self.AUTO_SYNC_INTERVAL, self._do_auto_sync)
        except:
            pass
    
    def _stop_auto_sync(self):
        """Stop auto-sync periodic task."""
        if self._auto_sync_job:
            try:
                self.after_cancel(self._auto_sync_job)
            except:
                pass
            self._auto_sync_job = None
    
    def destroy(self):
        """Override destroy to stop auto-sync."""
        self._stop_auto_sync()
        super().destroy()
