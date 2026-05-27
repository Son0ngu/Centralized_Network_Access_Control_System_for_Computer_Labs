"""
CSRF middleware (double-submit cookie pattern).

Why this exists
---------------
The admin web UI authenticates via httpOnly cookies (`access_token` /
`refresh_token`) set by ``WebAuthController``. With ``SameSite=Lax`` modern
browsers won't attach these cookies to a cross-site POST/PUT/PATCH/DELETE
triggered by a `<form>` from a different origin, which already blocks the
naive form-based CSRF flow.

But ``Lax`` is not a complete defence:

- Cookies are shared across sub-domains under the same eTLD+1, so a hostile
  page on ``evil.example.com`` can still mount a CSRF against
  ``admin.example.com``.
- Older browsers, edge ``Lax`` quirks (top-level navigations, prefetches),
  and proxies that strip ``SameSite`` make the cookie-only defence brittle.

This middleware adds a defence-in-depth layer on top of SameSite: a
double-submit cookie token. The server mints a random ``csrf_token`` on
login and stores it in a **non-httpOnly** cookie so client JS (``SaintAPI``)
can read it and echo it back in an ``X-CSRF-Token`` header. A cross-origin
attacker cannot read the cookie (Same-Origin Policy) and therefore cannot
forge the header, even if the browser were to leak the auth cookie.

Scope
-----
- Cookie-authenticated state-changing requests (POST / PUT / PATCH / DELETE)
  to admin paths are gated.
- Agent endpoints that authenticate via ``Authorization: Bearer …`` or
  ``X-API-Key`` are exempt: browsers do not auto-attach these headers, so
  the CSRF threat model does not apply.
- ``/admin/auth/login`` and ``/admin/auth/refresh`` are exempt because no
  authenticated session exists yet (the auth cookie is what we'd be
  protecting; until login completes there is nothing to protect).

Config gate
-----------
``ENFORCE_CSRF`` (default True). Set to False to disable enforcement, e.g.
in unit tests that don't want to mint cookies. Token minting always happens
on login so clients still get a working cookie when enforcement is later
re-enabled.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from typing import Optional

from flask import Flask, Response, g, jsonify, request

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Methods that need protection. ``HEAD`` / ``GET`` / ``OPTIONS`` / ``TRACE``
# are by definition safe (RFC 9110 §9.2.1).
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths exempt from CSRF enforcement.
# All admin blueprints mount under ``/api`` (see bootstrap/container.py), so
# the real URLs include the prefix.
# - ``/api/admin/auth/login``: no session to protect yet — the cookie we
#   would be defending doesn't exist.
# - ``/api/admin/auth/refresh``: cookie + SameSite already block cross-site
#   forging; skipping avoids kicking out idle tabs whose page-side script
#   hasn't yet picked up a rotated csrf cookie.
# - ``/api/auth/*`` and ``/api/agents/register``: agent paths that
#   authenticate via Bearer header or API key, not cookies.
_EXEMPT_PATH_PREFIXES = (
    "/api/admin/auth/login",
    "/api/admin/auth/refresh",
    "/api/auth/",
    "/api/agents/register",
)


def _config_value(name: str, default):
    """Look up a config value off the Flask config or installed config object."""
    try:
        from database.config import get_config_by_name
        return getattr(get_config_by_name(), name, default)
    except Exception:
        return default


def _enforce_csrf_enabled() -> bool:
    return bool(_config_value("ENFORCE_CSRF", True))


def _cookie_secure() -> bool:
    return bool(_config_value("ADMIN_COOKIE_SECURE", False))


def mint_csrf_token() -> str:
    """Return a fresh CSRF token (32 random bytes, hex encoded)."""
    return secrets.token_hex(32)


def set_csrf_cookie(response: Response, token: Optional[str] = None) -> str:
    """
    Attach the CSRF cookie to ``response``. Returns the token actually set so
    the caller can also include it in the JSON body for clients that prefer
    a single round-trip.

    Important: this cookie is intentionally NOT ``httponly`` — the page JS
    needs to read it and echo it back in the request header. The auth
    cookies remain httpOnly; the CSRF cookie alone is not a credential.
    """
    if token is None:
        token = mint_csrf_token()
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,
        secure=_cookie_secure(),
        samesite="Lax",
        path="/",
        # Match the access-token lifetime; the cookie is rotated on refresh.
        max_age=86400,
    )
    return token


def delete_csrf_cookie(response: Response) -> None:
    """Clear the CSRF cookie (called on logout)."""
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def _is_exempt_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _EXEMPT_PATH_PREFIXES)


def _is_bearer_or_api_key_request() -> bool:
    """A request authenticated by header credentials is not CSRF-vulnerable.

    Browsers do not auto-attach ``Authorization`` or ``X-API-Key`` headers,
    so an attacker on another origin cannot trigger such a request with the
    victim's credentials. We can safely skip CSRF for these.
    """
    if request.headers.get("X-API-Key"):
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith(("Bearer ", "ApiKey ")):
        # Distinguish from the admin cookie path: the admin web UI never
        # sends Authorization (it relies on the cookie), so a request with
        # Authorization is an API client.
        return True
    return False


def _csrf_failure(reason: str):
    logger.warning(
        "CSRF check failed: %s — method=%s path=%s",
        reason, request.method, request.path,
    )
    return jsonify({
        "success": False,
        "error": "CSRF token missing or invalid",
        "code": "CSRF_FAIL",
    }), 403


def _check_csrf():
    """
    Flask ``before_request`` hook: enforce CSRF on cookie-authed mutations.

    Returning a non-None value short-circuits the request — Flask will use
    it as the response. Returning None means "let the request continue".
    """
    if not _enforce_csrf_enabled():
        return None

    if request.method not in _UNSAFE_METHODS:
        return None

    if _is_exempt_path(request.path):
        return None

    if _is_bearer_or_api_key_request():
        return None

    # At this point we expect a cookie-authenticated browser request to a
    # mutating admin endpoint. Require the double-submit token.
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token:
        return _csrf_failure("missing csrf cookie")
    if not header_token:
        return _csrf_failure("missing X-CSRF-Token header")

    # Constant-time comparison to avoid timing oracles.
    if not hmac.compare_digest(cookie_token, header_token):
        return _csrf_failure("token mismatch")

    # Stash on g so handlers can choose to rotate the token if they want.
    g.csrf_token = cookie_token
    return None


def register_csrf(app: Flask) -> None:
    """Install the CSRF check as a global before_request hook."""
    app.before_request(_check_csrf)
    logger.info(
        "CSRF middleware registered (enforce=%s)",
        _enforce_csrf_enabled(),
    )
