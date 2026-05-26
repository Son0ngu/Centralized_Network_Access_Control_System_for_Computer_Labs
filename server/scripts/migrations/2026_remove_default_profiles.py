"""
Migration: Remove legacy Default whitelist profiles.

Previously, server/app.py ran `delete_many({"is_default": True})` on every
startup, which mutated business data silently. This script does the same
cleanup as a one-shot, idempotent migration.

Usage:
    cd server
    python scripts/migrations/2026_remove_default_profiles.py [--dry-run]
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from database.config import get_config, get_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration.remove_default_profiles")


def run(dry_run: bool = False) -> int:
    config = get_config()
    db = get_database(config)
    collection = db["whitelist_profiles"]

    query = {"is_default": True}
    count = collection.count_documents(query)
    logger.info("Found %d legacy default profile(s)", count)

    if count == 0:
        return 0

    if dry_run:
        for doc in collection.find(query):
            logger.info("Would delete _id=%s name=%s", doc.get("_id"), doc.get("name"))
        return count

    result = collection.delete_many(query)
    logger.info("Deleted %d default profile(s)", result.deleted_count)
    return result.deleted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be deleted")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
