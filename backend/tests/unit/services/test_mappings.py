"""Revision-owned direct mapping invariants and persistence contracts."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import os
from collections.abc import Iterator, Sequence
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.integrations.bitbucket.client import BitbucketBranch
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ADMIN_DATABASE_URL = os.environ.get(
    "VERBOFLEX_TEST_POSTGRES_ADMIN_URL",
    "postgresql://postgres@127.0.0.1:55432/postgres",
)


class BranchAdapter:
    """Exact provider-order branch fixture for Plan 07 membership validation."""

    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        self.calls: list[tuple[str, str]] = []

    async def list_repository_branches(
        self,
        _session: Session,
        *,
        workspace: str,
        repository_slug: str,
    ) -> tuple[BitbucketBranch, ...]:
        self.calls.append((workspace, repository_slug))
        return tuple(
            BitbucketBranch(name=name, commit_hash=f"{index + 1:040x}")
            for index, name in enumerate(self.names)
        )


@pytest.fixture
def mapping_database() -> Iterator[tuple[Config, sessionmaker[Session]]]:
    """Migrate one isolated PostgreSQL database for each mapping invariant."""
    database_name = f"verboflex_mappings_{uuid4().hex}"
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
        yield config, factory
    finally:
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _mapping_module() -> ModuleType:
    try:
        return importlib.import_module("verboflex.services.mappings")
    except ModuleNotFoundError as error:
        pytest.fail(f"mapping service must exist: {error}")


def _mapping_models() -> ModuleType:
    try:
        return importlib.import_module("verboflex.models.product_mapping")
    except ModuleNotFoundError as error:
        pytest.fail(f"mapping models must exist: {error}")


def _seed_candidate_graph(
    factory: sessionmaker[Session],
    *,
    product_id: UUID | None = None,
    repository_id: UUID | None = None,
    active_version: int = 3,
    candidate_version: int = 4,
) -> tuple[UUID, UUID, UUID, UUID]:
    """Create a live revision, editable candidate, and reusable repository."""
    durable_product_id = product_id or uuid4()
    durable_repository_id = repository_id or uuid4()
    active_id = uuid4()
    candidate_id = uuid4()
    with factory.begin() as session:
        product = Product(
            id=durable_product_id,
            display_name=f"Product {durable_product_id}",
            name_key=f"product {durable_product_id}",
            is_active=True,
        )
        session.add(product)
        session.flush()
        session.add_all(
            [
                ProductRevision(
                    id=active_id,
                    product_id=durable_product_id,
                    description="published",
                    version=active_version,
                    is_published=True,
                    published_at=datetime.now(UTC),
                ),
                ProductRevision(
                    id=candidate_id,
                    product_id=durable_product_id,
                    description="candidate",
                    version=candidate_version,
                    is_published=False,
                ),
            ]
        )
        if session.get(Repository, durable_repository_id) is None:
            session.add(
                Repository(
                    id=durable_repository_id,
                    workspace="mobile-team",
                    repository_slug=f"repo-{durable_repository_id.hex[:12]}",
                )
            )
        session.flush()
        product.active_revision_id = active_id
        product.candidate_revision_id = candidate_id
    return durable_product_id, active_id, candidate_id, durable_repository_id


def _revision_snapshot(
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    active_id: UUID,
    candidate_id: UUID,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    with factory() as session:
        product = session.get_one(Product, product_id)
        active = session.get_one(ProductRevision, active_id)
        candidate = session.get_one(ProductRevision, candidate_id)
        return (
            (
                product.active_revision_id,
                product.candidate_revision_id,
                product.is_active,
                active.version,
                active.description,
                active.is_published,
                active.published_at,
                active.updated_at,
            ),
            (
                candidate.version,
                candidate.description,
                candidate.is_published,
                candidate.published_at,
                candidate.updated_at,
            ),
        )


def _create_direct(
    module: ModuleType,
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    repository_id: UUID,
    expected_version: int,
    adapter: BranchAdapter,
    source_branch: str = "main",
    allowed_targets: Sequence[str] = ("release/2", "release/1", "release/1"),
    default_target: str = "release/1",
) -> Any:
    with factory() as session:
        return asyncio.run(
            module.create_direct_mapping(
                session,
                product_id=product_id,
                expected_candidate_version=expected_version,
                repository_id=repository_id,
                source_branch=source_branch,
                allowed_target_branches=allowed_targets,
                default_target_branch=default_target,
                adapter=adapter,
            )
        )


def _update_direct(
    module: ModuleType,
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    mapping_id: UUID,
    repository_id: UUID,
    expected_version: int,
    adapter: BranchAdapter,
    source_branch: str = "main",
    allowed_targets: Sequence[str] = ("release/1", "release/2"),
    default_target: str = "release/1",
) -> Any:
    with factory() as session:
        return asyncio.run(
            module.update_direct_mapping(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=expected_version,
                repository_id=repository_id,
                source_branch=source_branch,
                allowed_target_branches=allowed_targets,
                default_target_branch=default_target,
                adapter=adapter,
            )
        )


def _separate_sides(
    module: ModuleType,
    *,
    keys_repository_id: UUID,
    translations_repository_id: UUID,
    keys_branch: str = "keys/main",
    translations_branch: str = "translations/main",
) -> tuple[Any, Any]:
    return (
        module.MappingSideInput(
            role="keys",
            repository_id=keys_repository_id,
            source_branch=keys_branch,
        ),
        module.MappingSideInput(
            role="translations",
            repository_id=translations_repository_id,
            source_branch=translations_branch,
        ),
    )


def _create_separate(
    module: ModuleType,
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    sides: Sequence[Any],
    expected_version: int,
    adapter: BranchAdapter,
    allowed_targets: Sequence[str] = ("release/1", "release/2"),
    default_target: str = "release/1",
) -> Any:
    with factory() as session:
        return asyncio.run(
            module.create_separate_mapping(
                session,
                product_id=product_id,
                expected_candidate_version=expected_version,
                repository_sides=sides,
                allowed_target_branches=allowed_targets,
                default_target_branch=default_target,
                adapter=adapter,
            )
        )


def _update_separate(
    module: ModuleType,
    factory: sessionmaker[Session],
    *,
    product_id: UUID,
    mapping_id: UUID,
    sides: Sequence[Any],
    expected_version: int,
    adapter: BranchAdapter,
    allowed_targets: Sequence[str] = ("release/1", "release/2"),
    default_target: str = "release/1",
) -> Any:
    with factory() as session:
        return asyncio.run(
            module.update_separate_mapping(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                expected_candidate_version=expected_version,
                repository_sides=sides,
                allowed_target_branches=allowed_targets,
                default_target_branch=default_target,
                adapter=adapter,
            )
        )


def _opaque_cursor_payload(**overrides: object) -> str:
    payload: dict[str, object] = {
        "mapping_id": str(uuid4()),
        "primary_repository_id": str(uuid4()),
        "primary_source_branch": "main",
        "revision_id": str(uuid4()),
        "topology_rank": 0,
        "translations_repository_id": None,
        "translations_source_branch": None,
        "version": 1,
    }
    payload.update(overrides)
    raw = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_mapping_cursor_is_canonical_closed_and_candidate_bound() -> None:
    """Opaque cursors reject alternate encodings, shapes, and scalar types."""
    module = _mapping_module()
    position = module._MappingCursor(
        revision_id=uuid4(),
        topology_rank=1,
        primary_repository_id=uuid4(),
        primary_source_branch="keys",
        translations_repository_id=uuid4(),
        translations_source_branch="translations",
        mapping_id=uuid4(),
    )
    encoded = module._encode_cursor(position)
    assert module._decode_cursor(encoded) == position
    decoded_payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    noncanonical = (
        base64.urlsafe_b64encode(json.dumps(decoded_payload, indent=1).encode())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert noncanonical != encoded

    malformed = (
        None,
        "",
        "x" * 2049,
        "not-base64!",
        base64.urlsafe_b64encode(b"[]").rstrip(b"=").decode("ascii"),
        _opaque_cursor_payload(unexpected="field"),
        _opaque_cursor_payload(topology_rank=True),
        _opaque_cursor_payload(
            translations_repository_id=str(uuid4()),
            translations_source_branch=None,
        ),
        _opaque_cursor_payload(mapping_id=None),
        noncanonical,
    )
    for cursor in malformed:
        with pytest.raises(module.InvalidMappingCursor):
            module._decode_cursor(cursor)


def test_mapping_list_rejects_unbounded_or_unavailable_candidates(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Service callers cannot bypass page bounds or address missing candidates."""
    _config, factory = mapping_database
    module = _mapping_module()
    with factory() as session:
        for limit in (0, 101):
            with pytest.raises(ValueError, match="invalid page size"):
                module.list_candidate_mappings(session, product_id=uuid4(), limit=limit)
            with pytest.raises(ValueError, match="invalid page size"):
                module.list_revision_mappings(
                    session,
                    product_id=uuid4(),
                    revision_id=uuid4(),
                    limit=limit,
                )
        with pytest.raises(module.MappingNotFound):
            module.list_candidate_mappings(session, product_id=uuid4())

    product_id, _active_id, candidate_id, _repository_id = _seed_candidate_graph(factory)
    with factory.begin() as session:
        candidate = session.get_one(ProductRevision, candidate_id)
        candidate.is_published = True
        candidate.published_at = datetime.now(UTC)
    with factory() as session, pytest.raises(module.MappingNotFound):
        module.list_candidate_mappings(session, product_id=product_id)

    missing_revision_id = uuid4()

    class MissingRevisionSession:
        def begin(self) -> Any:
            return nullcontext()

        def get(self, _model: object, _identity: UUID) -> object:
            return SimpleNamespace(
                id=product_id,
                active_revision_id=missing_revision_id,
                candidate_revision_id=None,
            )

        def scalar(self, _statement: object) -> None:
            return None

    with pytest.raises(module.MappingNotFound, match="revision unavailable"):
        module.list_revision_mappings(
            cast(Session, MissingRevisionSession()),
            product_id=product_id,
            revision_id=missing_revision_id,
        )


