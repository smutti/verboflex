"""Real-PostgreSQL contracts for the global reusable repository registry."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


@pytest.fixture(scope="module")
def repository_session_factory() -> Iterator[sessionmaker[Session]]:
    """Migrate one isolated PostgreSQL database for registry and race proofs."""
    database_name = f"verboflex_repository_registry_{uuid4().hex}"
    with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
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
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _repository_contract() -> tuple[Any, Any]:
    """Load the public registry seams inside the test so RED is an executed failure."""
    model_module = importlib.import_module("verboflex.models.repository")
    service_module = importlib.import_module("verboflex.services.repositories")
    return model_module, service_module


def test_repository_identity_normalizes_lowercase_and_rejects_path_like_input() -> None:
    """Only structurally valid lowercase Bitbucket workspace/slug identity survives."""
    _model_module, service = _repository_contract()

    assert service.normalize_repository_identity(
        "  Team_Name\t",
        "  Mobile-App  ",
    ) == ("team_name", "mobile-app")

    invalid_pairs = (
        ("", "repo"),
        ("team", ""),
        ("   ", "repo"),
        ("team", "   "),
        ("../team", "repo"),
        ("team", "../repo"),
        ("team/sub", "repo"),
        ("team", "repo/sub"),
        ("team\\sub", "repo"),
        ("team name", "repo"),
        ("téam", "repo"),
        ("team", "repo.git"),
        ("-team", "repo"),
        ("team", "_repo"),
        ("a" * 101, "repo"),
        ("team", "r" * 101),
    )
    for workspace, repository_slug in invalid_pairs:
        with pytest.raises(ValueError, match="invalid repository identity"):
            service.normalize_repository_identity(workspace, repository_slug)


def test_repository_schema_is_global_credential_and_mapping_free(
    repository_session_factory: sessionmaker[Session],
) -> None:
    """D-07 persists provider identity only, with named durable constraints."""
    model_module, _service = _repository_contract()
    repository_model = model_module.Repository
    engine = repository_session_factory.kw["bind"]
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {"repositories"}
    columns = {column["name"] for column in inspector.get_columns("repositories")}
    assert columns == {
        "id",
        "provider",
        "workspace",
        "repository_slug",
        "descriptive_name",
        "descriptive_name_key",
        "created_at",
        "updated_at",
    }
    assert {
        constraint["name"] for constraint in inspector.get_unique_constraints("repositories")
    } >= {"uq_repositories_provider_identity"}
    assert {
        constraint["name"] for constraint in inspector.get_check_constraints("repositories")
    } >= {
        "ck_repositories_workspace_normalized",
        "ck_repositories_repository_slug_normalized",
        "ck_repositories_descriptive_name_state",
    }

    forbidden_fields = {
        "product_id",
        "credential",
        "token",
        "branch",
        "mapping",
        "topology",
        "format",
        "is_active",
        "active_revision_id",
        "candidate_revision_id",
    }
    assert forbidden_fields.isdisjoint(repository_model.__table__.columns.keys())

    from verboflex import models  # noqa: F401
    from verboflex.db.base import Base

    assert "repositories" in Base.metadata.tables


def test_sequential_duplicate_conflicts_and_uuid_reuse_is_a_separate_lookup(
    repository_session_factory: sessionmaker[Session],
) -> None:
    """Repeated registration never masquerades as reuse or another success."""
    model_module, service = _repository_contract()
    repository_model = model_module.Repository

    with repository_session_factory.begin() as session:
        session.query(repository_model).delete()

    with repository_session_factory() as session:
        created = service.register_repository(
            session,
            workspace="Team-One",
            repository_slug="Mobile-App",
            descriptive_name=" Mobile translations ",
            actor_id=None,
        )
    assert created.workspace == "team-one"
    assert created.repository_slug == "mobile-app"
    assert created.descriptive_name == "Mobile translations"

    with (
        repository_session_factory() as session,
        pytest.raises(service.RepositoryConflict, match="repository unavailable"),
    ):
        service.register_repository(
            session,
            workspace=" team-one ",
            repository_slug=" MOBILE-APP ",
            descriptive_name="Duplicate attempt",
            actor_id=None,
        )

    with repository_session_factory() as session:
        selected = service.get_repository(session, repository_id=created.id)
        assert selected == created
        assert len(session.scalars(select(repository_model)).all()) == 1


def test_two_session_registration_race_has_one_201_one_409_and_one_row(
    repository_session_factory: sessionmaker[Session],
) -> None:
    """Database uniqueness is the linearization point for equal registrations."""
    model_module, service = _repository_contract()
    repository_model = model_module.Repository
    with repository_session_factory.begin() as session:
        session.query(repository_model).delete()

    barrier = Barrier(2)

    def register_once(index: int) -> tuple[int, UUID | str]:
        with repository_session_factory() as session:
            barrier.wait()
            try:
                record = service.register_repository(
                    session,
                    workspace="Race-Team",
                    repository_slug="Shared-Repo",
                    descriptive_name=f"Winner candidate {index}",
                    actor_id=None,
                )
            except service.RepositoryConflict as error:
                return 409, str(error)
            return 201, record.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(register_once, range(2)))

    assert sorted(status_code for status_code, _result in results) == [201, 409]
    conflict = next(result for status_code, result in results if status_code == 409)
    assert conflict == "repository unavailable"
    with repository_session_factory() as session:
        durable = session.scalars(select(repository_model)).all()
    assert len(durable) == 1
    assert durable[0].workspace == "race-team"
    assert durable[0].repository_slug == "shared-repo"
