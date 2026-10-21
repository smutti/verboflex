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
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.role import Role
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.worker import import_tasks

HTML = b'<!DOCTYPE html><html><body><p class="fixed">Welcome {{name}}</p></body></html>'


@pytest.fixture
def html_api(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    adapter = RefreshSource(files={"mail/Welcome-EN.html": HTML}, commit_hashes=["a" * 40])
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
