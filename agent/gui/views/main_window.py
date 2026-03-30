import customtkinter as ctk
from typing import Dict, Optional

from ..styles import get_theme, WidgetStyles
from ..resources import ICONS, MENU_ICONS


class MainWindow(ctk.CTkFrame):
    """Main window with sidebar menu and content area."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self._theme = get_theme()
        self._current_view = None
        self._views: Dict[str, ctk.CTkFrame] = {}
        self._menu_buttons: Dict[str, ctk.CTkButton] = {}
        
        self._setup_ui()
        self._create_views()
        
        # Show dashboard by default
        self._show_view("dashboard")
    
    def _setup_ui(self):
        """Setup main UI layout with theme."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # === Sidebar ===
        self._sidebar = ctk.CTkFrame(
            self, 
            width=self._theme.spacing.sidebar_width, 
            corner_radius=0, 
            fg_color=self._theme.colors.sidebar_bg
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        
        # Logo/Title with brand styling
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", pady=(25, 10), padx=15)
        
        logo_icon = ctk.CTkLabel(
            logo_frame,
            text=f"{ICONS.shield}",
            font=self._theme.font("4xl"),
            text_color=self._theme.colors.accent_primary
        )
        logo_icon.pack()
        
        self._logo_label = ctk.CTkLabel(
            logo_frame,
            text="SAINT",
            font=self._theme.font("lg", "bold"),
            text_color=self._theme.colors.accent_primary
        )
        self._logo_label.pack(pady=(5, 0))
        
        # Subtitle
        subtitle = ctk.CTkLabel(
            logo_frame,
            text="Security Agent Integrated Network Tool",
            font=self._theme.font("xs"),
            text_color=self._theme.colors.text_muted
        )
        subtitle.pack()
        
        # Divider
        divider = ctk.CTkFrame(
            self._sidebar, 
            height=1, 
            fg_color=self._theme.colors.border_default
        )
        divider.pack(fill="x", padx=20, pady=(15, 20))
        
        # Menu items with icons
        menu_items = [
            ("dashboard", f"{ICONS.dashboard}", "Dashboard"),
            ("firewall", f"{ICONS.firewall}", "Firewall"),
            ("whitelist", f"{ICONS.whitelist}", "Whitelist"),
            ("logs", f"{ICONS.logs}", "Logs"),
            ("settings", f"{ICONS.settings}", "Settings")
        ]
        
        for view_name, icon, label in menu_items:
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {icon}  {label}",
                font=self._theme.font("md"),
                height=45,
                corner_radius=self._theme.borders.radius_md,
                fg_color="transparent",
                text_color=self._theme.colors.text_secondary,
                hover_color=self._theme.colors.sidebar_item_hover,
                anchor="w",
                command=lambda v=view_name: self._show_view(v)
            )
            btn.pack(fill="x", padx=12, pady=3)
            self._menu_buttons[view_name] = btn
        
        # Spacer
        spacer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        
        # Version info
        version_label = ctk.CTkLabel(
            self._sidebar,
            text="SAINT v1.0.0 • Vietnam Only",
            font=self._theme.font("xs"),
            text_color=self._theme.colors.text_disabled
        )
        version_label.pack(pady=(0, 20))
        
        # === Content Area ===
        self._content_area = ctk.CTkFrame(
            self, 
            corner_radius=0, 
            fg_color=self._theme.colors.bg_secondary
        )
        self._content_area.grid(row=0, column=1, sticky="nsew")
        self._content_area.grid_columnconfigure(0, weight=1)
        self._content_area.grid_rowconfigure(0, weight=1)
    
    def _create_views(self):
        """Register view classes for lazy loading — views are created on first access."""
        from .dashboard_view import DashboardView
        from .firewall_view import FirewallView
        from .whitelist_view import WhitelistView
        from .logs_view import LogsView
        from .settings_view import SettingsView

        self._view_classes = {
            "dashboard": DashboardView,
            "firewall": FirewallView,
            "whitelist": WhitelistView,
            "logs": LogsView,
            "settings": SettingsView,
        }

        # Connect agent_ready signal to update views
        from ..controllers.agent_controller import AgentController
        agent_ctrl = AgentController()
        agent_ctrl.signals.connect('whitelist_synced', self._on_agent_ready)
        agent_ctrl.signals.connect('status_changed', self._on_status_changed)

    def _get_view(self, view_name: str) -> Optional[ctk.CTkFrame]:
        """Get or lazily create a view by name."""
        if view_name not in self._views:
            cls = self._view_classes.get(view_name)
            if cls is None:
                return None
            self._views[view_name] = cls(self._content_area)
        return self._views[view_name]
    
    def _on_status_changed(self, data: Dict):
        """Handle agent status change - connect firewall manager."""
        status = data.get('status', '')
        if status == 'running':
            # Connect firewall manager to firewall view
            try:
                from ..controllers.agent_controller import AgentController
                agent_ctrl = AgentController()
                if agent_ctrl._agent and agent_ctrl._agent.firewall:
                    if "firewall" in self._views:
                        self._views["firewall"].set_firewall_manager(agent_ctrl._agent.firewall)
            except Exception as e:
                pass  # Firewall may not be available
    
    def _on_agent_ready(self, data: Dict):
        """Handle agent ready event - notify whitelist view."""
        if data.get('agent_ready') and "whitelist" in self._views:
            whitelist_view = self._views["whitelist"]
            if hasattr(whitelist_view, 'set_agent_ready'):
                whitelist_view.set_agent_ready(True)
    
    def _show_view(self, view_name: str):
        """Switch to specified view (lazy-created on first access)."""
        view = self._get_view(view_name)
        if view is None:
            return

        # Hide current view
        if self._current_view and self._current_view in self._views:
            self._views[self._current_view].grid_forget()

        # Show new view
        view.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self._current_view = view_name
        
        # Update menu button states
        self._update_menu_states(view_name)
    
    def _update_menu_states(self, active_view: str):
        """Update menu button visual states."""
        for view_name, btn in self._menu_buttons.items():
            if view_name == active_view:
                btn.configure(
                    fg_color=self._theme.colors.sidebar_item_active,
                    text_color=self._theme.colors.accent_primary
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=self._theme.colors.text_secondary
                )
