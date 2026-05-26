"""
Request IP helpers.

Centralizes client IP detection so audit logs, agent requests, and auth logs
use the same proxy-aware behavior.
"""

from flask import request


def _first_header_ip(value: str) -> str | None:
    """Return the first non-empty IP token from a comma-separated header."""
    if not value:
        return None

    for token in value.split(","):
        candidate = token.strip()
        if candidate:
            return candidate
    return None


def get_client_ip(default: str = "unknown") -> str:
    """
    Resolve the best client IP visible to Flask.

    Reverse proxies should set X-Forwarded-For or X-Real-IP. When those
    headers are absent, this falls back to request.remote_addr.
    """
    try:
        forwarded_for = _first_header_ip(request.headers.get("X-Forwarded-For", ""))
        if forwarded_for:
            return forwarded_for

        real_ip = request.headers.get("X-Real-IP", "").strip()
        if real_ip:
            return real_ip

        return request.remote_addr or default
    except RuntimeError:
        return default
