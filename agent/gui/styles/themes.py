import customtkinter as ctk
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
import logging

from .colors import (
    ColorPalette, 
    DARK_PALETTE, 
    LIGHT_PALETTE, 
    HIGH_CONTRAST_PALETTE,
    get_status_color,
    get_contrast_text
)

logger = logging.getLogger("gui.themes")


class ThemeMode(Enum):
    """Available theme modes."""
    DARK = "dark"
    LIGHT = "light"
    HIGH_CONTRAST = "high_contrast"
    SYSTEM = "system"


@dataclass
class FontConfig:
    """Font configuration for the application."""
    family: str = "Segoe UI"
    family_mono: str = "Consolas"
    
    # Sizes
    size_xs: int = 10
    size_sm: int = 11
    size_md: int = 13
    size_lg: int = 16
    size_xl: int = 20
    size_2xl: int = 24
    size_3xl: int = 28
    size_4xl: int = 32
    
    # Weights
    weight_normal: str = "normal"
    weight_bold: str = "bold"
    
    def get_font(self, size: str = "md", weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
        """Get a CTkFont with specified parameters."""
        size_map = {
            "xs": self.size_xs,
            "sm": self.size_sm,
            "md": self.size_md,
            "lg": self.size_lg,
            "xl": self.size_xl,
            "2xl": self.size_2xl,
            "3xl": self.size_3xl,
            "4xl": self.size_4xl,
        }
        
        return ctk.CTkFont(
            family=self.family_mono if mono else self.family,
            size=size_map.get(size, self.size_md),
            weight=weight
        )


@dataclass
class SpacingConfig:
    """Spacing configuration (padding, margins, gaps)."""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    
    # Component specific
    card_padding: int = 20
    button_padding_x: int = 16
    button_padding_y: int = 8
    input_padding: int = 12
    sidebar_width: int = 250


@dataclass
class BorderConfig:
    """Border configuration."""
    radius_sm: int = 4
    radius_md: int = 8
    radius_lg: int = 12
    radius_xl: int = 16
    radius_full: int = 9999
    
    width_thin: int = 1
    width_normal: int = 2
    width_thick: int = 3


class Theme:
    """
    Main theme class containing all styling information.
    """
    
    def __init__(
        self,
        name: str,
        mode: ThemeMode,
        colors: ColorPalette,
        fonts: Optional[FontConfig] = None,
        spacing: Optional[SpacingConfig] = None,
        borders: Optional[BorderConfig] = None
    ):
        self.name = name
        self.mode = mode
        self.colors = colors
        self.fonts = fonts or FontConfig()
        self.spacing = spacing or SpacingConfig()
        self.borders = borders or BorderConfig()
    
    def get_button_style(self, variant: str = "primary") -> Dict[str, Any]:
        """Get button styling based on variant."""
        styles = {
            "primary": {
                "fg_color": self.colors.accent_primary,
                "hover_color": self.colors.info_dark,
                "text_color": self.colors.text_inverse,
                "corner_radius": self.borders.radius_md,
            },
            "secondary": {
                "fg_color": self.colors.bg_elevated,
                "hover_color": self.colors.bg_hover,
                "text_color": self.colors.text_primary,
                "corner_radius": self.borders.radius_md,
            },
            "success": {
                "fg_color": self.colors.success,
                "hover_color": self.colors.success_dark,
                "text_color": self.colors.text_inverse,
                "corner_radius": self.borders.radius_md,
            },
            "danger": {
                "fg_color": self.colors.error,
                "hover_color": self.colors.error_dark,
                "text_color": self.colors.text_primary,
                "corner_radius": self.borders.radius_md,
            },
            "warning": {
                "fg_color": self.colors.warning,
                "hover_color": self.colors.warning_dark,
                "text_color": self.colors.text_inverse,
                "corner_radius": self.borders.radius_md,
            },
            "ghost": {
                "fg_color": "transparent",
                "hover_color": self.colors.bg_hover,
                "text_color": self.colors.text_primary,
                "corner_radius": self.borders.radius_md,
            },
            "outline": {
                "fg_color": "transparent",
                "hover_color": self.colors.accent_primary + "20",
                "text_color": self.colors.accent_primary,
                "border_color": self.colors.accent_primary,
                "border_width": self.borders.width_normal,
                "corner_radius": self.borders.radius_md,
            },
        }
        return styles.get(variant, styles["primary"])
    
    def get_input_style(self) -> Dict[str, Any]:
        """Get input field styling."""
        return {
            "fg_color": self.colors.bg_primary,
            "border_color": self.colors.border_default,
            "text_color": self.colors.text_primary,
            "placeholder_text_color": self.colors.text_muted,
            "corner_radius": self.borders.radius_md,
        }
    
    def get_card_style(self) -> Dict[str, Any]:
        """Get card/panel styling."""
        return {
            "fg_color": self.colors.bg_tertiary,
            "corner_radius": self.borders.radius_lg,
        }
    
    def get_sidebar_style(self) -> Dict[str, Any]:
        """Get sidebar styling."""
        return {
            "fg_color": self.colors.sidebar_bg,
            "corner_radius": 0,
        }
    
    def get_label_style(self, variant: str = "default") -> Dict[str, Any]:
        """Get label styling based on variant."""
        styles = {
            "default": {"text_color": self.colors.text_primary},
            "secondary": {"text_color": self.colors.text_secondary},
            "muted": {"text_color": self.colors.text_muted},
            "success": {"text_color": self.colors.success},
            "error": {"text_color": self.colors.error},
            "warning": {"text_color": self.colors.warning},
            "accent": {"text_color": self.colors.accent_primary},
        }
        return styles.get(variant, styles["default"])


# === Predefined Themes ===

DARK_THEME = Theme(
    name="Cyber Dark",
    mode=ThemeMode.DARK,
    colors=DARK_PALETTE
)

LIGHT_THEME = Theme(
    name="Light",
    mode=ThemeMode.LIGHT,
    colors=LIGHT_PALETTE
)

HIGH_CONTRAST_THEME = Theme(
    name="High Contrast",
    mode=ThemeMode.HIGH_CONTRAST,
    colors=HIGH_CONTRAST_PALETTE
)


class ThemeManager:
    """
    Singleton theme manager for application-wide theming.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._current_theme: Theme = DARK_THEME
        self._available_themes: Dict[str, Theme] = {
            "dark": DARK_THEME,
            "light": LIGHT_THEME,
            "high_contrast": HIGH_CONTRAST_THEME,
        }
        self._change_callbacks: List[Callable[[Theme], None]] = []
        
        # Apply initial theme to customtkinter
        self._apply_to_ctk()
        
        logger.info(f"ThemeManager initialized with theme: {self._current_theme.name}")
    
    @property
    def current(self) -> Theme:
        """Get current theme."""
        return self._current_theme
    
    @property
    def colors(self) -> ColorPalette:
        """Shortcut to current theme colors."""
        return self._current_theme.colors
    
    @property
    def fonts(self) -> FontConfig:
        """Shortcut to current theme fonts."""
        return self._current_theme.fonts
    
    @property
    def spacing(self) -> SpacingConfig:
        """Shortcut to current theme spacing."""
        return self._current_theme.spacing
    
    @property
    def borders(self) -> BorderConfig:
        """Shortcut to current theme borders."""
        return self._current_theme.borders
    
    def set_theme(self, theme_name: str) -> bool:
        """
        Set current theme by name.
        
        Args:
            theme_name: Name of theme ('dark', 'light', 'high_contrast')
            
        Returns:
            True if theme was changed
        """
        if theme_name not in self._available_themes:
            logger.warning(f"Unknown theme: {theme_name}")
            return False
        
        new_theme = self._available_themes[theme_name]
        if new_theme == self._current_theme:
            return False
        
        self._current_theme = new_theme
        self._apply_to_ctk()
        self._notify_change()
        
        logger.info(f"Theme changed to: {new_theme.name}")
        return True
    
    def register_theme(self, name: str, theme: Theme) -> None:
        """Register a custom theme."""
        self._available_themes[name] = theme
        logger.info(f"Registered custom theme: {name}")
    
    def on_theme_change(self, callback: Callable[[Theme], None]) -> None:
        """Register callback for theme changes."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)
    
    def _notify_change(self) -> None:
        """Notify all registered callbacks of theme change."""
        for callback in self._change_callbacks:
            try:
                callback(self._current_theme)
            except Exception as e:
                logger.error(f"Error in theme change callback: {e}")
    
    def _apply_to_ctk(self) -> None:
        """Apply theme to customtkinter."""
        mode = self._current_theme.mode
        
        if mode == ThemeMode.DARK or mode == ThemeMode.HIGH_CONTRAST:
            ctk.set_appearance_mode("dark")
        elif mode == ThemeMode.LIGHT:
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("system")
        
        # Set default color theme
        ctk.set_default_color_theme("blue")
    
    def get_available_themes(self) -> List[str]:
        """Get list of available theme names."""
        return list(self._available_themes.keys())
    
    # === Convenience Methods ===
    
    def button(self, variant: str = "primary") -> Dict[str, Any]:
        """Get button style."""
        return self._current_theme.get_button_style(variant)
    
    def input(self) -> Dict[str, Any]:
        """Get input style."""
        return self._current_theme.get_input_style()
    
    def card(self) -> Dict[str, Any]:
        """Get card style."""
        return self._current_theme.get_card_style()
    
    def sidebar(self) -> Dict[str, Any]:
        """Get sidebar style."""
        return self._current_theme.get_sidebar_style()
    
    def label(self, variant: str = "default") -> Dict[str, Any]:
        """Get label style."""
        return self._current_theme.get_label_style(variant)
    
    def font(self, size: str = "md", weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
        """Get font with specified parameters."""
        return self._current_theme.fonts.get_font(size, weight, mono)


# Global theme manager instance
def get_theme() -> ThemeManager:
    """Get the global theme manager instance."""
    return ThemeManager()
