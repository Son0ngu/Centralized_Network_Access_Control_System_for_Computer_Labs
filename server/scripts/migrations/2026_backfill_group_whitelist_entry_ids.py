"""Backfill ``_id`` on embedded ``groups.whitelist[]`` entries.

Context (Phase 3 of the cleanup plan, P1 #8):

  Embedded whitelist entries inside group documents had no real MongoDB
  ``_id``. The service layer synthesised a "pseudo-ID" string like
  ``group::<group_id>::<type>::<value>`` so the frontend had something to
  identify rows with. That contract is now centralised in
  :mod:`server.services.whitelist_entry_id`.

  Eventually we want to fold embedded entries into a unified
  ``whitelist_entries`` collection where every row has a proper ObjectId.
  This migration is the first step: give every existing embedded entry a
  stable ``_id`` so the next phase (writing through a real collection) can
  preserve identity during dual-write.

What this script does:

  1. Scan every group document with a non-empty ``whitelist`` array.
  2. For each embedded entry without an ``_id`` field, generate a fresh
     ObjectId and persist it in place.
  3. Skip entries that already have ``_id`` (idempotent).
  4. Log a one-line summary so re-runs show "0 new IDs" once we're
     converged.

Run:

  cd server
  python scripts/migrations/2026_backfill_group_whitelist_entry_ids.py

Or dry-run first:

  python scripts/migrations/2026_backfill_group_whitelist_entry_ids.py --dry-run

The script needs read+write on the configured database. It does NOT touch
the ``whitelist`` collection (global entries already have real ``_id``s
from MongoDB).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Make ``server/`` importable when this file is executed directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _SERVER_ROOT not in sys.path:
    sys.path.insert(0, _SERVER_ROOT)

from bson import ObjectId  # noqa: E402

from database.config import get_db, close_mongo_client  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("migrations.backfill_whitelist_ids")


def backfill(dry_run: bool = False) -> dict:
    """Scan groups, add ``_id`` to embedded entries that lack one.

    Returns a stats dict — handy for tests and re-run reporting.
    """
    db = get_db()
    groups = db.groups

    scanned_groups = 0
    scanned_entries = 0
    updated_groups = 0
    new_ids = 0

    for group in groups.find({"whitelist": {"$exists": True, "$ne": []}}):
        scanned_groups += 1
        whitelist = group.get("whitelist") or []
        if not isinstance(whitelist, list):
            continue

        mutated = False
        new_entries = []
        for entry in whitelist:
            scanned_entries += 1
            if isinstance(entry, dict):
                if entry.get("_id"):
                    new_entries.append(entry)
                    continue
                # Stamp a fresh ObjectId. We do not derive it from
                # (type, value) — that's still recoverable as the pseudo-ID
                # for legacy callers, but the canonical identity going
                # forward is this new ObjectId.
                entry_with_id = dict(entry)
                entry_with_id["_id"] = ObjectId()
                new_entries.append(entry_with_id)
                mutated = True
                new_ids += 1
            else:
                # Legacy entries stored as bare strings; promote to dict
                # with an _id and minimal fields so the collection schema
                # is uniform after migration.
                new_entries.append({
                    "_id": ObjectId(),
                    "value": str(entry),
                    "type": "domain",
                    "category": "uncategorized",
                    "priority": "normal",
                    "is_active": True,
                })
                mutated = True
                new_ids += 1

        if mutated:
            updated_groups += 1
            if not dry_run:
                groups.update_one(
                    {"_id": group["_id"]},
                    {"$set": {"whitelist": new_entries}},
                )

    stats = {
        "scanned_groups": scanned_groups,
        "scanned_entries": scanned_entries,
        "updated_groups": updated_groups,
        "new_ids_assigned": new_ids,
        "dry_run": dry_run,
    }
    logger.info("Migration summary: %s", stats)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report without writing back to MongoDB.",
    )
    args = parser.parse_args()

    try:
        backfill(dry_run=args.dry_run)
        return 0
    finally:
        close_mongo_client()


if __name__ == "__main__":
    raise SystemExit(main())
