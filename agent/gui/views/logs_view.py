"""
Logs View - View agent activity logs with terminal-style console.
Vietnam ONLY - Using customtkinter.

Features:
- Real-time log display
- Terminal-style appearance (black bg, green text)
- Log level filtering
- Search functionality
- Export capability
"""

import customtkinter as ctk
import logging
from typing import Optional

from .components.log_console import LogConsole, GUILogHandler


class LogsView(ctk.CTkFrame):
    """Logs view for displaying agent activity."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self._log_handler: Optional[GUILogHandler] = None
        
        self._setup_ui()
        self._setup_logging()
        self._add_welcome_logs()
    
    def _setup_ui(self):
        """Setup logs UI."""
        # Header
        self._create_header()
        
        # Controls
        self._create_controls()
        
        # Log Console
        self._create_console()
        
        # Status bar
        self._create_status_bar()
    
    def _create_header(self):
        """Create header with title."""
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        
        # Title
        title = ctk.CTkLabel(
            header,
            text="Activity Logs",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(side="left", anchor="w")
    
    def _create_controls(self):
        """Create control buttons and filters."""
        controls = ctk.CTkFrame(self, fg_color="transparent", height=45)
        controls.pack(fill="x", pady=(0, 15))
        controls.pack_propagate(False)
        
        # Filter dropdown
        filter_label = ctk.CTkLabel(
            controls, 
            text="Level:", 
            font=ctk.CTkFont(size=13)
        )
        filter_label.pack(side="left", padx=(0, 8))
        
        self._filter_var = ctk.StringVar(value="ALL")
        filter_menu = ctk.CTkOptionMenu(
            controls,
            values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self._filter_var,
            width=100,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#1a1a2e",
            button_color="#00d4ff",
            button_hover_color="#00b8d4",
            command=self._on_filter_change
        )
        filter_menu.pack(side="left", padx=(0, 15))
        
        # Search
        self._search_entry = ctk.CTkEntry(
            controls,
            placeholder_text="Search logs...",
            width=250,
            height=32,
            font=ctk.CTkFont(size=12),
            corner_radius=6,
            border_color="#3d3d54",
            fg_color="#0a0a12"
        )
        self._search_entry.pack(side="left", padx=(0, 15))
        
        # Export button
        export_btn = ctk.CTkButton(
            controls,
            text="📤 Export",
            width=90,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._on_export
        )
        export_btn.pack(side="right")
        
        # Clear button
        clear_btn = ctk.CTkButton(
            controls,
            text="🗑️ Clear",
            width=80,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#ff4444",
            hover_color="#cc3333",
            text_color="#ffffff",
            command=self._on_clear
        )
        clear_btn.pack(side="right", padx=(0, 10))
    
    def _create_console(self):
        """Create terminal-style log console."""
        # Console container
        console_frame = ctk.CTkFrame(self, fg_color="#0a0a12", corner_radius=12)
        console_frame.pack(fill="both", expand=True)
        
        # Log Console widget
        self._log_console = LogConsole(
            console_frame,
            max_lines=2000,
            font_family="Consolas",
            font_size=11,
            show_toolbar=True
        )
        self._log_console.pack(fill="both", expand=True, padx=5, pady=5)
    
    def _create_status_bar(self):
        """Create status bar."""
        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=25)
        status_frame.pack(fill="x", pady=(10, 0))
        status_frame.pack_propagate(False)
        
        self._status_label = ctk.CTkLabel(
            status_frame,
            text="📟 Log console ready",
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        )
        self._status_label.pack(side="left")
    
    def _setup_logging(self):
        """Setup logging handler to capture logs."""
        # Create handler that sends to console
        self._log_handler = GUILogHandler(self._log_console)
        self._log_handler.setLevel(logging.DEBUG)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)
        
        # Also add to specific loggers
        loggers_to_capture = [
            "agent",
            "core.agent",
            "firewall",
            "whitelist",
            "capture",
            "heartbeat",
            "gui",
        ]
        
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            if self._log_handler not in logger.handlers:
                logger.addHandler(self._log_handler)
    
    def _add_welcome_logs(self):
        """Add welcome/sample logs."""
        self._log_console.append_log("=" * 60, "INFO")
        self._log_console.append_log("  Firewall Agent Log Console", "INFO")
        self._log_console.append_log("  Vietnam ONLY - Enterprise Security", "INFO")
        self._log_console.append_log("=" * 60, "INFO")
        self._log_console.append_log("", "INFO")
        self._log_console.append_log("Log console initialized and ready", "INFO")
        self._log_console.append_log("Capturing logs from all agent modules", "DEBUG")
    
    def _on_filter_change(self, value: str):
        """Handle filter change."""
        self._status_label.configure(text=f"📟 Filter: {value}")
    
    def _on_clear(self):
        """Handle clear button."""
        self._log_console.clear()
    
    def _on_export(self):
        """Handle export button."""
        # TODO: Implement export functionality
        self._log_console.append_log("Export feature coming soon...", "INFO")
        self._status_label.configure(text="📟 Export not yet implemented")
    
    def append_log(self, message: str, level: str = "INFO"):
        """
        Append a log message to console.
        
        Args:
            message: Log message
            level: Log level
        """
        self._log_console.append_log(message, level)
    
    def get_log_handler(self) -> Optional[GUILogHandler]:
        """Get the logging handler for external use."""
        return self._log_handler
    
    def cleanup(self):
        """Cleanup logging handler."""
        if self._log_handler:
            # Remove from root logger
            root_logger = logging.getLogger()
            if self._log_handler in root_logger.handlers:
                root_logger.removeHandler(self._log_handler)
