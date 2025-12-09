from typing import Any, Dict
import customtkinter as ctk

from .colors import DARK_PALETTE, ColorPalette
from .themes import get_theme


class WidgetStyles:
    """
    Pre-configured widget styles for consistent UI.
    Use these to quickly style widgets without manual configuration.
    """
    
    # === Button Styles ===
    
    @staticmethod
    def primary_button(width: int = 120, height: int = 36) -> Dict[str, Any]:
        """Primary action button (cyan)."""
        theme = get_theme()
        return {
            "width": width,
            "height": height,
            "font": theme.font("sm", "bold"),
            "fg_color": theme.colors.accent_primary,
            "hover_color": theme.colors.info_dark,
            "text_color": theme.colors.text_inverse,
            "corner_radius": theme.borders.radius_md,
        }
    
    @staticmethod
    def secondary_button(width: int = 100, height: int = 32) -> Dict[str, Any]:
        """Secondary action button (dark)."""
        theme = get_theme()
        return {
            "width": width,
            "height": height,
            "font": theme.font("sm"),
            "fg_color": theme.colors.bg_elevated,
            "hover_color": theme.colors.bg_hover,
            "text_color": theme.colors.text_primary,
            "corner_radius": theme.borders.radius_md,
        }
    
    @staticmethod
    def success_button(width: int = 100, height: int = 36) -> Dict[str, Any]:
        """Success/confirm button (green)."""
        theme = get_theme()
        return {
            "width": width,
            "height": height,
            "font": theme.font("sm", "bold"),
            "fg_color": theme.colors.success,
            "hover_color": theme.colors.success_dark,
            "text_color": theme.colors.text_inverse,
            "corner_radius": theme.borders.radius_md,
        }
    
    @staticmethod
    def danger_button(width: int = 100, height: int = 36) -> Dict[str, Any]:
        """Danger/delete button (red)."""
        theme = get_theme()
        return {
            "width": width,
            "height": height,
            "font": theme.font("sm", "bold"),
            "fg_color": theme.colors.error,
            "hover_color": theme.colors.error_dark,
            "text_color": theme.colors.text_primary,
            "corner_radius": theme.borders.radius_md,
        }
    
    @staticmethod
    def icon_button(size: int = 32) -> Dict[str, Any]:
        """Icon-only button."""
        theme = get_theme()
        return {
            "width": size,
            "height": size,
            "font": theme.font("sm"),
            "fg_color": "transparent",
            "hover_color": theme.colors.bg_hover,
            "text_color": theme.colors.text_primary,
            "corner_radius": theme.borders.radius_md,
        }
    
    # === Input Styles ===
    
    @staticmethod
    def text_input(width: int = 200, height: int = 36) -> Dict[str, Any]:
        """Standard text input."""
        theme = get_theme()
        return {
            "width": width,
            "height": height,
            "font": theme.font("sm"),
            "fg_color": theme.colors.bg_primary,
            "border_color": theme.colors.border_default,
            "text_color": theme.colors.text_primary,
            "placeholder_text_color": theme.colors.text_muted,
            "corner_radius": theme.borders.radius_md,
        }
    
    @staticmethod
    def search_input(width: int = 250) -> Dict[str, Any]:
        """Search input with icon placeholder."""
        theme = get_theme()
        return {
            "width": width,
            "height": 36,
            "font": theme.font("sm"),
            "fg_color": theme.colors.bg_primary,
            "border_color": theme.colors.border_default,
            "text_color": theme.colors.text_primary,
            "placeholder_text_color": theme.colors.text_muted,
            "corner_radius": theme.borders.radius_lg,
        }
    
    # === Card Styles ===
    
    @staticmethod
    def card() -> Dict[str, Any]:
        """Standard card container."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.bg_tertiary,
            "corner_radius": theme.borders.radius_lg,
        }
    
    @staticmethod
    def elevated_card() -> Dict[str, Any]:
        """Elevated card with lighter background."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.bg_elevated,
            "corner_radius": theme.borders.radius_lg,
        }
    
    @staticmethod
    def status_card(status: str = "default") -> Dict[str, Any]:
        """Status card with colored accent."""
        theme = get_theme()
        
        status_colors = {
            "success": theme.colors.success_bg,
            "error": theme.colors.error_bg,
            "warning": theme.colors.warning_bg,
            "info": theme.colors.info_bg,
            "default": theme.colors.bg_tertiary,
        }
        
        return {
            "fg_color": status_colors.get(status, status_colors["default"]),
            "corner_radius": theme.borders.radius_lg,
        }
    
    # === Label Styles ===
    
    @staticmethod
    def title_label() -> Dict[str, Any]:
        """Page/section title."""
        theme = get_theme()
        return {
            "font": theme.font("3xl", "bold"),
            "text_color": theme.colors.accent_primary,
        }
    
    @staticmethod
    def heading_label() -> Dict[str, Any]:
        """Section heading."""
        theme = get_theme()
        return {
            "font": theme.font("xl", "bold"),
            "text_color": theme.colors.text_primary,
        }
    
    @staticmethod
    def body_label() -> Dict[str, Any]:
        """Body text."""
        theme = get_theme()
        return {
            "font": theme.font("md"),
            "text_color": theme.colors.text_primary,
        }
    
    @staticmethod
    def muted_label() -> Dict[str, Any]:
        """Muted/secondary text."""
        theme = get_theme()
        return {
            "font": theme.font("sm"),
            "text_color": theme.colors.text_muted,
        }
    
    @staticmethod
    def status_label(status: str) -> Dict[str, Any]:
        """Status text with color."""
        theme = get_theme()
        from .colors import get_status_color
        
        return {
            "font": theme.font("sm", "bold"),
            "text_color": get_status_color(status),
        }
    
    # === Dropdown/Select Styles ===
    
    @staticmethod
    def dropdown(width: int = 150) -> Dict[str, Any]:
        """Standard dropdown/option menu."""
        theme = get_theme()
        return {
            "width": width,
            "height": 32,
            "font": theme.font("sm"),
            "fg_color": theme.colors.bg_tertiary,
            "button_color": theme.colors.bg_hover,
            "button_hover_color": theme.colors.bg_active,
            "dropdown_fg_color": theme.colors.bg_tertiary,
            "dropdown_hover_color": theme.colors.bg_hover,
            "corner_radius": theme.borders.radius_md,
        }
    
    # === Console/Terminal Styles ===
    
    @staticmethod
    def console_textbox() -> Dict[str, Any]:
        """Terminal-style text display."""
        theme = get_theme()
        return {
            "font": theme.font("sm", mono=True),
            "fg_color": theme.colors.console_bg,
            "text_color": theme.colors.console_text,
            "corner_radius": theme.borders.radius_md,
        }
    
    # === Table Styles ===
    
    @staticmethod
    def table_header() -> Dict[str, Any]:
        """Table header row."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.bg_primary,
            "corner_radius": 0,
        }
    
    @staticmethod
    def table_row(index: int = 0) -> Dict[str, Any]:
        """Table row with alternating colors."""
        theme = get_theme()
        bg = theme.colors.bg_tertiary if index % 2 == 0 else theme.colors.bg_elevated
        return {
            "fg_color": bg,
            "corner_radius": 0,
        }
    
    # === Sidebar Styles ===
    
    @staticmethod
    def sidebar() -> Dict[str, Any]:
        """Sidebar container."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.sidebar_bg,
            "corner_radius": 0,
            "width": theme.spacing.sidebar_width,
        }
    
    @staticmethod
    def sidebar_item(active: bool = False) -> Dict[str, Any]:
        """Sidebar menu item."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.sidebar_item_active if active else "transparent",
            "hover_color": theme.colors.sidebar_item_hover,
            "text_color": theme.colors.accent_primary if active else theme.colors.text_secondary,
            "anchor": "w",
            "corner_radius": theme.borders.radius_md,
        }
    
    # === Progress/Status Styles ===
    
    @staticmethod
    def progress_bar() -> Dict[str, Any]:
        """Progress bar."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.bg_tertiary,
            "progress_color": theme.colors.accent_primary,
            "corner_radius": theme.borders.radius_full,
        }
    
    @staticmethod
    def switch() -> Dict[str, Any]:
        """Toggle switch."""
        theme = get_theme()
        return {
            "fg_color": theme.colors.bg_tertiary,
            "progress_color": theme.colors.success,
            "button_color": theme.colors.text_primary,
            "button_hover_color": theme.colors.accent_primary,
        }


