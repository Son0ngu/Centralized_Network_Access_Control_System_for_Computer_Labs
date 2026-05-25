"""Lightweight line-chart widget for time-series stats.

Built with raw `QPainter` instead of Qt Charts so we don't have to ship an
extra Qt module in the PyInstaller bundle. Good enough for ~60 data points
(e.g. last 30 minutes sampled every 30s).
"""

from collections import deque
from typing import Iterable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QPainter, QPainterPath, QPaintEvent, QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


class Sparkline(QWidget):
    """A ring-buffered line chart.

    Call `push(value)` to append a new sample; older samples are dropped
    automatically when `max_points` is exceeded. The widget repaints on
    each push.
    """

    def __init__(
        self,
        max_points: int = 60,
        line_color: str = "#0077cc",
        fill_color: str = "#0077cc22",
        grid_color: str = "#e0e0e8",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._max_points = max_points
        self._values: "deque[float]" = deque(maxlen=max_points)
        self._line_color = QColor(line_color)
        self._fill_color = QColor(fill_color)
        self._grid_color = QColor(grid_color)
        # Reasonable defaults — caller can override via setMinimumHeight.
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def push(self, value: float) -> None:
        """Append a new sample and repaint."""
        try:
            self._values.append(float(value))
        except (TypeError, ValueError):
            self._values.append(0.0)
        self.update()  # schedules repaint

    def set_values(self, values: Iterable[float]) -> None:
        """Replace the buffer with `values` (truncating to `max_points`)."""
        self._values = deque(
            (float(v) for v in values),
            maxlen=self._max_points,
        )
        self.update()

    def clear(self) -> None:
        self._values.clear()
        self.update()

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        # Small inner margin so the line doesn't kiss the widget edges.
        margin = 6.0
        plot = rect.adjusted(margin, margin, -margin, -margin)

        # 3 faint horizontal gridlines so the chart doesn't look like a
        # floating squiggle (no axes, just visual anchors).
        pen = QPen(self._grid_color)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        for i in range(1, 4):
            y = plot.top() + plot.height() * i / 4.0
            painter.drawLine(
                QPointF(plot.left(), y),
                QPointF(plot.right(), y),
            )

        n = len(self._values)
        if n < 2:
            # Nothing meaningful to plot yet — draw a baseline so the panel
            # doesn't look broken when the agent has just started.
            painter.setPen(QPen(self._line_color, 1.5))
            y = plot.bottom()
            painter.drawLine(
                QPointF(plot.left(), y),
                QPointF(plot.right(), y),
            )
            return

        max_v = max(self._values)
        min_v = min(self._values)
        # Guard against a flat series (max == min) — pin to mid-height.
        span = max(max_v - min_v, 1e-9)

        step_x = plot.width() / (self._max_points - 1)
        x0 = plot.right() - step_x * (n - 1)

        # Build the line path
        line_path = QPainterPath()
        for i, v in enumerate(self._values):
            normalized = (v - min_v) / span if span else 0.5
            x = x0 + step_x * i
            y = plot.bottom() - normalized * plot.height()
            if i == 0:
                line_path.moveTo(x, y)
            else:
                line_path.lineTo(x, y)

        # Fill area under the line
        fill_path = QPainterPath(line_path)
        last_x = x0 + step_x * (n - 1)
        fill_path.lineTo(last_x, plot.bottom())
        fill_path.lineTo(x0, plot.bottom())
        fill_path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._fill_color))
        painter.drawPath(fill_path)

        # Line on top
        pen = QPen(self._line_color)
        pen.setWidthF(2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line_path)
