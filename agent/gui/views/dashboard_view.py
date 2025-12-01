"""
Dashboard View - Shows agent status overview with real-time data.
Vietnam ONLY - Using customtkinter.

Features:
- StatusCard components for metrics display
- Real-time data binding from AgentController
- Periodic stats refresh using after()
- Activity log with auto-scroll
"""

import customtkinter as ctk
from typing import Dict, Optional

from .components import StatusCard, AnimatedStatusCard


class DashboardView(ctk.CTkFrame):
    """Dashboard view showing agent status and statistics."""
    
    # Refresh interval in milliseconds
    STATS_REFRESH_INTERVAL = 1000  # 1 second
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Agent controller reference
        self._controller = None
        
        # Status cards references
        self._cards: Dict[str, StatusCard] = {}
        
        # UI element references
        self._start_stop_btn: Optional[ctk.CTkButton] = None
        self._status_indicator: Optional[ctk.CTkLabel] = None
        self._log_textbox: Optional[ctk.CTkTextbox] = None
        
        # Periodic update tracking
        self._stats_update_id = None
        self._is_visible = True
        
        self._setup_ui()
        self._connect_controller()
        self._start_periodic_updates()
    
    def _connect_controller(self):
        """Connect to AgentController and setup signal handlers."""
        try:
            from ..controllers import AgentController
            self._controller = AgentController()
            
            # Connect signals
            self._controller.signals.connect('status_changed', self._on_status_changed)
            self._controller.signals.connect('stats_updated', self._on_stats_updated)
            self._controller.signals.connect('error_occurred', self._on_error)
            self._controller.signals.connect('packet_captured', self._on_packet_captured)
            self._controller.signals.connect('whitelist_synced', self._on_whitelist_synced)
            
        except Exception as e:
            print(f"Warning: Could not connect to AgentController: {e}")
    
    def _setup_ui(self):
        """Setup dashboard UI."""
        # Title row with controls
        self._setup_header()
        
        # Status cards grid
        self._setup_status_cards()
        
        # Real-time metrics row
        self._setup_realtime_metrics()
        
        # Activity log
        self._setup_activity_log()
    
    def _setup_header(self):
        """Setup header with title and controls."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title
        title = ctk.CTkLabel(
            header_frame,
            text="📊 Dashboard",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(side="left")
        
        # Start/Stop button
        self._start_stop_btn = ctk.CTkButton(
            header_frame,
            text="▶️ Start Agent",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#00ff88",
            hover_color="#00cc6a",
            text_color="#000000",
            command=self._toggle_agent
        )
        self._start_stop_btn.pack(side="right", padx=(0, 10))
        
        # Status indicator
        self._status_indicator = ctk.CTkLabel(
            header_frame,
            text="⚫ Stopped",
            font=ctk.CTkFont(size=14),
            text_color="#888888"
        )
        self._status_indicator.pack(side="right", padx=(0, 20))
    
    def _setup_status_cards(self):
        """Setup main status cards grid."""
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 15))
        
        # Configure grid columns
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)
        
        # Card 1: Agent Status
        self._cards['status'] = AnimatedStatusCard(
            cards_frame,
            title="Agent Status",
            value="Stopped",
            icon="🔴",
            color="#ff4444",
            subtitle="Not running",
            width=180,
            height=110
        )
        self._cards['status'].grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        
        # Card 2: Firewall Mode
        self._cards['mode'] = StatusCard(
            cards_frame,
            title="Firewall Mode",
            value="—",
            icon="🛡️",
            color="#888888",
            subtitle="Mode not set",
            width=180,
            height=110
        )
        self._cards['mode'].grid(row=0, column=1, padx=4, sticky="nsew")
        
        # Card 3: Whitelist Domains
        self._cards['domains'] = AnimatedStatusCard(
            cards_frame,
            title="Whitelist",
            value="0",
            icon="📋",
            color="#00d4ff",
            subtitle="domains + patterns",
            width=180,
            height=110
        )
        self._cards['domains'].grid(row=0, column=2, padx=4, sticky="nsew")
        
        # Card 4: Uptime
        self._cards['uptime'] = StatusCard(
            cards_frame,
            title="Uptime",
            value="0s",
            icon="⏱️",
            color="#ffa500",
            subtitle="Agent runtime",
            width=180,
            height=110
        )
        self._cards['uptime'].grid(row=0, column=3, padx=(8, 0), sticky="nsew")
    
    def _setup_realtime_metrics(self):
        """Setup real-time metrics row."""
        metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        metrics_frame.pack(fill="x", pady=(0, 15))
        
        # Configure grid columns
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)
        
        # Card 5: Whitelisted IPs
        self._cards['ips'] = AnimatedStatusCard(
            metrics_frame,
            title="Allowed IPs",
            value="0",
            icon="🌐",
            color="#00ff88",
            subtitle="In whitelist",
            width=180,
            height=110
        )
        self._cards['ips'].grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        
        # Card 6: Packets/sec
        self._cards['packets'] = AnimatedStatusCard(
            metrics_frame,
            title="Packets",
            value="0",
            icon="📦",
            color="#9966ff",
            subtitle="captured",
            width=180,
            height=110
        )
        self._cards['packets'].grid(row=0, column=1, padx=4, sticky="nsew")
        
        # Card 7: Server Connection
        self._cards['server'] = StatusCard(
            metrics_frame,
            title="Server",
            value="Offline",
            icon="🔗",
            color="#ff4444",
            subtitle="Connection status",
            width=180,
            height=110
        )
        self._cards['server'].grid(row=0, column=2, padx=4, sticky="nsew")
        
        # Card 8: Last Sync
        self._cards['sync'] = StatusCard(
            metrics_frame,
            title="Last Sync",
            value="Never",
            icon="🔄",
            color="#888888",
            subtitle="Whitelist sync",
            width=180,
            height=110
        )
        self._cards['sync'].grid(row=0, column=3, padx=(8, 0), sticky="nsew")
    
    def _setup_activity_log(self):
        """Setup activity log section."""
        log_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1a1a2e")
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        # Log header
        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=15, pady=(15, 10))
        
        log_title = ctk.CTkLabel(
            log_header,
            text="📋 Activity Log",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        log_title.pack(side="left")
        
        # Log controls
        clear_btn = ctk.CTkButton(
            log_header,
            text="🗑️ Clear",
            width=70,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._clear_log
        )
        clear_btn.pack(side="right")
        
        # Log textbox
        self._log_textbox = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0f0f1a",
            text_color="#00ff88",
            corner_radius=8,
            height=180
        )
        self._log_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self._log_textbox.configure(state="disabled")
        
        # Initial log message
        self._append_log("Dashboard initialized. Click 'Start Agent' to begin.")
    
    # ========================================
    # PERIODIC UPDATES (Data Binding)
    # ========================================
    
    def _start_periodic_updates(self):
        """Start periodic stats updates."""
        self._update_stats_display()
    
    def _update_stats_display(self):
        """Fetch and display current stats from controller."""
        if self._controller and self._is_visible:
            try:
                # Get agent info
                info = self._controller.get_agent_info()
                stats = info.get('stats', {})
                
                # Update uptime card
                uptime = stats.get('uptime_seconds', 0)
                self._cards['uptime'].set_value(self._format_uptime(uptime))
                
                # Update domain/pattern counts
                domains = stats.get('domains_count', 0)
                patterns = stats.get('patterns_count', 0)
                self._cards['domains'].set_value(str(domains + patterns))
                self._cards['domains'].set_subtitle(f"{domains} domains, {patterns} patterns")
                
                # Update IP count
                ips = stats.get('ips_count', 0)
                self._cards['ips'].set_value(str(ips))
                
                # Update packets count
                packets = stats.get('packets_captured', 0)
                self._cards['packets'].set_value(str(packets))
                
                # Update server status based on agent status
                if info.get('is_registered'):
                    self._cards['server'].set_value("Online")
                    self._cards['server'].set_color("#00ff88")
                elif self._controller.is_running:
                    self._cards['server'].set_value("Connecting...")
                    self._cards['server'].set_color("#ffa500")
                else:
                    self._cards['server'].set_value("Offline")
                    self._cards['server'].set_color("#ff4444")
                
            except Exception as e:
                pass  # Silently ignore stats update errors
        
        # Schedule next update
        self._stats_update_id = self.after(
            self.STATS_REFRESH_INTERVAL,
            self._update_stats_display
        )
    
    def _stop_periodic_updates(self):
        """Stop periodic updates."""
        if self._stats_update_id:
            self.after_cancel(self._stats_update_id)
            self._stats_update_id = None
    
    # ========================================
    # AGENT CONTROL METHODS
    # ========================================
    
    def _toggle_agent(self):
        """Toggle agent start/stop."""
        if not self._controller:
            self._append_log("ERROR: AgentController not available")
            return
        
        if self._controller.is_running:
            self._stop_agent()
        else:
            self._start_agent()
    
    def _start_agent(self):
        """Start the agent."""
        self._append_log("Starting agent...")
        self._update_button_state("starting")
        
        if self._controller.start_agent():
            self._append_log("Agent start initiated")
        else:
            self._append_log("ERROR: Failed to start agent")
            self._update_button_state("stopped")
    
    def _stop_agent(self):
        """Stop the agent."""
        self._append_log("Stopping agent...")
        self._update_button_state("stopping")
        
        if self._controller.stop_agent():
            self._append_log("Agent stop initiated")
        else:
            self._append_log("ERROR: Failed to stop agent")
    
    def _update_button_state(self, state: str):
        """Update Start/Stop button appearance."""
        if not self._start_stop_btn:
            return
        
        states = {
            "stopped": ("▶️ Start Agent", "#00ff88", "#00cc6a", "#000000"),
            "starting": ("⏳ Starting...", "#ffa500", "#cc8400", "#000000"),
            "running": ("⏹️ Stop Agent", "#ff4444", "#cc3333", "#ffffff"),
            "stopping": ("⏳ Stopping...", "#ffa500", "#cc8400", "#000000"),
            "error": ("⚠️ Error", "#ff4444", "#cc3333", "#ffffff"),
        }
        
        text, fg, hover, text_color = states.get(state, states["stopped"])
        
        self._start_stop_btn.configure(
            text=text,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color
        )
    
    # ========================================
    # SIGNAL HANDLERS (called from AgentController)
    # ========================================
    
    def _on_status_changed(self, data: Dict):
        """Handle agent status change."""
        status = data.get('status', 'unknown')
        message = data.get('message', '')
        
        if status == 'running':
            self._cards['status'].set_value("Running")
            self._cards['status'].set_icon("🟢")
            self._cards['status'].set_color("#00ff88")
            self._cards['status'].set_subtitle("Agent is active")
            self._status_indicator.configure(text="🟢 Running", text_color="#00ff88")
            self._update_button_state("running")
            
            # Update mode card
            info = self._controller.get_agent_info()
            mode = info.get('firewall_mode', 'monitor')
            enabled = info.get('firewall_enabled', False)
            
            # Format mode display - all 4 modes
            mode_display = {
                'monitor': 'Monitor',
                'whitelist_only': 'Whitelist',
                'block': 'Block',
                'warn': 'Warn'
            }.get(mode, mode.title())
            
            # Mode-specific icons and colors
            mode_config = {
                'monitor': ('👁️', '#00d4ff', 'Observing traffic'),
                'whitelist_only': ('🛡️', '#00ff88', 'Only whitelist allowed'),
                'block': ('🚫', '#ff4444', 'Blocking non-whitelist'),
                'warn': ('⚠️', '#ffa500', 'Warning on violations')
            }.get(mode, ('👁️', '#888888', 'Unknown mode'))
            
            if enabled:
                self._cards['mode'].set_value(mode_display)
                self._cards['mode'].set_icon(mode_config[0])
                self._cards['mode'].set_color(mode_config[1])
                self._cards['mode'].set_subtitle(mode_config[2])
            else:
                self._cards['mode'].set_value(mode_display)
                self._cards['mode'].set_icon('👁️')
                self._cards['mode'].set_color('#00d4ff')
                self._cards['mode'].set_subtitle('Firewall disabled')
            
        elif status == 'stopped':
            self._cards['status'].set_value("Stopped")
            self._cards['status'].set_icon("🔴")
            self._cards['status'].set_color("#ff4444")
            self._cards['status'].set_subtitle("Not running")
            self._status_indicator.configure(text="⚫ Stopped", text_color="#888888")
            self._update_button_state("stopped")
            
            self._cards['mode'].set_value("—")
            self._cards['mode'].set_icon("🛡️")
            self._cards['mode'].set_color("#888888")
            self._cards['mode'].set_subtitle("Mode not set")
            
            # Reset other cards
            self._cards['server'].set_value("Offline")
            self._cards['server'].set_color("#ff4444")
            
            # Show stopped confirmation
            self._append_stopped_banner()
            
        elif status == 'starting':
            self._cards['status'].set_value("Starting...")
            self._cards['status'].set_icon("🟡")
            self._cards['status'].set_color("#ffa500")
            self._cards['status'].set_subtitle("Initializing")
            self._status_indicator.configure(text="🟡 Starting", text_color="#ffa500")
            self._append_startup_banner()
            
        elif status == 'stopping':
            self._cards['status'].set_value("Stopping...")
            self._cards['status'].set_icon("🟡")
            self._cards['status'].set_color("#ffa500")
            self._cards['status'].set_subtitle("Shutting down")
            self._status_indicator.configure(text="🟡 Stopping", text_color="#ffa500")
            self._append_shutdown_banner()
        
        if message:
            self._append_log(f"[STATUS] {message}")
    
    def _on_stats_updated(self, data: Dict):
        """Handle stats update from agent."""
        # Update domain/pattern counts
        domains = data.get('domains_count', 0)
        patterns = data.get('patterns_count', 0)
        self._cards['domains'].set_value(str(domains + patterns))
        self._cards['domains'].set_subtitle(f"{domains} domains, {patterns} patterns")
        
        # Update IP count
        ips = data.get('ips_count', 0)
        self._cards['ips'].set_value(str(ips))
        
        # Update uptime
        uptime = data.get('uptime_seconds', 0)
        self._cards['uptime'].set_value(self._format_uptime(uptime))
        
        # Update packets
        packets = data.get('packets_captured', 0)
        self._cards['packets'].set_value(str(packets))
    
    def _on_error(self, data: Dict):
        """Handle agent error."""
        error = data.get('error', 'Unknown error')
        message = data.get('message', '')
        
        self._cards['status'].set_value("⚠️ Error")
        self._cards['status'].set_color("#ff4444")
        self._cards['status'].set_subtitle("Error occurred")
        self._status_indicator.configure(text="⚠️ Error", text_color="#ff4444")
        self._update_button_state("error")
        
        self._append_log(f"[ERROR] {error}")
        if message:
            self._append_log(f"[ERROR] {message}")
    
    def _on_packet_captured(self, data: Dict):
        """Handle packet captured event."""
        domain = data.get('domain', '')
        dest_ip = data.get('dest_ip', '')
        action = data.get('action', 'detected')
        protocol = data.get('protocol', '')
        port = data.get('port', '')
        
        # Skip empty/unknown entries
        if not domain and not dest_ip:
            return
        
        # Update packets count
        current = int(self._cards['packets'].get_value() or 0)
        self._cards['packets'].set_value(str(current + 1))
        
        # Build display target
        target = domain if domain and domain != 'unknown' else dest_ip
        if not target or target == 'unknown':
            return
        
        # Build protocol info
        proto_info = ""
        if protocol and protocol != 'unknown':
            proto_info = f" ({protocol}"
            if port and port != 'unknown':
                proto_info += f":{port}"
            proto_info += ")"
        
        # Log the event with better formatting
        if action.lower() == 'blocked':
            self._append_log(f"🚫 BLOCKED: {target}{proto_info}")
        elif action.lower() == 'allowed':
            self._append_log(f"✅ ALLOWED: {target}{proto_info}")
        else:
            self._append_log(f"📡 {target}{proto_info}")
    
    def _on_whitelist_synced(self, data: Dict):
        """Handle whitelist sync event."""
        success = data.get('success', False)
        
        if success:
            self._cards['sync'].set_value("Just now")
            self._cards['sync'].set_color("#00ff88")
            self._append_log("[SYNC] Whitelist synchronized successfully")
        else:
            self._cards['sync'].set_value("Failed")
            self._cards['sync'].set_color("#ff4444")
            self._append_log("[SYNC] Whitelist sync failed")
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def _append_log(self, message: str):
        """Append message to activity log."""
        if not self._log_textbox:
            return
        
        try:
            from shared.time_utils import now_vietnam
            timestamp = now_vietnam().strftime("%H:%M:%S")
        except ImportError:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
        
        self._log_textbox.configure(state="normal")
        self._log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self._log_textbox.see("end")  # Auto-scroll to bottom
        self._log_textbox.configure(state="disabled")
    
    def _append_shutdown_banner(self):
        """Append a formatted shutdown banner to log."""
        if not self._log_textbox:
            return
        
        try:
            from shared.time_utils import now_vietnam, uptime_string
            timestamp = now_vietnam().strftime("%H:%M:%S %d/%m/%Y")
            uptime = uptime_string()
        except ImportError:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            uptime = "N/A"
        
        # Get stats before shutdown
        stats = {}
        if self._controller:
            stats = self._controller.get_stats()
        
        packets = stats.get('packets_captured', 0)
        domains = stats.get('domains_count', 0) + stats.get('patterns_count', 0)
        
        self._log_textbox.configure(state="normal")
        
        # Banner lines
        banner = [
            "",
            "╔" + "═" * 48 + "╗",
            "║" + "  🛑 AGENT SHUTDOWN INITIATED".center(48) + "║",
            "╠" + "═" * 48 + "╣",
            f"║  📅 Time: {timestamp}".ljust(49) + "║",
            f"║  ⏱️  Uptime: {uptime}".ljust(49) + "║",
            f"║  📦 Packets: {packets}".ljust(49) + "║",
            f"║  📋 Domains: {domains}".ljust(49) + "║",
            "╠" + "═" * 48 + "╣",
            "║  ⏳ Cleaning up resources...".ljust(49) + "║",
            "╚" + "═" * 48 + "╝",
            ""
        ]
        
        for line in banner:
            self._log_textbox.insert("end", f"{line}\n")
        
        self._log_textbox.see("end")
        self._log_textbox.configure(state="disabled")
    
    def _append_startup_banner(self):
        """Append a formatted startup banner to log."""
        if not self._log_textbox:
            return
        
        try:
            from shared.time_utils import now_vietnam
            timestamp = now_vietnam().strftime("%H:%M:%S %d/%m/%Y")
        except ImportError:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        
        # Get agent info
        hostname = "Unknown"
        mode = "Monitor"
        try:
            import socket
            hostname = socket.gethostname()
            if self._controller:
                info = self._controller.get_agent_info()
                mode = info.get('firewall_mode', 'monitor').title()
        except:
            pass
        
        self._log_textbox.configure(state="normal")
        
        # Banner lines  
        banner = [
            "",
            "╔" + "═" * 48 + "╗",
            "║" + "  🚀 FIREWALL AGENT STARTING".center(48) + "║",
            "╠" + "═" * 48 + "╣",
            f"║  📅 Time: {timestamp}".ljust(49) + "║",
            f"║  💻 Host: {hostname[:35]}".ljust(49) + "║",
            f"║  🔥 Mode: {mode}".ljust(49) + "║",
            "╠" + "═" * 48 + "╣",
            "║  ⚙️  Initializing components...".ljust(49) + "║",
            "║  📡 Connecting to server...".ljust(49) + "║",
            "║  🛡️  Setting up firewall rules...".ljust(49) + "║",
            "╚" + "═" * 48 + "╝",
            ""
        ]
        
        for line in banner:
            self._log_textbox.insert("end", f"{line}\n")
        
        self._log_textbox.see("end")
        self._log_textbox.configure(state="disabled")
    
    def _append_stopped_banner(self):
        """Append a formatted stopped confirmation banner."""
        if not self._log_textbox:
            return
        
        try:
            from shared.time_utils import now_vietnam
            timestamp = now_vietnam().strftime("%H:%M:%S %d/%m/%Y")
        except ImportError:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        
        self._log_textbox.configure(state="normal")
        
        banner = [
            "",
            "┌" + "─" * 48 + "┐",
            "│" + "  ✅ AGENT STOPPED SUCCESSFULLY".center(48) + "│",
            "├" + "─" * 48 + "┤",
            f"│  📅 Time: {timestamp}".ljust(49) + "│",
            "│  🧹 Resources cleaned up".ljust(49) + "│",
            "│  🔓 Firewall rules cleared".ljust(49) + "│",
            "└" + "─" * 48 + "┘",
            ""
        ]
        
        for line in banner:
            self._log_textbox.insert("end", f"{line}\n")
        
        self._log_textbox.see("end")
        self._log_textbox.configure(state="disabled")
    
    def _clear_log(self):
        """Clear activity log."""
        if not self._log_textbox:
            return
        
        self._log_textbox.configure(state="normal")
        self._log_textbox.delete("1.0", "end")
        self._log_textbox.configure(state="disabled")
        self._append_log("Log cleared.")
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds to readable string."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def destroy(self):
        """Clean up when view is destroyed."""
        self._stop_periodic_updates()
        self._is_visible = False
        super().destroy()
