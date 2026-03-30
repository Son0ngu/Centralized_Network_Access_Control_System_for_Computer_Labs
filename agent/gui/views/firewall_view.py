import customtkinter as ctk
import threading
from typing import Dict, List, Optional

from .components.data_table import DataTable


class FirewallView(ctk.CTkFrame):
    """Firewall view for managing firewall rules."""
    
    # Refresh interval in ms
    REFRESH_INTERVAL = 5000
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._firewall_manager = None
        self._refresh_job = None
        self._setup_ui()
        
        # Start periodic refresh
        self._start_refresh()
    
    def set_firewall_manager(self, manager):
        """Set reference to FirewallManager."""
        self._firewall_manager = manager
        self._refresh_rules()
    
    def _setup_ui(self):
        """Setup firewall UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        
        # Title
        title = ctk.CTkLabel(
            header,
            text="🔥 Firewall Rules",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#0077cc"
        )
        title.pack(side="left", anchor="w")

        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=100,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#d0d0d8",
            hover_color="#c0c0c8",
            text_color="#1a1a2e",
            command=self._refresh_rules
        )
        refresh_btn.pack(side="right")

        # Stats section
        stats_frame = ctk.CTkFrame(self, fg_color="#e8e8ed", corner_radius=12, height=80)
        stats_frame.pack(fill="x", pady=(0, 15))
        stats_frame.pack_propagate(False)

        stats_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_inner.pack(fill="both", expand=True, padx=20, pady=15)

        # Policy status
        self._policy_label = ctk.CTkLabel(
            stats_inner,
            text="🛡 Policy: Loading...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1a1a2e"
        )
        self._policy_label.pack(side="left")

        # Rule count
        self._rule_count_label = ctk.CTkLabel(
            stats_inner,
            text="Rules: --",
            font=ctk.CTkFont(size=14),
            text_color="#4a4a5a"
        )
        self._rule_count_label.pack(side="left", padx=(30, 0))

        # Mode
        self._mode_label = ctk.CTkLabel(
            stats_inner,
            text="⚙️ Mode: --",
            font=ctk.CTkFont(size=14),
            text_color="#4a4a5a"
        )
        self._mode_label.pack(side="left", padx=(30, 0))

        # Table section
        table_frame = ctk.CTkFrame(self, fg_color="#e8e8ed", corner_radius=12)
        table_frame.pack(fill="both", expand=True)
        
        # DataTable for rules
        columns = [
            {"key": "ip", "title": "IP Address", "width": 200, "weight": 2},
            {"key": "direction", "title": "Direction", "width": 100, "weight": 1},
            {"key": "action", "title": "Action", "width": 100, "weight": 1},
            {"key": "protocol", "title": "Protocol", "width": 100, "weight": 1},
            {"key": "rule_name", "title": "Rule Name", "width": 250, "weight": 2},
        ]
        
        self._table = DataTable(
            table_frame,
            columns=columns,
            on_delete=None,  # Don't allow deletion from UI
            show_actions=False
        )
        self._table.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        status_frame.pack(fill="x", pady=(10, 0))
        status_frame.pack_propagate(False)
        
        self._status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="#00ff88"
        )
        self._status_label.pack(side="left")
    
    def _start_refresh(self):
        """Start periodic refresh."""
        self._refresh_rules()
        self._refresh_job = self.after(self.REFRESH_INTERVAL, self._start_refresh)
    
    def _refresh_rules(self):
        """Refresh firewall rules display."""
        try:
            self._status_label.configure(text="Refreshing...", text_color="#ffa500")
            
            # Run in background
            threading.Thread(target=self._load_rules, daemon=True).start()
            
        except Exception as e:
            self._status_label.configure(text=f"Error: {e}", text_color="#ff4444")
    
    def _load_rules(self):
        """Load firewall rules (runs in background thread)."""
        try:
            rules = []
            policy_status = "Unknown"
            mode = "Unknown"
            
            if self._firewall_manager:
                # Get rules from manager
                allowed_ips = self._firewall_manager.allowed_ips
                rule_prefix = self._firewall_manager.rule_prefix
                
                for ip in allowed_ips:
                    rules.append({
                        "ip": ip,
                        "direction": "Outbound",
                        "action": "Allow",
                        "protocol": "Any",
                        "rule_name": f"{rule_prefix}_Allow_{ip.replace('.', '_')}"
                    })
                
                # Get policy status
                if hasattr(self._firewall_manager, 'policy_manager'):
                    if self._firewall_manager.policy_manager.default_deny_enabled:
                        policy_status = "Default Deny (Active)"
                    else:
                        policy_status = "Default Allow"
                
                # Get mode
                if self._firewall_manager.whitelist_mode_active:
                    mode = "Whitelist Only"
                else:
                    mode = "Monitor"
            else:
                # Try to get rules from netsh directly
                rules = self._get_rules_from_netsh()
                policy_status = self._get_policy_from_netsh()
            
            # Update UI in main thread
            self.after(0, lambda: self._update_ui(rules, policy_status, mode))
            
        except Exception as e:
            self.after(0, lambda: self._status_label.configure(
                text=f"Load error: {e}", 
                text_color="#ff4444"
            ))
    
    def _get_rules_from_netsh(self) -> List[Dict]:
        """Get firewall rules using netsh."""
        import subprocess
        
        rules = []
        try:
            # Get rules with our prefix
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", 
                 "name=all", "dir=out", "status=enabled"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                current_rule = {}
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if not line:
                        if current_rule.get('rule_name', '').startswith('FirewallController'):
                            rules.append(current_rule)
                        current_rule = {}
                    elif ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if 'rule name' in key:
                            current_rule['rule_name'] = value
                        elif 'direction' in key:
                            current_rule['direction'] = value
                        elif 'action' in key:
                            current_rule['action'] = value
                        elif 'protocol' in key:
                            current_rule['protocol'] = value
                        elif 'remoteip' in key:
                            current_rule['ip'] = value
                
                # Add last rule
                if current_rule.get('rule_name', '').startswith('FirewallController'):
                    rules.append(current_rule)
                    
        except Exception as e:
            pass
        
        return rules
    
    def _get_policy_from_netsh(self) -> str:
        """Get firewall policy using netsh."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "currentprofile"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Outbound' in line and 'Block' in line:
                        return "Default Deny (Active)"
                    elif 'Outbound' in line and 'Allow' in line:
                        return "Default Allow"
                        
        except Exception:
            pass
        
        return "Unknown"
    
    def _update_ui(self, rules: List[Dict], policy_status: str, mode: str):
        """Update UI with rules data."""
        try:
            # Update policy label
            if "Deny" in policy_status or "Block" in policy_status:
                self._policy_label.configure(
                    text=f"🛡 Policy: {policy_status}",
                    text_color="#00ff88"
                )
            else:
                self._policy_label.configure(
                    text=f"🛡 Policy: {policy_status}",
                    text_color="#ffa500"
                )
            
            # Update rule count
            self._rule_count_label.configure(text=f"Rules: {len(rules)}")
            
            # Update mode
            if mode == "Whitelist Only":
                self._mode_label.configure(text=f"⚙️ Mode: {mode}", text_color="#00ff88")
            else:
                self._mode_label.configure(text=f"⚙️ Mode: {mode}", text_color="#aaaaaa")
            
            # Update table
            self._table.set_data(rules)
            
            # Update status
            self._status_label.configure(
                text=f"Loaded {len(rules)} rules",
                text_color="#00ff88"
            )
            
        except Exception as e:
            self._status_label.configure(text=f"UI error: {e}", text_color="#ff4444")
    
    def destroy(self):
        """Clean up when view is destroyed."""
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        super().destroy()
