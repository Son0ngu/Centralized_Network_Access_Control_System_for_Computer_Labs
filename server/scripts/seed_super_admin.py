#!/usr/bin/env python3
"""
Seed Super Admin Script
-----------------------
Creates the first Super Admin account for the platform.

Usage:
    python seed_super_admin.py [--email EMAIL] [--password PASSWORD]
    
    If email/password not provided, will prompt interactively or generate random password.

Example:
    python seed_super_admin.py --email superadmin@firewall-controller.local
    
Notes:
    - Only ONE Super Admin can exist
    - Super Admin has no tenant_id (platform-wide access)
    - 2FA is enabled by default for security
    - This script should only be run once during initial setup
"""

import os
import sys
import argparse
import secrets
import string

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import get_config, get_database
from models.admin_model import AdminModel, ROLE_SUPER_ADMIN
from time_utils import now_vietnam


def generate_secure_password(length: int = 24) -> str:
    """Generate a cryptographically secure password."""
    # Ensure at least one of each required character type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
    ]
    
    # Fill the rest with random characters
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def print_banner():
    """Print a nice banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           FIREWALL CONTROLLER - SUPER ADMIN SETUP             ║
╠═══════════════════════════════════════════════════════════════╣
║  This script creates the platform Super Admin account.        ║
║  Run this ONCE during initial setup.                          ║
╚═══════════════════════════════════════════════════════════════╝
""")


def seed_super_admin(email: str = None, password: str = None, 
                     full_name: str = None, interactive: bool = True) -> dict:
    """
    Create the Super Admin account.
    
    Args:
        email: Admin email (default: superadmin@firewall-controller.local)
        password: Admin password (generates random if not provided)
        full_name: Admin full name
        interactive: If True, will prompt for missing values
    
    Returns:
        Dict with created admin info
    """
    # Get database
    config = get_config()
    db = get_database(config)
    admin_model = AdminModel(db)
    
    # Check if Super Admin already exists
    existing = admin_model.get_super_admin()
    if existing:
        print(f"\n❌ ERROR: Super Admin already exists!")
        print(f"   Email: {existing['email']}")
        print(f"   Created: {existing['created_at']}")
        print(f"\n   Only ONE Super Admin is allowed.")
        print(f"   To reset, delete the admin from database first.")
        return None
    
    # Get email
    if not email:
        default_email = "superadmin@firewall-controller.local"
        if interactive:
            email_input = input(f"\nEnter Super Admin email [{default_email}]: ").strip()
            email = email_input if email_input else default_email
        else:
            email = default_email
    
    # Get password
    generated_password = False
    if not password:
        if interactive:
            print("\nPassword requirements:")
            print("  - Minimum 8 characters")
            print("  - At least 1 uppercase, 1 lowercase, 1 digit, 1 special character")
            print("  - Leave blank to generate a secure random password")
            password_input = input("\nEnter password (or press Enter to generate): ").strip()
            if password_input:
                password = password_input
            else:
                password = generate_secure_password()
                generated_password = True
        else:
            password = generate_secure_password()
            generated_password = True
    
    # Get full name
    if not full_name:
        default_name = "System Administrator"
        if interactive:
            name_input = input(f"\nEnter full name [{default_name}]: ").strip()
            full_name = name_input if name_input else default_name
        else:
            full_name = default_name
    
    # Confirm before creating
    if interactive:
        print(f"\n{'═'*50}")
        print("Creating Super Admin with:")
        print(f"  Email:     {email}")
        print(f"  Full Name: {full_name}")
        print(f"  Password:  {'[GENERATED]' if generated_password else '[PROVIDED]'}")
        print(f"  2FA:       Enabled (email)")
        print(f"{'═'*50}")
        
        confirm = input("\nProceed? [Y/n]: ").strip().lower()
        if confirm and confirm != 'y':
            print("\n❌ Aborted.")
            return None
    
    # Create Super Admin
    try:
        admin_data = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": ROLE_SUPER_ADMIN,
            "tenant_id": None,  # Super Admin has no tenant
        }
        
        admin = admin_model.create_admin(admin_data)
        
        print(f"\n{'═'*60}")
        print("✅ SUPER ADMIN CREATED SUCCESSFULLY!")
        print(f"{'═'*60}")
        print(f"\n  📧 Email:    {email}")
        print(f"  👤 Name:     {full_name}")
        
        if generated_password:
            print(f"\n  🔑 Password: {password}")
            print(f"\n  ⚠️  SAVE THIS PASSWORD! It will not be shown again.")
        
        print(f"\n  🔐 2FA is ENABLED by default for security.")
        print(f"     You will need to verify via email on first login.")
        
        print(f"\n  📅 Created:  {now_vietnam().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}\n")
        
        return {
            "email": email,
            "full_name": full_name,
            "password": password if generated_password else None,
            "admin_id": str(admin["_id"])
        }
        
    except ValueError as e:
        print(f"\n❌ Validation Error: {e}")
        return None
    except Exception as e:
        print(f"\n❌ Error creating Super Admin: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create Super Admin for Firewall Controller"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        help="Super Admin email address"
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        help="Super Admin password (generates random if not provided)"
    )
    parser.add_argument(
        "--name", "-n",
        type=str,
        help="Super Admin full name"
    )
    parser.add_argument(
        "--non-interactive", "-y",
        action="store_true",
        help="Run without prompts (use defaults/generated values)"
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    result = seed_super_admin(
        email=args.email,
        password=args.password,
        full_name=args.name,
        interactive=not args.non_interactive
    )
    
    if result:
        print("You can now log in to the Super Admin dashboard.")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
