import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def info(msg: str) -> None:
    print(f"{Colors.CYAN}ℹ {msg}{Colors.RESET}")


def success(msg: str) -> None:
    print(f"{Colors.GREEN} {msg}{Colors.RESET}")


def error(msg: str) -> None:
    print(f"{Colors.RED} {msg}{Colors.RESET}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW} {msg}{Colors.RESET}")


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength. Returns (valid, message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if password.isdigit():
        return False, "Password cannot be entirely numeric."
    return True, ""


def prompt_username(existing_username: str | None = None) -> str:
    """Prompt for a username interactively."""
    if existing_username:
        return existing_username

    while True:
        try:
            username = input(f"{Colors.BOLD}Username: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)

        if not username:
            warn("Username cannot be blank.")
            continue

        if " " in username:
            warn("Username cannot contain spaces.")
            continue

        return username


def prompt_email() -> str:
    """Prompt for email (optional)."""
    try:
        email = input(f"{Colors.BOLD}Email address (optional): {Colors.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(1)
    return email or None


def prompt_password() -> str:
    """Prompt for password with confirmation."""
    while True:
        try:
            password = getpass.getpass(f"{Colors.BOLD}Password: {Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)

        valid, msg = validate_password(password)
        if not valid:
            warn(msg)
            continue

        try:
            confirm = getpass.getpass(f"{Colors.BOLD}Password (again): {Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)

        if password != confirm:
            warn("Passwords do not match. Please try again.")
            continue

        return password


def create_superuser(username: str, password: str, email: str = None) -> None:
    """Create the superuser in the database."""
    try:
        from auth_repository import SQLiteUserRepository
        from auth_service import AuthenticationService, UserManagementService
    except ImportError as e:
        error(f"Failed to import auth modules: {e}")
        error("Make sure you are running this script from the project root directory.")
        sys.exit(1)

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tournament.db")
    info(f"Using database: {db_path}")

    try:
        repo = SQLiteUserRepository(db_path)
        auth_service = AuthenticationService(repo)
        user_mgmt = UserManagementService(repo, auth_service)

        existing = repo.get_admin_by_username(username)
        if existing:
            error(f"An admin with username '{username}' already exists.")
            sys.exit(1)

        user_mgmt.register_admin(username=username, password=password, email=email)

    except Exception as e:
        error(f"Failed to create superuser: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an admin (superuser) account for the NEXUS tournament engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_superuser.py
  python create_superuser.py --username alice --email alice@example.com
        """,
    )
    parser.add_argument(
        "--username",
        metavar="USERNAME",
        help="Admin username (prompted if not provided)",
    )
    parser.add_argument(
        "--email",
        metavar="EMAIL",
        help="Admin email address (optional, prompted if not provided)",
    )
    parser.add_argument(
        "--noinput",
        action="store_true",
        help="Do not prompt for input (requires --username and PASSWORD env var)",
    )

    args = parser.parse_args()

    print()

    if args.noinput:
        username = args.username
        email = args.email
        password = os.environ.get("SUPERUSER_PASSWORD")

        if not username:
            error("--username is required when using --noinput")
            sys.exit(1)
        if not password:
            error(
                "SUPERUSER_PASSWORD environment variable is required when using --noinput"
            )
            sys.exit(1)

        valid, msg = validate_password(password)
        if not valid:
            error(f"Invalid password: {msg}")
            sys.exit(1)
    else:
        info("Enter the details for the new admin account.")
        info("Press Ctrl+C at any time to cancel.\n")

        username = prompt_username(args.username)
        email = args.email if args.email else prompt_email()
        password = prompt_password()

    print()
    info(f"Creating superuser '{username}'...")

    create_superuser(username, password, email)

    print()
    separator()
    success(f"Superuser '{username}' created successfully!")
    if email:
        success(f"Email: {email}")
    separator()
    print()
    info("You can now log in at: http://localhost:5000/login")
    print()


if __name__ == "__main__":
    main()
