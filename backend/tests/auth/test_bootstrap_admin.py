"""PostgreSQL contracts for privileged first-admin and reset operations."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.passwords import PasswordPolicyError, verify_password
from verboflex.cli import (
    BootstrapAdminError,
    ResetPasswordError,
    SecretInputError,
    bootstrap_first_admin,
    build_parser,
    main,
    read_password,
    reset_user_password,
)
from verboflex.db import session as db_session
from verboflex.models.auth_session import AuthSession
from verboflex.models.role import Role
from verboflex.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture
def auth_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated database and provide independent transactions."""
    database_name = f"verboflex_bootstrap_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        statement = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        admin_connection.execute(statement)

    database_url = ADMIN_DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    sqlalchemy_url = database_url.replace("postgresql://", "postgresql+psycopg://")
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    command.upgrade(config, "head")
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    try:
        yield factory
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            statement = sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database_name)
            )
            admin_connection.execute(statement)


def test_bootstrap_creates_one_normalized_active_admin_without_a_default(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Establish one temporary-password admin from explicit secret input."""
    password = "  密碼 phrase 2026!  "
    with auth_session_factory() as session:
        bootstrap_first_admin(
            session,
            email=" \tADMIN@EXAMPLE.COM\r",
            display_name="Admin User",
            password=password,
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        user = session.execute(select(User)).scalar_one()
        assert user.email == "admin@example.com"
        assert user.display_name == "Admin User"
        assert user.is_active is True
        assert user.must_change_password is True
        assert user.token_version == 0
        assert user.hashed_password != password
        assert user.hashed_password.startswith("$argon2")
        assert verify_password(password, user.hashed_password) is True
        assert [role.name for role in user.roles] == ["admin"]


def test_concurrent_bootstrap_attempts_leave_exactly_one_admin(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Serialize the empty-database decision across independent transactions."""

    def attempt_bootstrap(attempt: int) -> str:
        with auth_session_factory() as session:
            try:
                bootstrap_first_admin(
                    session,
                    email=f"admin{attempt}@example.com",
                    display_name=f"Admin {attempt}",
                    password=f"bootstrap phrase {attempt}!",
                )
            except BootstrapAdminError:
                return "refused"
            return "created"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(attempt_bootstrap, range(4)))

    assert outcomes.count("created") == 1
    assert outcomes.count("refused") == 3
    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one()
        assert len(admin_role.users) == 1


