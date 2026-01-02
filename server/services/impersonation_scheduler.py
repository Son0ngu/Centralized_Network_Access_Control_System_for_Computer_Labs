"""
Impersonation Scheduler - Auto-expire impersonation sessions
-------------------------------------------------------------
Runs periodically to check and expire old impersonation sessions.
"""

import logging
from threading import Thread, Event
from time import sleep

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


class ImpersonationExpiryScheduler:
    """
    Background scheduler to auto-expire impersonation sessions.
    """
    
    def __init__(self, impersonation_model, interval_seconds: int = 60):
        """
        Initialize the scheduler.
        
        Args:
            impersonation_model: ImpersonationLogModel instance
            interval_seconds: How often to check for expired sessions
        """
        self.impersonation_model = impersonation_model
        self.interval = interval_seconds
        self._stop_event = Event()
        self._thread = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def start(self):
        """Start the background scheduler."""
        if self._thread and self._thread.is_alive():
            self.logger.warning("Scheduler already running")
            return
        
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info(f"Impersonation expiry scheduler started (interval: {self.interval}s)")
    
    def stop(self):
        """Stop the background scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self.logger.info("Impersonation expiry scheduler stopped")
    
    def _run(self):
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                expired_count = self.impersonation_model.expire_old_sessions()
                if expired_count > 0:
                    self.logger.info(f"Auto-expired {expired_count} impersonation session(s)")
            except Exception as e:
                self.logger.error(f"Error in expiry scheduler: {e}")
            
            # Wait for next interval (or until stop is called)
            self._stop_event.wait(self.interval)
    
    def check_now(self) -> int:
        """Manually trigger an expiry check."""
        try:
            return self.impersonation_model.expire_old_sessions()
        except Exception as e:
            self.logger.error(f"Error in manual expiry check: {e}")
            return 0


def init_impersonation_scheduler(impersonation_model, interval_seconds: int = 60):
    """
    Initialize and start the global impersonation expiry scheduler.
    
    Args:
        impersonation_model: ImpersonationLogModel instance
        interval_seconds: Check interval (default 60s)
        
    Returns:
        ImpersonationExpiryScheduler instance
    """
    global _scheduler
    
    if _scheduler:
        _scheduler.stop()
    
    _scheduler = ImpersonationExpiryScheduler(impersonation_model, interval_seconds)
    _scheduler.start()
    
    return _scheduler


def get_impersonation_scheduler():
    """Get the global scheduler instance."""
    return _scheduler


def stop_impersonation_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
