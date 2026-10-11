"""Behavioral RED contract for the first scalar translation proposal tracer."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import connect, sql
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from verboflex.auth.access_tokens import decode_access_token
from verboflex.main import app
from verboflex.models.import_job import ImportJob
from verboflex.models.review import ReviewActivity, TranslationProposal, TranslationProposalValue
from verboflex.models.translation import TranslationKey, TranslationValue, TranslationValueRevision
from verboflex.services.signed_cursor import CursorBinding, CursorPosition, SignedCursorCodec


def _support() -> ModuleType:
    path = Path(__file__).with_name("test_translation_constraints.py")
    spec = importlib.util.spec_from_file_location("_phase4_constraint_api_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUPPORT = _support()
BACKEND_ROOT = SUPPORT.BACKEND_ROOT
ADMIN_DATABASE_URL = SUPPORT.ADMIN_DATABASE_URL
TRANSLATIONS_PATH = SUPPORT.TRANSLATIONS_PATH


def _missing(assertion_id: str, detail: str) -> None:
    pytest.fail(f"PHASE5_SCALAR_MISSING[{assertion_id}]: {detail}")


def _require_scalar_contract() -> None:
    """Fail with a named behavior gap, never an import/collection error."""
    schema_name = "verboflex.schemas.reviews"
    route_name = "verboflex.api.v1.routes.translation_reviews"
    if importlib.util.find_spec(schema_name) is None:
        _missing("save-schema", "SaveTranslationProposalRequest is not implemented")
    schemas = importlib.import_module(schema_name)
    required_schemas = {
        "SaveTranslationProposalRequest",
        "TranslationProposalResponse",
        "TranslationProposalConflictResponse",
    }
    absent_schemas = sorted(name for name in required_schemas if not hasattr(schemas, name))
    if absent_schemas:
        _missing("save-schema", f"missing public schemas: {absent_schemas}")
    if importlib.util.find_spec(route_name) is None:
        _missing("save-route", "scalar proposal route module is not implemented")
    path = "/api/v1/translations/{translation_group_id}/proposal"
    operation = app.openapi().get("paths", {}).get(path, {}).get("put")
    if operation is None:
        _missing("save-route", f"PUT {path} is not registered")
    if operation.get("operationId") != "saveTranslationProposal":
        _missing("operation-id", "generated operation must be saveTranslationProposal")


@contextmanager
def _review_database() -> Iterator[sessionmaker[Session]]:
    database_name = f"verboflex_review_api_{uuid4().hex}"
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
        app.dependency_overrides.clear()
        engine.dispose()
        with connect(ADMIN_DATABASE_URL, autocommit=True) as admin_connection:
            admin_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _seed_scalar_basis(
    factory: sessionmaker[Session],
    *,
    name: str,
    active: bool = True,
    selector_kind: str = "scalar",
    deleted: bool = False,
) -> dict[str, object]:
    ids = SUPPORT._seed_constraint_group(factory, name=name, active=active, deleted=deleted)
    group_id = ids["group"]
    assert isinstance(group_id, UUID)
    basis: list[dict[str, object]] = []
    with factory.begin() as session:
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .where(TranslationValue.id.in_(ids["values"]))
                .order_by(TranslationValue.id)
            )
        )
        for position, value in enumerate(values):
            selector_bytes = (
                f'{{"version":1,"kind":"{selector_kind}","fields":{{"index":{position}}}}}'
            ).encode()
            value.selector_kind = selector_kind
            value.selector_bytes = selector_bytes
            value.selector_digest = hashlib.sha256(selector_bytes).hexdigest()
            digest = hashlib.sha256(f"basis:{value.id}:1".encode()).hexdigest()
            session.add(
                TranslationValueRevision(
                    value_id=value.id,
                    translation_key_id=value.translation_key_id,
                    revision_number=1,
                    revision_digest=digest,
                    import_job_id=ids["import"],
                    import_execution_id=ids["execution"],
                    source_reference_position=0,
                    source_commit_hash="a" * 40,
                    source_text=value.source_text,
                    translated_text=value.translated_text,
                    display_text=value.display_text,
                    structure=value.structure,
                    review_state=value.review_state,
                    is_deleted=value.is_deleted,
                    deleted_at=value.deleted_at,
                    correlation_reference=None,
                )
            )
            basis.append(
                {
                    "translation_value_id": value.id,
                    "selector_version": value.selector_version,
                    "selector_digest": value.selector_digest,
                    "basis_revision_number": 1,
                    "basis_digest": digest,
                    "published_text": value.translated_text,
                    "published_state": value.review_state,
                }
            )
        return {
            **ids,
            "group": group_id,
            "basis": basis,
        }


def _payload(
    ids: dict[str, object], proposed_text: str, *, expected_version: int = 0
) -> dict[str, object]:
    basis = ids["basis"]
    assert isinstance(basis, list)
    return {
        "values": [
            {
                "translation_value_id": str(item["translation_value_id"]),
                "selector_version": item["selector_version"],
                "selector_digest": item["selector_digest"],
                "basis_revision_number": item["basis_revision_number"],
                "basis_digest": item["basis_digest"],
                "proposed_text": f"{proposed_text}:{index}" if index else proposed_text,
            }
            for index, item in enumerate(reversed(basis))
        ],
        "expected_version": expected_version,
    }


def _save_proposal(
    ids: dict[str, object],
    *,
    token: str,
    text: str = "pending",
) -> dict[str, object]:
    response = asyncio.run(
        SUPPORT._request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{ids['group']}/proposal",
            token=token,
            json=_payload(ids, text),
        )
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    return body


def _transition(
    ids: dict[str, object],
    *,
    token: str,
    target_state: str,
    expected_version: int,
    reason: str | None | object = ...,  # omitted and explicit null are distinct inputs
) -> object:
    payload: dict[str, object] = {
        "target_state": target_state,
        "expected_version": expected_version,
    }
    if reason is not ...:
        payload["reason"] = reason
    return asyncio.run(
        SUPPORT._request(
            "POST",
            f"{TRANSLATIONS_PATH}/{ids['group']}/proposal/state",
            token=token,
            json=payload,
        )
    )


def _activity(
    ids: dict[str, object],
    *,
    token: str,
    cursor: str | None = None,
) -> object:
    suffix = f"?cursor={cursor}" if cursor is not None else ""
    return asyncio.run(
        SUPPORT._request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/activity{suffix}",
            token=token,
        )
    )


def _assert_scalar_projection(
    body: dict[str, object],
    ids: dict[str, object],
    proposed_text: str,
) -> None:
    assert body["translation_group_id"] == str(ids["group"])
    assert body["language"] == "it"
    assert body["version"] == 1
    assert body["state"] == "draft"
    assert body["reconciliation_required"] is False
    published = body["published"]
    pending = body["pending"]
    activity = body["activity"]
    assert isinstance(published, list)
    assert isinstance(pending, list)
    assert isinstance(activity, dict)
    basis = ids["basis"]
    assert isinstance(basis, list)
    assert len(published) == len(pending) == len(basis) == 2
    published_by_id = {item["translation_value_id"]: item for item in published}
    pending_by_id = {item["translation_value_id"]: item for item in pending}
    for index, item in enumerate(reversed(basis)):
        value_id = str(item["translation_value_id"])
        assert published_by_id[value_id] == {
            "translation_value_id": value_id,
            "selector_version": item["selector_version"],
            "selector_digest": item["selector_digest"],
            "revision_number": item["basis_revision_number"],
            "revision_digest": item["basis_digest"],
            "text": item["published_text"],
            "review_state": item["published_state"],
        }
        assert pending_by_id[value_id]["basis_digest"] == item["basis_digest"]
        assert pending_by_id[value_id]["text"] == (
            f"{proposed_text}:{index}" if index else proposed_text
        )
    assert activity["kind"] == "proposal_saved"
    assert activity["proposal_version"] == 1
    assert isinstance(activity["actor_id"], str)
    assert isinstance(activity["created_at"], str)


def test_scalar_proposal_save_preserves_imported_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_scalar_contract()

    async def forbidden_provider(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("proposal save must not invoke Bitbucket")

    def forbidden_worker(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("proposal save must not dispatch Celery")

    from celery.app.task import Task

    from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter

    monkeypatch.setattr(BitbucketHttpAdapter, "read_repository_source_file", forbidden_provider)
    monkeypatch.setattr(Task, "delay", forbidden_worker)

    cases = (
        ("admin", ""),
        ("product_manager_reviewer", "A😀 e\u0301 — مرحبا — 中文"),
        ("translator", "𐐷\u0301 שלום 日本語"),
    )
    with _review_database() as factory:
        SUPPORT._configure_dependencies(factory)
        seeded: list[tuple[dict[str, object], str]] = []
        for index, (role, proposed_text) in enumerate(cases):
            ids = _seed_scalar_basis(factory, name=f"Scalar save {index}")
            token = SUPPORT._create_authority(factory, role_names=(role,))
            response = asyncio.run(
                SUPPORT._request(
                    "PUT",
                    f"{TRANSLATIONS_PATH}/{ids['group']}/proposal",
                    token=token,
                    json=_payload(ids, proposed_text),
                )
            )
            assert response.status_code == 200
            _assert_scalar_projection(response.json(), ids, proposed_text)
            seeded.append((ids, proposed_text))

        updated_ids = seeded[0][0]
        update_token = SUPPORT._create_authority(factory, role_names=("admin",))
        updated = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{updated_ids['group']}/proposal",
                token=update_token,
                json=_payload(updated_ids, "Aggiornata 日本語", expected_version=1),
            )
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert {item["text"] for item in updated.json()["pending"]} == {
            "Aggiornata 日本語",
            "Aggiornata 日本語:1",
        }
        stale = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{updated_ids['group']}/proposal",
                token=update_token,
                json=_payload(updated_ids, "stale", expected_version=1),
            )
        )
        assert stale.status_code == 409
        stale_body = stale.json()
        assert stale_body["detail"] == "Translation proposal conflict"
        assert stale_body["attempted_version"] == 1
        assert stale_body["latest"]["version"] == 2
        assert len(stale_body["attempted_values"]) == 2
        assert len(stale_body["latest"]["pending"]) == 2

        with factory() as session:
            assert session.scalar(select(func.count()).select_from(TranslationProposal)) == 3
            assert session.scalar(select(func.count()).select_from(TranslationProposalValue)) == 6
            assert session.scalar(select(func.count()).select_from(ReviewActivity)) == 4
            for ids, proposed_text in seeded:
                basis = ids["basis"]
                assert isinstance(basis, list)
                for item in basis:
                    imported = session.get_one(TranslationValue, item["translation_value_id"])
                    assert imported.translated_text == item["published_text"]
                    assert imported.display_text == item["published_text"]
                    assert imported.review_state == item["published_state"]
                pending_values = tuple(
                    session.scalars(
                        select(TranslationProposalValue).where(
                            TranslationProposalValue.proposal_id
                            == select(TranslationProposal.id)
                            .where(
                                TranslationProposal.translation_key_id == ids["key"],
                                TranslationProposal.language == "it",
                            )
                            .scalar_subquery()
                        )
                    )
                )
                assert len(pending_values) == 2
                prefix = (
                    "Aggiornata 日本語" if ids["group"] == updated_ids["group"] else proposed_text
                )
                assert {item.proposed_text for item in pending_values} == {prefix, f"{prefix}:1"}
            jobs = tuple(session.scalars(select(ImportJob).order_by(ImportJob.id)))
            assert {(job.state, job.retry_count) for job in jobs} == {("current", 0)}


def test_scalar_proposal_save_rejects_viewer_and_foreign_authority() -> None:
    _require_scalar_contract()

    with _review_database() as factory:
        readable = _seed_scalar_basis(factory, name="Viewer readable")
        foreign = _seed_scalar_basis(factory, name="Foreign selector")
        inactive = _seed_scalar_basis(factory, name="Inactive group", active=False)
        deleted = _seed_scalar_basis(factory, name="Deleted group", deleted=True)
        viewer = SUPPORT._create_authority(factory, role_names=("viewer",))
        admin = SUPPORT._create_authority(factory, role_names=("admin",))
        SUPPORT._configure_dependencies(factory)

        detail = asyncio.run(
            SUPPORT._request("GET", f"{TRANSLATIONS_PATH}/{readable['group']}", token=viewer)
        )
        assert detail.status_code == 200
        denied = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{readable['group']}/proposal",
                token=viewer,
                json=_payload(readable, "viewer cannot persist"),
            )
        )
        assert denied.status_code == 403
        assert denied.json() == {"detail": "Translation action denied"}

        unavailable_responses = []
        for group_id, payload in (
            (uuid4(), _payload(readable, "absent")),
            (inactive["group"], _payload(inactive, "inactive")),
            (deleted["group"], _payload(deleted, "deleted")),
            (readable["group"], _payload(foreign, "foreign")),
        ):
            unavailable_responses.append(
                asyncio.run(
                    SUPPORT._request(
                        "PUT",
                        f"{TRANSLATIONS_PATH}/{group_id}/proposal",
                        token=admin,
                        json=payload,
                    )
                )
            )
        for response in unavailable_responses:
            assert response.status_code == 404
            assert response.json() == {"detail": "Translation unavailable"}

        duplicate_payload = _payload(readable, "duplicate")
        values = duplicate_payload["values"]
        assert isinstance(values, list)
        duplicate_payload["values"] = [values[0], values[0]]
        duplicate = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{readable['group']}/proposal",
                token=admin,
                json=duplicate_payload,
            )
        )
        assert duplicate.status_code == 422

        readable_payload = _payload(readable, "exact-set")
        readable_values = readable_payload["values"]
        foreign_values = _payload(foreign, "foreign-member")["values"]
        assert isinstance(readable_values, list)
        assert isinstance(foreign_values, list)
        fake = {
            **readable_values[0],
            "translation_value_id": str(uuid4()),
            "selector_digest": "f" * 64,
        }
        for invalid_values in (
            readable_values[:1],
            [*readable_values, fake],
            [readable_values[0], foreign_values[1]],
        ):
            rejected = asyncio.run(
                SUPPORT._request(
                    "PUT",
                    f"{TRANSLATIONS_PATH}/{readable['group']}/proposal",
                    token=admin,
                    json={"values": invalid_values, "expected_version": 0},
                )
            )
            assert rejected.status_code == 404
            assert rejected.json() == {"detail": "Translation unavailable"}
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(TranslationProposal)) == 0
            assert session.scalar(select(func.count()).select_from(TranslationProposalValue)) == 0
            assert session.scalar(select(func.count()).select_from(ReviewActivity)) == 0


@pytest.mark.parametrize(
    "selector_kind",
    [
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
    ],
)
def test_complete_aggregate_supports_every_canonical_selector_kind(
    selector_kind: str,
) -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name=selector_kind, selector_kind=selector_kind)
        token = SUPPORT._create_authority(factory, role_names=("translator",))
        SUPPORT._configure_dependencies(factory)
        response = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{ids['group']}/proposal",
                token=token,
                json=_payload(ids, ""),
            )
        )
        assert response.status_code == 200
        assert len(response.json()["pending"]) == 2
        assert response.json()["pending"][0]["text"] in {"", ":1"}


def test_basis_drift_retains_draft_then_fresh_complete_resave_reconciles() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Basis drift")
        token = SUPPORT._create_authority(factory, role_names=("translator",))
        SUPPORT._configure_dependencies(factory)
        path = f"{TRANSLATIONS_PATH}/{ids['group']}/proposal"
        assert (
            asyncio.run(
                SUPPORT._request("PUT", path, token=token, json=_payload(ids, "pending"))
            ).status_code
            == 200
        )

        basis = ids["basis"]
        assert isinstance(basis, list)
        changed = basis[0]
        with factory.begin() as session:
            value = session.get_one(TranslationValue, changed["translation_value_id"])
            fresh_digest = hashlib.sha256(f"basis:{value.id}:2".encode()).hexdigest()
            session.add(
                TranslationValueRevision(
                    value_id=value.id,
                    translation_key_id=value.translation_key_id,
                    revision_number=2,
                    revision_digest=fresh_digest,
                    import_job_id=ids["import"],
                    import_execution_id=ids["execution"],
                    source_reference_position=0,
                    source_commit_hash="a" * 40,
                    source_text=value.source_text,
                    translated_text="imported-new",
                    display_text="imported-new",
                    structure=value.structure,
                    review_state="draft",
                    is_deleted=False,
                    deleted_at=None,
                    correlation_reference=None,
                )
            )
            value.translated_text = "imported-new"
            value.display_text = "imported-new"

        stale = asyncio.run(
            SUPPORT._request(
                "PUT", path, token=token, json=_payload(ids, "still pending", expected_version=1)
            )
        )
        assert stale.status_code == 409
        assert stale.json()["detail"] == "Translation proposal basis stale"
        assert stale.json()["latest"]["reconciliation_required"] is True
        with factory() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == ids["key"]
                )
            )
            assert proposal is not None
            assert (proposal.version, proposal.state, proposal.reconciliation_required) == (
                1,
                "draft",
                True,
            )
            assert session.scalar(select(func.count()).select_from(TranslationProposalValue)) == 2
            assert session.scalar(select(func.count()).select_from(ReviewActivity)) == 1

        changed["basis_revision_number"] = 2
        changed["basis_digest"] = hashlib.sha256(
            f"basis:{changed['translation_value_id']}:2".encode()
        ).hexdigest()
        reconciled = asyncio.run(
            SUPPORT._request(
                "PUT", path, token=token, json=_payload(ids, "rebased", expected_version=1)
            )
        )
        assert reconciled.status_code == 200
        assert reconciled.json()["version"] == 2
        assert reconciled.json()["reconciliation_required"] is False


@pytest.mark.parametrize(
    ("role_name", "allowed"),
    [
        ("admin", True),
        ("product_manager_reviewer", True),
        ("translator", False),
        ("viewer", False),
    ],
)
def test_review_transition_enforces_role_matrix_and_never_changes_imported_authority(
    role_name: str,
    allowed: bool,
) -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name=f"Transition {role_name}")
        actor_token = SUPPORT._create_authority(factory, role_names=(role_name,))
        save_token = (
            actor_token
            if role_name in ("admin", "product_manager_reviewer")
            else SUPPORT._create_authority(factory, role_names=("admin",))
        )
        SUPPORT._configure_dependencies(factory)
        saved = _save_proposal(ids, token=save_token)
        published_before = saved["published"]

        response = _transition(
            ids,
            token=actor_token,
            target_state="approved",
            expected_version=1,
        )

        if allowed:
            assert response.status_code == 200
            body = response.json()
            assert body["state"] == "approved"
            assert body["version"] == 2
            assert body["published"] == published_before
            assert body["activity"]["kind"] == "state_changed"
            assert body["activity"]["from_state"] == "draft"
            assert body["activity"]["to_state"] == "approved"
        else:
            assert response.status_code == 403
            assert response.json() == {"detail": "Translation action denied"}

        with factory() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == ids["key"]
                )
            )
            assert proposal is not None
            assert proposal.state == ("approved" if allowed else "draft")
            assert proposal.version == (2 if allowed else 1)
            assert session.scalar(select(func.count()).select_from(ReviewActivity)) == (
                2 if allowed else 1
            )
            basis = ids["basis"]
            assert isinstance(basis, list)
            for item in basis:
                imported = session.get_one(TranslationValue, item["translation_value_id"])
                assert imported.translated_text == item["published_text"]
                assert imported.review_state == item["published_state"]


def test_review_transition_retains_reason_and_returns_fresh_stale_authority() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Transition reason")
        reviewer = SUPPORT._create_authority(factory, role_names=("product_manager_reviewer",))
        SUPPORT._configure_dependencies(factory)
        _save_proposal(ids, token=reviewer)

        rejected_without_reason = _transition(
            ids,
            token=reviewer,
            target_state="rejected",
            expected_version=1,
        )
        assert rejected_without_reason.status_code == 200
        assert rejected_without_reason.json()["activity"]["reason"] is None

        returned_to_draft = _transition(
            ids,
            token=reviewer,
            target_state="draft",
            expected_version=2,
        )
        assert returned_to_draft.status_code == 200
        exact_reason = "  Motivo esatto 日本語\nseconda riga  "
        rejected = _transition(
            ids,
            token=reviewer,
            target_state="rejected",
            expected_version=3,
            reason=exact_reason,
        )
        assert rejected.status_code == 200
        assert rejected.json()["version"] == 4
        assert rejected.json()["activity"]["reason"] == exact_reason

        stale = _transition(
            ids,
            token=reviewer,
            target_state="approved",
            expected_version=3,
        )
        assert stale.status_code == 409
        assert stale.json()["detail"] == "Translation proposal conflict"
        assert stale.json()["expected_version"] == 3
        assert stale.json()["latest"]["version"] == 4
        assert stale.json()["latest"]["state"] == "rejected"

        invalid_state = _transition(
            ids,
            token=reviewer,
            target_state="published",
            expected_version=4,
        )
        assert invalid_state.status_code == 422
        supplied_for_approval = _transition(
            ids,
            token=reviewer,
            target_state="approved",
            expected_version=4,
            reason="not permitted",
        )
        assert supplied_for_approval.status_code == 422
        with factory() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == ids["key"]
                )
            )
            assert proposal is not None
            assert (proposal.version, proposal.state) == (4, "rejected")
            reasons = tuple(
                session.scalars(
                    select(ReviewActivity.reason)
                    .where(ReviewActivity.proposal_id == proposal.id)
                    .order_by(ReviewActivity.proposal_version)
                )
            )
            assert reasons == (None, None, None, exact_reason)


@pytest.mark.parametrize("max_chars", [0, 4])
def test_approval_recomputes_current_authority_before_mutation(max_chars: int) -> None:
    with _review_database() as factory:
        reviewer = SUPPORT._create_authority(factory, role_names=("admin",))
        SUPPORT._configure_dependencies(factory)

        over_limit = _seed_scalar_basis(factory, name="Over limit approval")
        _save_proposal(over_limit, token=reviewer, text="too long")
        constraint_response = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{over_limit['group']}/constraints/it",
                token=reviewer,
                json={"max_chars": max_chars, "expected_version": 0},
            )
        )
        assert constraint_response.status_code == 200

        stale_basis = _seed_scalar_basis(factory, name="Stale basis approval")
        _save_proposal(stale_basis, token=reviewer)
        stale_members = stale_basis["basis"]
        assert isinstance(stale_members, list)
        with factory.begin() as session:
            member = stale_members[0]
            value = session.get_one(TranslationValue, member["translation_value_id"])
            session.add(
                TranslationValueRevision(
                    value_id=value.id,
                    translation_key_id=value.translation_key_id,
                    revision_number=2,
                    revision_digest=hashlib.sha256(f"fresh:{value.id}".encode()).hexdigest(),
                    import_job_id=stale_basis["import"],
                    import_execution_id=stale_basis["execution"],
                    source_reference_position=0,
                    source_commit_hash="a" * 40,
                    source_text=value.source_text,
                    translated_text=value.translated_text,
                    display_text=value.display_text,
                    structure=value.structure,
                    review_state=value.review_state,
                    is_deleted=False,
                    deleted_at=None,
                    correlation_reference=None,
                )
            )

        incomplete = _seed_scalar_basis(factory, name="Incomplete approval")
        _save_proposal(incomplete, token=reviewer)
        with factory.begin() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == incomplete["key"]
                )
            )
            assert proposal is not None
            session.delete(proposal.values[0])

        deleted = _seed_scalar_basis(factory, name="Deleted transition")
        _save_proposal(deleted, token=reviewer)
        with factory.begin() as session:
            key = session.get_one(TranslationKey, deleted["key"])
            key.is_deleted = True
            key.deleted_at = SUPPORT.datetime.now(SUPPORT.UTC)
            for value_id in deleted["values"]:
                value = session.get_one(TranslationValue, value_id)
                value.is_deleted = True
                value.deleted_at = key.deleted_at

        absent = _seed_scalar_basis(factory, name="No proposal")

        blocked_cases = (
            (over_limit, 409, "Translation proposal review blocked"),
            (stale_basis, 409, "Translation proposal review blocked"),
            (incomplete, 409, "Translation proposal review blocked"),
            (deleted, 404, "Translation unavailable"),
            (absent, 404, "Translation unavailable"),
        )
        for ids, expected_status, detail in blocked_cases:
            response = _transition(
                ids,
                token=reviewer,
                target_state="approved",
                expected_version=1,
            )
            assert response.status_code == expected_status
            assert response.json()["detail"] == detail

        with factory() as session:
            proposals = tuple(session.scalars(select(TranslationProposal)))
            assert all(
                proposal.version == 1 and proposal.state == "draft" for proposal in proposals
            )
            assert session.scalar(select(func.count()).select_from(ReviewActivity)) == 4


def test_approval_accepts_corrected_draft_when_imported_text_exceeds_limit() -> None:
    with _review_database() as factory:
        reviewer = SUPPORT._create_authority(factory, role_names=("admin",))
        SUPPORT._configure_dependencies(factory)
        ids = _seed_scalar_basis(factory, name="Corrected imported violation")
        response = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{ids['group']}/constraints/it",
                token=reviewer,
                json={"max_chars": 1, "expected_version": 0},
            )
        )
        assert response.status_code == 200
        assert response.json()["violating_count"] > 0
        payload = _payload(ids, "C")
        for value in payload["values"]:
            value["proposed_text"] = "C"
        saved = asyncio.run(
            SUPPORT._request(
                "PUT",
                f"{TRANSLATIONS_PATH}/{ids['group']}/proposal",
                token=reviewer,
                json=payload,
            )
        )
        assert saved.status_code == 200
        approved = _transition(ids, token=reviewer, target_state="approved", expected_version=1)
        assert approved.status_code == 200
        assert approved.json()["state"] == "approved"
        assert all(not value["is_over_limit"] for value in approved.json()["pending"])


def test_activity_history_pages_every_event_once_with_equal_timestamp_uuid_ties() -> None:
    assert (
        app.openapi()["paths"]["/api/v1/translations/{translation_group_id}/activity"]["get"][
            "operationId"
        ]
        == "listTranslationReviewActivity"
    )
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Activity paging")
        viewer = SUPPORT._create_authority(factory, role_names=("viewer",))
        author = SUPPORT._create_authority(factory, role_names=("translator",))
        SUPPORT._configure_dependencies(factory)
        saved = _save_proposal(ids, token=author, text="value before review")
        assert saved["activity"]["before_values"] == []

        fixed_time = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
        with factory.begin() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == ids["key"]
                )
            )
            assert proposal is not None
            original = session.scalar(
                select(ReviewActivity).where(ReviewActivity.proposal_id == proposal.id)
            )
            assert original is not None and original.after_values is not None
            snapshot = original.after_values
            for sequence in range(1, 25):
                session.add(
                    ReviewActivity(
                        id=UUID(int=sequence),
                        proposal_id=proposal.id,
                        translation_key_id=proposal.translation_key_id,
                        language=proposal.language,
                        kind="state_changed",
                        proposal_version=sequence + 1,
                        from_state="draft" if sequence % 2 else "rejected",
                        to_state="rejected" if sequence % 2 else "draft",
                        before_values=snapshot,
                        after_values=snapshot,
                        reason=("理由\nexact" if sequence == 24 else None),
                        comment_id=None,
                        actor_id=proposal.updated_by,
                        created_at=fixed_time,
                    )
                )

        first = _activity(ids, token=viewer)
        assert first.status_code == 200
        first_body = first.json()
        assert len(first_body["items"]) == 20
        assert [item["id"] for item in first_body["items"]] == [
            str(UUID(int=sequence)) for sequence in range(24, 4, -1)
        ]
        assert first_body["next_cursor"]
        newest = first_body["items"][0]
        assert newest == {
            "id": str(UUID(int=24)),
            "translation_group_id": str(ids["group"]),
            "language": "it",
            "kind": "state_changed",
            "proposal_version": 25,
            "from_state": "rejected",
            "to_state": "draft",
            "before_values": saved["activity"]["after_values"],
            "after_values": saved["activity"]["after_values"],
            "reason": "理由\nexact",
            "comment_id": None,
            "actor_id": newest["actor_id"],
            "created_at": fixed_time.isoformat().replace("+00:00", "Z"),
        }

        second = _activity(ids, token=viewer, cursor=first_body["next_cursor"])
        assert second.status_code == 200
        second_body = second.json()
        assert len(second_body["items"]) == 5
        assert second_body["next_cursor"] is None
        all_ids = [item["id"] for item in first_body["items"] + second_body["items"]]
        assert len(all_ids) == len(set(all_ids)) == 25
        assert second_body["items"][-1]["kind"] == "proposal_saved"
        assert second_body["items"][-1]["from_state"] is None
        assert second_body["items"][-1]["to_state"] == "draft"


def test_activity_history_empty_and_cursor_bindings_fail_closed() -> None:
    with _review_database() as factory:
        source = _seed_scalar_basis(factory, name="Activity cursor source")
        other = _seed_scalar_basis(factory, name="Activity cursor other")
        empty = _seed_scalar_basis(factory, name="Activity empty")
        author = SUPPORT._create_authority(factory, role_names=("translator",))
        first_viewer = SUPPORT._create_authority(factory, role_names=("viewer",))
        second_viewer = SUPPORT._create_authority(factory, role_names=("viewer",))
        SUPPORT._configure_dependencies(factory)
        _save_proposal(source, token=author)
        with factory.begin() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == source["key"]
                )
            )
            assert proposal is not None
            event = session.scalar(
                select(ReviewActivity).where(ReviewActivity.proposal_id == proposal.id)
            )
            assert event is not None
            for sequence in range(1, 21):
                session.add(
                    ReviewActivity(
                        id=UUID(int=100 + sequence),
                        proposal_id=proposal.id,
                        translation_key_id=proposal.translation_key_id,
                        language=proposal.language,
                        kind="state_changed",
                        proposal_version=sequence + 1,
                        from_state="draft",
                        to_state="rejected",
                        before_values=event.after_values,
                        after_values=event.after_values,
                        reason=None,
                        comment_id=None,
                        actor_id=proposal.updated_by,
                        created_at=datetime(2031, 1, 1, tzinfo=UTC),
                    )
                )

        empty_response = _activity(empty, token=first_viewer)
        assert empty_response.status_code == 200
        assert empty_response.json() == {"items": [], "next_cursor": None}

        first = _activity(source, token=first_viewer)
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        assert isinstance(cursor, str)
        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        for response in (
            _activity(source, token=first_viewer, cursor="malformed"),
            _activity(source, token=first_viewer, cursor=tampered),
            _activity(source, token=second_viewer, cursor=cursor),
            _activity(other, token=first_viewer, cursor=cursor),
        ):
            assert response.status_code == 422
            assert response.json() == {"detail": "Invalid review activity cursor"}

        viewer_id = decode_access_token(first_viewer, settings=SUPPORT._settings()).user_id
        with factory() as session:
            proposal = session.scalar(
                select(TranslationProposal).where(
                    TranslationProposal.translation_key_id == source["key"]
                )
            )
            assert proposal is not None
            cross_kind = SignedCursorCodec(SUPPORT.SIGNING_SECRET).encode(
                binding=CursorBinding(
                    kind="comments",
                    principal_id=viewer_id,
                    scope=f"{proposal.translation_key_id}:{proposal.language}",
                    filters={"group": str(source["group"]), "language": proposal.language},
                    page_size=20,
                    direction="descending",
                ),
                position=CursorPosition(
                    created_at=datetime(2031, 1, 1, tzinfo=UTC),
                    id=UUID(int=101),
                ),
            )
        wrong_kind = _activity(source, token=first_viewer, cursor=cross_kind)
        assert wrong_kind.status_code == 422
        assert wrong_kind.json() == {"detail": "Invalid review activity cursor"}

        absent = _activity({"group": uuid4()}, token=first_viewer)
        assert absent.status_code == 404
        assert absent.json() == {"detail": "Translation unavailable"}


def test_review_activity_database_evidence_rejects_update_and_delete() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Activity append only")
        author = SUPPORT._create_authority(factory, role_names=("translator",))
        SUPPORT._configure_dependencies(factory)
        saved = _save_proposal(ids, token=author)
        activity_id = saved["activity"]["id"]

        for statement in (
            "UPDATE review_activities SET reason = reason WHERE id = :id",
            "DELETE FROM review_activities WHERE id = :id",
        ):
            with factory() as session:
                with pytest.raises(DBAPIError):
                    session.execute(text(statement), {"id": UUID(activity_id)})
                    session.commit()
                session.rollback()
        with factory() as session:
            assert session.get(ReviewActivity, UUID(activity_id)) is not None
