"""Public GitHub runs through real PostgreSQL preview/publication/import authority."""

import asyncio
import hashlib
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import (
    _seed_preview_graph,
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from verboflex.integrations.github.client import GitHubHttpAdapter
from verboflex.integrations.readers import RepositoryReadAdapters
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.models.user import User
from verboflex.services.import_jobs import (
    execute_import_job,
    get_import_job,
    start_or_refresh_import,
)
from verboflex.services.preview_jobs import (
    confirm_preview_job,
    create_or_reuse_preview_job,
    execute_preview_job,
    get_preview_job,
)
from verboflex.services.publication import publish_product_candidate
from verboflex.services.writeback_authority import _capture_mapping
from verboflex.worker.import_tasks import _process_import_with_adapter
from verboflex.worker.preview_tasks import process_preview

__all__ = ["clean_preview_database", "preview_session_factory"]
COMMIT = "a" * 40


def test_public_preview_publish_import_and_refresh_without_bitbucket(preview_session_factory):
    factory = preview_session_factory
    product_id, _, revision_id, mapping_id = _seed_preview_graph(factory)
    actor_id = uuid4()
    with factory.begin() as session:
        mapping = session.get(ProductRepositoryMapping, mapping_id)
        repository = session.get(Repository, mapping.sides[0].repository_id)
        repository.provider = "github"
        repository.workspace, repository.repository_slug = "owner", "repo"
        mapping.sides[0].localization_root = "locales"
        session.add(
            User(
                id=actor_id,
                email=f"{actor_id}@example.test",
                display_name="Admin",
                hashed_password="unused",
                must_change_password=False,
            )
        )
        connection = session.get(BitbucketConnection, 1)
        connection.access_token_ciphertext = None
        connection.scope_profile = None
        connection.provider_expires_at = None
    contents = {
        "locales/en.json": b'{"greeting":"Hello"}',
        "locales/it.json": b'{"greeting":"Ciao"}',
    }
    calls = []

    def handler(request):
        calls.append(request)
        assert "bitbucket" not in request.url.host
        assert "authorization" not in request.headers
        if "/branches/" in request.url.path:
            return httpx.Response(200, json={"name": "main", "commit": {"sha": COMMIT}})
        if "/git/trees/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {
                            "path": path,
                            "type": "blob",
                            "mode": "100644",
                            "size": len(content),
                            "sha": hashlib.sha1(
                                b"blob " + str(len(content)).encode() + b"\0" + content
                            ).hexdigest(),
                        }
                        for path, content in contents.items()
                    ],
                },
            )
        path = request.url.path.split(f"/{COMMIT}/", 1)[1]
        return httpx.Response(200, content=contents[path])

    adapter = RepositoryReadAdapters(
        None, GitHubHttpAdapter(transport=httpx.MockTransport(handler))
    )
    with factory() as session:
        job = create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": COMMIT},
            enqueuer=lambda _: None,
            actor_id=None,
        )
    assert job.connection_generation == 0
    execute_preview_job(
        factory,
        job_id=job.id,
        processor=lambda identity: process_preview(identity, factory=factory, adapter=adapter),
    )
    with factory() as session:
        ready = get_preview_job(session, job_id=job.id)
    assert ready.state == "succeeded" and ready.is_current
    layout = ready.result["layout_candidates"][0]
    with factory() as session:
        confirm_preview_job(
            session,
            job_id=job.id,
            preview_digest=ready.result["digest"],
            layout_candidate_id=UUID(layout["id"]),
            layout_candidate_version=1,
            base_language="en",
            actor_id=actor_id,
        )
    with factory() as session:
        publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=revision_id,
            expected_candidate_version=4,
            actor_id=None,
        )
    for expected_sequence in (1, 2):
        with factory() as session:
            imported = start_or_refresh_import(
                session,
                product_id=product_id,
                mapping_id=mapping_id,
                enqueuer=lambda _: None,
                actor_id=None,
            )
        execute_import_job(
            factory,
            import_id=imported.id,
            processor=lambda identity: asyncio.run(
                _process_import_with_adapter(identity, factory=factory, adapter=adapter)
            ),
        )
        with factory() as session:
            current = get_import_job(session, product_id=product_id, import_id=imported.id)
        assert current.state == "current", current
        assert current.capability == "ready"
        assert current.execution_number == expected_sequence
        assert len(current.active_baseline.source_references) == 2
    with factory() as session:
        assert len(tuple(session.scalars(select(TranslationValue)))) == 2
        scopes = tuple(session.scalars(select(LocalizationScope)))
        assert len(scopes) == 1
        with pytest.raises(WritebackRejected) as rejected:
            _capture_mapping(session, scopes[0], reference_limit=500, byte_limit=20_971_520)
        assert rejected.value.reason == WritebackReason.UNSUPPORTED_PROVIDER
    asyncio.run(adapter.aclose())


def test_repository_uniqueness_includes_provider_and_existing_default_is_bitbucket(
    preview_session_factory,
):
    factory = preview_session_factory
    with factory.begin() as session:
        first = Repository(workspace="same", repository_slug="repo")
        second = Repository(provider="github", workspace="same", repository_slug="repo")
        dotted = Repository(provider="github", workspace="same", repository_slug="repo.name")
        session.add_all([first, second, dotted])
        session.flush()
        assert first.provider == "bitbucket"
        assert first.id != second.id
    with factory() as session:
        assert len(tuple(session.scalars(select(Repository)))) == 3
