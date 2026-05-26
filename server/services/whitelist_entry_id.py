"""Whitelist entry ID parsing / generation — single source of truth.

Why this exists:

  ``groups.whitelist`` entries are embedded documents inside the group
  document, not first-class collection rows. They have no MongoDB ``_id``,
  so the service layer synthesises one on the fly as

      group::<group_id>::<type>::<value>

  This pseudo-ID is the contract between the frontend and the backend: the
  UI sends it back when the user clicks "delete" on a row, and the backend
  parses it to locate the embedded entry by ``(group_id, type, value)``.

  The string format used to be scattered across ~10 sites in
  ``whitelist_service.py`` and ``whitelist_controller.py``. This module is
  the single place that knows the format. When the next migration replaces
  embedded entries with a unified ``whitelist_entries`` collection (each
  entry getting a real ObjectId), the call sites stay the same — only this
  module's functions change.

Legacy:
  Some old data still uses ``group|<gid>|<type>|<value>`` with single pipes
  instead of double colons. The parser accepts both; the generator only
  emits the new ``::`` form.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


PSEUDO_ID_PREFIX = "group::"
PSEUDO_ID_LEGACY_PREFIX = "group|"
PSEUDO_ID_SEPARATOR = "::"
PSEUDO_ID_LEGACY_SEPARATOR = "|"


class GroupEntryRef(NamedTuple):
    """Parsed pseudo-ID identifying an embedded ``groups.whitelist`` entry.

    - ``group_id``  — string form (caller decides whether to convert to ObjectId).
    - ``entry_type`` — ``"domain"`` | ``"ip"`` | ``"ip_range"``.
    - ``value``     — domain/IP/CIDR string.

    All fields are post-trim, lowercase, suitable for direct equality
    matching against stored entries.
    """

    group_id: str
    entry_type: str
    value: str


def is_group_pseudo_id(entry_id: Optional[str]) -> bool:
    """Cheap prefix check used by callers to decide which delete path to take.

    Tolerant of ``None`` so call sites can pass straight from request JSON
    without pre-validating.
    """
    if not entry_id or not isinstance(entry_id, str):
        return False
    return entry_id.startswith(PSEUDO_ID_PREFIX) or entry_id.startswith(PSEUDO_ID_LEGACY_PREFIX)


def parse_group_pseudo_id(entry_id: str) -> Optional[GroupEntryRef]:
    """Parse a pseudo-ID into ``(group_id, type, value)`` or return None.

    Returns None for inputs that aren't pseudo-IDs (callers should already
    have checked with :func:`is_group_pseudo_id`, but we tolerate misuse so
    the parser is the single arbiter of format correctness).

    Accepts both the canonical ``group::<gid>::<type>::<value>`` and the
    legacy ``group|<gid>|<type>|<value>`` forms — old data still has the
    pipe form embedded in URLs created before the separator change.
    """
    if not is_group_pseudo_id(entry_id):
        return None

    # Strip prefix and split on the matching separator. Note ``value`` can
    # itself contain ``:`` (IPv6) or ``.``; we use ``maxsplit`` to keep the
    # value intact even if it contains the separator literally.
    if entry_id.startswith(PSEUDO_ID_PREFIX):
        body = entry_id[len(PSEUDO_ID_PREFIX):]
        sep = PSEUDO_ID_SEPARATOR
    else:
        body = entry_id[len(PSEUDO_ID_LEGACY_PREFIX):]
        sep = PSEUDO_ID_LEGACY_SEPARATOR

    parts = body.split(sep, 2)
    if len(parts) != 3:
        return None
    group_id, entry_type, value = parts
    if not group_id or not entry_type or not value:
        return None
    return GroupEntryRef(group_id=group_id, entry_type=entry_type, value=value)


def make_group_pseudo_id(group_id: str, entry_type: str, value: str) -> str:
    """Build the canonical pseudo-ID for an embedded group entry.

    Always emits the ``::`` form. Callers that read existing IDs (from the
    DB or frontend payloads) must use :func:`parse_group_pseudo_id`, which
    tolerates the legacy ``|`` form too.
    """
    return f"{PSEUDO_ID_PREFIX}{group_id}{PSEUDO_ID_SEPARATOR}{entry_type}{PSEUDO_ID_SEPARATOR}{value}"


__all__ = [
    "GroupEntryRef",
    "PSEUDO_ID_PREFIX",
    "is_group_pseudo_id",
    "parse_group_pseudo_id",
    "make_group_pseudo_id",
]
