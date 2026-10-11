"""Real HTTP regressions for translation request and failure boundaries."""

import asyncio
from uuid import UUID

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.api.test_translations import (
    TRANSLATIONS_PATH,
    _configure_dependencies,
    _create_authority,
    _request,
    _seed_visible_group,
    clean_translation_api_database,
    translation_api_session_factory,
)
from tests.integration.test_preview_jobs import (
    COMMIT_HASH,
    _base_language_candidate,
    _seed_active_revalidation_authority,
    preview_session_factory,
)
from verboflex.main import app
from verboflex.models.preview_job import ActiveRevisionRevalidationConfirmation
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.services import preview_jobs

# Reuse the isolated PostgreSQL fixture without collecting its source module's tests.
__all__ = [
    "clean_translation_api_database",
    "translation_api_session_factory",
    "preview_session_factory",
]


def test_explicit_http_page_size_preserves_fixed_contract(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    product_id, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)
    params = {"product_id": str(product_id), "language": "it", "page_size": "50"}

    response = asyncio.run(_request(TRANSLATIONS_PATH, token=token, params=params))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(group_id)]
    assert response.json()["next_cursor"] is None
    for invalid in ("49", "51", "050", "+50", "50.0", "5e1", " 50", "50 ", "", "true"):
        rejected = asyncio.run(
            _request(TRANSLATIONS_PATH, token=token, params={**params, "page_size": invalid})
        )
        assert rejected.status_code == 422, invalid
        assert rejected.json()["detail"][0]["loc"] == ["query", "page_size"]

    parameters = app.openapi()["paths"][TRANSLATIONS_PATH]["get"]["parameters"]
    page_size = next(item["schema"] for item in parameters if item["name"] == "page_size")
    assert page_size["type"] == "integer"
    assert page_size["const"] == 50
    assert page_size["default"] == 50


@pytest.mark.parametrize("endpoint", ["", "/options", "/detail"])
def test_database_read_failure_returns_fixed_unavailable_response(
    translation_api_session_factory: sessionmaker[Session],
    endpoint: str,
) -> None:
    _, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)
    path = f"/{group_id}" if endpoint == "/detail" else endpoint
    engine = translation_api_session_factory.kw["bind"]

    def fail_translation_read(_connection, _cursor, statement, _parameters, _context, _many):
        if "translation_values" in statement or "products" in statement:
            raise RuntimeError("database failed: private provider credential sentinel")

    event.listen(engine, "before_cursor_execute", fail_translation_read)
    try:
        response = asyncio.run(_request(TRANSLATIONS_PATH + path, token=token))
    finally:
        event.remove(engine, "before_cursor_execute", fail_translation_read)

    assert response.status_code == 503
    assert response.json() == {"detail": "Translation search unavailable"}
    recovered = asyncio.run(_request(TRANSLATIONS_PATH + path, token=token))
    assert recovered.status_code == 200


def test_constraint_commit_failure_rolls_back_write_and_redacts_error(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    _, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("admin",))
    _configure_dependencies(translation_api_session_factory)
    with translation_api_session_factory() as session:
        initial_count = session.scalar(select(func.count()).select_from(TranslationConstraint))

    def fail_commit(session):
        session.flush()
        raise RuntimeError("commit failed: private provider credential sentinel")

    async def put_constraint():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.put(
                f"{TRANSLATIONS_PATH}/{group_id}/constraints/it",
                headers={"Authorization": f"Bearer {token}"},
                json={"max_chars": 7, "expected_version": 0},
            )

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = asyncio.run(put_constraint())
    finally:
        event.remove(Session, "before_commit", fail_commit)

    assert response.status_code == 503
    assert response.json() == {"detail": "Translation constraint unavailable"}
    with translation_api_session_factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(TranslationConstraint)) == initial_count
        )
    recovered = asyncio.run(put_constraint())
    assert recovered.status_code == 200
    assert recovered.json()["explicit_maximum"] == 7
    assert recovered.json()["version"] == 1


def test_active_preview_without_base_language_cannot_create_confirmation(
    preview_session_factory: sessionmaker[Session],
) -> None:
    candidate = _base_language_candidate("en", "it")
    product_id, revision_id, mapping_id, _, _ = _seed_active_revalidation_authority(
        preview_session_factory,
        base_language=None,
        selected_layout_id=UUID(str(candidate["id"])),
    )
    token = _create_authority(preview_session_factory, role_names=("admin",))
    _configure_dependencies(preview_session_factory)
    with preview_session_factory() as session:
        job = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            product_id=product_id,
            active_revision_id=revision_id,
            mapping_id=mapping_id,
            expected_active_revision_version=4,
            commits={"direct": COMMIT_HASH},
            enqueuer=lambda _id: None,
            actor_id=None,
        )
    preview_jobs.execute_preview_job(
        preview_session_factory,
        job_id=job.id,
        processor=lambda identity: {
            "detector_version": identity.detector_version,
            "digest": identity.input_digest,
            "layout_candidates": [candidate],
        },
    )
    with preview_session_factory() as session:
        completed = preview_jobs.get_active_revision_revalidation_job(session, job_id=job.id)
    assert completed.result is not None

    async def confirm():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.post(
                f"/api/v1/admin/active-revision-revalidation-jobs/{job.id}/confirmation",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "active_revision_id": str(revision_id),
                    "active_revision_version": 4,
                    "mapping_id": str(mapping_id),
                    "connection_generation": completed.connection_generation,
                    "commits": [{"role": "direct", "commit_hash": COMMIT_HASH}],
                    "preview_digest": completed.result["digest"],
                    "layout_candidate_id": candidate["id"],
                    "layout_candidate_version": 1,
                    "base_language": "en",
                },
            )

    response = asyncio.run(confirm())
    assert response.status_code == 409
    assert response.json() == {"detail": "base_language_required"}
    with preview_session_factory() as session:
        assert session.get(ActiveRevisionRevalidationConfirmation, job.id) is None
