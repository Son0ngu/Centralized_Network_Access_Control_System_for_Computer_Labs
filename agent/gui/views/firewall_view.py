"""
Firewall View - Firewall rules management.
Vietnam ONLY - Using customtkinter.
"""

import customtkinter as ctk


class FirewallView(ctk.CTkFrame):
    """Firewall view for managing firewall rules."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup firewall UI."""
        # Title
        title = ctk.CTkLabel(
            self,
            text="🔥 Firewall Rules",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(anchor="w", pady=(0, 30))
        
        # Controls frame
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 20))
        
        # Mode selector
        mode_label = ctk.CTkLabel(controls, text="Mode:", font=ctk.CTkFont(size=14))
        mode_label.pack(side="left", padx=(0, 10))
        
        self._mode_var = ctk.StringVar(value="monitor")
        mode_menu = ctk.CTkOptionMenu(
            controls,
            values=["monitor", "enforce", "disabled"],
            variable=self._mode_var,
            width=150,
            fg_color="#1a1a2e",
            button_color="#00d4ff",
            button_hover_color="#00b8d4"
        )
        mode_menu.pack(side="left", padx=(0, 30))
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            controls,
            text="🔄 Refresh",
            width=100,
            fg_color="#1a1a2e",
            hover_color="#2d2d44"
        )
        refresh_btn.pack(side="left")
        
        # Content area
        content = ctk.CTkFrame(self, corner_radius=12, fg_color="#1a1a2e")
        content.pack(fill="both", expand=True)
        
        placeholder = ctk.CTkLabel(
            content,
            text="Hello Firewall! 🔥\n\nFirewall rules will be displayed here.",
            font=ctk.CTkFont(size=18),
            text_color="#888888"
        )
        placeholder.pack(expand=True)
