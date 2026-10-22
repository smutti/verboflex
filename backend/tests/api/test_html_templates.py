"""Real imports, HTTP permissions and durable HTML branch jobs with synthetic data."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.integration.test_branch_workflow import Remote, run
from tests.integration.test_confirmed_layout_refresh import (
    RefreshSource,
    _published_confirmation,
    _run,
)
from tests.integration.test_preview_jobs import (
    clean_preview_database as clean_preview_database,
)
from tests.integration.test_preview_jobs import (
    preview_session_factory as preview_session_factory,
)
from tests.legacy_product_fixtures import mirror_fixture_role
from tests.unit.localization.test_html_images import PNG
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.db.session import get_db_session
from verboflex.localization.html_images import image_data_uri
from verboflex.main import app
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.import_job import ImportExecution
from verboflex.models.role import Role
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.worker import import_tasks

HTML = (
    b'<!DOCTYPE html><html><body><img src="/images/logo.png">'
    b'<p class="fixed">Welcome {{name}}</p></body></html>'
)


@pytest.fixture
def html_api(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    adapter = RefreshSource(
        files={"mail/Welcome-EN.html": HTML, "images/logo.png": PNG}, commit_hashes=["a" * 40]
    )
    product_id, mapping_id = _published_confirmation(factory, adapter)
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "create_repository_read_adapters", lambda _: adapter)
    imported = _run(factory, product_id, mapping_id)
    assert imported.state == "current"
    actor_id = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=f"{actor_id}@example.test",
                display_name="HTML editor",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
                roles=[session.scalar(select(Role).where(Role.name == "admin"))],
            )
        )
    principal = Principal(
        actor_id, f"{actor_id}@example.test", "HTML editor", (RoleName.ADMIN,), False
    )
    with factory() as session:
        values = tuple(session.scalars(select(TranslationValue)).all())
    seed = SimpleNamespace(
        product_id=product_id,
        mapping_id=mapping_id,
        actor_id=actor_id,
        adapter=adapter,
        value_ids=tuple(v.id for v in values),
    )

    def db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_principal] = lambda: principal
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/products/{product_id}/branch-workflow",
            json={
                "mapping_id": str(mapping_id),
                "work_branch": "main",
                "target_branch": "release",
            },
        )
        assert response.status_code == 200, response.text
        seed.workflow_id = response.json()["workflow_id"]
        yield client, seed, factory
    app.dependency_overrides.clear()


def test_html_preview_and_api_variable_protection(html_api):
    client, seed, _ = html_api
    group = f"/api/v1/translations/{seed.value_ids[0]}"
    preview = client.get(group + "/html-preview")
    assert preview.status_code == 200, preview.text
    assert '<p class="fixed">' in preview.json()["document"]
    assert "{{name}}" not in preview.json()["document"]
    assert image_data_uri(PNG) in preview.json()["document"]
    assert preview.json()["missing_images"] == 0
    # Preview requests must not contact the repository.
    requests = list(seed.adapter.requests)
    assert client.get(group + "/html-preview").status_code == 200
    assert seed.adapter.requests == requests
    detail = client.get(group).json()
    value = detail["values"][0]
    latest = value["history"][0]
    body = {
        "expected_version": 0,
        "values": [
            {
                "translation_value_id": value["id"],
                "selector_version": value["selector_version"],
                "selector_digest": value["selector_digest"],
                "basis_revision_number": latest["revision_number"],
                "basis_digest": latest["revision_digest"],
                "proposed_text": "Changed {{other}}",
            }
        ],
    }
    assert client.put(group + "/proposal", json=body).status_code == 422
    body["values"][0]["proposed_text"] = "Hello {{name}}"
    response = client.put(group + "/proposal", json=body)
    assert response.status_code == 200, response.text


def test_html_image_refresh_after_connection_revalidation_and_reactivation(html_api):
    from verboflex.models.bitbucket_connection import BitbucketConnection
    from verboflex.models.product import ProductRevision
    from verboflex.models.product_mapping import ProductRepositoryMapping
    from verboflex.services import preview_jobs, publication
    from verboflex.worker import preview_tasks

    client, seed, factory = html_api
    with factory.begin() as session:
        session.get_one(BitbucketConnection, 1).generation += 1
        mapping = session.get_one(ProductRepositoryMapping, seed.mapping_id)
        revision = session.get_one(ProductRevision, mapping.revision_id)
        revision_id, version = revision.id, revision.version
        selected_id = mapping.selected_layout_candidate_id
    with factory() as session:
        publication.deactivate_product(session, actor_id=seed.actor_id, product_id=seed.product_id)
    with factory() as session:
        job = preview_jobs.create_or_reuse_active_revision_revalidation_job(
            session,
            actor_id=seed.actor_id,
            product_id=seed.product_id,
            active_revision_id=revision_id,
            mapping_id=seed.mapping_id,
            expected_active_revision_version=version,
            commits={"direct": "a" * 40},
            enqueuer=lambda _: None,
        )
    preview_jobs.execute_preview_job(
        factory,
        job_id=job.id,
        processor=lambda identity: preview_tasks.process_preview(
            identity,
            factory=factory,
            adapter=seed.adapter,
        ),
    )
    with factory() as session:
        completed = preview_jobs.get_active_revision_revalidation_job(session, job_id=job.id)
    assert completed.state == "succeeded"
    with factory() as session:
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=job.id,
            preview_digest=completed.result["digest"],
            layout_candidate_id=selected_id,
            layout_candidate_version=1,
            base_language="en",
            actor_id=seed.actor_id,
        )
    with factory() as session:
        publication.reactivate_product(
            session,
            actor_id=seed.actor_id,
            product_id=seed.product_id,
            active_revision_id=revision_id,
            expected_active_version=version,
        )
    # Reactivation must not immediately invalidate the evidence just confirmed.
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    preview = client.get(f"/api/v1/translations/{seed.value_ids[0]}/html-preview")
    assert preview.status_code == 200
    assert image_data_uri(PNG) in preview.json()["document"]
    assert preview.json()["missing_images"] == 0
    # Active products still cannot create or reconfirm revalidation jobs.
    with factory() as session, pytest.raises(preview_jobs.PreviewJobConflict):
        preview_jobs.confirm_active_revision_revalidation(
            session,
            job_id=job.id,
            preview_digest=completed.result["digest"],
            layout_candidate_id=selected_id,
            layout_candidate_version=1,
            base_language="en",
            actor_id=seed.actor_id,
        )
    with factory.begin() as session:
        session.get_one(BitbucketConnection, 1).generation += 1
    with factory() as session:
        assert not preview_jobs.is_current_preview_confirmation(
            session,
            session.get_one(ProductRevision, revision_id),
            session.get_one(ProductRepositoryMapping, seed.mapping_id),
        )


def test_new_html_language_is_a_durable_commit_without_pr(html_api):
    client, seed, factory = html_api
    endpoint = f"/api/v1/products/{seed.product_id}/html-languages"
    response = client.post(endpoint, json={"workflow_id": seed.workflow_id, "language": "fr-BE"})
    assert response.status_code == 202, response.text
    with factory() as session:
        from uuid import UUID

        job = session.get(BranchJob, UUID(response.json()["id"]))
        assert job.state == "queued" and job.intent is None
        job_id = job.id
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    assert run(factory, remote, job_id) == ("committed", None)
    assert remote.versions[remote.head]["mail/Welcome-FR-BE.html"] == HTML
    assert remote.prs == []
    assert remote.commits[0].files[0].new_file is True
    assert remote.commits[0].initialize_language is True
    # The same old source cannot create a second language after the branch advances.
    response = client.post(endpoint, json={"workflow_id": seed.workflow_id, "language": "nl-BE"})
    assert response.status_code == 202
    from uuid import UUID

    assert run(factory, remote, UUID(response.json()["id"])) == ("blocked", "import_changed")
    cancelled = client.delete(endpoint + "/" + response.json()["id"])
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "declined"
    assert client.delete(endpoint + "/" + str(job_id)).status_code == 409
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    with factory() as session:
        translated = session.scalar(
            select(TranslationValue).where(TranslationValue.language == "fr-BE")
        )
        group = f"/api/v1/translations/{translated.id}"
    detail = client.get(group).json()
    assert detail["mutation_eligible"] is True
    value = detail["values"][0]
    latest = value["history"][0]
    saved = client.put(
        group + "/proposal",
        json={
            "expected_version": 0,
            "values": [
                {
                    "translation_value_id": value["id"],
                    "selector_version": value["selector_version"],
                    "selector_digest": value["selector_digest"],
                    "basis_revision_number": latest["revision_number"],
                    "basis_digest": latest["revision_digest"],
                    "proposed_text": "Bonjour {{name}}",
                }
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    reviewed = client.post(
        group + "/proposal/state",
        json={
            "expected_version": saved.json()["version"],
            "target_state": "approved",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    with factory() as session:
        approval = session.scalar(select(BranchJob).where(BranchJob.kind == "commit"))
        approval_id = approval.id
    assert run(factory, remote, approval_id) == ("committed", None)
    assert remote.versions[remote.head]["mail/Welcome-FR-BE.html"] == HTML.replace(
        b"Welcome", b"Bonjour"
    )
    assert remote.prs == []


@pytest.mark.parametrize("role", ["translator", "viewer"])
def test_html_language_creation_requires_reviewer_permissions(html_api, role):
    client, seed, factory = html_api
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == role))
        ]
        mirror_fixture_role(session, seed.actor_id)
    result = client.post(
        f"/api/v1/products/{seed.product_id}/html-languages",
        json={"workflow_id": seed.workflow_id, "language": "it"},
    )
    assert result.status_code == 403
    assert client.get(f"/api/v1/translations/{seed.value_ids[0]}/html-preview").status_code == 200


def test_html_language_existing_or_foreign_scope_is_rejected(html_api):
    client, seed, _ = html_api
    endpoint = f"/api/v1/products/{seed.product_id}/html-languages"
    assert (
        client.post(endpoint, json={"workflow_id": seed.workflow_id, "language": "en"}).status_code
        == 409
    )
    assert (
        client.post(endpoint, json={"workflow_id": str(uuid4()), "language": "it"}).status_code
        == 409
    )


def test_image_snapshot_refresh_keeps_translation_revisions_and_saved_proposal(html_api):
    client, seed, factory = html_api
    group = f"/api/v1/translations/{seed.value_ids[0]}"
    detail = client.get(group).json()
    value = detail["values"][0]
    revision = value["history"][0]
    response = client.put(
        group + "/proposal",
        json={
            "expected_version": 0,
            "values": [
                {
                    "translation_value_id": value["id"],
                    "selector_version": value["selector_version"],
                    "selector_digest": value["selector_digest"],
                    "basis_revision_number": revision["revision_number"],
                    "basis_digest": revision["revision_digest"],
                    "proposed_text": "Hello {{name}}",
                }
            ],
        },
    )
    assert response.status_code == 200
    seed.adapter.files["images/logo.png"] = PNG + b"different-image-version"
    seed.adapter.commit_hashes = ["b" * 40]
    before = client.get(group + "/html-preview").json()
    assert image_data_uri(PNG) in before["document"]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    after = client.get(group + "/html-preview").json()
    assert image_data_uri(seed.adapter.files["images/logo.png"]) in after["document"]
    current = client.get(group).json()
    assert current["values"][0]["history"] == value["history"]
    assert current["pending_change"]["values"][0]["text"] == "Hello {{name}}"
    assert current["pending_change"]["version"] == 1
    with factory() as session:
        executions = session.scalars(
            select(ImportExecution).where(ImportExecution.state == "succeeded")
        ).all()
        assert len(executions) == 2
        assert all(execution.html_preview_images is not None for execution in executions)


def test_legacy_imports_report_missing_images_until_refresh(html_api, monkeypatch):
    client, seed, factory = html_api
    from unittest.mock import AsyncMock

    from verboflex.services import html_preview_images

    # Simulate the previous worker during staging, respecting terminal immutability.
    with monkeypatch.context() as patch:
        patch.setattr(
            html_preview_images, "collect_html_preview_images", AsyncMock(return_value=None)
        )
        assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    preview = client.get(f"/api/v1/translations/{seed.value_ids[0]}/html-preview")
    assert preview.status_code == 200
    assert preview.json()["missing_images"] == 1
    assert "data:image/" not in preview.json()["document"]
    # A refresh at the same commit upgrades old previews without repository changes.
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    refreshed = client.get(f"/api/v1/translations/{seed.value_ids[0]}/html-preview")
    assert refreshed.json()["missing_images"] == 0
    assert image_data_uri(PNG) in refreshed.json()["document"]


def test_preview_images_follow_product_access_and_are_not_public(html_api):
    client, seed, factory = html_api
    endpoint = f"/api/v1/translations/{seed.value_ids[0]}/html-preview"
    assert client.get(endpoint).status_code == 200
    with factory.begin() as session:
        session.get(User, seed.actor_id).is_active = False
    response = client.get(endpoint)
    assert response.status_code == 404
    assert "data:image" not in response.text
