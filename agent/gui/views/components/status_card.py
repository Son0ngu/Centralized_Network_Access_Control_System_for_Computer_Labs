import customtkinter as ctk
from typing import Optional


class StatusCard(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        title: str = "Title",
        value: str = "0",
        icon: str = "📊",
        color: str = "#00d4ff",
        subtitle: str = "",
        width: int = 200,
        height: int = 120,
        **kwargs
    ):
        super().__init__(
            parent,
            corner_radius=12,
            fg_color="#e8e8ed",
            width=width,
            height=height,
            **kwargs
        )
        
        self._title = title
        self._value = value
        self._icon = icon
        self._color = color
        self._subtitle = subtitle
        
        # Prevent size shrinking
        self.grid_propagate(False)
        self.pack_propagate(False)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup card UI layout."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Icon + Title row
        self.grid_rowconfigure(1, weight=1)  # Value row
        self.grid_rowconfigure(2, weight=0)  # Subtitle row
        
        # Top row: Icon and Title
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        
        # Icon
        self._icon_label = ctk.CTkLabel(
            top_frame,
            text=self._icon,
            font=ctk.CTkFont(size=20),
            text_color=self._color
        )
        self._icon_label.pack(side="left")
        
        # Title
        self._title_label = ctk.CTkLabel(
            top_frame,
            text=self._title,
            font=ctk.CTkFont(size=12),
            text_color="#6a6a7a"
        )
        self._title_label.pack(side="left", padx=(8, 0))
        
        # Value (center, large) - with wrapping support
        self._value_label = ctk.CTkLabel(
            self,
            text=self._value,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self._color,
            wraplength=160,
            justify="center"
        )
        self._value_label.grid(row=1, column=0, sticky="nsew", padx=10)
        
        # Subtitle (optional)
        self._subtitle_label = ctk.CTkLabel(
            self,
            text=self._subtitle,
            font=ctk.CTkFont(size=11),
            text_color="#9a9aaa"
        )
        self._subtitle_label.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))
    
    # ========================================
    # PUBLIC API
    # ========================================
    
    def set_value(self, value: str):
        """Update the displayed value."""
        self._value = value
        self._value_label.configure(text=value)
    
    def set_title(self, title: str):
        """Update the title."""
        self._title = title
        self._title_label.configure(text=title)
    
    def set_icon(self, icon: str):
        """Update the icon."""
        self._icon = icon
        self._icon_label.configure(text=icon)
    
    def set_color(self, color: str):
        """Update the accent color."""
        self._color = color
        self._icon_label.configure(text_color=color)
        self._value_label.configure(text_color=color)
    
    def set_subtitle(self, subtitle: str):
        """Update the subtitle."""
        self._subtitle = subtitle
        self._subtitle_label.configure(text=subtitle)
    
    def get_value(self) -> str:
        """Get current value."""
        return self._value
    
    def set_status(self, status: str, color: str):
        """Set status with color (convenience method)."""
        self.set_value(status)
        self.set_color(color)