def test_mapping_projection_rejects_unknown_persisted_topology() -> None:
    """Corrupt stored topology values never escape through the closed projection."""
    module = _mapping_module()
    models = _mapping_models()
    mapping = models.ProductRepositoryMapping(
        id=uuid4(),
        revision_id=uuid4(),
        topology="manual",
        identity_key="invalid",
    )
    with pytest.raises(module.InvalidMappingInput, match="invalid persisted mapping"):
        module._record(mapping, candidate_version=1)


def test_direct_mapping_is_revision_owned_and_has_one_exact_repository_side(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Direct persists one side, exact branch, set targets, and no layout guess."""
    _config, factory = mapping_database
    module = _mapping_module()
    models = _mapping_models()
    product_id, active_id, candidate_id, repository_id = _seed_candidate_graph(factory)
    before_active, before_candidate = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )
    adapter = BranchAdapter(("main", "release/1", "release/2"))

    record = _create_direct(
        module,
        factory,
        product_id=product_id,
        repository_id=repository_id,
        expected_version=4,
        adapter=adapter,
    )

    assert record.revision_id == candidate_id
    assert record.topology == "direct"
    assert record.primary_repository_id == repository_id
    assert record.primary_source_branch == "main"
    assert record.allowed_target_branches == ("release/1", "release/2")
    assert record.default_target_branch == "release/1"
    assert record.selected_layout_candidate_id is None
    assert record.selected_layout_version is None
    assert record.candidate_version == 5
    assert adapter.calls == [("mobile-team", f"repo-{repository_id.hex[:12]}")]

    with factory() as session:
        mapping = session.get_one(models.ProductRepositoryMapping, record.id)
        sides = session.scalars(
            select(models.ProductMappingRepositorySide).where(
                models.ProductMappingRepositorySide.mapping_id == record.id
            )
        ).all()
        targets = session.scalars(
            select(models.ProductMappingAllowedTarget)
            .where(models.ProductMappingAllowedTarget.mapping_id == record.id)
            .order_by(models.ProductMappingAllowedTarget.branch.collate("C"))
        ).all()
        assert mapping.revision_id == candidate_id
        assert [(side.role, side.repository_id, side.source_branch) for side in sides] == [
            ("direct", repository_id, "main")
        ]
        assert [(target.branch, target.is_default) for target in targets] == [
            ("release/1", True),
            ("release/2", False),
        ]

    after_active, after_candidate = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )
    assert after_active == before_active
    assert after_candidate[0] == before_candidate[0] + 1
    assert after_candidate[1:4] == before_candidate[1:4]


@pytest.mark.parametrize(
    ("allowed_targets", "default_target"),
    [
        ((), "release/1"),
        (("",), ""),
        (("release/1",), "release/2"),
        (("release/1", 7), "release/1"),
    ],
)
def test_target_set_rejects_empty_malformed_or_nonmember_default_without_mutation(
    mapping_database: tuple[Config, sessionmaker[Session]],
    allowed_targets: Sequence[Any],
    default_target: str,
) -> None:
    """D-11/D-18 require a normalized nonempty set and one member default."""
    _config, factory = mapping_database
    module = _mapping_module()
    product_id, active_id, candidate_id, repository_id = _seed_candidate_graph(factory)
    before = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )

    with pytest.raises(module.InvalidMappingInput):
        _create_direct(
            module,
            factory,
            product_id=product_id,
            repository_id=repository_id,
            expected_version=4,
            adapter=BranchAdapter(("main", "release/1", "release/2")),
            allowed_targets=allowed_targets,
            default_target=default_target,
        )

    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )
        == before
    )


@pytest.mark.parametrize(
    ("source_branch", "allowed_targets", "expected_error"),
    [
        ("Main", ("release/1",), "MappingBranchConflict"),
        ("main", ("Release/1",), "MappingTargetConflict"),
    ],
)
def test_branches_must_match_current_live_discovery_exactly(
    mapping_database: tuple[Config, sessionmaker[Session]],
    source_branch: str,
    allowed_targets: Sequence[str],
    expected_error: str,
) -> None:
    """Branch spelling is opaque provider authority and never case-normalized."""
    _config, factory = mapping_database
    module = _mapping_module()
    product_id, active_id, candidate_id, repository_id = _seed_candidate_graph(factory)
    before = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )

    with pytest.raises(getattr(module, expected_error)):
        _create_direct(
            module,
            factory,
            product_id=product_id,
            repository_id=repository_id,
            expected_version=4,
            adapter=BranchAdapter(("main", "release/1")),
            source_branch=source_branch,
            allowed_targets=allowed_targets,
            default_target=allowed_targets[0],
        )

    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )
        == before
    )


def test_duplicate_identity_conflicts_while_identical_update_is_a_true_noop(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Duplicate create conflicts; normalized identical save changes nothing."""
    _config, factory = mapping_database
    module = _mapping_module()
    models = _mapping_models()
    product_id, active_id, candidate_id, repository_id = _seed_candidate_graph(factory)
    adapter = BranchAdapter(("main", "release/1", "release/2", "release/3"))
    created = _create_direct(
        module,
        factory,
        product_id=product_id,
        repository_id=repository_id,
        expected_version=4,
        adapter=adapter,
    )
    with factory() as session:
        persisted = session.get_one(models.ProductRepositoryMapping, created.id)
        timestamps = (persisted.created_at, persisted.updated_at)
    after_create = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )

    with pytest.raises(module.MappingConflict):
        _create_direct(
            module,
            factory,
            product_id=product_id,
            repository_id=repository_id,
            expected_version=5,
            adapter=adapter,
        )
    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )
        == after_create
    )

    no_op = _update_direct(
        module,
        factory,
        product_id=product_id,
        mapping_id=created.id,
        repository_id=repository_id,
        expected_version=5,
        adapter=adapter,
        allowed_targets=("release/2", "release/1", "release/1"),
    )
    assert no_op.candidate_version == 5
    with factory() as session:
        persisted = session.get_one(models.ProductRepositoryMapping, created.id)
        assert (persisted.created_at, persisted.updated_at) == timestamps
        assert persisted.selected_layout_candidate_id is None
        assert persisted.selected_layout_version is None
    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )
        == after_create
    )

    changed = _update_direct(
        module,
        factory,
        product_id=product_id,
        mapping_id=created.id,
        repository_id=repository_id,
        expected_version=5,
        adapter=adapter,
        allowed_targets=("release/1", "release/3"),
        default_target="release/3",
    )
    assert changed.candidate_version == 6
    assert changed.allowed_target_branches == ("release/1", "release/3")
    assert changed.default_target_branch == "release/3"
    active_after_change, _candidate_after_change = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )
    assert active_after_change == after_create[0]


