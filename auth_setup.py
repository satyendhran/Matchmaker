"""
Setup Script for Authentication System
======================================
This script helps set up the authentication system for the tournament management app.
"""

import os
import sys


def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")

    required = ["flask", "flask_cors"]
    missing = []

    for package in required:
        try:
            __import__(package)
            print(f"  {package}")
        except ImportError:
            print(f"  {package} (missing)")
            missing.append(package)

    if missing:
        print(f"\n Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install flask flask-cors")
        return False

    print("\n All dependencies installed\n")
    return True


def create_default_admin():
    """Create default admin account."""
    print("Creating default admin account...")

    try:
        from auth_repository import SQLiteUserRepository
        from auth_service import AuthenticationService, UserManagementService

        repo = SQLiteUserRepository()
        auth_service = AuthenticationService(repo)
        user_mgmt = UserManagementService(repo, auth_service)

        admin = repo.get_admin_by_username("admin")
        if admin:
            print("  ℹ Default admin already exists")
            return

    except Exception as e:
        print(f"   Error creating admin: {e}")
        return False

    return True


def verify_files():
    """Verify all required files are present."""
    print("Verifying authentication files...")

    required_files = [
        "auth_core.py",
        "auth_repository.py",
        "auth_service.py",
        "auth_middleware.py",
        "auth_routes.py",
        "app_with_auth.py",
        "login.html",
    ]

    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"   {file}")
        else:
            print(f"   {file} (missing)")
            missing.append(file)

    if missing:
        print(f"\n Missing files: {', '.join(missing)}")
        return False

    print("\n All files present\n")
    return True


def backup_original_app():
    """Backup original app.py if it exists."""
    if os.path.exists("app.py"):
        print("Backing up original app.py...")

        if os.path.exists("app_backup.py"):
            print("  ℹ Backup already exists (app_backup.py)")
        else:
            try:
                import shutil

                shutil.copy("app.py", "app_backup.py")
                print("   Backed up to app_backup.py")
            except Exception as e:
                print(f"   Error backing up: {e}")
                return False

        print()

    return True


def main():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("Tournament System - Authentication Setup")
    print("=" * 60 + "\n")

    if not check_dependencies():
        print("\nPlease install missing dependencies and run setup again.")
        sys.exit(1)

    if not verify_files():
        print("\nPlease ensure all authentication files are in the current directory.")
        sys.exit(1)

    if not backup_original_app():
        print("\nWarning: Could not backup original app.py")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            sys.exit(1)

    if not create_default_admin():
        print("\nWarning: Could not create default admin")
        print("You may need to create an admin manually.")

    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run the application:")
    print("   python app_with_auth.py")
    print("\n2. Open your browser to:")
    print("   http://localhost:5000/login.html")
    print("\n3. Login with admin credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    print("\n4. CHANGE THE ADMIN PASSWORD IMMEDIATELY!")
    print("\n5. Read AUTH_README.md for complete documentation")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
