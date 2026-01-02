"""
DNS View
---------
Display DNS Proxy statistics and query information.
Replaces FirewallView with DNS-centric information.
"""

import customtkinter as ctk
import threading
from typing import Dict, List, Optional
from datetime import datetime

from .components.data_table import DataTable


class DNSView(ctk.CTkFrame):
    """DNS Proxy view for monitoring DNS queries and statistics."""
    
    # Refresh interval in ms
    REFRESH_INTERVAL = 2000
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._dns_proxy = None
        self._refresh_job = None
        self._recent_queries: List[Dict] = []
        self._setup_ui()
        
        # Start periodic refresh
        self._start_refresh()
    
    def set_dns_proxy(self, dns_proxy):
        """Set reference to DNS Proxy (server or orchestrator)."""
        self._dns_proxy = dns_proxy
        self._refresh_stats()
    
    def _setup_ui(self):
        """Setup DNS view UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        
        # Title
        title = ctk.CTkLabel(
            header,
            text="🌐 DNS Proxy",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(side="left", anchor="w")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=100,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#2d2d44",
            hover_color="#3d3d54",
            command=self._refresh_stats
        )
        refresh_btn.pack(side="right")
        
        # === Stats Cards Section ===
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 15))
        
        # Configure grid for 5 cards
        for i in range(5):
            stats_frame.grid_columnconfigure(i, weight=1, minsize=160)
        
        # Card 1: Server Status
        self._status_card = self._create_stat_card(
            stats_frame, 0, "🔌 Status", "Stopped", "#ff4444"
        )
        
        # Card 2: Total Queries
        self._queries_card = self._create_stat_card(
            stats_frame, 1, "📊 Queries", "0", "#00d4ff"
        )
        
        # Card 3: Block Rate
        self._block_card = self._create_stat_card(
            stats_frame, 2, "🚫 Blocked", "0%", "#ff6b6b"
        )
        
        # Card 4: Cache Hit Rate
        self._cache_card = self._create_stat_card(
            stats_frame, 3, "💾 Cache Hit", "0%", "#00ff88"
        )
        
        # Card 5: Allowed
        self._allowed_card = self._create_stat_card(
            stats_frame, 4, "✅ Allowed", "0", "#4ecdc4"
        )
        
        # === Detailed Stats Section ===
        detail_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12, height=100)
        detail_frame.pack(fill="x", pady=(0, 15))
        detail_frame.pack_propagate(False)
        
        detail_inner = ctk.CTkFrame(detail_frame, fg_color="transparent")
        detail_inner.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Row 1: UDP/TCP stats
        row1 = ctk.CTkFrame(detail_inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))
        
        self._udp_label = ctk.CTkLabel(
            row1, text="UDP Queries: 0", font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self._udp_label.pack(side="left")
        
        self._tcp_label = ctk.CTkLabel(
            row1, text="TCP Queries: 0", font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self._tcp_label.pack(side="left", padx=(30, 0))
        
        self._upstream_label = ctk.CTkLabel(
            row1, text="Upstream: 0", font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self._upstream_label.pack(side="left", padx=(30, 0))
        
        self._errors_label = ctk.CTkLabel(
            row1, text="Errors: 0", font=ctk.CTkFont(size=13),
            text_color="#ff6b6b"
        )
        self._errors_label.pack(side="left", padx=(30, 0))
        
        # Row 2: Cache stats
        row2 = ctk.CTkFrame(detail_inner, fg_color="transparent")
        row2.pack(fill="x")
        
        self._cache_size_label = ctk.CTkLabel(
            row2, text="Cache Size: 0", font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self._cache_size_label.pack(side="left")
        
        self._cache_hits_label = ctk.CTkLabel(
            row2, text="Cache Hits: 0", font=ctk.CTkFont(size=13),
            text_color="#00ff88"
        )
        self._cache_hits_label.pack(side="left", padx=(30, 0))
        
        self._cache_misses_label = ctk.CTkLabel(
            row2, text="Cache Misses: 0", font=ctk.CTkFont(size=13),
            text_color="#ffa500"
        )
        self._cache_misses_label.pack(side="left", padx=(30, 0))
        
        # === Recent Queries Table ===
        table_header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        table_header.pack(fill="x", pady=(10, 5))
        table_header.pack_propagate(False)
        
        table_title = ctk.CTkLabel(
            table_header,
            text="📝 Query Statistics",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        table_title.pack(side="left")
        
        table_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=12)
        table_frame.pack(fill="both", expand=True)
        
        # Table with DNS-specific columns
        columns = [
            {"key": "metric", "title": "Metric", "width": 250, "weight": 2},
            {"key": "value", "title": "Value", "width": 150, "weight": 1},
            {"key": "description", "title": "Description", "width": 350, "weight": 3},
        ]
        
        self._table = DataTable(
            table_frame,
            columns=columns,
            on_delete=None,
            show_actions=False
        )
        self._table.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        status_frame.pack(fill="x", pady=(10, 0))
        status_frame.pack_propagate(False)
        
        self._status_label = ctk.CTkLabel(
            status_frame,
            text="Waiting for DNS Proxy...",
            font=ctk.CTkFont(size=12),
            text_color="#ffa500"
        )
        self._status_label.pack(side="left")
        
        self._last_update_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#666666"
        )
        self._last_update_label.pack(side="right")
    
    def _create_stat_card(self, parent, column: int, title: str, value: str, color: str) -> Dict:
        """Create a statistics card."""
        card = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=12, height=90)
        card.grid(row=0, column=column, padx=5, pady=5, sticky="nsew")
        card.pack_propagate(False)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        
        title_label = ctk.CTkLabel(
            inner, text=title, font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        title_label.pack(anchor="w")
        
        value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=color,
            anchor="w",
            wraplength=200
        )
        value_label.pack(anchor="w", pady=(5, 0), fill="x")
        
        return {"card": card, "title": title_label, "value": value_label, "color": color}
    
    def _start_refresh(self):
        """Start periodic refresh."""
        self._refresh_stats()
        self._refresh_job = self.after(self.REFRESH_INTERVAL, self._start_refresh)
    
    def _refresh_stats(self):
        """Refresh DNS statistics display."""
        try:
            self._status_label.configure(text="Refreshing...", text_color="#ffa500")
            threading.Thread(target=self._load_stats, daemon=True).start()
        except Exception as e:
            self._status_label.configure(text=f"Error: {e}", text_color="#ff4444")
    
    def _load_stats(self):
        """Load DNS stats (runs in background thread)."""
        try:
            stats = {}
            is_running = False
            
            if self._dns_proxy:
                # Check if it's a DNSProxyServer or DNSProxyOrchestrator
                if hasattr(self._dns_proxy, 'get_stats'):
                    stats = self._dns_proxy.get_stats()
                    is_running = True
                elif hasattr(self._dns_proxy, '_server') and self._dns_proxy._server:
                    stats = self._dns_proxy._server.get_stats()
                    is_running = self._dns_proxy._server.is_running()
            
            # Update UI in main thread
            self.after(0, lambda: self._update_ui(stats, is_running))
            
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))
    
    def _update_ui(self, stats: Dict, is_running: bool):
        """Update UI with stats (must run in main thread)."""
        try:
            # Update status card
            if is_running:
                self._status_card["value"].configure(text="Running", text_color="#00ff88")
            else:
                self._status_card["value"].configure(text="Stopped", text_color="#ff4444")
            
            # Extract stats
            server_stats = stats.get("server", {})
            handler_stats = stats.get("handler", {})
            cache_stats = stats.get("cache", {})
            
            # Total queries
            total_queries = handler_stats.get("total_queries", 0)
            self._queries_card["value"].configure(text=str(total_queries))
            
            # Block rate
            block_rate = handler_stats.get("block_rate_percent", 0)
            blocked = handler_stats.get("blocked", 0)
            self._block_card["value"].configure(text=f"{block_rate}%")
            
            # Cache hit rate
            cache_hits = cache_stats.get("hits", handler_stats.get("cache_hits", 0))
            cache_misses = cache_stats.get("misses", 0)
            cache_total = cache_hits + cache_misses
            cache_hit_rate = round(cache_hits / max(1, cache_total) * 100, 1) if cache_total > 0 else 0
            self._cache_card["value"].configure(text=f"{cache_hit_rate}%")
            
            # Allowed queries
            allowed = handler_stats.get("allowed", 0)
            self._allowed_card["value"].configure(text=str(allowed))
            
            # Detailed stats
            udp_queries = server_stats.get("udp_queries", 0)
            tcp_queries = server_stats.get("tcp_queries", 0)
            upstream_queries = handler_stats.get("upstream_queries", 0)
            errors = handler_stats.get("errors", 0) + server_stats.get("udp_errors", 0) + server_stats.get("tcp_errors", 0)
            
            self._udp_label.configure(text=f"UDP Queries: {udp_queries}")
            self._tcp_label.configure(text=f"TCP Queries: {tcp_queries}")
            self._upstream_label.configure(text=f"Upstream: {upstream_queries}")
            self._errors_label.configure(text=f"Errors: {errors}")
            
            # Cache details
            cache_size = cache_stats.get("size", cache_stats.get("entries", 0))
            self._cache_size_label.configure(text=f"Cache Size: {cache_size}")
            self._cache_hits_label.configure(text=f"Cache Hits: {cache_hits}")
            self._cache_misses_label.configure(text=f"Cache Misses: {cache_misses}")
            
            # Build table data with all metrics
            table_data = self._build_metrics_table(stats, handler_stats, cache_stats, server_stats)
            self._table.set_data(table_data)
            
            # Update status
            self._status_label.configure(
                text="Ready" if is_running else "DNS Proxy not running",
                text_color="#00ff88" if is_running else "#ffa500"
            )
            self._last_update_label.configure(
                text=f"Last update: {datetime.now().strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            self._status_label.configure(text=f"UI Error: {e}", text_color="#ff4444")
    
    def _build_metrics_table(self, stats: Dict, handler: Dict, cache: Dict, server: Dict) -> List[Dict]:
        """Build metrics table data."""
        metrics = []
        
        # Handler metrics
        metrics.append({
            "metric": "📊 Total Queries",
            "value": str(handler.get("total_queries", 0)),
            "description": "Total DNS queries processed by the proxy"
        })
        metrics.append({
            "metric": "✅ Allowed Queries",
            "value": str(handler.get("allowed", 0)),
            "description": "Queries allowed by whitelist"
        })
        metrics.append({
            "metric": "🚫 Blocked Queries",
            "value": str(handler.get("blocked", 0)),
            "description": "Queries blocked (NXDOMAIN returned)"
        })
        metrics.append({
            "metric": "📈 Block Rate",
            "value": f"{handler.get('block_rate_percent', 0)}%",
            "description": "Percentage of queries blocked"
        })
        
        # Cache metrics
        metrics.append({
            "metric": "💾 Cache Hits",
            "value": str(cache.get("hits", handler.get("cache_hits", 0))),
            "description": "Queries served from cache"
        })
        metrics.append({
            "metric": "📤 Cache Misses",
            "value": str(cache.get("misses", 0)),
            "description": "Queries forwarded to upstream"
        })
        metrics.append({
            "metric": "🗃️ Cache Size",
            "value": str(cache.get("size", cache.get("entries", 0))),
            "description": "Number of cached DNS entries"
        })
        
        # Server metrics
        metrics.append({
            "metric": "🔵 UDP Queries",
            "value": str(server.get("udp_queries", 0)),
            "description": "Queries received over UDP"
        })
        metrics.append({
            "metric": "🟢 TCP Queries",
            "value": str(server.get("tcp_queries", 0)),
            "description": "Queries received over TCP"
        })
        
        # Upstream metrics
        metrics.append({
            "metric": "🌍 Upstream Queries",
            "value": str(handler.get("upstream_queries", 0)),
            "description": "Queries forwarded to upstream DNS"
        })
        
        # Firewall sync
        firewall_stats = stats.get("firewall_sync", {})
        metrics.append({
            "metric": "🔥 Firewall Syncs",
            "value": str(handler.get("firewall_syncs", firewall_stats.get("total_syncs", 0))),
            "description": "IPs synced to DNS-only mode (no Windows Firewall)"
        })
        
        # Errors
        total_errors = (
            handler.get("errors", 0) + 
            server.get("udp_errors", 0) + 
            server.get("tcp_errors", 0)
        )
        metrics.append({
            "metric": "⚠️ Errors",
            "value": str(total_errors),
            "description": "Total errors during query processing"
        })
        
        return metrics
    
    def _show_error(self, error: str):
        """Show error message."""
        self._status_label.configure(text=f"Error: {error}", text_color="#ff4444")
    
    def destroy(self):
        """Clean up on destroy."""
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        super().destroy()