def test_repository_reuse_never_shares_mapping_configuration_between_products(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """D-08 keeps branch, targets, layout, and version revision-owned."""
    _config, factory = mapping_database
    module = _mapping_module()
    repository_id = uuid4()
    first_product, _first_active, _first_candidate, _repository = _seed_candidate_graph(
        factory,
        repository_id=repository_id,
    )
    second_product, _second_active, _second_candidate, _repository = _seed_candidate_graph(
        factory,
        repository_id=repository_id,
    )
    adapter = BranchAdapter(("main", "develop", "release/1", "release/2"))

    first = _create_direct(
        module,
        factory,
        product_id=first_product,
        repository_id=repository_id,
        expected_version=4,
        adapter=adapter,
        source_branch="main",
        allowed_targets=("release/1",),
        default_target="release/1",
    )
    second = _create_direct(
        module,
        factory,
        product_id=second_product,
        repository_id=repository_id,
        expected_version=4,
        adapter=adapter,
        source_branch="develop",
        allowed_targets=("release/2",),
        default_target="release/2",
    )
    first_changed = _update_direct(
        module,
        factory,
        product_id=first_product,
        mapping_id=first.id,
        repository_id=repository_id,
        expected_version=5,
        adapter=adapter,
        source_branch="main",
        allowed_targets=("release/1", "release/2"),
        default_target="release/2",
    )
    with factory() as session:
        second_after = module.get_mapping(session, mapping_id=second.id)

    assert first_changed.allowed_target_branches == ("release/1", "release/2")
    assert second_after.primary_source_branch == "develop"
    assert second_after.allowed_target_branches == ("release/2",)
    assert second_after.default_target_branch == "release/2"


def test_separate_mapping_requires_exact_keys_and_translations_sides(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Separate keeps one mapping UUID with two explicit reusable repository sides."""
    _config, factory = mapping_database
    module = _mapping_module()
    models = _mapping_models()
    product_id, active_id, candidate_id, keys_repository_id = _seed_candidate_graph(factory)
    translations_repository_id = uuid4()
    with factory.begin() as session:
        session.add(
            Repository(
                id=translations_repository_id,
                workspace="translations-team",
                repository_slug=f"translations-{translations_repository_id.hex[:12]}",
            )
        )
    adapter = BranchAdapter(("keys/main", "translations/main", "release/1", "release/2"))
    sides = _separate_sides(
        module,
        keys_repository_id=keys_repository_id,
        translations_repository_id=translations_repository_id,
    )
    before_active, _before_candidate = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )

    created = _create_separate(
        module,
        factory,
        product_id=product_id,
        sides=sides,
        expected_version=4,
        adapter=adapter,
    )

    assert created.topology == "separate"
    assert created.primary_repository_id == keys_repository_id
    assert created.primary_source_branch == "keys/main"
    assert created.translations_repository_id == translations_repository_id
    assert created.translations_source_branch == "translations/main"
    assert created.allowed_target_branches == ("release/1", "release/2")
    assert created.default_target_branch == "release/1"
    assert created.candidate_version == 5
    assert adapter.calls == [
        ("mobile-team", f"repo-{keys_repository_id.hex[:12]}"),
        (
            "translations-team",
            f"translations-{translations_repository_id.hex[:12]}",
        ),
    ]
    with factory() as session:
        persisted = session.get_one(models.ProductRepositoryMapping, created.id)
        assert persisted.revision_id == candidate_id
        assert [side.role for side in persisted.sides] == ["keys", "translations"]
    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )[0]
        == before_active
    )

    invalid_sides = (
        sides[:1],
        (*sides, module.MappingSideInput("keys", keys_repository_id, "other")),
        (sides[0], module.MappingSideInput("keys", translations_repository_id, "other")),
    )
    after_create = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )
    for invalid in invalid_sides:
        with pytest.raises(module.InvalidMappingInput, match="exact keys and translations"):
            _create_separate(
                module,
                factory,
                product_id=product_id,
                sides=invalid,
                expected_version=5,
                adapter=adapter,
            )
    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )
        == after_create
    )


def test_topology_change_preserves_mapping_identity_and_invalidates_layout(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Direct-to-separate replacement clears preview authority, never active state."""
    _config, factory = mapping_database
    module = _mapping_module()
    product_id, active_id, candidate_id, keys_repository_id = _seed_candidate_graph(factory)
    translations_repository_id = uuid4()
    with factory.begin() as session:
        session.add(
            Repository(
                id=translations_repository_id,
                workspace="translations-team",
                repository_slug=f"translations-{translations_repository_id.hex[:12]}",
            )
        )
    adapter = BranchAdapter(("main", "keys/main", "translations/main", "release/1", "release/2"))
    direct = _create_direct(
        module,
        factory,
        product_id=product_id,
        repository_id=keys_repository_id,
        expected_version=4,
        adapter=adapter,
    )
    selected_layout_id = uuid4()
    with factory.begin() as session:
        persisted = session.get_one(ProductRepositoryMapping, direct.id)
        persisted.selected_layout_candidate_id = selected_layout_id
        persisted.selected_layout_version = 7
    before_active = _revision_snapshot(
        factory,
        product_id=product_id,
        active_id=active_id,
        candidate_id=candidate_id,
    )[0]

    changed = _update_separate(
        module,
        factory,
        product_id=product_id,
        mapping_id=direct.id,
        sides=_separate_sides(
            module,
            keys_repository_id=keys_repository_id,
            translations_repository_id=translations_repository_id,
        ),
        expected_version=5,
        adapter=adapter,
    )

    assert changed.id == direct.id
    assert changed.topology == "separate"
    assert changed.selected_layout_candidate_id is None
    assert changed.selected_layout_version is None
    assert changed.candidate_version == 6
    assert (
        _revision_snapshot(
            factory,
            product_id=product_id,
            active_id=active_id,
            candidate_id=candidate_id,
        )[0]
        == before_active
    )


def test_mapping_grouping_preview_uses_only_the_writable_side_and_configured_targets() -> None:
    """Direct writes its side; Separate writes Translations, with exact configured targets."""
    module = _mapping_module()
    repository_id = uuid4()
    translations_repository_id = uuid4()
    mapping_id = uuid4()
    revision_id = uuid4()

    direct = module.MappingRecord(
        id=mapping_id,
        revision_id=revision_id,
        topology="direct",
        primary_repository_id=repository_id,
        primary_source_branch="main",
        translations_repository_id=None,
        translations_source_branch=None,
        allowed_target_branches=("Release/1", "release/1"),
        default_target_branch="release/1",
        selected_layout_candidate_id=None,
        selected_layout_version=None,
        candidate_version=5,
    )
    separate = module.MappingRecord(
        id=mapping_id,
        revision_id=revision_id,
        topology="separate",
        primary_repository_id=repository_id,
        primary_source_branch="keys/main",
        translations_repository_id=translations_repository_id,
        translations_source_branch="translations/main",
        allowed_target_branches=("release/1", "release/2"),
        default_target_branch="release/2",
        selected_layout_candidate_id=None,
        selected_layout_version=None,
        candidate_version=5,
    )

    direct_preview = module.pr_grouping_preview(direct)
    separate_preview = module.pr_grouping_preview(separate)

    assert direct_preview.repository_id == repository_id
    assert direct_preview.allowed_target_branches == ("Release/1", "release/1")
    assert direct_preview.default_target_branch == "release/1"
    assert separate_preview.repository_id == translations_repository_id
    assert separate_preview.allowed_target_branches == ("release/1", "release/2")
    assert separate_preview.default_target_branch == "release/2"
    assert separate_preview.default_key == separate_preview.key_for_target("release/2")

    with pytest.raises(module.InvalidMappingInput, match="invalid persisted mapping"):
        module.pr_grouping_preview(
            module.MappingRecord(
                id=mapping_id,
                revision_id=revision_id,
                topology="separate",
                primary_repository_id=repository_id,
                primary_source_branch="keys/main",
                translations_repository_id=None,
                translations_source_branch=None,
                allowed_target_branches=("release/1",),
                default_target_branch="release/1",
                selected_layout_candidate_id=None,
                selected_layout_version=None,
                candidate_version=5,
            )
        )


def test_schema_is_reversible_revision_owned_and_has_no_manual_or_lifecycle_controls(
    mapping_database: tuple[Config, sessionmaker[Session]],
) -> None:
    """Named schema excludes product state and administrator-authored layout controls."""
    config, factory = mapping_database
    models = _mapping_models()
    engine = factory.kw["bind"]
    inspector = inspect(engine)
    expected_tables = {
        "product_repository_mappings",
        "product_mapping_repository_sides",
        "product_mapping_allowed_targets",
    }
    assert expected_tables <= set(inspector.get_table_names())
    mapping_columns = {
        column["name"] for column in inspector.get_columns("product_repository_mappings")
    }
    assert {
        "id",
        "revision_id",
        "topology",
        "identity_key",
        "base_language",
        "selected_layout_candidate_id",
        "selected_layout_version",
        "confirmed_preview_job_id",
        "confirmed_preview_digest",
        "preview_confirmed_by",
        "preview_confirmed_at",
        "created_at",
        "updated_at",
    } == mapping_columns
    assert {
        "is_active",
        "active",
        "enabled",
        "disabled",
        "status",
        "format",
        "layout",
        "glob",
        "path",
        "file_list",
        "locale_template",
    }.isdisjoint(mapping_columns)
    confirmation_foreign_keys = {
        foreign_key["constrained_columns"][0]: (
            foreign_key["referred_table"],
            (foreign_key.get("options") or {}).get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys("product_repository_mappings")
        if foreign_key["constrained_columns"][0]
        in {"confirmed_preview_job_id", "preview_confirmed_by"}
    }
    assert confirmation_foreign_keys == {
        "confirmed_preview_job_id": ("preview_jobs", "RESTRICT"),
        "preview_confirmed_by": ("users", "RESTRICT"),
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("product_repository_mappings")
    } >= {
        "ck_product_repository_mappings_base_language_length",
        "ck_product_repository_mappings_base_language_normalized",
        "ck_product_repository_mappings_preview_confirmation_state",
    }
    assert "uq_product_repository_mappings_confirmed_preview_job" in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("product_repository_mappings")
    }
    assert models.ProductRepositoryMapping.__table__.metadata is Product.__table__.metadata

    command.downgrade(config, "0004_bitbucket_connection")
    assert expected_tables.isdisjoint(inspect(engine).get_table_names())
    command.upgrade(config, "head")
    assert expected_tables <= set(inspect(engine).get_table_names())
