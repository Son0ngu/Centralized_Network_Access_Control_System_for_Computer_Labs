import customtkinter as ctk
import json
from pathlib import Path
from tkinter import messagebox
from ..controllers.agent_controller import AgentController


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
        """Load configuration from encrypted or plaintext file."""
        try:
            from config.crypto import decrypt_config, ENCRYPTED_EXT
            enc_path = self._config_path.with_suffix(self._config_path.suffix + ENCRYPTED_EXT)
            if enc_path.exists():
                config = decrypt_config(self._config_path)
                if config is not None:
                    return config
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
                url_value = self._entries['server_url'].get()
                self._config['server']['url'] = url_value
                # Keep urls list in sync so runtime respects the chosen endpoint
                self._config['server']['urls'] = [url_value]
            
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
            
            # Save encrypted
            from config.crypto import encrypt_config
            encrypt_config(self._config, self._config_path)
            
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
            text_color="#0077cc"
        )
        title.pack(anchor="w", pady=(0, 30))
        
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        
        # ========================================
        # AUTHENTICATION SECTION (IMPORTANT!)
        # ========================================
        self._create_section(content, "🔑 Authentication")
        
        auth_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#e8e8ed")
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
            fg_color="#ffffff",
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
            fg_color="#d0d0d8",
            hover_color="#c0c0c8",
            text_color="#1a1a2e",
            command=self._toggle_api_key_visibility
        )
        show_btn.pack(side="left")
        
        # Help text
        help_text = ctk.CTkLabel(
            auth_frame,
            text="💡 Get your API key from the server Web UI: /api-keys",
            font=ctk.CTkFont(size=11),
            text_color="#6a6a7a"
        )
        help_text.pack(anchor="w", padx=20, pady=(0, 15))
        
        # ========================================
        # SERVER SETTINGS
        # ========================================
        self._create_section(content, "🌐 Server Connection")
        
        server_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#e8e8ed")
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
        
        agent_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#e8e8ed")
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
            fg_color="#ffffff",
            button_color="#0077cc",
            text_color="#1a1a2e"
        )
        log_menu.pack(side="left")
        
        # ========================================
        # FIREWALL BACKUP & RESTORE
        # ========================================
        self._create_section(content, "🔥 Firewall Backup & Restore")

        fw_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#e8e8ed")
        fw_frame.pack(fill="x", pady=(0, 20))

        # Description
        ctk.CTkLabel(
            fw_frame,
            text="Firewall state is automatically saved before SAINT applies changes.\n"
                 "Use the Restore button to revert firewall to the pre-SAINT state.",
            font=ctk.CTkFont(size=12),
            text_color="#4a4a5a",
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=20, pady=(15, 10))

        # Snapshot file path (readonly)
        fw_config = self._config.get('firewall', {}).get('backup', {})
        backup_path = fw_config.get('path', 'profiles/backup.wfw')
        self._create_input_row(fw_frame, "Snapshot File:", backup_path, 0, readonly=True)

        # Restore button
        restore_row = ctk.CTkFrame(fw_frame, fg_color="transparent")
        restore_row.pack(fill="x", padx=20, pady=(5, 15))

        restore_btn = ctk.CTkButton(
            restore_row,
            text="♻️ Restore Firewall",
            width=160,
            height=34,
            fg_color="#0077cc",
            hover_color="#005fa3",
            text_color="#ffffff",
            command=self._manual_restore
        )
        restore_btn.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            restore_row,
            text="Restore firewall to the state before SAINT started",
            font=ctk.CTkFont(size=11),
            text_color="#6a6a7a"
        ).pack(side="left")
        
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
            fg_color="#0077cc",
            hover_color="#00b8d4",
            text_color="#ffffff",
            command=self._save_config
        )
        save_btn.pack()
        
        # Status label
        self._status_label = ctk.CTkLabel(
            save_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#6a6a7a"
        )
        self._status_label.pack(pady=(15, 0))
        
        # Config file path info
        path_label = ctk.CTkLabel(
            content,
            text=f"📁 Config file: {self._config_path.absolute()}",
            font=ctk.CTkFont(size=11),
            text_color="#6a6a7a"
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
            text_color="#1a1a2e"
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
            fg_color="#ffffff" if not readonly else "#e8e8ed",
            text_color="#1a1a2e"
        )
        entry.insert(0, default)
        if readonly:
            entry.configure(state="disabled")
        entry.pack(side="left")
        
        return entry

    def _manual_restore(self):
        """Restore firewall to pre-SAINT state from snapshot file."""
        try:
            fw_config = self._config.get('firewall', {}).get('backup', {})
            backup_path = fw_config.get('path', 'profiles/backup.wfw')

            file_path = Path(backup_path)
            if not file_path.exists():
                self._show_save_error(f"No snapshot found: {file_path}\nAgent must have run at least once.")
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)

            timestamp = snapshot.get('timestamp', 'unknown')

            confirm = messagebox.askyesno(
                "Restore Firewall",
                f"Restore firewall to the state saved at:\n{timestamp}\n\n"
                "This will revert all changes made by SAINT.\n\nContinue?",
                icon="question"
            )
            if not confirm:
                return

            # Try via agent if running
            ctrl = AgentController()
            if ctrl.is_running and ctrl._agent and ctrl._agent.firewall:
                if ctrl._agent.firewall.restore_snapshot(backup_path):
                    self._show_status("Firewall restored to pre-SAINT state", "#00cc6f")
                    return

            # Standalone restore via netsh
            from firewall.utils import FirewallUtils

            policies = snapshot.get('policies', {})
            for profile, action in policies.items():
                if action not in ("allow", "block"):
                    continue
                policy_arg = "blockinbound,blockoutbound" if action == "block" else "blockinbound,allowoutbound"
                FirewallUtils.run_netsh_command([
                    "advfirewall", "set", f"{profile}profile",
                    "firewallpolicy", policy_arg
                ])

            # Clear SAINT rules
            rule_prefix = self._config.get('firewall', {}).get('rule_prefix', 'FirewallController')
            self._clear_saint_rules(rule_prefix)

            self._show_status("Firewall restored to pre-SAINT state", "#00cc6f")

        except Exception as e:
            self._show_save_error(f"Restore failed: {e}")

    def _clear_saint_rules(self, rule_prefix: str) -> int:
        """Remove all SAINT firewall rules. Returns count of removed rules."""
        from firewall.utils import FirewallUtils

        result = FirewallUtils.run_netsh_command([
            "advfirewall", "firewall", "show", "rule", "name=all"
        ], timeout=60)

        removed = 0
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.strip().startswith("Rule Name:"):
                    rule_name = line.strip()[10:].strip()
                    if rule_name.startswith(rule_prefix):
                        del_r = FirewallUtils.run_netsh_command([
                            "advfirewall", "firewall", "delete", "rule",
                            f"name={rule_name}"
                        ])
                        if del_r.returncode == 0:
                            removed += 1
        return removed

    def _show_status(self, text: str, color: str):
        """Show status message."""
        if hasattr(self, '_status_label'):
            self._status_label.configure(text=text, text_color=color)
            self.after(5000, lambda: self._status_label.configure(text=""))
