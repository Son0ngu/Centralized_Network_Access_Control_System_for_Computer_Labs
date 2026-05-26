"""
DEPRECATED module path - kept as a shim for backwards compatibility.

The implementation has moved to ``controllers/web_auth_controller.py`` and the
class is now called :class:`WebAuthController`. The old import path

    from controllers.admin_auth_controller import AdminAuthController

still works because we re-export the alias below, but new code should import
``WebAuthController`` directly from ``controllers.web_auth_controller``.
This shim will be removed once all callers (and external integrators, if any)
have migrated.
"""

from controllers.web_auth_controller import (  # noqa: F401
    WebAuthController,
    AdminAuthController,
    COOKIE_ACCESS_NAME,
    COOKIE_REFRESH_NAME,
    COOKIE_HTTPONLY,
    COOKIE_SAMESITE,
    COOKIE_PATH,
    _cookie_secure,
)

__all__ = ["WebAuthController", "AdminAuthController"]