# === Convenience Functions ===

def apply_style(widget: Any, style: Dict[str, Any]) -> None:
    """
    Apply a style dictionary to a widget.
    
    Args:
        widget: The widget to style
        style: Style dictionary from WidgetStyles
    """
    try:
        widget.configure(**style)
    except Exception as e:
        pass  # Silently ignore if widget doesn't support some properties


def create_styled_button(
    parent,
    text: str,
    variant: str = "primary",
    command=None,
    **kwargs
) -> ctk.CTkButton:
    """
    Create a pre-styled button.
    
    Args:
        parent: Parent widget
        text: Button text
        variant: 'primary', 'secondary', 'success', 'danger'
        command: Button command
        **kwargs: Additional button options
        
    Returns:
        Styled CTkButton
    """
    styles = {
        "primary": WidgetStyles.primary_button,
        "secondary": WidgetStyles.secondary_button,
        "success": WidgetStyles.success_button,
        "danger": WidgetStyles.danger_button,
    }
    
    style_func = styles.get(variant, styles["primary"])
    style = style_func()
    style.update(kwargs)
    
    return ctk.CTkButton(parent, text=text, command=command, **style)


def create_styled_input(
    parent,
    placeholder: str = "",
    variant: str = "text",
    **kwargs
) -> ctk.CTkEntry:
    """
    Create a pre-styled input.
    
    Args:
        parent: Parent widget
        placeholder: Placeholder text
        variant: 'text', 'search'
        **kwargs: Additional entry options
        
    Returns:
        Styled CTkEntry
    """
    styles = {
        "text": WidgetStyles.text_input,
        "search": WidgetStyles.search_input,
    }
    
    style_func = styles.get(variant, styles["text"])
    style = style_func()
    style.update(kwargs)
    
    return ctk.CTkEntry(parent, placeholder_text=placeholder, **style)


def create_styled_card(parent, **kwargs) -> ctk.CTkFrame:
    """
    Create a pre-styled card frame.
    
    Args:
        parent: Parent widget
        **kwargs: Additional frame options
        
    Returns:
        Styled CTkFrame
    """
    style = WidgetStyles.card()
    style.update(kwargs)
    return ctk.CTkFrame(parent, **style)
