"""
Firewall Controller Agent - GUI Entry Point

GUI application using customtkinter + ttkbootstrap.
Vietnam ONLY - Clean implementation.
"""

import sys
import os

# Add agent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import FirewallControllerApp


def main():
    """Main entry point for GUI application."""
    app = FirewallControllerApp()
    app.run()


if __name__ == "__main__":
    main()
