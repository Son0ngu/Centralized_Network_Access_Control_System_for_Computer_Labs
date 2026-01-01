import customtkinter as ctk
import os
from .views.main_window import MainWindow
from .controllers import AgentController


class FirewallControllerApp:
    
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
        self._root = None
        self._main_window = None
        self._controller = None
        
        # Configure customtkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
    
    def run(self):
        """Start the GUI application."""
        try:
            # Create root window
            self._root = ctk.CTk()
            
            # Set icon for Windows
            try:
                icon_path = os.path.join(os.path.dirname(__file__), "..", "miku.ico")
                self._root.iconbitmap(icon_path)
            except Exception:
                pass
            
            self._root.title("SAINT - Security Agent Integrated Network Tool")
            self._root.geometry("1200x800")
            self._root.minsize(900, 600)
            
            self._controller = AgentController()
            self._controller.set_root(self._root)
            
            # Create main window with sidebar and content area
            self._main_window = MainWindow(self._root)
            self._main_window.pack(fill="both", expand=True)
            
            # Center window on screen
            self._center_window()
            
            # Handle window close
            self._root.protocol("WM_DELETE_WINDOW", self._on_close)
            
            # Start main loop
            self._root.mainloop()
            
        except Exception as e:
            print(f"GUI Error: {e}")
            raise
    
    def _center_window(self):
        """Center window on screen."""
        if not self._root:
            return
        
        self._root.update_idletasks()
        width = self._root.winfo_width()
        height = self._root.winfo_height()
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self._root.geometry(f"{width}x{height}+{x}+{y}")
    
    def _on_close(self):
        """Handle window close - stop agent if running."""
        if self._controller and self._controller.is_running:
            print("Stopping agent before exit...")
            self._controller.stop_agent()
            # Shorter wait - cleanup is now faster
            self._root.after(200, self._do_quit)
        else:
            self._do_quit()
    
    def _do_quit(self):
        """Actually quit the application."""
        if self._root:
            self._root.quit()
            self._root.destroy()
    
    def quit(self):
        """Quit the application."""
        self._on_close()
