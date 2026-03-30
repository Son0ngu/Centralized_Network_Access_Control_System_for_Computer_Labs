from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ColorPalette:
    """
    Immutable color palette for consistent theming.
    All colors in hex format.
    """
    
    # === Background Colors ===
    bg_primary: str = "#0a0a12"       # Deepest dark - main background
    bg_secondary: str = "#0f0f1a"     # Slightly lighter - content areas
    bg_tertiary: str = "#1a1a2e"      # Cards, panels
    bg_elevated: str = "#22223a"      # Elevated elements, hover states
    bg_hover: str = "#2d2d44"         # Hover backgrounds
    bg_active: str = "#3d3d54"        # Active/pressed states
    
    # === Accent Colors ===
    accent_primary: str = "#00d4ff"   # Cyan - primary actions, links
    accent_secondary: str = "#7c3aed" # Purple - secondary actions
    accent_tertiary: str = "#06b6d4"  # Teal - tertiary elements
    
    # === Status Colors ===
    success: str = "#00ff88"          # Green - success, allowed, online
    success_dark: str = "#00cc6f"     # Darker green for hover
    success_bg: str = "#1a3d2a"       # Dark green background
    
    warning: str = "#ffa500"          # Orange - warnings, pending
    warning_dark: str = "#cc8400"     # Darker orange for hover
    warning_bg: str = "#3d3a1a"       # Dark orange background
    
    error: str = "#ff4444"            # Red - error, blocked, danger
    error_dark: str = "#cc3333"       # Darker red for hover
    error_bg: str = "#3d1a1a"         # Dark red background
    
    info: str = "#00d4ff"             # Cyan - info messages
    info_dark: str = "#00b8d4"        # Darker cyan for hover
    info_bg: str = "#1a2d3d"          # Dark cyan background
    
    # === Text Colors ===
    text_primary: str = "#ffffff"     # Primary text - white
    text_secondary: str = "#b8b8c8"   # Secondary text - light gray
    text_muted: str = "#888899"       # Muted text - gray
    text_disabled: str = "#555566"    # Disabled text - dark gray
    text_inverse: str = "#000000"     # Inverse text - black (on light bg)
    
    # === Border Colors ===
    border_default: str = "#2d2d44"   # Default borders
    border_light: str = "#3d3d54"     # Lighter borders
    border_focus: str = "#00d4ff"     # Focus ring color
    border_error: str = "#ff4444"     # Error border
    border_success: str = "#00ff88"   # Success border
    
    # === Special Colors ===
    overlay: str = "#000000"          # Modal overlay
    shadow: str = "#000000"           # Shadow color
    gradient_start: str = "#0a0a12"   # Gradient start
    gradient_end: str = "#1a1a2e"     # Gradient end
    
    # === Sidebar Colors ===
    sidebar_bg: str = "#0a0a12"       # Sidebar background
    sidebar_item: str = "transparent" # Sidebar item default
    sidebar_item_hover: str = "#1a1a2e"   # Sidebar item hover
    sidebar_item_active: str = "#1a2d3d"  # Sidebar active item (dark cyan)
    
    # === Chart/Graph Colors ===
    chart_1: str = "#00d4ff"          # Primary chart color
    chart_2: str = "#00ff88"          # Secondary chart color
    chart_3: str = "#ffa500"          # Tertiary chart color
    chart_4: str = "#7c3aed"          # Quaternary chart color
    chart_5: str = "#ff4444"          # Fifth chart color
    
    # === Terminal/Console Colors ===
    console_bg: str = "#0a0a12"       # Console background
    console_text: str = "#00ff88"     # Console default text (matrix green)
    console_prompt: str = "#00d4ff"   # Console prompt
    console_error: str = "#ff4444"    # Console error text
    console_warning: str = "#ffa500"  # Console warning text
    console_info: str = "#00d4ff"     # Console info text
    console_debug: str = "#888899"    # Console debug text


# === Predefined Palettes ===

