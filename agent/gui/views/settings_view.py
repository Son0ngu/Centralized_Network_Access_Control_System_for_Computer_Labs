"""
Settings View - Agent configuration settings.
Vietnam ONLY - Using customtkinter.
"""

import customtkinter as ctk


class SettingsView(ctk.CTkFrame):
    """Settings view for agent configuration."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._setup_ui()
    
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
        
        # Server Settings Section
        self._create_section(content, "🌐 Server Connection")
        
        server_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        server_frame.pack(fill="x", pady=(0, 20))
        
        # Server URL
        self._create_input_row(server_frame, "Server URL:", "https://firewall-controller.onrender.com", 0)
        
        # Heartbeat interval
        self._create_input_row(server_frame, "Heartbeat Interval (s):", "30", 1)
        
        # Sync interval
        self._create_input_row(server_frame, "Sync Interval (s):", "60", 2)
        
        # Agent Settings Section
        self._create_section(content, "🤖 Agent Configuration")
        
        agent_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        agent_frame.pack(fill="x", pady=(0, 20))
        
        # Agent ID
        self._create_input_row(agent_frame, "Agent ID:", "agent-001", 0, readonly=True)
        
        # Log level
        log_row = ctk.CTkFrame(agent_frame, fg_color="transparent")
        log_row.pack(fill="x", padx=20, pady=10)
        
        log_label = ctk.CTkLabel(log_row, text="Log Level:", width=150, anchor="w")
        log_label.pack(side="left")
        
        self._log_level_var = ctk.StringVar(value="INFO")
        log_menu = ctk.CTkOptionMenu(
            log_row,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self._log_level_var,
            width=200,
            fg_color="#0f0f1a",
            button_color="#00d4ff"
        )
        log_menu.pack(side="left")
        
        # Network Settings Section
        self._create_section(content, "🔌 Network Settings")
        
        network_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="#1a1a2e")
        network_frame.pack(fill="x", pady=(0, 20))
        
        # Auto-detect IP
        auto_ip_row = ctk.CTkFrame(network_frame, fg_color="transparent")
        auto_ip_row.pack(fill="x", padx=20, pady=10)
        
        auto_ip_label = ctk.CTkLabel(auto_ip_row, text="Auto-detect Public IP:", width=150, anchor="w")
        auto_ip_label.pack(side="left")
        
        self._auto_ip_switch = ctk.CTkSwitch(auto_ip_row, text="", onvalue=True, offvalue=False)
        self._auto_ip_switch.select()
        self._auto_ip_switch.pack(side="left")
        
        # Enable Npcap auto-install
        npcap_row = ctk.CTkFrame(network_frame, fg_color="transparent")
        npcap_row.pack(fill="x", padx=20, pady=10)
        
        npcap_label = ctk.CTkLabel(npcap_row, text="Auto-install Npcap:", width=150, anchor="w")
        npcap_label.pack(side="left")
        
        self._npcap_switch = ctk.CTkSwitch(npcap_row, text="", onvalue=True, offvalue=False)
        self._npcap_switch.select()
        self._npcap_switch.pack(side="left")
        
        # Save button
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
            text_color="#000000"
        )
        save_btn.pack()
        
        # Hello message
        hello = ctk.CTkLabel(
            content,
            text="Hello Settings! ⚙️",
            font=ctk.CTkFont(size=14),
            text_color="#666666"
        )
        hello.pack(pady=20)
    
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
        """Create an input row with label and entry."""
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