def test_second_bootstrap_rolls_back_without_changing_authority(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Refuse every later bootstrap without users or role joins changing."""
    with auth_session_factory() as session:
        bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )

    with (
        auth_session_factory() as session,
        pytest.raises(BootstrapAdminError, match="users already exist"),
    ):
        bootstrap_first_admin(
            session,
            email="second@example.com",
            display_name="Second",
            password="second admin phrase!",
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Role)) == 4


def test_bootstrap_rejects_a_blank_display_name_without_writing(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Whitespace-only display identity fails before durable authority exists."""
    with (
        auth_session_factory() as session,
        pytest.raises(BootstrapAdminError, match="display name is required"),
    ):
        bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name=" \t\r\n",
            password="first admin phrase!",
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_bootstrap_rolls_back_when_the_fixed_admin_role_is_missing(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """A damaged seed cannot create a user without its required authority."""
    with auth_session_factory.begin() as session:
        admin_role = session.execute(select(Role).where(Role.name == "admin")).scalar_one()
        session.delete(admin_role)

    with (
        auth_session_factory() as session,
        pytest.raises(BootstrapAdminError, match="admin role is unavailable"),
    ):
        bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(Role)) == 3


def test_admin_reset_rehashes_and_revokes_every_session_atomically(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Reset credentials, bump token version, and revoke all refresh authority."""
    current_password = "first admin phrase!"
    with auth_session_factory() as session:
        user = bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password=current_password,
        )
        user_id = user.id

    expires_at = datetime.now(UTC) + timedelta(days=7)
    with auth_session_factory.begin() as session:
        user = session.get_one(User, user_id)
        user.must_change_password = False
        user.token_version = 7
        session.add_all(
            [
                AuthSession(
                    user_id=user_id,
                    family_id=uuid4(),
                    token_hash="a" * 64,
                    expires_at=expires_at,
                ),
                AuthSession(
                    user_id=user_id,
                    family_id=uuid4(),
                    token_hash="b" * 64,
                    expires_at=expires_at,
                ),
            ]
        )
        previous_hash = user.hashed_password

    new_password = "new admin phrase 2026!"
    with auth_session_factory() as session:
        reset_user_password(session, email=" ADMIN@EXAMPLE.COM ", password=new_password)

    with auth_session_factory() as session:
        user = session.get_one(User, user_id)
        sessions = session.execute(select(AuthSession)).scalars().all()
        assert user.hashed_password != previous_hash
        assert verify_password(new_password, user.hashed_password) is True
        assert user.must_change_password is True
        assert user.token_version == 8
        assert len(sessions) == 2
        assert all(auth_session.revoked_at is not None for auth_session in sessions)


def test_admin_reset_does_not_revoke_another_users_session(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """Credential recovery is scoped to the selected user's refresh authority."""
    with auth_session_factory() as session:
        admin = bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )
        admin_id = admin.id

    expires_at = datetime.now(UTC) + timedelta(days=7)
    with auth_session_factory.begin() as session:
        admin = session.get_one(User, admin_id)
        other_user = User(
            email="other@example.com",
            display_name="Other User",
            hashed_password=admin.hashed_password,
        )
        session.add(other_user)
        session.flush()
        other_user_id = other_user.id
        session.add_all(
            [
                AuthSession(
                    user_id=admin_id,
                    family_id=uuid4(),
                    token_hash="c" * 64,
                    expires_at=expires_at,
                ),
                AuthSession(
                    user_id=other_user_id,
                    family_id=uuid4(),
                    token_hash="d" * 64,
                    expires_at=expires_at,
                ),
            ]
        )

    with auth_session_factory() as session:
        reset_user_password(
            session,
            email="admin@example.com",
            password="replacement admin phrase!",
        )

    with auth_session_factory() as session:
        admin_session = session.execute(
            select(AuthSession).where(AuthSession.user_id == admin_id)
        ).scalar_one()
        other_session = session.execute(
            select(AuthSession).where(AuthSession.user_id == other_user_id)
        ).scalar_one()
        assert admin_session.revoked_at is not None
        assert other_session.revoked_at is None


def test_admin_reset_preserves_an_existing_session_revocation_time(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """A reset never rewrites the audit time of authority revoked earlier."""
    with auth_session_factory() as session:
        admin = bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )
        admin_id = admin.id

    previous_revocation = datetime(2026, 1, 1, tzinfo=UTC)
    with auth_session_factory.begin() as session:
        session.add(
            AuthSession(
                user_id=admin_id,
                family_id=uuid4(),
                token_hash="e" * 64,
                revoked_at=previous_revocation,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )

    with auth_session_factory() as session:
        reset_user_password(
            session,
            email="admin@example.com",
            password="replacement admin phrase!",
        )

    with auth_session_factory() as session:
        auth_session = session.execute(select(AuthSession)).scalar_one()
        assert auth_session.revoked_at == previous_revocation


@pytest.mark.parametrize(
    ("rejected_password", "message"),
    [
        ("first admin phrase!", "must differ from current password"),
        ("admin@example.com", "must not equal login email"),
    ],
)
def test_rejected_admin_reset_rolls_back_every_authority_field(
    auth_session_factory: sessionmaker[Session],
    rejected_password: str,
    message: str,
) -> None:
    """Rejected reset inputs leave hashes, versions, flags, and sessions intact."""
    current_password = "first admin phrase!"
    with auth_session_factory() as session:
        user = bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password=current_password,
        )
        user_id = user.id

    with auth_session_factory.begin() as session:
        user = session.get_one(User, user_id)
        user.must_change_password = False
        session.add(
            AuthSession(
                user_id=user_id,
                family_id=uuid4(),
                token_hash="c" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        previous_hash = user.hashed_password
        previous_version = user.token_version

    with auth_session_factory() as session, pytest.raises(PasswordPolicyError, match=message):
        reset_user_password(
            session,
            email="admin@example.com",
            password=rejected_password,
        )

    with auth_session_factory() as session:
        user = session.get_one(User, user_id)
        auth_session = session.execute(select(AuthSession)).scalar_one()
        assert user.hashed_password == previous_hash
        assert user.token_version == previous_version
        assert user.must_change_password is False
        assert auth_session.revoked_at is None


def test_reset_unknown_account_is_non_mutating_and_non_enumerating(
    auth_session_factory: sessionmaker[Session],
) -> None:
    """An unavailable reset target exposes no database detail and changes nothing."""
    with (
        auth_session_factory() as session,
        pytest.raises(ResetPasswordError, match="account unavailable"),
    ):
        reset_user_password(
            session,
            email="unknown@example.com",
            password="replacement protected phrase!",
        )

    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(Role)) == 4


def test_cli_exposes_only_non_secret_bootstrap_and_reset_arguments() -> None:
    """Passwords have no normal argument, default, or parsed namespace field."""
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert set(subparsers.choices) == {"bootstrap-admin", "reset-password"}

    bootstrap = parser.parse_args(
        [
            "bootstrap-admin",
            "--email",
            "admin@example.com",
            "--display-name",
            "Admin",
        ]
    )
    reset = parser.parse_args(["reset-password", "--email", "admin@example.com"])
    assert "password" not in vars(bootstrap)
    assert "password" not in vars(reset)


def test_cli_bootstrap_reads_secret_outside_argv_and_never_echoes_it(
    auth_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The dispatcher obtains the password only through its secret reader."""
    secret = "bootstrap from protected input!"
    exit_code = main(
        [
            "bootstrap-admin",
            "--email",
            "admin@example.com",
            "--display-name",
            "Admin",
        ],
        password_reader=lambda _prompt: secret,
        session_provider=auth_session_factory,
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert secret not in output.out
    assert secret not in output.err
    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_cli_reset_dispatches_without_exposing_the_replacement_password(
    auth_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Wire reset to the same protected reader and atomic service boundary."""
    with auth_session_factory() as session:
        user = bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )
        user_id = user.id

    replacement = "replacement protected phrase!"
    exit_code = main(
        ["reset-password", "--email", "admin@example.com"],
        password_reader=lambda _prompt: replacement,
        session_provider=auth_session_factory,
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert replacement not in output.out
    assert replacement not in output.err
    with auth_session_factory() as session:
        user = session.get_one(User, user_id)
        assert verify_password(replacement, user.hashed_password) is True
        assert user.must_change_password is True
        assert user.token_version == 1


def test_stdin_secret_reader_preserves_intentional_spaces_without_echo(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-terminal stdin strips only its line ending, never password spaces."""
    monkeypatch.setattr("sys.stdin", StringIO("  protected phrase  \n"))

    password = read_password("Password: ")

    output = capsys.readouterr()
    assert password == "  protected phrase  "
    assert password not in output.out
    assert password not in output.err


def test_terminal_secret_reader_delegates_to_getpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive terminals use getpass instead of visible stdin reads."""
    terminal = StringIO()
    monkeypatch.setattr(terminal, "isatty", lambda: True)
    monkeypatch.setattr("sys.stdin", terminal)
    monkeypatch.setattr("verboflex.cli.getpass.getpass", lambda _prompt: "protected phrase!")

    assert read_password("Password: ") == "protected phrase!"


def test_closed_stdin_fails_without_inventing_a_default_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EOF is a hard input error rather than an implicit credential."""
    monkeypatch.setattr("sys.stdin", StringIO())

    with pytest.raises(SecretInputError, match="password input is required"):
        read_password("Password: ")


def test_cli_returns_non_secret_failure_for_expected_bootstrap_refusal(
    auth_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expected admin errors produce a non-zero, password-free diagnostic."""
    with auth_session_factory() as session:
        bootstrap_first_admin(
            session,
            email="admin@example.com",
            display_name="Admin",
            password="first admin phrase!",
        )

    secret = "second protected phrase!"
    exit_code = main(
        [
            "bootstrap-admin",
            "--email",
            "second@example.com",
            "--display-name",
            "Second",
        ],
        password_reader=lambda _prompt: secret,
        session_provider=auth_session_factory,
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert "users already exist" in output.err
    assert secret not in output.out
    assert secret not in output.err


def test_cli_masks_invalid_email_details(
    auth_session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Identity parsing failures collapse to the canonical safe diagnostic."""
    exit_code = main(
        [
            "bootstrap-admin",
            "--email",
            "not an email",
            "--display-name",
            "Admin",
        ],
        password_reader=lambda _prompt: "protected phrase!",
        session_provider=auth_session_factory,
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert output.err.strip() == "invalid email address"


def test_cli_defaults_use_stdin_and_the_configured_session_factory(
    auth_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real dispatcher defaults wire stdin to the application session seam."""
    monkeypatch.setattr("sys.stdin", StringIO("protected default phrase!\n"))
    monkeypatch.setattr("verboflex.cli.SessionFactory", auth_session_factory)

    assert (
        main(
            [
                "bootstrap-admin",
                "--email",
                "admin@example.com",
                "--display-name",
                "Admin",
            ]
        )
        == 0
    )
    with auth_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_database_dependency_rolls_back_on_caller_failure(
    auth_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request exception cannot leave an uncommitted identity write behind."""
    monkeypatch.setattr(db_session, "SessionFactory", auth_session_factory)
    dependency = db_session.get_db_session()
    session = next(dependency)
    session.add(
        User(
            email="rollback@example.com",
            display_name="Rollback",
            hashed_password="non-secret-test-hash",
        )
    )
    session.flush()

    with pytest.raises(RuntimeError, match="forced rollback"):
        dependency.throw(RuntimeError("forced rollback"))

    with auth_session_factory() as verification_session:
        assert verification_session.scalar(select(func.count()).select_from(User)) == 0
