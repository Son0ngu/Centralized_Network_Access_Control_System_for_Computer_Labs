import hashlib
import logging
import platform
import socket
import subprocess
import threading
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


class DeviceIdentityProvider:
    """Lazy, cached accessor for the per-host SAINT device id.

    Why lazy: ``generate_device_id`` shells out to PowerShell (CIM/WMI calls)
    and can take 0.5-2s. Doing that at module-import time meant every
    ``import agent.core`` paid the cost, including unit tests that don't
    need the value. Now the price is paid on first read.

    Why a class with class-level cache (not just a function with @lru_cache):
    tests can call :meth:`reset` between cases without monkey-patching, and
    the cache is shared across all threads (the lock makes concurrent first
    reads safe).
    """

    _cached_device_id: Optional[str] = None
    _cached_hostname: Optional[str] = None
    _lock = threading.Lock()

    @classmethod
    def get_device_id(cls) -> str:
        """Return the cached hardware-derived device id (compute on first call)."""
        # Double-checked locking — cheap read in the steady state.
        if cls._cached_device_id is not None:
            return cls._cached_device_id
        with cls._lock:
            if cls._cached_device_id is None:
                cls._cached_device_id = generate_device_id()
            return cls._cached_device_id

    @classmethod
    def get_hostname(cls) -> str:
        """Return the OS hostname, cached after first read."""
        if cls._cached_hostname is not None:
            return cls._cached_hostname
        with cls._lock:
            if cls._cached_hostname is None:
                cls._cached_hostname = socket.gethostname().strip() or "Unknown Agent"
            return cls._cached_hostname

    @classmethod
    def reset(cls) -> None:
        """Clear the cache (for tests that mock ``generate_device_id``)."""
        with cls._lock:
            cls._cached_device_id = None
            cls._cached_hostname = None


def __getattr__(name: str):
    """Module-level lazy attributes for ``AGENT_DEVICE_ID`` / ``AGENT_HOSTNAME``.

    PEP 562 hook: ``from agent.core.agent import AGENT_DEVICE_ID`` still works
    as before from the caller's perspective, but generation now happens
    on first attribute access rather than at module import. Callers that
    import the module without naming these attributes (most tests, the Qt
    GUI startup path) skip the PowerShell calls entirely.

    Anything else still raises ``AttributeError`` as usual.
    """
    if name == "AGENT_DEVICE_ID":
        return DeviceIdentityProvider.get_device_id()
    if name == "AGENT_HOSTNAME":
        return DeviceIdentityProvider.get_hostname()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def _new_default_state() -> Dict:
    """Fresh ``state`` dict — every AgentRuntime owns its own."""
    return {
        "startup_completed": False,
        "registration_completed": False,
        "components_initialized": False,
        "initialization_completed": False,
        "initialization_time": None,
        "admin_privileges": False,
        "local_ip": None,
        "agent_id": None,
    }


# Process-wide shared state dict. Backwards-compat: lots of code does
# ``from agent.core.agent import agent_state`` and reads/writes the dict in
# place. We keep that contract — the singleton ``Agent`` aliases its
# ``state`` property to this dict so reads stay coherent.
agent_state: Dict = _new_default_state()


