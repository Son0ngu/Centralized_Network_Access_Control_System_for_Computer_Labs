"""Qt entry point for the SAINT agent GUI.

Only the view layer is Qt. Agent lifecycle, worker threads, and UI signals are
handled by framework-agnostic controllers in `agent/controllers/`.
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .signal_bridge import QtSignalBridge
from .styles import GLOBAL_QSS


def run() -> int:
    """Launch the Qt GUI and return the QApplication exit code."""
    # Lazy import: the controller pulls in the rest of the agent stack and we
    # do not want that loaded just to discover Qt is missing.
    from controllers import AgentController

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SAINT")
    app.setStyle("Fusion")  # Consistent base across Win10/11/Win7
    app.setStyleSheet(GLOBAL_QSS)

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "miku.ico",
    )
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    controller = AgentController()
    bridge = QtSignalBridge(controller.signals)

    window = MainWindow(controller, bridge)
    window.show()

    return app.exec()
