"""
Agent State Management - Global state and device identification.
Vietnam ONLY - Clean implementation.
"""

import logging
import platform
import socket
import uuid
from typing import Dict, Optional

logger = logging.getLogger("core.agent")


def generate_device_id() -> str:
    """Create a stable device identifier using MAC + system fingerprint."""
    try:
        mac = uuid.getnode()
        mac_hex = f"{mac:012x}"
        
        system_fingerprint = f"{platform.system()}-{platform.release()}-{platform.machine()}"
        hashed_fingerprint = uuid.uuid5(uuid.NAMESPACE_DNS, system_fingerprint).hex[:12]
        
        return f"{mac_hex}-{hashed_fingerprint}"
    except Exception as e:
        logger.warning(f"Could not generate device ID, falling back to hostname: {e}")
        return socket.gethostname().strip() or "UnknownDevice"


# Global constants
AGENT_HOSTNAME = socket.gethostname().strip() or "Unknown Agent"
AGENT_DEVICE_ID = generate_device_id()

# Agent state tracking
agent_state: Dict = {
    "startup_completed": False,
    "registration_completed": False,
    "components_initialized": False,
    "initialization_completed": False,
    "initialization_time": None,
    "admin_privileges": False,
    "local_ip": None,
    "agent_id": None
}


class Agent:
    """
    Agent singleton for managing global state and components.
    """
    
    _instance: Optional['Agent'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Component references - ALL components must be defined here
        self.config: Optional[Dict] = None
        self.firewall = None
        self.whitelist = None
        self.log_sender = None
        self.sniffer = None  # FIX: Add sniffer attribute
        self.heartbeat = None  # FIX: Add heartbeat attribute
        
        # Legacy aliases for backward compatibility
        self.packet_sniffer = None
        self.heartbeat_sender = None
        
        # State
        self.running = True
        
        logger.debug("Agent singleton initialized")
    
    @property
    def hostname(self) -> str:
        return AGENT_HOSTNAME
    
    @property
    def device_id(self) -> str:
        return AGENT_DEVICE_ID
    
    @property
    def state(self) -> Dict:
        return agent_state
    
    def update_state(self, **kwargs):
        """Update agent state."""
        agent_state.update(kwargs)
    
    def get_agent_id(self) -> Optional[str]:
        """Get current agent ID."""
        if self.config:
            return self.config.get('agent_id')
        return agent_state.get('agent_id')
    
    def get_agent_token(self) -> Optional[str]:
        """Get current agent token."""
        if self.config:
            return self.config.get('agent_token')
        return None
    
    def is_registered(self) -> bool:
        """Check if agent is registered."""
        return agent_state.get('registration_completed', False)
    
    def is_running(self) -> bool:
        """Check if agent is running."""
        return self.running and agent_state.get('startup_completed', False)
    
    def stop(self):
        """Signal agent to stop."""
        self.running = False


# Global agent instance
def get_agent() -> Agent:
    """Get the global agent instance."""
    return Agent()