from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class IconSet:
    """
    Collection of icons used throughout the application.
    Using emoji/unicode for cross-platform compatibility.
    """
    
    # === Navigation Icons ===
    dashboard: str = "📊"
    firewall: str = "🛡"
    whitelist: str = "📋"
    logs: str = "📝"
    settings: str = "⚙️"
    
    # === Status Icons ===
    online: str = "🟢"
    offline: str = "🔴"
    warning: str = "🟡"
    pending: str = "🟠"
    
    # === Action Icons ===
    start: str = "▶️"
    stop: str = "⏹️"
    pause: str = "⏸️"
    restart: str = "🔄"
    refresh: str = "🔄"
    sync: str = "☁️"
    add: str = "➕"
    remove: str = "➖"
    delete: str = "🗑️"
    edit: str = "✏️"
    save: str = "💾"
    cancel: str = "❌"
    close: str = "✖️"
    check: str = "✅"
    clear: str = "🧹"
    copy: str = "📋"
    export: str = "📤"
    import_: str = "📥"
    download: str = "⬇️"
    upload: str = "⬆️"
    
    # === Security Icons ===
    shield: str = "🛡"
    shield_check: str = "✅"
    shield_warning: str = "⚠️"
    lock: str = "🔒"
    unlock: str = "🔓"
    key: str = "🔑"
    alert: str = "🚨"
    block: str = "🚫"
    allow: str = "✅"
    
    # === Network Icons ===
    network: str = "🌐"
    server: str = "🖥️"
    connection: str = "🔗"
    disconnected: str = "🔌"
    ip_address: str = "🖥️"
    dns: str = "🌍"
    packet: str = "📦"
    traffic: str = "📶"
    
    # === System Icons ===
    computer: str = "🖥️"
    cpu: str = "⚡"
    memory: str = "🧠"
    disk: str = "💿"
    time: str = "🕐"
    clock: str = "⏰"
    calendar: str = "📅"
    uptime: str = "⏱️"
    
    # === File Icons ===
    file: str = "📄"
    folder: str = "📁"
    config: str = "📋"
    log_file: str = "📜"
    
    # === User Icons ===
    user: str = "👤"
    admin: str = "👑"
    group: str = "👥"
    
    # === Info Icons ===
    info: str = "ℹ️"
    help: str = "❓"
    question: str = "❔"
    warning_sign: str = "⚠️"
    error_sign: str = "❌"
    success_sign: str = "✅"
    
    # === Console Icons ===
    console: str = "📟"
    terminal: str = "🖥️"
    command: str = ">"
    
    # === Theme Icons ===
    sun: str = "☀️"
    moon: str = "🌙"
    palette: str = "🎨"
    
    # === Chart Icons ===
    chart: str = "📈"
    chart_up: str = "📈"
    chart_down: str = "📉"
    pie_chart: str = "🥧"
    bar_chart: str = "📊"
    
    # === App Icons ===
    app_icon: str = "🔥"  # Firewall
    brand: str = "🔥"
    logo: str = "🛡"


# Global icon set instance
ICONS = IconSet()


# === Icon Categories for Menu ===

MENU_ICONS: Dict[str, str] = {
    "dashboard": ICONS.dashboard,
    "firewall": ICONS.firewall,
    "whitelist": ICONS.whitelist,
    "logs": ICONS.logs,
    "settings": ICONS.settings,
}

STATUS_ICONS: Dict[str, str] = {
    "running": ICONS.online,
    "stopped": ICONS.offline,
    "starting": ICONS.pending,
    "stopping": ICONS.warning,
    "error": ICONS.error_sign,
    "connected": ICONS.online,
    "disconnected": ICONS.offline,
    "active": ICONS.online,
    "inactive": ICONS.offline,
    "enabled": ICONS.check,
    "disabled": ICONS.close,
    "allowed": ICONS.allow,
    "blocked": ICONS.block,
    "pending": ICONS.pending,
}

ACTION_ICONS: Dict[str, str] = {
    "start": ICONS.start,
    "stop": ICONS.stop,
    "restart": ICONS.restart,
    "refresh": ICONS.refresh,
    "sync": ICONS.sync,
    "add": ICONS.add,
    "delete": ICONS.delete,
    "edit": ICONS.edit,
    "save": ICONS.save,
    "cancel": ICONS.cancel,
    "clear": ICONS.clear,
    "export": ICONS.export,
}


def get_icon(name: str, fallback: str = "•") -> str:
    """
    Get icon by name.
    
    Args:
        name: Icon name
        fallback: Fallback character if icon not found
        
    Returns:
        Icon character
    """
    # Check all icon dictionaries
    if hasattr(ICONS, name):
        return getattr(ICONS, name)
    
    if name in MENU_ICONS:
        return MENU_ICONS[name]
    
    if name in STATUS_ICONS:
        return STATUS_ICONS[name]
    
    if name in ACTION_ICONS:
        return ACTION_ICONS[name]
    
    return fallback


def get_status_icon(status: str) -> str:
    """Get icon for a status string."""
    return STATUS_ICONS.get(status.lower(), ICONS.info)


def get_menu_icon(menu_name: str) -> str:
    """Get icon for a menu item."""
    return MENU_ICONS.get(menu_name.lower(), ICONS.file)


def get_action_icon(action: str) -> str:
    """Get icon for an action."""
    return ACTION_ICONS.get(action.lower(), ICONS.check)


# === ASCII Art Logo ===

ASCII_LOGO = """
╔═══════════════════════════════════════════╗
║                S A I N T                  ║
║   Security Agent Intelligence Network Tool║
║   Enterprise Security Management          ║
║   Edition                    ║
╚═══════════════════════════════════════════╝
"""

ASCII_LOGO_SMALL = """
                S A I N T
Security Agent Intelligence Network Tool
"""

SPLASH_LOGO = """
    ███████╗ █████╗ ██╗███╗   ██╗████████╗
    ██╔════╝██╔══██╗██║████╗  ██║╚══██╔══╝
    ███████╗███████║██║██╔██╗ ██║   ██║   
    ╚════██║██╔══██║██║██║╚██╗██║   ██║   
    ███████║██║  ██║██║██║ ╚████║   ██║   
    ╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝   
    Security Agent Intelligence Network Tool
"""
