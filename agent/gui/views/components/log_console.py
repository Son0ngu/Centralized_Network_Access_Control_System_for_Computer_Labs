"""
Log Console Component - Terminal-style log viewer.
Vietnam ONLY - Using customtkinter.

Features:
- Terminal-like appearance (black bg, green text)
- Auto-scroll to bottom
- Log level coloring
- Search/filter capability
- Custom logging.Handler integration
"""

import customtkinter as ctk
import logging
import queue
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime


class LogConsole(ctk.CTkFrame):
    """
    Terminal-style log console widget.
    
    Features:
    - Hacker/admin style (black background, green text)
    - Auto-scroll to bottom
    - Color-coded log levels
    - Max lines limit to prevent memory issues
    """
    
    # Log level colors
    LEVEL_COLORS = {
        "DEBUG": "#888888",
        "INFO": "#00ff88",
        "WARNING": "#ffa500",
        "ERROR": "#ff4444",
        "CRITICAL": "#ff00ff",
        "BLOCK": "#ff4444",
        "ALLOW": "#00ff88",
        "PACKET": "#00d4ff",
        "SYNC": "#9966ff",
        "STARTUP": "#00d4ff",
        "SHUTDOWN": "#ff6b6b",
        "SUCCESS": "#00ff88",
    }
    
    # Special event icons
    LEVEL_ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
        "BLOCK": "🚫",
        "ALLOW": "✅",
        "PACKET": "📡",
        "SYNC": "🔄",
        "STARTUP": "🚀",
        "SHUTDOWN": "🛑",
        "SUCCESS": "✅",
    }
    
    def __init__(
        self,
        parent,
        max_lines: int = 1000,
        font_family: str = "Consolas",
        font_size: int = 11,
        show_toolbar: bool = True,
        **kwargs
    ):
        super().__init__(parent, fg_color="#0a0a12", corner_radius=12, **kwargs)
        
        self._max_lines = max_lines
        self._font_family = font_family
        self._font_size = font_size
        self._show_toolbar = show_toolbar
        self._line_count = 0
        self._paused = False
        self._filter_level = "ALL"
        
        # Message queue for thread-safe logging
        self._log_queue: queue.Queue = queue.Queue()
        
        self._setup_ui()
        self._start_queue_processor()
    
    def _setup_ui(self):
        """Setup console UI."""
        if self._show_toolbar:
            self._create_toolbar()
        
        # Console text area
        self._console = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family=self._font_family, size=self._font_size),
            fg_color="#0a0a12",
            text_color="#00ff88",
            corner_radius=8,
            wrap="none"
        )
        self._console.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self._console.configure(state="disabled")
        
        # Configure text tags for colors
        # Note: customtkinter doesn't support tags like tkinter.Text
        # We'll use a simpler approach with formatted text
    
    def _create_toolbar(self):
        """Create toolbar with controls."""
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        toolbar.pack_propagate(False)
        
        # Title
        title = ctk.CTkLabel(
            toolbar,
            text="📟 Console",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#00ff88"
        )
        title.pack(side="left")
        
        # Line count
        self._line_count_label = ctk.CTkLabel(
            toolbar,
            text="0 lines",
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        )
        self._line_count_label.pack(side="left", padx=(15, 0))
        
        # Clear button
        clear_btn = ctk.CTkButton(
            toolbar,
            text="🗑️ Clear",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self.clear
        )
        clear_btn.pack(side="right")
        
        # Pause button
        self._pause_btn = ctk.CTkButton(
            toolbar,
            text="⏸️ Pause",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._toggle_pause
        )
        self._pause_btn.pack(side="right", padx=(0, 5))
        
        # Level filter
        self._level_var = ctk.StringVar(value="ALL")
        level_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self._level_var,
            width=90,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#2d2d44",
            button_color="#3d3d54",
            button_hover_color="#4d4d64",
            command=self._on_level_change
        )
        level_menu.pack(side="right", padx=(0, 5))
    
    def _toggle_pause(self):
        """Toggle pause state."""
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="▶️ Resume", fg_color="#ffa500")
        else:
            self._pause_btn.configure(text="⏸️ Pause", fg_color="#2d2d44")
    
    def _on_level_change(self, value: str):
        """Handle level filter change."""
        self._filter_level = value
    
    def _start_queue_processor(self):
        """Start background queue processor."""
        def process():
            try:
                while True:
                    msg = self._log_queue.get_nowait()
                    if not self._paused:
                        self._append_log_internal(msg)
            except queue.Empty:
                pass
            
            # Schedule next check
            self.after(50, process)
        
        self.after(50, process)
    
    def append_log(
        self,
        message: str,
        level: str = "INFO",
        timestamp: Optional[str] = None
    ):
        """
        Append a log message (thread-safe).
        
        Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            try:
                from shared.time_utils import now_vietnam
                timestamp = now_vietnam().strftime("%H:%M:%S")
            except ImportError:
                timestamp = datetime.now().strftime("%H:%M:%S")
        
        log_entry = {
            "timestamp": timestamp,
            "level": level.upper(),
            "message": message
        }
        self._log_queue.put(log_entry)
    
    def _append_log_internal(self, log_entry: Dict):
        """Internal method to append log to console."""
        level = log_entry.get("level", "INFO")
        
        # Apply level filter
        if self._filter_level != "ALL":
            level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if level in level_order:
                filter_idx = level_order.index(self._filter_level)
                log_idx = level_order.index(level)
                if log_idx < filter_idx:
                    return
        
        timestamp = log_entry.get("timestamp", "")
        message = log_entry.get("message", "")
        
        # Format line
        color = self.LEVEL_COLORS.get(level, "#00ff88")
        formatted_line = f"[{timestamp}] [{level:8}] {message}\n"
        
        # Append to console
        self._console.configure(state="normal")
        self._console.insert("end", formatted_line)
        self._line_count += 1
        
        # Trim if exceeds max lines
        if self._line_count > self._max_lines:
            self._console.delete("1.0", "2.0")
            self._line_count -= 1
        
        # Auto-scroll
        self._console.see("end")
        self._console.configure(state="disabled")
        
        # Update line count label
        if hasattr(self, '_line_count_label'):
            self._line_count_label.configure(text=f"{self._line_count} lines")
    
    def clear(self):
        """Clear console."""
        self._console.configure(state="normal")
        self._console.delete("1.0", "end")
        self._console.configure(state="disabled")
        self._line_count = 0
        
        if hasattr(self, '_line_count_label'):
            self._line_count_label.configure(text="0 lines")
        
        self.append_log("Console cleared", "INFO")
    
    def write(self, message: str):
        """Write method for compatibility with logging handlers."""
        if message.strip():
            self.append_log(message.strip(), "INFO")
    
    def flush(self):
        """Flush method for compatibility with logging handlers."""
        pass


class GUILogHandler(logging.Handler):
    """
    Custom logging.Handler that sends logs to LogConsole.
    
    Usage:
        console = LogConsole(parent)
        handler = GUILogHandler(console)
        logging.getLogger().addHandler(handler)
    """
    
    def __init__(self, log_console: LogConsole):
        super().__init__()
        self._console = log_console
        
        # Set formatter
        self.setFormatter(logging.Formatter('%(message)s'))
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            msg = self.format(record)
            level = record.levelname
            
            # Get timestamp from record
            timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            
            self._console.append_log(msg, level, timestamp)
            
        except Exception:
            self.handleError(record)


class QueueLogHandler(logging.Handler):
    """
    Logging handler that puts logs in a queue.
    Useful for thread-safe communication with GUI.
    """
    
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self._queue = log_queue
        self.setFormatter(logging.Formatter('%(message)s'))
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record to queue."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name,
                "module": record.module,
            }
            self._queue.put(log_entry)
        except Exception:
            self.handleError(record)
