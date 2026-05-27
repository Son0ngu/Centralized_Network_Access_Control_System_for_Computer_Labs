"""Migrate embedded ``groups.whitelist[]`` rows to ``whitelist_entries``.

Default mode is dry-run. Pass ``--write`` to insert missing rows. The
embedded array is intentionally left in place for one compatibility release;
service reads use ``whitelist_entries`` first and fall back to embedded rows
when a group has not been migrated.
"""

import argparse
import json
import os
import sys

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from database.config import close_mongo_client, get_config, get_database
from models.group_model import GroupModel
from models.whitelist_entry_model import WhitelistEntryModel
from time_utils import now_vietnam

MAX_INVALID_ENTRY_SAMPLES = 50


def _normalise_embedded_entry(group_id, entry):
    now = now_vietnam()
    if isinstance(entry, dict):
        value = entry.get("value")
        entry_type = entry.get("type", "domain")
        legacy_id = entry.get("_id")
        row = {
            "scope": "group",
            "group_id": str(group_id),
            "legacy_embedded_id": str(legacy_id) if legacy_id else None,
            "type": entry_type,
            "value": str(value).strip().lower() if value else "",
            "category": entry.get("category", "uncategorized"),
            "priority": entry.get("priority", "normal"),
            "notes": entry.get("notes"),
            "added_by": entry.get("added_by", "migration"),
            "added_date": entry.get("added_date") or now,
            "created_at": entry.get("created_at") or now,
            "updated_at": entry.get("updated_at") or now,
            "is_active": entry.get("is_active", True),
            "migrated_from": "groups.whitelist",
            "migrated_at": now,
        }
    else:
        row = {
            "scope": "group",
            "group_id": str(group_id),
            "legacy_embedded_id": None,
            "type": "domain",
            "value": str(entry).strip().lower(),
            "category": "uncategorized",
            "priority": "normal",
            "added_by": "migration",
            "added_date": now,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "migrated_from": "groups.whitelist",
            "migrated_at": now,
        }
    if not row["value"]:
        return None
    return row


def migrate(write=False):
    config = get_config()
    db = get_database(config)
    groups = GroupModel(db)
    entries = WhitelistEntryModel(db)

    stats = {
        "groups_scanned": 0,
        "embedded_entries_scanned": 0,
        "entries_existing": 0,
        "entries_inserted": 0,
        "entries_skipped_invalid": 0,
        "invalid_entries": [],
        "dry_run": not write,
    }

    for group in groups.collection.find({"whitelist": {"$exists": True, "$ne": []}}):
        stats["groups_scanned"] += 1
        group_id = group["_id"]
        for index, embedded in enumerate(group.get("whitelist", [])):
            stats["embedded_entries_scanned"] += 1
            row = _normalise_embedded_entry(group_id, embedded)
            if not row:
                stats["entries_skipped_invalid"] += 1
                if len(stats["invalid_entries"]) < MAX_INVALID_ENTRY_SAMPLES:
                    stats["invalid_entries"].append({
                        "group_id": str(group_id),
                        "group_name": group.get("name"),
                        "entry_index": index,
                        "entry_preview": repr(embedded)[:300],
                    })
                continue

            existing = None
            legacy_id = row.get("legacy_embedded_id")
            if legacy_id:
                existing = entries.collection.find_one({
                    "scope": "group",
                    "group_id": str(group_id),
                    "legacy_embedded_id": legacy_id,
                })
            if not existing:
                existing = entries.collection.find_one({
                    "scope": "group",
                    "group_id": str(group_id),
                    "type": row["type"],
                    "value": row["value"],
                })
            if existing:
                stats["entries_existing"] += 1
                continue

            if write:
                entries.insert_entry(row)
            stats["entries_inserted"] += 1

    close_mongo_client()
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Insert missing whitelist_entries rows. Omit for dry-run.",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit with code 2 if any embedded rows cannot be migrated.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print migration stats as JSON for CI/runbook checks.",
    )
    args = parser.parse_args()
    stats = migrate(write=args.write)
    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        for key, value in stats.items():
            print(f"{key}: {value}")

    if args.fail_on_invalid and stats["entries_skipped_invalid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