class AnimatedStatusCard(StatusCard):    
    def __init__(
        self,
        parent,
        title: str = "Title",
        value: str = "0",
        icon: str = "📊",
        color: str = "#00d4ff",
        subtitle: str = "",
        show_trend: bool = False,
        animate: bool = True,
        **kwargs
    ):
        self._show_trend = show_trend
        self._animate = animate
        self._previous_value: Optional[float] = None
        self._animation_id = None
        
        super().__init__(
            parent,
            title=title,
            value=value,
            icon=icon,
            color=color,
            subtitle=subtitle,
            **kwargs
        )
    
    def _setup_ui(self):
        """Setup card UI with trend indicator."""
        super()._setup_ui()
        
        if self._show_trend:
            # Trend indicator
            self._trend_label = ctk.CTkLabel(
                self,
                text="",
                font=ctk.CTkFont(size=14),
                text_color="#6a6a7a"
            )
            self._trend_label.place(relx=0.85, rely=0.5, anchor="center")
    
    def set_value(self, value: str, animate: bool = None):
  
        should_animate = animate if animate is not None else self._animate
        
        # Update trend indicator
        if self._show_trend and hasattr(self, '_trend_label'):
            self._update_trend(value)
        
        if should_animate and self._is_numeric(value) and self._is_numeric(self._value):
            self._animate_value_change(float(self._value), float(value))
        else:
            self._value = value
            self._value_label.configure(text=value)
        
        # Store for trend calculation
        if self._is_numeric(value):
            self._previous_value = float(value)
    
    def _update_trend(self, new_value: str):
        """Update trend indicator based on value change."""
        if not self._is_numeric(new_value) or self._previous_value is None:
            return
        
        new_val = float(new_value)
        diff = new_val - self._previous_value
        
        if diff > 0:
            self._trend_label.configure(text="↑", text_color="#00ff88")
        elif diff < 0:
            self._trend_label.configure(text="↓", text_color="#ff4444")
        else:
            self._trend_label.configure(text="→", text_color="#6a6a7a")
    
    def _animate_value_change(self, start: float, end: float, duration_ms: int = 300):
        """Animate numeric value change."""
        # Cancel any existing animation
        if self._animation_id:
            self.after_cancel(self._animation_id)
        
        steps = 10
        step_duration = duration_ms // steps
        diff = end - start
        step_value = diff / steps
        
        def animate_step(current_step: int):
            if current_step >= steps:
                self._value = str(int(end) if end == int(end) else round(end, 1))
                self._value_label.configure(text=self._value)
                return
            
            current_value = start + (step_value * (current_step + 1))
            display_value = str(int(current_value) if current_value == int(current_value) else round(current_value, 1))
            self._value_label.configure(text=display_value)
            
            self._animation_id = self.after(step_duration, lambda: animate_step(current_step + 1))
        
        animate_step(0)
    
    def _is_numeric(self, value: str) -> bool:
        """Check if value is numeric."""
        try:
            float(value.replace(',', ''))
            return True
        except (ValueError, AttributeError):
            return False
    
    def pulse(self):
        """Trigger a pulse animation effect."""
        original_color = self._color
        
        def restore():
            self._value_label.configure(text_color=original_color)
        
        # Flash white then restore
        self._value_label.configure(text_color="#ffffff")
        self.after(150, restore)


class StatusCardGrid(ctk.CTkFrame):

    def __init__(
        self,
        parent,
        columns: int = 4,
        card_width: int = 200,
        card_height: int = 120,
        gap: int = 15,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self._columns = columns
        self._card_width = card_width
        self._card_height = card_height
        self._gap = gap
        self._cards = {}
        self._row = 0
        self._col = 0
        
        # Configure grid columns
        for i in range(columns):
            self.grid_columnconfigure(i, weight=1)
    
    def add_card(
        self,
        card_id: str,
        title: str,
        value: str = "0",
        icon: str = "📊",
        color: str = "#00d4ff",
        subtitle: str = "",
        animated: bool = False
    ) -> StatusCard:

        CardClass = AnimatedStatusCard if animated else StatusCard
        
        card = CardClass(
            self,
            title=title,
            value=value,
            icon=icon,
            color=color,
            subtitle=subtitle,
            width=self._card_width,
            height=self._card_height
        )
        
        # Place in grid
        card.grid(
            row=self._row,
            column=self._col,
            padx=(0 if self._col == 0 else self._gap // 2, 0 if self._col == self._columns - 1 else self._gap // 2),
            pady=(0, self._gap),
            sticky="nsew"
        )
        
        # Store reference
        self._cards[card_id] = card
        
        # Move to next position
        self._col += 1
        if self._col >= self._columns:
            self._col = 0
            self._row += 1
        
        return card
    
    def get_card(self, card_id: str) -> Optional[StatusCard]:
        """Get a card by ID."""
        return self._cards.get(card_id)
    
    def update_card(self, card_id: str, **kwargs):
    
        card = self._cards.get(card_id)
        if not card:
            return
        
        if 'value' in kwargs:
            card.set_value(kwargs['value'])
        if 'title' in kwargs:
            card.set_title(kwargs['title'])
        if 'icon' in kwargs:
            card.set_icon(kwargs['icon'])
        if 'color' in kwargs:
            card.set_color(kwargs['color'])
        if 'subtitle' in kwargs:
            card.set_subtitle(kwargs['subtitle'])
    
    def update_all(self, data: dict):
 
        for card_id, props in data.items():
            self.update_card(card_id, **props)
