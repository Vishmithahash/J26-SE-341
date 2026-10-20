"""Internal CLI for operator administrator provisioning and role promotion.

Guarantees:
- Pure module imports and --help flags do NOT connect to the database.
- Database sessions are created only during command execution.
- Passwords are never accepted via command line arguments; secure getpass prompts are used.
- Passwords, hashes, and tokens are never printed or logged.
- Existing accounts are protected against accidental overwrites or silent password changes.

Usage:
  python -m app.shared.auth.cli --help
  python -m app.shared.auth.cli create-admin --name "Admin Name" --email "admin@example.com"
  python -m app.shared.auth.cli promote-admin --email "user@example.com" --yes
"""

import argparse
import getpass
import sys

from app.shared.auth.models import normalize_email
from app.shared.auth.schemas import EMAIL_REGEX


def _validate_email(email: str) -> str:
    cleaned = email.strip()
    if not cleaned or len(cleaned) > 255 or not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email format.")
    return cleaned


def _get_validated_password() -> str:
    pwd = getpass.getpass("Enter administrator password (min 15 chars): ")
    if len(pwd) < 15:
        raise ValueError("Password must be at least 15 characters.")
    if len(pwd) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    confirm = getpass.getpass("Confirm administrator password: ")
    if pwd != confirm:
        raise ValueError("Passwords do not match.")
    return pwd


def handle_create_admin(args: argparse.Namespace) -> int:
    name = args.name.strip()
    if not name:
        print("[ERROR] Administrator name cannot be empty.", file=sys.stderr)
        return 1

    try:
        email = _validate_email(args.email)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    try:
        password = _get_validated_password()
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    # Lazy import database connection only upon command execution
    from app.database import SessionLocal
    from app.shared.auth.service import provision_admin

    db = SessionLocal()
    try:
        user = provision_admin(db=db, name=name, email=email, password=password)
        print(
            f"[SUCCESS] Administrator '{user.canonical_email}' created successfully (ID: {user.id})."
        )
        return 0
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        # Sanitize unexpected database error output
        print(
            f"[ERROR] Failed to provision administrator: {type(e).__name__}",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()


def handle_promote_admin(args: argparse.Namespace) -> int:
    try:
        email = _validate_email(args.email)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    canonical_email = normalize_email(email)

    if not args.yes:
        confirmation = (
            input(
                f"Are you sure you want to promote '{canonical_email}' to ADMIN? (yes/no): "
            )
            .strip()
            .lower()
        )
        if confirmation not in ("yes", "y"):
            print("[INFO] Promotion cancelled by operator.")
            return 0

    from app.database import SessionLocal
    from app.shared.auth.service import promote_user_to_admin

    db = SessionLocal()
    try:
        user, was_already_admin = promote_user_to_admin(db=db, email=canonical_email)
        if was_already_admin:
            print(f"[INFO] User '{user.canonical_email}' is already an ADMIN.")
        else:
            print(
                f"[SUCCESS] User '{user.canonical_email}' successfully promoted to ADMIN."
            )
        return 0
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Failed to promote user: {type(e).__name__}", file=sys.stderr)
        return 1
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.shared.auth.cli",
        description="Internal Administrator Provisioning & Promotion CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    create_parser = subparsers.add_parser(
        "create-admin",
        help="Create a new administrator account with interactive password entry.",
    )
    create_parser.add_argument("--name", required=True, help="Full display name")
    create_parser.add_argument(
        "--email", required=True, help="Administrator email address"
    )
    create_parser.set_defaults(handler=handle_create_admin)

    # promote-admin
    promote_parser = subparsers.add_parser(
        "promote-admin",
        help="Promote an existing user to administrator without modifying password.",
    )
    promote_parser.add_argument(
        "--email", required=True, help="User email address to promote"
    )
    promote_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation prompt",
    )
    promote_parser.set_defaults(handler=handle_promote_admin)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.handler(args))


if __name__ == "__main__":
    main()
