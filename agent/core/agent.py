import hashlib
import logging
import platform
import socket
import subprocess
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger("core.agent")

def _hash_ids(ids: List[str]) -> str:
    joined = "|".join(ids).encode("utf-8", errors="ignore")
    return hashlib.sha256(joined).hexdigest()[:24]


def _windows_hardware_ids() -> List[str]:
    ids: List[str] = []

    def _ps(command: str) -> Optional[str]:
        try:
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", command],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            cleaned = output.strip()
            return cleaned or None
        except Exception:
            return None

    ids.append(_ps("(Get-CimInstance Win32_BIOS).SerialNumber"))
    ids.append(_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber"))
    ids.append(_ps("(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).SerialNumber"))

    return [i for i in ids if i]

def generate_device_id() -> str:
    try:
        system = platform.system().lower()

        hardware_ids: List[str] = []
        hardware_ids = _windows_hardware_ids()
        hardware_ids = [i for i in hardware_ids if i]

        if hardware_ids:
            return _hash_ids(hardware_ids)

        mac = uuid.getnode()
        mac_hex = f"{mac:012x}"
        return _hash_ids([mac_hex, platform.platform()])
    except Exception as e:
        logger.warning(f"Could not generate device ID, falling back to hostname: {e}")
        return socket.gethostname().strip() or "UnknownDevice"

AGENT_HOSTNAME = socket.gethostname().strip() or "Unknown Agent"
AGENT_DEVICE_ID = generate_device_id()

agent_state: Dict = {
    "startup_completed": False,
    "registration_completed": False,
    "components_initialized": False,
    "initialization_completed": False,
    "initialization_time": None,
    "admin_privileges": False,
    "local_ip": None,
    "agent_id": None,
    "dns_proxy_mode": None,  # DNS Proxy operating mode
}
class Agent:
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
        
        self.config: Optional[Dict] = None
        self.firewall = None
        self.whitelist = None
        self.log_sender = None
        self.heartbeat = None  
        
        # DNS Proxy System (Phase 1 - Proactive DNS Control)
        self.dns_proxy_orchestrator = None  # DNSProxyOrchestrator instance
        
        # Legacy: PacketSniffer (now optional - bypass detection only)
        self.sniffer = None  
        self.packet_sniffer = None
        self.heartbeat_sender = None
        
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
        agent_state.update(kwargs)
    
    def get_agent_id(self) -> Optional[str]:
        if self.config:
            return self.config.get('agent_id')
        return agent_state.get('agent_id')
    
    def get_agent_token(self) -> Optional[str]:
        if self.config:
            return self.config.get('agent_token')
        return None
    
    def is_registered(self) -> bool:
        return agent_state.get('registration_completed', False)
    
    def is_running(self) -> bool:
        return self.running and agent_state.get('startup_completed', False)
    
    def stop(self):
        self.running = False

def get_agent() -> Agent:
    return Agent()