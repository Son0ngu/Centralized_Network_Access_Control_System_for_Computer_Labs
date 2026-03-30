import customtkinter as ctk
import logging
import queue
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime


class LogConsole(ctk.CTkFrame):

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
        super().__init__(parent, fg_color="#e8e8ed", corner_radius=12, **kwargs)
        
        self._max_lines = max_lines
        self._font_family = font_family
        self._font_size = font_size
        self._show_toolbar = show_toolbar
        self._line_count = 0
        self._paused = False
        self._filter_level = "ALL"
        self._history: List[Dict[str, str]] = []
        
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
            fg_color="#ffffff",
            text_color="#1a1a2e",
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
            text_color="#1a1a2e"
        )
        title.pack(side="left")
        
        # Line count
        self._line_count_label = ctk.CTkLabel(
            toolbar,
            text="0 lines",
            font=ctk.CTkFont(size=11),
            text_color="#6a6a7a"
        )
        self._line_count_label.pack(side="left", padx=(15, 0))
        
        # Pause button
        self._pause_btn = ctk.CTkButton(
            toolbar,
            text="⏸️ Pause",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#d0d0d8",
            hover_color="#c0c0c8",
            text_color="#1a1a2e",
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
            fg_color="#d0d0d8",
            button_color="#c0c0c8",
            button_hover_color="#b0b0b8",
            text_color="#1a1a2e",
            command=self._on_level_change
        )
        level_menu.pack(side="right", padx=(0, 5))
    
    def _toggle_pause(self):
        """Toggle pause state."""
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="▶️ Resume", fg_color="#ffa500", text_color="#1a1a2e")
        else:
            self._pause_btn.configure(text="⏸️ Pause", fg_color="#d0d0d8", text_color="#1a1a2e")
    
    def _on_level_change(self, value: str):
        """Handle level filter change."""
        self.set_filter_level(value)

    def set_filter_level(self, level: str):
        """Update the active filter level and redraw existing logs."""
        self._filter_level = level.upper()
        self._rebuild_from_history()
    
    def _passes_filter(self, level: str) -> bool:
        """Return True if the level should be shown under the current filter."""
        if self._filter_level == "ALL":
            return True
        level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level in level_order and self._filter_level in level_order:
            return level_order.index(level) >= level_order.index(self._filter_level)
        return True

    def _write_line(self, log_entry: Dict):
        """Render a single log entry into the console without mutating history."""
        level = log_entry.get("level", "INFO")
        timestamp = log_entry.get("timestamp", "")
        message = log_entry.get("message", "")

        # Color currently unused by CTkTextbox but retained for future styling
        self.LEVEL_COLORS.get(level, "#00ff88")

        formatted_line = f"[{timestamp}] [{level:8}] {message}\n"
        self._console.insert("end", formatted_line)
        self._line_count += 1

    def _rebuild_from_history(self):
        """Re-render the console from stored history applying the current filter."""
        self._console.configure(state="normal")
        self._console.delete("1.0", "end")
        self._line_count = 0

        for entry in self._history:
            if self._passes_filter(entry.get("level", "INFO")):
                self._write_line(entry)

        self._console.see("end")
        self._console.configure(state="disabled")

        if hasattr(self, '_line_count_label'):
            self._line_count_label.configure(text=f"{self._line_count} lines")
    
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
        timestamp = log_entry.get("timestamp", "")
        message = log_entry.get("message", "")

        # Always retain full history for export (independent of UI filter)
        self._history.append({
            "timestamp": timestamp,
            "level": level,
            "message": message,
        })
        if len(self._history) > self._max_lines:
            self._history.pop(0)
        
        # Apply level filter
        if not self._passes_filter(level):
            return
        
        # Append to console
        self._console.configure(state="normal")
        self._write_line(log_entry)
        
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
        self._history = []
        
        if hasattr(self, '_line_count_label'):
            self._line_count_label.configure(text="0 lines")
        
        self.append_log("Console cleared", "INFO")

    def get_history(self) -> List[Dict[str, str]]:
        """Return a copy of the log history for export."""
        return list(self._history)
    
    def write(self, message: str):
        """Write method for compatibility with logging handlers."""
        if message.strip():
            self.append_log(message.strip(), "INFO")
    
    def flush(self):
        """Flush method for compatibility with logging handlers."""
        pass


class GUILogHandler(logging.Handler):

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
