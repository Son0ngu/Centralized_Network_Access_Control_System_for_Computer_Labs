"""
Core agent module - Main agent logic and lifecycle management.
Vietnam ONLY - Modular implementation.
"""

from .agent import Agent, agent_state, AGENT_HOSTNAME, AGENT_DEVICE_ID, get_agent
from .lifecycle import initialize_components, cleanup, build_lifecycle_log
from .registry import register_agent, try_register_with_server
from .handlers import handle_domain_detection, create_domain_handler
from .token_manager import (
    TokenManager,
    init_token_manager,
    get_token_manager,
    get_auth_headers
)

__all__ = [
    'Agent',
    'get_agent',
    'agent_state',
    'AGENT_HOSTNAME',
    'AGENT_DEVICE_ID',
    'initialize_components',
    'cleanup',
    'build_lifecycle_log',
    'register_agent',
    'try_register_with_server',
    'handle_domain_detection',
    'create_domain_handler',
    'TokenManager',
    'init_token_manager',
    'get_token_manager',
    'get_auth_headers'
]