class AgentRuntime:
    """Plain-data runtime container for an agent process.

    Holds per-process state (config, attached component handles, run flag)
    and exposes the device identity properties. No singleton enforcement —
    construct as many as you need (tests, multi-tenant test harnesses).

    Why this exists separately from :class:`Agent`:

      The original ``Agent`` class was a singleton via ``__new__``. Production
      callers (``lifecycle.initialize_components``, ``QtMainWindow``,
      ``registry.try_register_with_server``) all reach for "the agent" via
      :func:`get_agent` and assume one process = one runtime. That contract
      is fine for production but hostile to tests and any future
      multi-tenant scenario.

      ``AgentRuntime`` provides the constructor-injection surface. Code that
      can take a runtime as a parameter should do so; code stuck on the
      singleton continues to call :func:`get_agent`. Migration is opt-in.

    Field grid:

      ``config``           — dict loaded from ``agent/config/defaults.py``
                             + on-disk overrides; populated by the
                             lifecycle once registration succeeds.
      ``firewall`` etc.    — handles to component services started by the
                             lifecycle. ``None`` until ``start_components``
                             attaches them. Setting them on the runtime is
                             how the worker thread shares them with the GUI.
      ``state``            — fast-read shared dict (startup_completed,
                             registration_completed, …). Independent
                             default dict per runtime so two runtimes
                             don't trample each other.
      ``running``          — boolean flag flipped by :meth:`stop` to
                             request graceful shutdown.
    """

    def __init__(self, state: Optional[Dict] = None):
        self.config: Optional[Dict] = None
        self.firewall = None
        self.whitelist = None
        self.log_sender = None
        self.sniffer = None
        self.heartbeat = None
        self.packet_sniffer = None
        self.heartbeat_sender = None
        self.running = True
        # Tests can inject a pre-populated state dict; production gets a
        # fresh one. Defaulting to the shared module-level ``agent_state``
        # is intentional for the singleton; new runtimes get their own.
        self._state: Dict = state if state is not None else _new_default_state()

    # ------------------------------------------------------------------
    # Identity — delegated to the lazy provider so test rigs don't pay
    # the PowerShell cost just by constructing a runtime.
    # ------------------------------------------------------------------

    @property
    def hostname(self) -> str:
        return DeviceIdentityProvider.get_hostname()

    @property
    def device_id(self) -> str:
        return DeviceIdentityProvider.get_device_id()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> Dict:
        return self._state

    def update_state(self, **kwargs) -> None:
        self._state.update(kwargs)

    def get_agent_id(self) -> Optional[str]:
        if self.config:
            return self.config.get('agent_id')
        return self._state.get('agent_id')

    def get_agent_token(self) -> Optional[str]:
        if self.config:
            return self.config.get('agent_token')
        return None

    def is_registered(self) -> bool:
        return self._state.get('registration_completed', False)

    def is_running(self) -> bool:
        return self.running and self._state.get('startup_completed', False)

    def stop(self) -> None:
        """Signal a graceful shutdown to anything polling ``is_running``."""
        self.running = False


class Agent(AgentRuntime):
    """Singleton :class:`AgentRuntime` for legacy ``get_agent()`` callers.

    Why keep the singleton wrapper:

      Lots of code does ``Agent().firewall = manager`` or
      ``from agent.core.agent import agent_state``. Migrating every site to
      pass a runtime down the call chain is a much bigger change than the
      current cleanup pass justifies. The singleton stays, but it now
      *is-a* AgentRuntime — so new code can take ``AgentRuntime`` as a type
      hint and accept either the production singleton or a test runtime
      without branching.

    Notable: the singleton's ``_state`` is the module-level ``agent_state``
    dict, so anyone doing ``from .agent import agent_state`` continues to
    see in-place mutations. A non-singleton ``AgentRuntime()`` gets its
    own state dict.
    """

    _instance: Optional['Agent'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def reset_for_test(cls) -> None:
        """Drop the singleton so the next ``get_agent()`` returns a fresh one."""
        cls._instance = None

    def __init__(self):
        if self._initialized:
            return
        # Bind the runtime to the shared module-level ``agent_state`` so
        # legacy ``from .agent import agent_state`` callers see the same dict.
        super().__init__(state=agent_state)
        self._initialized = True
        logger.debug("Agent singleton initialized")


def get_agent() -> Agent:
    """Return the process-wide singleton agent runtime."""
    return Agent()


def make_runtime(state: Optional[Dict] = None) -> AgentRuntime:
    """Construct a fresh, non-singleton :class:`AgentRuntime`.

    Use this in tests or anywhere you need isolation from the singleton.
    Production startup keeps calling :func:`get_agent`.
    """
    return AgentRuntime(state=state)