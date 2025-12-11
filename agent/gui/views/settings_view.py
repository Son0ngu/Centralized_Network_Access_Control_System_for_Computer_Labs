import customtkinter as ctk
import json
from pathlib import Path


class SettingsView(ctk.CTkFrame):
    """Settings view for agent configuration."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._config_path = self._find_config_path()
        self._config = self._load_config()
        self._entries = {}  # Store entry references
        self._setup_ui()
    
    def _find_config_path(self) -> Path:
        """Find the config file path."""
        possible_paths = [
            Path("agent_config.json"),
            Path("agent/agent_config.json"),
            Path(__file__).parent.parent.parent / "agent_config.json",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return Path("agent_config.json")
    
    def _load_config(self) -> dict:
        """Load configuration from file."""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        return {}
    
    def _save_config(self):
        """Save configuration to file."""
        try:
            # Update config from entries
            if 'api_key' in self._entries:
                if 'auth' not in self._config:
                    self._config['auth'] = {}
                self._config['auth']['api_key'] = self._entries['api_key'].get()
            
            if 'server_url' in self._entries:
                if 'server' not in self._config:
                    self._config['server'] = {}
                self._config['server']['url'] = self._entries['server_url'].get()
            
            if 'heartbeat_interval' in self._entries:
                if 'heartbeat' not in self._config:
                    self._config['heartbeat'] = {}
                try:
                    self._config['heartbeat']['interval'] = int(self._entries['heartbeat_interval'].get())
                except ValueError:
                    pass
            
            if 'sync_interval' in self._entries:
                if 'whitelist' not in self._config:
                    self._config['whitelist'] = {}
                try:
                    self._config['whitelist']['update_interval'] = int(self._entries['sync_interval'].get())
                except ValueError:
                    pass
            
            # Save to file
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            
            self._show_save_success()
        except Exception as e:
            self._show_save_error(str(e))
    
    def _show_save_success(self):
        """Show save success message."""
        if hasattr(self, '_status_label'):
            self._status_label.configure(text="Settings saved successfully!", text_color="#00ff88")
            self.after(3000, lambda: self._status_label.configure(text=""))
    
    def _show_save_error(self, error: str):
        """Show save error message."""
        if hasattr(self, '_status_label'):
            self._status_label.configure(text=f"Error: {error}", text_color="#ff4444")
    
    def _setup_ui(self):
        """Setup settings UI."""
        # Title
        title = ctk.CTkLabel(
            self,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(anchor="w", pady=(0, 30))
        
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        
        # ========================================
        # AUTHENTICATION SECTION (IMPORTANT!)
        # ========================================
        self._create_section(content, "🔑 Authentication")
        
        auth_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        auth_frame.pack(fill="x", pady=(0, 20))
        
        # API Key input
        api_key_row = ctk.CTkFrame(auth_frame, fg_color="transparent")
        api_key_row.pack(fill="x", padx=20, pady=15)
        
        api_key_label = ctk.CTkLabel(
            api_key_row, 
            text="API Key:", 
            width=150, 
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        api_key_label.pack(side="left")
        
        current_api_key = self._config.get('auth', {}).get('api_key', '')
        self._entries['api_key'] = ctk.CTkEntry(
            api_key_row,
            width=400,
            height=38,
            corner_radius=6,
            fg_color="#0f0f1a",
            placeholder_text="Paste your API key here (fwc_...)",
            show="•" if current_api_key else ""
        )
        self._entries['api_key'].insert(0, current_api_key)
        self._entries['api_key'].pack(side="left", padx=(0, 10))
        
        # Show/Hide button
        self._show_key = False
        show_btn = ctk.CTkButton(
            api_key_row,
            text="👁",
            width=40,
            height=38,
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._toggle_api_key_visibility
        )
        show_btn.pack(side="left")
        
        # Help text
        help_text = ctk.CTkLabel(
            auth_frame,
            text="💡 Get your API key from the server Web UI: /api-keys",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        help_text.pack(anchor="w", padx=20, pady=(0, 15))
        
        # ========================================
        # SERVER SETTINGS
        # ========================================
        self._create_section(content, "🌐 Server Connection")
        
        server_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        server_frame.pack(fill="x", pady=(0, 20))
        
        # Server URL
        current_url = self._config.get('server', {}).get('url', 'http://localhost:5000')
        self._entries['server_url'] = self._create_input_row(
            server_frame, "Server URL:", current_url, 0
        )
        
        # Heartbeat interval
        current_heartbeat = str(self._config.get('heartbeat', {}).get('interval', 30))
        self._entries['heartbeat_interval'] = self._create_input_row(
            server_frame, "Heartbeat Interval (s):", current_heartbeat, 1
        )
        
        # Sync interval
        current_sync = str(self._config.get('whitelist', {}).get('update_interval', 60))
        self._entries['sync_interval'] = self._create_input_row(
            server_frame, "Sync Interval (s):", current_sync, 2
        )
        
        # ========================================
        # AGENT SETTINGS
        # ========================================
        self._create_section(content, "🤖 Agent Configuration")
        
        agent_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        agent_frame.pack(fill="x", pady=(0, 20))
        
        # Agent ID (readonly)
        import socket
        hostname = socket.gethostname()
        self._create_input_row(agent_frame, "Hostname:", hostname, 0, readonly=True)
        
        # Log level
        log_row = ctk.CTkFrame(agent_frame, fg_color="transparent")
        log_row.pack(fill="x", padx=20, pady=10)
        
        log_label = ctk.CTkLabel(log_row, text="Log Level:", width=150, anchor="w")
        log_label.pack(side="left")
        
        current_log_level = self._config.get('logging', {}).get('level', 'INFO')
        self._log_level_var = ctk.StringVar(value=current_log_level)
        log_menu = ctk.CTkOptionMenu(
            log_row,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self._log_level_var,
            width=200,
            fg_color="#0f0f1a",
            button_color="#00d4ff"
        )
        log_menu.pack(side="left")
        
        # (Network settings removed in UI)
        
        # ========================================
        # SAVE BUTTON & STATUS
        # ========================================
        save_frame = ctk.CTkFrame(content, fg_color="transparent")
        save_frame.pack(fill="x", pady=30)
        
        save_btn = ctk.CTkButton(
            save_frame,
            text="💾 Save Settings",
            width=200,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#00d4ff",
            hover_color="#00b8d4",
            text_color="#000000",
            command=self._save_config
        )
        save_btn.pack()
        
        # Status label
        self._status_label = ctk.CTkLabel(
            save_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#666666"
        )
        self._status_label.pack(pady=(15, 0))
        
        # Config file path info
        path_label = ctk.CTkLabel(
            content,
            text=f"📁 Config file: {self._config_path.absolute()}",
            font=ctk.CTkFont(size=11),
            text_color="#555555"
        )
        path_label.pack(pady=10)
    
    def _toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        self._show_key = not self._show_key
        if 'api_key' in self._entries:
            current_value = self._entries['api_key'].get()
            self._entries['api_key'].configure(show="" if self._show_key else "•")
    
    def _create_section(self, parent, title: str):
        """Create a section header."""
        label = ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff"
        )
        label.pack(anchor="w", pady=(20, 10))
    
    def _create_input_row(self, parent, label: str, default: str, row: int, readonly: bool = False):
        """Create an input row with label and entry. Returns the entry widget."""
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=10)
        
        label_widget = ctk.CTkLabel(row_frame, text=label, width=150, anchor="w")
        label_widget.pack(side="left")
        
        entry = ctk.CTkEntry(
            row_frame,
            width=300,
            height=35,
            corner_radius=6,
            fg_color="#0f0f1a" if not readonly else "#2d2d44"
        )
        entry.insert(0, default)
        if readonly:
            entry.configure(state="disabled")
        entry.pack(side="left")
        
        return entry
