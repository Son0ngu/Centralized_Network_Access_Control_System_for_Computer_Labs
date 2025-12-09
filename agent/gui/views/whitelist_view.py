"""
Whitelist View - Domain/IP whitelist management with CRUD operations.
Vietnam ONLY - Using customtkinter.

Features:
- DataTable displaying IP list
- Add IP input and button
- Delete action per row
- Refresh and sync buttons
- Statistics display
"""

import customtkinter as ctk
import threading
from typing import Dict, List, Optional

from ..controllers.whitelist_controller import WhitelistController, get_whitelist_controller
from .components.data_table import DataTable


class WhitelistView(ctk.CTkFrame):
    """Whitelist view for managing allowed domains/IPs."""
    
    # Auto-sync interval in milliseconds (30 seconds)
    AUTO_SYNC_INTERVAL = 30000
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Get controller
        self._controller = get_whitelist_controller()
        
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
        
        # Add IP section
        self._create_add_section()
        
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
    
    def _create_add_section(self):
        """Create add IP input section."""
        add_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12, height=70)
        add_frame.pack(fill="x", pady=(0, 15))
        add_frame.pack_propagate(False)
        
        # Inner container
        inner = ctk.CTkFrame(add_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Label
        label = ctk.CTkLabel(
            inner,
            text="Add New IP:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        )
        label.pack(side="left")
        
        # IP input
        self._ip_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Enter IP address (e.g., 192.168.1.1)",
            width=300,
            height=40,
            font=ctk.CTkFont(size=13),
            corner_radius=8,
            border_color="#3d3d54",
            fg_color="#0a0a12"
        )
        self._ip_entry.pack(side="left", padx=(15, 0))
        
        # Bind Enter key
        self._ip_entry.bind("<Return>", lambda e: self._on_add_ip())
        
        # Add button
        add_btn = ctk.CTkButton(
            inner,
            text="➕ Add IP",
            width=100,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#00ff88",
            hover_color="#00cc6f",
            text_color="#000000",
            command=self._on_add_ip
        )
        add_btn.pack(side="left", padx=(10, 0))
        
        # Clear button
        clear_btn = ctk.CTkButton(
            inner,
            text="✖️ Clear",
            width=80,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._on_clear_input
        )
        clear_btn.pack(side="left", padx=(5, 0))
    
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
        
        # Search entry
        self._search_entry = ctk.CTkEntry(
            stats_frame,
            placeholder_text="Filter IPs...",
            width=200,
            height=32,
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
            on_delete=self._on_delete_row,
            show_actions=True
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
        self._controller.on_data_changed(self._update_table)
        self._controller.on_error(self._show_error)
        self._controller.on_success(self._show_success)
    
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
        
        # Filter data
        filtered_data = []
        for ip_data in data:
            ip = ip_data.get("ip", "")
            
            # Apply filter
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
            f"🖥️ IPs: {ips}  |  "
            f"Active: {stats.get('active', 0)}"
        )
        
        sync_count = stats.get('sync_count', 0)
        if sync_count > 0:
            stats_text += f"  |  Syncs: {sync_count}"
        
        self._stats_label.configure(text=stats_text)
    
    def _on_add_ip(self):
        """Handle add IP button click."""
        ip = self._ip_entry.get().strip()
        
        if not ip:
            self._show_error("Please enter an IP address")
            return
        
        # Validate first
        is_valid, error = WhitelistController.validate_ip(ip)
        if not is_valid:
            self._show_error(error)
            return
        
        # Add IP
        self._controller.add_ip(ip)
        
        # Clear input
        self._ip_entry.delete(0, "end")
    
    def _on_delete_row(self, row_data: Dict):
        """Handle delete button click."""
        ip = row_data.get("ip", "")
        
        if ip:
            # Confirm dialog would be nice, but for now just delete
            self._controller.remove_ip(ip)
    
    def _on_clear_input(self):
        """Clear IP input field."""
        self._ip_entry.delete(0, "end")
    
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
    
    def _on_search(self, event=None):
        """Handle search/filter."""
        data = self._controller.get_all_ips()
        self._update_table(data)
    
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
