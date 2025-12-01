"""
Data Table Component - Reusable table widget for displaying data.
Vietnam ONLY - Using customtkinter.

Features:
- Scrollable table with headers
- Action buttons per row (Delete, Edit)
- Sortable columns
- Search/filter support
"""

import customtkinter as ctk
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime


class DataTable(ctk.CTkFrame):
    """
    A reusable data table widget.
    
    Usage:
        table = DataTable(
            parent,
            columns=[
                {"key": "ip", "title": "IP Address", "width": 150},
                {"key": "date", "title": "Added Date", "width": 120},
                {"key": "status", "title": "Status", "width": 80},
            ],
            on_delete=lambda row: print(f"Delete {row}")
        )
        table.set_data([
            {"ip": "192.168.1.1", "date": "2024-01-01", "status": "Active"},
        ])
    """
    
    def __init__(
        self,
        parent,
        columns: List[Dict[str, Any]],
        on_delete: Optional[Callable[[Dict], None]] = None,
        on_edit: Optional[Callable[[Dict], None]] = None,
        show_actions: bool = True,
        row_height: int = 40,
        **kwargs
    ):
        super().__init__(parent, fg_color="#1a1a2e", corner_radius=12, **kwargs)
        
        self._columns = columns
        self._on_delete = on_delete
        self._on_edit = on_edit
        self._show_actions = show_actions
        self._row_height = row_height
        self._data: List[Dict] = []
        self._row_widgets: List[List[ctk.CTkFrame]] = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup table UI."""
        # Header
        self._header_frame = ctk.CTkFrame(self, fg_color="#0f0f1a", corner_radius=0)
        self._header_frame.pack(fill="x", padx=2, pady=(2, 0))
        
        self._create_header()
        
        # Scrollable body
        self._body_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self._body_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        
        # Configure body grid with weight from column config
        for i, col in enumerate(self._columns):
            weight = col.get("weight", 1)
            minsize = col.get("width", 100)
            self._body_frame.grid_columnconfigure(i, weight=weight, minsize=minsize, uniform="col")
        
        if self._show_actions:
            self._body_frame.grid_columnconfigure(len(self._columns), weight=0, minsize=100)
    
    def _create_header(self):
        """Create table header row."""
        for i, col in enumerate(self._columns):
            weight = col.get("weight", 1)
            minsize = col.get("width", 100)
            self._header_frame.grid_columnconfigure(i, weight=weight, minsize=minsize, uniform="col")
            
            header_cell = ctk.CTkLabel(
                self._header_frame,
                text=col.get("title", col.get("key", "")),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#00d4ff",
                anchor="w"
            )
            header_cell.grid(row=0, column=i, padx=10, pady=8, sticky="ew")
        
        if self._show_actions:
            self._header_frame.grid_columnconfigure(len(self._columns), weight=0, minsize=100)
            action_header = ctk.CTkLabel(
                self._header_frame,
                text="Actions",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#00d4ff",
                anchor="center"
            )
            action_header.grid(row=0, column=len(self._columns), padx=10, pady=8)
    
    def set_data(self, data: List[Dict]):
        """Set table data and refresh display."""
        self._data = data if data else []
        # Use after_idle to avoid Tkinter callback conflicts
        try:
            self.after_idle(self._refresh_table)
        except Exception:
            self._refresh_table()
    
    def add_row(self, row_data: Dict):
        """Add a single row to the table."""
        self._data.append(row_data)
        try:
            self.after_idle(self._refresh_table)
        except Exception:
            self._refresh_table()
    
    def remove_row(self, index: int):
        """Remove row at index."""
        if 0 <= index < len(self._data):
            self._data.pop(index)
            try:
                self.after_idle(self._refresh_table)
            except Exception:
                self._refresh_table()
    
    def remove_row_by_key(self, key: str, value: Any):
        """Remove row where key matches value."""
        self._data = [row for row in self._data if row.get(key) != value]
        self._refresh_table()
    
    def get_data(self) -> List[Dict]:
        """Get current table data."""
        return self._data.copy()
    
    def clear(self):
        """Clear all table data."""
        self._data = []
        self._refresh_table()
    
    def _refresh_table(self):
        """Refresh table display."""
        # Clear existing rows safely
        try:
            # Get all children first
            children = list(self._body_frame.winfo_children())
            for widget in children:
                try:
                    if widget.winfo_exists():
                        widget.destroy()
                except Exception:
                    pass  # Widget already destroyed
        except Exception:
            pass
        
        self._row_widgets = []
        
        # Create rows
        for row_idx, row_data in enumerate(self._data):
            self._create_row(row_idx, row_data)
    
    def _create_row(self, row_idx: int, row_data: Dict):
        """Create a single table row."""
        row_widgets = []
        
        # Alternate row colors
        bg_color = "#1a1a2e" if row_idx % 2 == 0 else "#22223a"
        
        # Data cells - place directly in body_frame for proper grid alignment
        for col_idx, col in enumerate(self._columns):
            key = col.get("key", "")
            value = row_data.get(key, "")
            
            # Format value based on type
            display_value = self._format_value(value, col.get("type"))
            
            # Color based on status
            text_color = "#ffffff"
            if key == "status":
                if str(value).lower() in ["active", "allowed", "online"]:
                    text_color = "#00ff88"
                elif str(value).lower() in ["blocked", "denied", "offline"]:
                    text_color = "#ff4444"
                elif str(value).lower() in ["pending", "syncing"]:
                    text_color = "#ffa500"
            
            # Cell frame for background color
            cell_frame = ctk.CTkFrame(self._body_frame, fg_color=bg_color, corner_radius=0, height=self._row_height)
            cell_frame.grid(row=row_idx, column=col_idx, sticky="nsew", pady=(0, 1))
            cell_frame.grid_propagate(False)
            
            cell = ctk.CTkLabel(
                cell_frame,
                text=display_value,
                font=ctk.CTkFont(size=12),
                text_color=text_color,
                anchor="w"
            )
            cell.pack(fill="both", expand=True, padx=10, pady=8)
            row_widgets.append(cell)
        
        # Action buttons
        if self._show_actions:
            action_cell = ctk.CTkFrame(self._body_frame, fg_color=bg_color, corner_radius=0, height=self._row_height)
            action_cell.grid(row=row_idx, column=len(self._columns), sticky="nsew", pady=(0, 1))
            action_cell.grid_propagate(False)
            
            action_frame = ctk.CTkFrame(action_cell, fg_color="transparent")
            action_frame.pack(expand=True)
            
            if self._on_delete:
                delete_btn = ctk.CTkButton(
                    action_frame,
                    text="🗑️",
                    width=30,
                    height=28,
                    font=ctk.CTkFont(size=12),
                    fg_color="#ff4444",
                    hover_color="#cc3333",
                    command=lambda rd=row_data: self._handle_delete(rd)
                )
                delete_btn.pack(side="left", padx=2)
            
            if self._on_edit:
                edit_btn = ctk.CTkButton(
                    action_frame,
                    text="✏️",
                    width=30,
                    height=28,
                    font=ctk.CTkFont(size=12),
                    fg_color="#ffa500",
                    hover_color="#cc8400",
                    command=lambda rd=row_data: self._handle_edit(rd)
                )
                edit_btn.pack(side="left", padx=2)
        
        self._row_widgets.append(row_widgets)
    
    def _format_value(self, value: Any, value_type: Optional[str] = None) -> str:
        """Format value for display."""
        if value is None:
            return "-"
        
        if value_type == "datetime" and isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
        
        if value_type == "date" and isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d")
        
        return str(value)
    
    def _handle_delete(self, row_data: Dict):
        """Handle delete button click."""
        if self._on_delete:
            self._on_delete(row_data)
    
    def _handle_edit(self, row_data: Dict):
        """Handle edit button click."""
        if self._on_edit:
            self._on_edit(row_data)
    
    def get_row_count(self) -> int:
        """Get number of rows."""
        return len(self._data)


class SearchableDataTable(ctk.CTkFrame):
    """
    DataTable with integrated search functionality.
    """
    
    def __init__(
        self,
        parent,
        columns: List[Dict[str, Any]],
        search_keys: Optional[List[str]] = None,
        **kwargs
    ):
        # Extract table kwargs
        on_delete = kwargs.pop("on_delete", None)
        on_edit = kwargs.pop("on_edit", None)
        show_actions = kwargs.pop("show_actions", True)
        
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self._columns = columns
        self._search_keys = search_keys or [col["key"] for col in columns]
        self._full_data: List[Dict] = []
        
        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 10))
        
        self._search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search...",
            width=300,
            height=35,
            corner_radius=8,
            fg_color="#1a1a2e"
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<KeyRelease>", self._on_search)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            width=60,
            height=35,
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._clear_search
        )
        clear_btn.pack(side="left", padx=(10, 0))
        
        # Count label
        self._count_label = ctk.CTkLabel(
            search_frame,
            text="0 items",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self._count_label.pack(side="right")
        
        # Data table
        self._table = DataTable(
            self,
            columns=columns,
            on_delete=on_delete,
            on_edit=on_edit,
            show_actions=show_actions
        )
        self._table.pack(fill="both", expand=True)
    
    def set_data(self, data: List[Dict]):
        """Set table data."""
        self._full_data = data
        self._apply_filter()
    
    def add_row(self, row_data: Dict):
        """Add a row."""
        self._full_data.append(row_data)
        self._apply_filter()
    
    def remove_row_by_key(self, key: str, value: Any):
        """Remove row by key."""
        self._full_data = [row for row in self._full_data if row.get(key) != value]
        self._apply_filter()
    
    def get_data(self) -> List[Dict]:
        """Get all data."""
        return self._full_data.copy()
    
    def clear(self):
        """Clear all data."""
        self._full_data = []
        self._apply_filter()
    
    def _on_search(self, event=None):
        """Handle search input."""
        self._apply_filter()
    
    def _clear_search(self):
        """Clear search and show all."""
        self._search_entry.delete(0, "end")
        self._apply_filter()
    
    def _apply_filter(self):
        """Apply search filter to data."""
        query = self._search_entry.get().lower().strip()
        
        if not query:
            filtered_data = self._full_data
        else:
            filtered_data = []
            for row in self._full_data:
                for key in self._search_keys:
                    value = str(row.get(key, "")).lower()
                    if query in value:
                        filtered_data.append(row)
                        break
        
        self._table.set_data(filtered_data)
        self._update_count(len(filtered_data), len(self._full_data))
    
    def _update_count(self, shown: int, total: int):
        """Update count label."""
        if shown == total:
            self._count_label.configure(text=f"{total} items")
        else:
            self._count_label.configure(text=f"{shown} of {total} items")
