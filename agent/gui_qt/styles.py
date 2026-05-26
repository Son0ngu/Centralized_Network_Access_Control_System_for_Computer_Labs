"""Qt style sheet (QSS) for the SAINT agent GUI.

Colours are referenced as constants so view code can pull them into inline
styles for status-driven colour changes.
"""

# Palette
BG_WINDOW = "#f5f5f7"        # Main window background
BG_CARD = "#e8e8ed"          # Cards / panels
BG_INPUT = "#ffffff"         # Entries, textboxes
BG_HOVER = "#dcdce2"

FG_PRIMARY = "#1a1a2e"       # Main text
FG_SECONDARY = "#6a6a7a"     # Subtitles
FG_MUTED = "#9a9aaa"

ACCENT_BLUE = "#0077cc"
ACCENT_GREEN = "#00aa55"     # Slightly darker than the CTk #00ff88 so it
                             # reads cleanly on light backgrounds (the bright
                             # neon was a dark-mode legacy from CTk).
ACCENT_RED = "#cc3333"
ACCENT_ORANGE = "#cc7a00"
ACCENT_PURPLE = "#9966ff"

BORDER_LIGHT = "#d0d0d8"

# Status colour helpers - used by status cards / log banners
STATUS_COLORS = {
    "ok": ACCENT_GREEN,
    "running": ACCENT_GREEN,
    "online": ACCENT_GREEN,
    "active": ACCENT_GREEN,
    "stopped": "#888888",
    "offline": ACCENT_RED,
    "error": ACCENT_RED,
    "blocked": ACCENT_RED,
    "starting": ACCENT_ORANGE,
    "stopping": ACCENT_ORANGE,
    "degraded": ACCENT_ORANGE,
    "syncing": ACCENT_ORANGE,
    "pending": ACCENT_ORANGE,
}


# Global QSS applied to QApplication. Per-widget overrides happen in the
# widget classes themselves so this stylesheet stays readable.
GLOBAL_QSS = f"""
QWidget {{
    background-color: {BG_WINDOW};
    color: {FG_PRIMARY};
    font-family: "Segoe UI", "San Francisco", sans-serif;
    font-size: 13px;
}}

/* QLabel inherits the QWidget rule above by default, which paints a window-
 * coloured rectangle behind every label - including labels sitting INSIDE a
 * coloured card frame, producing an ugly "tiled" look. Make labels transparent
 * so they pick up their parent panel's background instead. */
QLabel {{
    background-color: transparent;
}}

QFrame#card {{
    background-color: {BG_CARD};
    border-radius: 12px;
    border: 0;
}}

QFrame#sidebar {{
    background-color: {BG_CARD};
    border-right: 1px solid {BORDER_LIGHT};
}}

QPushButton {{
    background-color: {BORDER_LIGHT};
    color: {FG_PRIMARY};
    border: 0;
    border-radius: 8px;
    padding: 8px 14px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
}}
QPushButton:disabled {{
    color: {FG_MUTED};
}}

QPushButton#sidebar_item {{
    background-color: transparent;
    text-align: left;
    padding: 10px 16px;
    border-radius: 6px;
    color: {FG_PRIMARY};
}}
QPushButton#sidebar_item:hover {{
    background-color: {BG_HOVER};
}}
QPushButton#sidebar_item:checked {{
    background-color: {ACCENT_BLUE};
    color: white;
}}

QPushButton#primary {{
    background-color: {ACCENT_BLUE};
    color: white;
}}
QPushButton#primary:hover {{
    background-color: #005fa3;
}}

QPushButton#success {{
    background-color: {ACCENT_GREEN};
    color: white;
}}
QPushButton#success:hover {{
    background-color: #008844;
}}

QPushButton#danger {{
    background-color: {ACCENT_RED};
    color: white;
}}
QPushButton#danger:hover {{
    background-color: #aa2828;
}}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 6px 8px;
    color: {FG_PRIMARY};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {ACCENT_BLUE};
}}

QPlainTextEdit#activity_log {{
    background-color: {BG_INPUT};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}}

QLabel#title {{
    font-size: 24px;
    font-weight: bold;
    color: {ACCENT_BLUE};
}}

QLabel#card_title {{
    color: {FG_SECONDARY};
    font-size: 12px;
}}

QLabel#card_value {{
    font-size: 22px;
    font-weight: bold;
}}

QLabel#card_subtitle {{
    color: {FG_MUTED};
    font-size: 11px;
}}

QHeaderView::section {{
    background-color: {BG_CARD};
    color: {ACCENT_BLUE};
    border: 0;
    padding: 8px 10px;
    font-weight: bold;
}}

QTableView {{
    background-color: {BG_INPUT};
    alternate-background-color: {BG_CARD};
    gridline-color: {BORDER_LIGHT};
    border: 0;
    selection-background-color: {ACCENT_BLUE};
    selection-color: white;
}}
"""
