"""SAINT agent entry point — launches the PySide6 GUI.

Used both for running from source and as the script frozen into the
PyInstaller bundle (see `saint_agent.spec`).

    python agent/agent_gui.py
"""

import os
import sys

# Add the project root and the agent directory to sys.path so the existing
# `from controllers import ...` / `from core import ...` absolute imports
# keep working when this script is launched directly. When frozen by
# PyInstaller these are no-ops (modules are already on the bundled sys.path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        from gui_qt.app import run
    except ImportError as exc:
        # In dev, this usually means PySide6 isn't installed yet.
        # In the frozen .exe this should never happen — if it does the
        # bundle is broken.
        print(
            f"Failed to import the Qt GUI module: {exc}\n"
            "Run `pip install -r agent/requirements.txt` to install PySide6.",
            file=sys.stderr,
        )
        return 2
    return run()


if __name__ == "__main__":
    sys.exit(main())
