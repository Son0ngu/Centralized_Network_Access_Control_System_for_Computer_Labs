"""
Agent Controller - Bridge between GUI and Core Agent.
Vietnam ONLY - Clean implementation.

Uses threading + callback pattern for non-blocking GUI.
customtkinter uses after() for thread-safe UI updates.
"""

import logging
import threading
import queue
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("gui.agent_controller")


class AgentStatus(Enum):
    """Agent status enum."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class AgentEvent:
    """Event data from agent to GUI."""
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class AgentSignals:
    """
    Signal-like pattern for customtkinter.
    Uses callbacks instead of Qt Signals.
    Thread-safe communication from Agent thread to GUI thread.
    """
    
    def __init__(self):
        self._callbacks: Dict[str, List[Callable]] = {
            'status_changed': [],
            'packet_captured': [],
            'log_received': [],
            'error_occurred': [],
            'stats_updated': [],
            'whitelist_synced': [],
        }
        self._event_queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
    
    def connect(self, signal_name: str, callback: Callable) -> bool:
        """Connect a callback to a signal."""
        with self._lock:
            if signal_name in self._callbacks:
                self._callbacks[signal_name].append(callback)
                return True
            return False
    
    def disconnect(self, signal_name: str, callback: Callable) -> bool:
        """Disconnect a callback from a signal."""
        with self._lock:
            if signal_name in self._callbacks and callback in self._callbacks[signal_name]:
                self._callbacks[signal_name].remove(callback)
                return True
            return False
    
    def emit(self, signal_name: str, data: Any = None):
        """
        Queue an event to be processed by GUI thread.
        This is thread-safe and won't block.
        """
        event = AgentEvent(
            event_type=signal_name,
            data=data if data else {},
            timestamp=self._get_timestamp()
        )
        self._event_queue.put(event)
    
    def process_events(self, root) -> None:
        """
        Process queued events in GUI thread.
        Call this from customtkinter's after() loop.
        """
        try:
            while True:
                try:
                    event = self._event_queue.get_nowait()
                    self._dispatch_event(event)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error processing events: {e}")
        
        # Schedule next check (every 100ms)
        if root and root.winfo_exists():
            root.after(100, lambda: self.process_events(root))
    
    def _dispatch_event(self, event: AgentEvent):
        """Dispatch event to registered callbacks."""
        with self._lock:
            callbacks = self._callbacks.get(event.event_type, []).copy()
        
        for callback in callbacks:
            try:
                callback(event.data)
            except Exception as e:
                logger.error(f"Error in callback for {event.event_type}: {e}")
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        try:
            from shared.time_utils import now
            return now()
        except ImportError:
            import time
            return time.time()


class AgentController:
    """
    Controller bridging GUI and Core Agent.
    Runs agent in separate thread to keep GUI responsive.
    """
    
    _instance: Optional['AgentController'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Signals for GUI communication
        self.signals = AgentSignals()
        
        # Agent state
        self._status = AgentStatus.STOPPED
        self._agent = None
        self._config = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Statistics
        self._stats = {
            'packets_captured': 0,
            'domains_detected': 0,
            'blocked_count': 0,
            'allowed_count': 0,
            'uptime_seconds': 0,
        }
        
        self._root = None  # Reference to CTk root for after()
        
        logger.info("AgentController initialized")
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def is_running(self) -> bool:
        return self._status == AgentStatus.RUNNING
    
    @property
    def stats(self) -> Dict:
        return self._stats.copy()
    
    def set_root(self, root) -> None:
        """Set CTk root and start event processing."""
        self._root = root
        # Start processing events in GUI thread
        self.signals.process_events(root)
    
    def start_agent(self) -> bool:
        """
        Start agent in background thread.
        Returns immediately, status updates via signals.
        """
        if self._status in [AgentStatus.RUNNING, AgentStatus.STARTING]:
            logger.warning("Agent already running or starting")
            return False
        
        self._status = AgentStatus.STARTING
        self.signals.emit('status_changed', {'status': 'starting'})
        
        # Reset stop event
        self._stop_event.clear()
        
        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._agent_worker,
            daemon=True,
            name="AgentWorker"
        )
        self._worker_thread.start()
        
        logger.info("Agent worker thread started")
        return True
    
    def stop_agent(self) -> bool:
        """
        Stop agent gracefully.
        Returns immediately, status updates via signals.
        """
        if self._status not in [AgentStatus.RUNNING, AgentStatus.STARTING]:
            logger.warning("Agent not running")
            return False
        
        self._status = AgentStatus.STOPPING
        self.signals.emit('status_changed', {'status': 'stopping'})
        
        # Signal worker to stop
        self._stop_event.set()
        
        # Stop agent components
        if self._agent:
            self._agent.stop()
        
        logger.info("Agent stop requested")
        return True
    
    def _agent_worker(self):
        """
        Worker thread - runs agent components.
        This runs in background, communicates via signals.
        """
        try:
            logger.info("Agent worker starting...")
            
            # Import agent components
            from config import get_config
            from core import get_agent, initialize_components, cleanup
            from shared.time_utils import sleep, uptime_string
            
            # Get agent instance
            self._agent = get_agent()
            
            # Load configuration
            logger.info("Loading configuration...")
            self._config = get_config()
            
            # Ensure device ID
            from core import AGENT_DEVICE_ID
            self._config["device_id"] = AGENT_DEVICE_ID
            
            # Initialize components
            logger.info("Initializing components...")
            if not initialize_components(self._config):
                raise RuntimeError("Component initialization failed")
            
            # Connect WhitelistController to agent's WhitelistManager
            if self._agent.whitelist:
                from .whitelist_controller import WhitelistController
                whitelist_ctrl = WhitelistController()
                whitelist_ctrl.set_whitelist_manager(self._agent.whitelist)
                logger.info("WhitelistController connected to WhitelistManager")
            
            # Mark as running
            self._status = AgentStatus.RUNNING
            self.signals.emit('status_changed', {
                'status': 'running',
                'message': 'Agent started successfully'
            })
            
            logger.info("Agent running - entering main loop")
            
            # Main loop
            loop_count = 0
            while not self._stop_event.is_set() and self._agent.running:
                sleep(1)
                loop_count += 1
                
                # Update stats every second
                self._update_stats()
                
                # Emit stats every 5 seconds
                if loop_count % 5 == 0:
                    self.signals.emit('stats_updated', self._stats.copy())
                    logger.debug(f"Agent loop #{loop_count}, uptime: {uptime_string()}")
            
            logger.info("Agent worker loop ended")
            
        except Exception as e:
            logger.error(f"Agent worker error: {e}", exc_info=True)
            self._status = AgentStatus.ERROR
            self.signals.emit('error_occurred', {
                'error': str(e),
                'message': 'Agent encountered an error'
            })
        
        finally:
            # Cleanup
            try:
                from core import cleanup
                cleanup(self._config)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            self._status = AgentStatus.STOPPED
            self.signals.emit('status_changed', {
                'status': 'stopped',
                'message': 'Agent stopped'
            })
            
            logger.info("Agent worker finished")
    
    def _update_stats(self):
        """Update internal statistics."""
        try:
            from shared.time_utils import uptime
            self._stats['uptime_seconds'] = int(uptime())
            
            # Get stats from components if available
            if self._agent:
                # Whitelist stats
                if self._agent.whitelist and hasattr(self._agent.whitelist, '_state'):
                    whitelist_stats = self._agent.whitelist._state.get_stats()
                    self._stats['domains_count'] = whitelist_stats.get('domains_count', 0)
                    self._stats['patterns_count'] = whitelist_stats.get('patterns_count', 0)
                    self._stats['ips_count'] = whitelist_stats.get('ips_count', 0)
                
                # Sniffer stats (if available)
                if self._agent.sniffer and hasattr(self._agent.sniffer, 'packet_count'):
                    self._stats['packets_captured'] = getattr(self._agent.sniffer, 'packet_count', 0)
                
                # Log sender stats
                if self._agent.log_sender and hasattr(self._agent.log_sender, 'get_status'):
                    sender_status = self._agent.log_sender.get_status()
                    self._stats['logs_sent'] = sender_status.get('logs_sent', 0)
                    self._stats['queue_size'] = sender_status.get('queue_size', 0)
                    
        except Exception as e:
            logger.debug(f"Stats update error: {e}")
    
    def get_agent_info(self) -> Dict:
        """Get current agent information."""
        info = {
            'status': self._status.name,
            'is_running': self.is_running,
            'stats': self._stats.copy(),
        }
        
        if self._agent:
            info['hostname'] = self._agent.hostname
            info['device_id'] = self._agent.device_id
            info['agent_id'] = self._agent.get_agent_id()
            info['is_registered'] = self._agent.is_registered()
        
        if self._config:
            info['firewall_mode'] = self._config.get('firewall', {}).get('mode', 'unknown')
            info['firewall_enabled'] = self._config.get('firewall', {}).get('enabled', False)
        
        return info
    
    def get_stats(self) -> Dict:
        """Get current agent statistics."""
        return self._stats.copy()
    
    def force_whitelist_sync(self) -> bool:
        """Force immediate whitelist sync."""
        if not self.is_running or not self._agent:
            return False
        
        try:
            if self._agent.whitelist:
                success = self._agent.whitelist.sync_now()
                if success:
                    self.signals.emit('whitelist_synced', {'success': True})
                return success
        except Exception as e:
            logger.error(f"Force sync error: {e}")
            self.signals.emit('error_occurred', {'error': str(e)})
        
        return False


# Global controller instance
def get_agent_controller() -> AgentController:
    """Get the global agent controller instance."""
    return AgentController()
