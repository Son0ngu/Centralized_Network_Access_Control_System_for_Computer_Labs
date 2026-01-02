#!/usr/bin/env python3
"""
Migration Script: Update Admin Roles
-------------------------------------
Migrates existing admin accounts from old role="admin" to new role="tenant_admin".

This is a ONE-TIME migration for existing installations.

What this script does:
1. Finds all admins with role="admin" (old schema)
2. Updates them to role="tenant_admin" (new schema)
3. Ensures tenant_id is set for all tenant_admins
4. Reports any issues

Usage:
    python migrate_admin_roles.py [--dry-run]
    
Options:
    --dry-run    Show what would be changed without making changes
"""

import os
import sys
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import get_config, get_database
from models.admin_model import ROLE_TENANT_ADMIN, ROLE_SUPER_ADMIN
from time_utils import now_vietnam


def print_banner():
    """Print a nice banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           ADMIN ROLE MIGRATION SCRIPT                         ║
╠═══════════════════════════════════════════════════════════════╣
║  Migrates old role="admin" → role="tenant_admin"              ║
║  Run this ONCE after upgrading to multi-role system.          ║
╚═══════════════════════════════════════════════════════════════╝
""")


def migrate_admin_roles(dry_run: bool = False):
    """
    Migrate admin roles from old schema to new schema.
    
    Args:
        dry_run: If True, only show what would be changed
    """
    config = get_config()
    db = get_database(config)
    admins_collection = db.admins
    
    print(f"\n{'='*60}")
    print(f"{'DRY RUN - No changes will be made' if dry_run else 'MIGRATION STARTED'}")
    print(f"{'='*60}\n")
    
    # Find all admins with old role="admin"
    old_admins = list(admins_collection.find({"role": "admin"}))
    
    print(f"Found {len(old_admins)} admin(s) with old role='admin'\n")
    
    if not old_admins:
        print("✅ No migration needed. All admins already use new role system.")
        return
    
    # Statistics
    migrated = 0
    errors = 0
    warnings = []
    
    for admin in old_admins:
        admin_id = str(admin["_id"])
        email = admin.get("email", "unknown")
        tenant_id = admin.get("tenant_id")
        
        print(f"\n{'─'*40}")
        print(f"Admin: {email}")
        print(f"  ID: {admin_id}")
        print(f"  Tenant ID: {tenant_id or 'None'}")
        print(f"  Current Role: {admin.get('role')}")
        
        # Check if this admin has a tenant_id
        if not tenant_id:
            # This admin has no tenant - could be a problem
            warnings.append(f"  ⚠️  Admin {email} has no tenant_id")
            print(f"  ⚠️  WARNING: No tenant_id - skipping")
            print(f"      This admin may need manual review")
            continue
        
        # Migrate to tenant_admin
        new_role = ROLE_TENANT_ADMIN
        print(f"  New Role: {new_role}")
        
        if not dry_run:
            try:
                result = admins_collection.update_one(
                    {"_id": admin["_id"]},
                    {"$set": {
                        "role": new_role,
                        "updated_at": now_vietnam()
                    }}
                )
                
                if result.modified_count > 0:
                    print(f"  ✅ Migrated successfully")
                    migrated += 1
                else:
                    print(f"  ❌ No changes made")
                    errors += 1
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                errors += 1
        else:
            print(f"  📋 Would migrate to: {new_role}")
            migrated += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("MIGRATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total admins processed: {len(old_admins)}")
    print(f"  Successfully migrated:  {migrated}")
    print(f"  Errors:                 {errors}")
    print(f"  Warnings:               {len(warnings)}")
    
    if warnings:
        print(f"\nWarnings:")
        for warning in warnings:
            print(warning)
    
    if dry_run:
        print(f"\n{'='*60}")
        print("This was a DRY RUN. Run without --dry-run to apply changes.")
        print(f"{'='*60}")
    else:
        print(f"\n✅ Migration completed at {now_vietnam().strftime('%Y-%m-%d %H:%M:%S')}")


def verify_migration():
    """Verify migration was successful."""
    config = get_config()
    db = get_database(config)
    admins_collection = db.admins
    
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}\n")
    
    # Count by role
    roles = admins_collection.aggregate([
        {"$group": {"_id": "$role", "count": {"$sum": 1}}}
    ])
    
    role_counts = {r["_id"]: r["count"] for r in roles}
    
    print("Current role distribution:")
    print(f"  super_admin:  {role_counts.get('super_admin', 0)}")
    print(f"  tenant_admin: {role_counts.get('tenant_admin', 0)}")
    print(f"  admin (old):  {role_counts.get('admin', 0)}")
    
    # Check for any remaining old roles
    old_count = role_counts.get('admin', 0)
    if old_count > 0:
        print(f"\n⚠️  WARNING: {old_count} admin(s) still have old role='admin'")
    else:
        print(f"\n✅ All admins have been migrated to new role system")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate admin roles from old to new schema"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--verify", "-v",
        action="store_true",
        help="Only verify current state, don't migrate"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.verify:
        verify_migration()
    else:
        migrate_admin_roles(dry_run=args.dry_run)
        verify_migration()


if __name__ == "__main__":
    main()