# Dark Mode (Default) - Cybersecurity theme
DARK_PALETTE = ColorPalette()

# Light Mode (Alternative)
LIGHT_PALETTE = ColorPalette(
    bg_primary="#f5f5f7",
    bg_secondary="#ffffff",
    bg_tertiary="#e8e8ed",
    bg_elevated="#ffffff",
    bg_hover="#e0e0e5",
    bg_active="#d0d0d8",

    accent_primary="#0077cc",
    accent_secondary="#5b21b6",
    accent_tertiary="#0891b2",

    text_primary="#1a1a2e",
    text_secondary="#4a4a5a",
    text_muted="#6a6a7a",
    text_disabled="#9a9aaa",
    text_inverse="#ffffff",

    border_default="#d0d0d8",
    border_light="#e0e0e5",
    border_focus="#0077cc",

    sidebar_bg="#ffffff",
    sidebar_item_hover="#f0f0f5",
    sidebar_item_active="#e0eef8",

    info="#0077cc",
    info_dark="#005fa3",
    info_bg="#e8f4fd",

    success_bg="#e8f8f0",
    warning_bg="#fef8e8",
    error_bg="#fde8e8",

    console_bg="#ffffff",
    console_text="#1a1a2e",
)

# High Contrast (Accessibility)
HIGH_CONTRAST_PALETTE = ColorPalette(
    bg_primary="#000000",
    bg_secondary="#0a0a0a",
    bg_tertiary="#151515",
    
    accent_primary="#00ffff",
    success="#00ff00",
    warning="#ffff00",
    error="#ff0000",
    
    text_primary="#ffffff",
    text_secondary="#ffffff",
    text_muted="#cccccc",
    
    border_default="#ffffff",
    border_focus="#00ffff",
)


# === Color Utility Functions ===

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex color."""
    return f"#{r:02x}{g:02x}{b:02x}"


def lighten_color(hex_color: str, factor: float = 0.2) -> str:
    """Lighten a color by a factor (0-1)."""
    r, g, b = hex_to_rgb(hex_color)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return rgb_to_hex(r, g, b)


def darken_color(hex_color: str, factor: float = 0.2) -> str:
    """Darken a color by a factor (0-1)."""
    r, g, b = hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return rgb_to_hex(r, g, b)


def with_alpha(hex_color: str, alpha: int) -> str:
    """Add alpha channel to hex color (0-255)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return f"#{hex_color}{alpha:02x}"
    return hex_color


def get_contrast_text(bg_color: str) -> str:
    """Get appropriate text color (black or white) for background."""
    r, g, b = hex_to_rgb(bg_color)
    # Calculate relative luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#ffffff"


# === Status Color Mapping ===

STATUS_COLORS: Dict[str, str] = {
    # Agent states
    "running": DARK_PALETTE.success,
    "stopped": DARK_PALETTE.error,
    "starting": DARK_PALETTE.warning,
    "stopping": DARK_PALETTE.warning,
    "error": DARK_PALETTE.error,
    
    # Connection states
    "connected": DARK_PALETTE.success,
    "disconnected": DARK_PALETTE.error,
    "connecting": DARK_PALETTE.warning,
    
    # Firewall states
    "active": DARK_PALETTE.success,
    "inactive": DARK_PALETTE.text_muted,
    "enabled": DARK_PALETTE.success,
    "disabled": DARK_PALETTE.error,
    
    # Action states
    "allowed": DARK_PALETTE.success,
    "blocked": DARK_PALETTE.error,
    "pending": DARK_PALETTE.warning,
    
    # Log levels
    "debug": DARK_PALETTE.console_debug,
    "info": DARK_PALETTE.info,
    "warning": DARK_PALETTE.warning,
    "error": DARK_PALETTE.error,
    "critical": DARK_PALETTE.error,
}


def get_status_color(status: str) -> str:
    """Get color for a given status string."""
    return STATUS_COLORS.get(status.lower(), DARK_PALETTE.text_muted)
