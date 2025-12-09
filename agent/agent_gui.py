import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import FirewallControllerApp


def main():
    app = FirewallControllerApp()
    app.run()


if __name__ == "__main__":
    main()
