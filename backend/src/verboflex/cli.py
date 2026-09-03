"""Privileged non-secret administrative command seams."""

import argparse
import getpass
import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from verboflex.auth.identity import ASCII_WHITESPACE, normalize_email
from verboflex.auth.passwords import (
    PasswordPolicyError,
    hash_password,
)
from verboflex.db.session import SessionFactory
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services import admin_users as admin_user_service

FIRST_ADMIN_LOCK_KEY = 0x564552424F464C58


class SessionProvider(Protocol):
    """Callable that returns an independent SQLAlchemy session."""

    def __call__(self) -> Session: ...


class PasswordReader(Protocol):
    """Callable secret-input boundary used by the CLI and its tests."""

    def __call__(self, prompt: str) -> str: ...


class SecretInputError(RuntimeError):
    """Raised when stdin closes without supplying a password."""


class BootstrapAdminError(RuntimeError):
    """Raised when the database is not eligible for first-admin bootstrap."""


ResetPasswordError = admin_user_service.ResetPasswordError
DeactivateUserError = admin_user_service.DeactivateUserError


def bootstrap_first_admin(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> User:
    """Create the only eligible first admin under a PostgreSQL transaction lock."""
    normalized_email = normalize_email(email)
    normalized_display_name = display_name.strip(ASCII_WHITESPACE)
    if not normalized_display_name:
        raise BootstrapAdminError("display name is required")
    password_hash = hash_password(password)

    with session.begin():
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": FIRST_ADMIN_LOCK_KEY},
        )
        if session.scalar(select(func.count()).select_from(User)) != 0:
            raise BootstrapAdminError("bootstrap refused: users already exist")
        admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one_or_none()
        if admin_role is None:
            raise BootstrapAdminError("bootstrap refused: admin role is unavailable")

        user = User(
            email=normalized_email,
            display_name=normalized_display_name,
            hashed_password=password_hash,
            is_active=True,
            must_change_password=True,
            token_version=0,
            roles=[admin_role],
        )
        session.add(user)
        session.flush()
        return user


def reset_user_password(
    session: Session,
    *,
    email: str,
    password: str,
) -> None:
    """Delegate the privileged CLI reset to shared password authority."""
    admin_user_service.replace_user_password(session, email=email, password=password)


def deactivate_user(
    session: Session,
    *,
    email: str,
    now: datetime | None = None,
) -> None:
    """Delegate the privileged CLI transition to shared session revocation."""
    admin_user_service.deactivate_user_by_email(session, email=email, now=now)


def build_parser() -> argparse.ArgumentParser:
    """Build the three Phase 1 admin commands with no password argument."""
    parser = argparse.ArgumentParser(prog="verboflex")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-admin", help="create the first internal administrator"
    )
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.add_argument("--display-name", required=True)

    reset_parser = subparsers.add_parser(
        "reset-password", help="administratively replace an internal password"
    )
    reset_parser.add_argument("--email", required=True)

    deactivate_parser = subparsers.add_parser(
        "deactivate-user", help="deactivate an internal account and revoke its sessions"
    )
    deactivate_parser.add_argument("--email", required=True)
    return parser


def read_password(prompt: str) -> str:
    """Read a secret through getpass on a terminal or one line of stdin."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    password = sys.stdin.readline()
    if password == "":
        raise SecretInputError("password input is required")
    return password.rstrip("\r\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    password_reader: PasswordReader | None = None,
    session_provider: SessionProvider | None = None,
) -> int:
    """Dispatch a non-secret admin command and return a process exit code."""
    arguments = build_parser().parse_args(argv)
    read_secret = password_reader or read_password
    provide_session = session_provider or SessionFactory

    try:
        with provide_session() as session:
            if arguments.command == "deactivate-user":
                deactivate_user(session, email=arguments.email)
                print("Account deactivated; all sessions revoked.")
            elif arguments.command == "bootstrap-admin":
                password = read_secret("Password: ")
                bootstrap_first_admin(
                    session,
                    email=arguments.email,
                    display_name=arguments.display_name,
                    password=password,
                )
                print("First administrator created.")
            else:
                password = read_secret("Password: ")
                reset_user_password(session, email=arguments.email, password=password)
                print("Password reset completed; password change is required.")
    except (
        admin_user_service.AdminUserConflict,
        BootstrapAdminError,
        DeactivateUserError,
        PasswordPolicyError,
        ResetPasswordError,
        SecretInputError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError:
        print("invalid email address", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint-only wiring (01-SPEC)
    raise SystemExit(main())
