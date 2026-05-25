"""Bridge `AgentSignals` worker events to Qt signals.

Controllers emit events from background worker threads into a plain Python
queue. This bridge polls that queue on the Qt GUI thread and re-emits each
event as a typed Qt signal.
"""

import queue
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal


# Match controllers.agent_controller constants.
_DRAIN_INTERVAL_MS = 50
_MAX_EVENTS_PER_TICK = 100


class QtSignalBridge(QObject):
    """Re-emits `AgentSignals` events as Qt signals on the GUI thread."""

    status_changed = Signal(dict)
    stats_updated = Signal(dict)
    packet_captured = Signal(dict)
    log_received = Signal(dict)
    error_occurred = Signal(dict)
    whitelist_synced = Signal(dict)

    def __init__(self, agent_signals, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._signals = agent_signals
        self._timer = QTimer(self)
        self._timer.setInterval(_DRAIN_INTERVAL_MS)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

        self._signal_map = {
            "status_changed": self.status_changed,
            "stats_updated": self.stats_updated,
            "packet_captured": self.packet_captured,
            "log_received": self.log_received,
            "error_occurred": self.error_occurred,
            "whitelist_synced": self.whitelist_synced,
        }

    def _drain(self) -> None:
        """Drain a bounded event batch without blocking the GUI thread."""
        try:
            event_queue = self._signals._event_queue
        except AttributeError:
            return

        processed = 0
        while processed < _MAX_EVENTS_PER_TICK:
            try:
                event = event_queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch(event)
            processed += 1

        if processed >= _MAX_EVENTS_PER_TICK:
            QTimer.singleShot(0, self._drain)

    def _dispatch(self, event) -> None:
        sig = self._signal_map.get(event.event_type)
        if sig is None:
            return
        try:
            sig.emit(event.data or {})
        except Exception:
            pass

    def stop(self) -> None:
        """Stop polling when the GUI is shutting down."""
        self._timer.stop()
