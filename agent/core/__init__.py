"""SAINT agent ``core`` package — runtime, lifecycle, identity.

Lazy device identity:

  ``from agent.core import AGENT_DEVICE_ID`` and
  ``from agent.core.agent import AGENT_DEVICE_ID`` both still work as before
  for consumers, but the actual hardware probe (PowerShell CIM calls) only
  fires on first read via :class:`DeviceIdentityProvider`. See the docstring
  in ``agent/core/agent.py`` for the rationale.

  New code should prefer ``DeviceIdentityProvider.get_device_id()`` /
  ``.get_hostname()`` — they're explicit about the lazy compute and they
  expose ``.reset()`` for tests.
"""

from .agent import (
    Agent,
    AgentRuntime,
    agent_state,
    DeviceIdentityProvider,
    generate_device_id,
    get_agent,
    make_runtime,
)
from .lifecycle import (
    initialize_components,
    cleanup,
    build_lifecycle_log,
    InitResult,
    ComponentStatus,
    LifecycleContext,
    AgentComponent,
    build_default_components,
    start_components,
    stop_components,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_DEGRADED,
    STATUS_FAILED,
)
from .registry import register_agent, try_register_with_server
from .handlers import handle_domain_detection, create_domain_handler
from .token_manager import (
    TokenManager,
    init_token_manager,
    get_token_manager,
    get_auth_headers
)


def __getattr__(name: str):
    """Lazy package-level attributes for the legacy module-constant API.

    Mirrors the same trick we use in ``agent.core.agent`` so a caller doing
    ``from agent.core import AGENT_DEVICE_ID`` still doesn't trigger the
    PowerShell probe unless they actually name the symbol. Without this hook
    the eager import below would defeat the laziness.
    """
    if name == "AGENT_DEVICE_ID":
        return DeviceIdentityProvider.get_device_id()
    if name == "AGENT_HOSTNAME":
        return DeviceIdentityProvider.get_hostname()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'Agent',
    'AgentRuntime',
    'get_agent',
    'make_runtime',
    'agent_state',
    'AGENT_HOSTNAME',
    'AGENT_DEVICE_ID',
    'DeviceIdentityProvider',
    'generate_device_id',
    'initialize_components',
    'cleanup',
    'build_lifecycle_log',
    'InitResult',
    'ComponentStatus',
    'LifecycleContext',
    'AgentComponent',
    'build_default_components',
    'start_components',
    'stop_components',
    'STATUS_OK',
    'STATUS_SKIPPED',
    'STATUS_DEGRADED',
    'STATUS_FAILED',
    'register_agent',
    'try_register_with_server',
    'handle_domain_detection',
    'create_domain_handler',
    'TokenManager',
    'init_token_manager',
    'get_token_manager',
    'get_auth_headers'
]
