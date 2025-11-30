"""
Services module - Background services for the agent.
Vietnam ONLY - Modular implementation.
"""

from .heartbeat import HeartbeatSender
from .windows_service import run_as_service

__all__ = ['HeartbeatSender', 'run_as_service']