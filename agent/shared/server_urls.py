"""Centralized agent → server URL resolver.

The agent has several components (registration, whitelist sync, heartbeat,
log sender) that need the list of server URLs to call. Historically each
one had its own resolver and silently fell back to ``http://localhost:5000``
when the user hadn't configured anything yet. That made "offline mode" mean
different things in different components: registration would skip, but
whitelist/heartbeat/log sender would happily contact a local address.

This module is the single source of truth. By default (production), an empty
config yields an empty list and the calling component must treat that as
"OFFLINE — skip work until the user sets a URL in Settings." A development
build (or test) may opt in to the localhost fallback explicitly.
"""

from typing import Dict, Iterable, List, Optional

DEV_DEFAULT_URL = "http://localhost:5000"


def collect_server_urls(config: Optional[Dict], allow_dev_default: bool = False) -> List[str]:
    """Return a deduplicated list of server URLs to try.

    Args:
        config: Agent config dict (may be None).
        allow_dev_default: When True and no URL is configured, return
            ``[DEV_DEFAULT_URL]`` so local dev/test runs keep working.
            Production callers MUST leave this False so an unconfigured
            agent silently stays offline instead of leaking to localhost.
    """
    urls: List[str] = []
    if not config:
        return [DEV_DEFAULT_URL] if allow_dev_default else []

    server_cfg = config.get("server") or {}

    raw_urls: Iterable = server_cfg.get("urls") or []
    if isinstance(raw_urls, (list, tuple)):
        urls.extend(str(u) for u in raw_urls)

    primary = server_cfg.get("url") or config.get("server_url")
    if primary:
        urls.append(str(primary))

    # Strip + dedupe, preserving order
    seen = set()
    cleaned: List[str] = []
    for u in urls:
        stripped = u.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        cleaned.append(stripped)

    if cleaned:
        return cleaned

    return [DEV_DEFAULT_URL] if allow_dev_default else []
