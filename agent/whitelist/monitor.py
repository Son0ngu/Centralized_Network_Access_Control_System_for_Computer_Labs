import logging
import threading
from typing import Callable, Optional

# Fix: Add now_iso to import
from shared.time_utils import now, now_iso, sleep

logger = logging.getLogger("whitelist.monitor")


class WhitelistMonitor:
    """
    Background monitor for whitelist changes and sync.
    """
    
    def __init__(self, sync_callback: Callable, interval: float = 60.0):
        """
        Initialize whitelist monitor.
        
        Args:
            sync_callback: Function to call for sync
            interval: Check interval in seconds
        """
        self._sync_callback = sync_callback
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_sync = now()
        self._sync_count = 0
        self._error_count = 0
    
    def start(self) -> None:
        """Start the monitor."""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="WhitelistMonitor"
        )
        self._thread.start()
        logger.info(f"Whitelist monitor started (interval: {self._interval}s)")
    
    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Whitelist monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitor loop."""
        while self._running:
            try:
                # Call sync callback
                success = self._sync_callback()
                
                if success:
                    self._last_sync = now()
                    self._sync_count += 1
                else:
                    self._error_count += 1
                    
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                self._error_count += 1
            
            # Interruptible sleep
            for _ in range(int(self._interval)):
                if not self._running:
                    break
                sleep(1)
    
    def get_status(self) -> dict:
        """Get monitor status."""
        return {
            "running": self._running,
            "interval": self._interval,
            "last_sync": now_iso() if self._last_sync else None,
            "sync_count": self._sync_count,
            "error_count": self._error_count
        }