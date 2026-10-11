"""History pages project frozen evidence without loading private file/proof bytes."""

from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import Text, select

from tests.api.test_submission_reviews import review_api as review_api
from tests.api.test_submissions import ready_api as ready_api
from tests.api.test_submissions import submit
from tests.integration.test_preview_jobs import clean_preview_database as clean_preview_database
from tests.integration.test_preview_jobs import preview_session_factory as preview_session_factory
from verboflex.core.config import Settings, get_settings
from verboflex.models.submission import ChangeSet


@pytest.fixture
def history_api(ready_api):
    client, seed, factory, _, _, _ = ready_api
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr("history-test-signing-secret-32-characters")
    )
    batch = submit(ready_api)
    assert batch.status_code == 202, batch.text
    return ready_api, UUID(batch.json()["groups"][0]["id"])


def test_history_lists_durable_group_and_frozen_value_diff(history_api):
    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets"
    page = client.get(base)
    assert page.status_code == 200, page.text
    assert page.json()["items"][0]["id"] == str(group_id)
    assert page.json()["page_size"] == 25
    values = client.get(f"{base}/{group_id}/values")
    assert values.status_code == 200, values.text
    assert len(values.json()["items"]) == 2
    assert {item["proposed_text"] for item in values.json()["items"]} == {"Ok"}
    with factory() as session:
        assert session.scalars(select(ChangeSet)).one().status == "queued"


def test_history_actor_remains_original_submitter_for_another_reader_without_email(history_api):
    from uuid import uuid4

    from verboflex.auth.principal import Principal, get_current_principal
    from verboflex.models.role import Role
    from verboflex.models.user import User
    from verboflex.schemas.users import RoleName

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    reader_id = uuid4()
    with factory.begin() as session:
        submitter = session.get(User, seed.actor_id)
        submitter.display_name = "Original submitter, renamed"
        submitter_email = submitter.email
        session.add(
            User(
                id=reader_id,
                email="history-reader@example.test",
                display_name="Current reader",
                hashed_password="unused",
                must_change_password=False,
                roles=[session.scalar(select(Role).where(Role.name == "viewer"))],
            )
        )
    client.app.dependency_overrides[get_current_principal] = lambda: Principal(
        reader_id, "history-reader@example.test", "Current reader", (RoleName.VIEWER,), False
    )
    base = f"/api/v1/products/{seed.product_id}/change-sets"
    detail = client.get(f"{base}/{group_id}")
    assert detail.status_code == 200
    expected = {"id": str(seed.actor_id), "display_name": "Original submitter, renamed"}
    assert detail.json().get("actor") == expected
    page = client.get(base)
    assert page.status_code == 200
    assert page.json()["items"][0]["actor"] == expected
    for response in (detail, page):
        assert submitter_email not in response.text
        assert "history-reader@example.test" not in response.text
        assert '"email"' not in response.text


def test_read_pages_are_authorized_and_never_load_private_proofs_or_raw_files(
    history_api, monkeypatch
):
    from sqlalchemy import event

    from verboflex.services import submission_codec, submissions

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready

    def forbidden(*args, **kwargs):
        pytest.fail("history must never decode full private writeback proof")

    monkeypatch.setattr(submission_codec, "decode_prepared_writeback", forbidden)
    monkeypatch.setattr(submissions, "load_change_set_bundle", forbidden)
    queries = []

    def capture(_conn, _cursor, statement, *_):
        queries.append(statement)

    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        base = f"/api/v1/products/{seed.product_id}/change-sets"
        for suffix in (
            "",
            f"/{group_id}",
            *(f"/{group_id}/{kind}" for kind in ("items", "values", "files", "activity")),
        ):
            result = client.get(base + suffix)
            assert result.status_code == 200, result.text
            assert "prepared_payload" not in result.text and "original_bytes" not in result.text
        detail = client.get(f"{base}/{group_id}").json()
        assert detail["provenance_available"] and detail["sources"][0]["commit_hash"] == "a" * 40
        assert detail["attempt_started_at"] is not None
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert queries and not any("prepared_payload" in sql for sql in queries)
    assert not any(
        "SELECT change_set_files.content" in sql or "SELECT change_set_files.original_bytes" in sql
        for sql in queries
    )


def test_history_preserves_frozen_values_and_reports_newer_pending_version(history_api):
    from verboflex.models.review import TranslationProposal, TranslationProposalValue

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    before = client.get(base + "/values").json()
    with factory.begin() as session:
        proposal = session.get(TranslationProposal, seed.proposal_id)
        proposal.version += 1
        proposal.state = "draft"
        for value in session.scalars(
            select(TranslationProposalValue).where(
                TranslationProposalValue.proposal_id == proposal.id
            )
        ):
            value.proposed_text = "newer"
    items = client.get(base + "/items").json()["items"]
    assert items[0]["proposal_version"] == seed.version
    assert items[0]["current_version"] == seed.version + 1 and items[0]["newer_version_available"]
    assert client.get(base + "/values").json() == before
    filtered = client.get(base.rsplit("/", 1)[0], params={"key_id": str(seed.key_id)})
    assert [r["id"] for r in filtered.json()["items"]] == [str(group_id)]
    from uuid import uuid4

    assert client.get(base.rsplit("/", 1)[0], params={"key_id": str(uuid4())}).json()["items"] == []


def test_32_member_values_have_exact_25_and_7_pages_and_bound_cursors(request, monkeypatch):
    import tests.api.test_submission_reviews as review_tests

    original = review_tests.seed_writeback_authority
    monkeypatch.setattr(
        review_tests,
        "seed_writeback_authority",
        lambda factory, patch: original(factory, patch, members=32),
    )
    ready, group_id = request.getfixturevalue("history_api")
    client, seed, _, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    first = client.get(base + "/values").json()
    assert len(first["items"]) == 25 and first["next_cursor"]
    second = client.get(base + "/values", params={"cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 7 and second["next_cursor"] is None
    assert len({v["value_id"] for v in first["items"] + second["items"]}) == 32
    assert client.get(base + "/files", params={"cursor": first["next_cursor"]}).status_code == 422
    tampered = first["next_cursor"][:-1] + ("A" if first["next_cursor"][-1] != "A" else "B")
    assert client.get(base + "/values", params={"cursor": tampered}).status_code == 422


def test_value_page_byte_budget_is_applied_before_loading_values(request, monkeypatch):
    import tests.api.test_submission_reviews as review_tests
    from verboflex.services import submission_history

    original = review_tests.seed_writeback_authority
    monkeypatch.setattr(
        review_tests,
        "seed_writeback_authority",
        lambda factory, patch: original(factory, patch, members=32),
    )
    ready, group_id = request.getfixturevalue("history_api")
    client, seed, factory, _, _, _ = ready
    from sqlalchemy import func

    from verboflex.models.submission import ChangeSetItem

    with factory() as session:
        size = session.scalar(select(func.octet_length(ChangeSetItem.members[0].cast(Text))))
    monkeypatch.setattr(submission_history, "MAX_PAGE_BYTES", size * 2)
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}/values"
    page = client.get(base).json()
    assert 1 <= len(page["items"]) < 25 and page["next_cursor"]
    seen = {v["value_id"] for v in page["items"]}
    while page["next_cursor"]:
        page = client.get(base, params={"cursor": page["next_cursor"]}).json()
        assert seen.isdisjoint(v["value_id"] for v in page["items"])
        seen.update(v["value_id"] for v in page["items"])
    assert len(seen) == 32


def test_activity_is_typed_private_payload_free_and_cursor_paginated(history_api):
    from uuid import uuid4

    from verboflex.models.submission import ChangeSetEvent

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    with factory.begin() as session:
        group = session.get(ChangeSet, group_id)
        for _index in range(31):
            session.add(
                ChangeSetEvent(
                    id=uuid4(),
                    change_set_id=group_id,
                    attempt=1,
                    execution_fence=1,
                    proof_sequence=1,
                    event_kind="observation",
                    step="pull_request",
                    outcome="verified",
                    request_digest="a" * 64,
                    receipt={
                        "id": 7,
                        "url": "javascript:private",
                        "state": "OPEN",
                        "source_branch": group.source_branch,
                        "source_commit": "b" * 40,
                        "target_branch": group.target_branch,
                        "target_commit": group.target_head,
                        "response_body": "do-not-expose",
                        "access_token": "do-not-expose",
                    },
                )
            )
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}/activity"
    first = client.get(base)
    assert (
        first.status_code == 200
        and "do-not-expose" not in first.text
        and "javascript:" not in first.text
    )
    data = first.json()
    assert len(data["items"]) == 25 and all(e["receipt"]["url"] is None for e in data["items"])
    second = client.get(base, params={"cursor": data["next_cursor"]}).json()
    assert len(second["items"]) == 6 and second["next_cursor"] is None
    assert len({e["id"] for e in data["items"] + second["items"]}) == 31


def test_history_group_file_item_pagination_and_key_scope(history_api):
    from uuid import uuid4

    from tests.integration.test_submission_schema import _clone_file, _clone_group
    from verboflex.models.submission import ChangeSetFile, ChangeSetItem

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    # Derived storage rows isolate pagination: they never grant worker authority.
    with factory.begin() as session:
        group = session.get(ChangeSet, group_id)
        file = session.scalars(select(ChangeSetFile)).one()
        item = session.scalars(select(ChangeSetItem)).one()
        for index in range(27):
            _clone_group(session, group)
            session.add(_clone_file(file, group, path=f"pages/{index}.xml"))
            session.add(
                ChangeSetItem(
                    change_set_id=group_id,
                    proposal_id=uuid4(),
                    proposal_version=1,
                    repository_id=group.repository_id,
                    provider_repository_id=group.provider_repository_id,
                    target_branch=group.target_branch,
                    key_id=uuid4(),
                    language="it",
                    members=[{**item.members[0], "key": "界" * 600}],
                )
            )
    base = f"/api/v1/products/{seed.product_id}/change-sets"
    for suffix in ("", f"/{group_id}/files", f"/{group_id}/items"):
        page1 = client.get(base + suffix)
        assert page1.status_code == 200, page1.text
        first = page1.json()
        assert len(first["items"]) == 25 and first["next_cursor"]
        second = client.get(base + suffix, params={"cursor": first["next_cursor"]}).json()
        assert len(second["items"]) == 3 and second["next_cursor"] is None
    items = client.get(f"{base}/{group_id}/items").json()["items"]
    assert any(i["key_truncated"] and len(i["key"]) == 512 for i in items)
    cursor = client.get(base).json()["next_cursor"]
    assert (
        client.get(base, params={"cursor": cursor, "key_id": str(seed.key_id)}).status_code == 422
    )


def test_read_authority_and_cursor_binding_survive_role_changes_safely(history_api):
    from uuid import uuid4

    from verboflex.models.role import Role
    from verboflex.models.user import User

    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == "viewer"))
        ]
    for suffix in ("", "/items", "/values", "/files", "/activity"):
        assert client.get(base + suffix).status_code == 200
        assert (
            client.get(base.replace(str(seed.product_id), str(uuid4())) + suffix).status_code == 404
        )
    with factory.begin() as session:
        session.get(User, seed.actor_id).is_active = False
    assert client.get(base + "/values").status_code == 403


def test_legacy_frozen_rows_report_unavailable_provenance(request):
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    from verboflex.models.submission import ChangeSetItem

    def legacy(session, *_):
        for row in session.new:
            if isinstance(row, ChangeSetItem):
                row.members = [
                    {
                        k: v
                        for k, v in m.items()
                        if k not in {"source", "sources", "format", "file_changed_values"}
                    }
                    for m in row.members
                ]

    event.listen(Session, "before_flush", legacy)
    try:
        ready, group_id = request.getfixturevalue("history_api")
    finally:
        event.remove(Session, "before_flush", legacy)
    client, seed, _, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    detail = client.get(base).json()
    assert detail["sources"] == [] and not detail["provenance_available"]
    assert client.get(base + "/values").json()["items"][0]["source"] is None
    assert client.get(base + "/files").json()["items"][0]["source"] is None


def test_retried_attempt_has_its_own_durable_polling_age(history_api):
    ready, group_id = history_api
    client, seed, factory, _, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    original = client.get(base).json()
    with factory.begin() as session:
        session.get(ChangeSet, group_id).status = "blocked"
    result = client.post(base + "/retry", json={"expected_attempt": 1})
    assert result.status_code == 202, result.text
    after = client.get(base).json()
    assert after["attempt"] == 2
    assert after["attempt_started_at"] > original["attempt_started_at"]
    assert client.get(base).json()["attempt_started_at"] == after["attempt_started_at"]


@pytest.mark.parametrize("separate", [False, True])
def test_provenance_uses_accepted_import_even_when_unchanged_basis_revision_is_older(
    request, monkeypatch, separate
):
    import asyncio
    from uuid import uuid4

    import tests.api.test_submission_reviews as review_tests
    from tests.integration.test_confirmed_layout_refresh import _run
    from tests.integration.test_submission_review_jobs import create, get
    from tests.integration.test_writeback_authority import PreparedSource
    from verboflex.models.translation import TranslationValueRevision
    from verboflex.services.submission_reviews import execute_submission_review

    seed_original = review_tests.seed_writeback_authority
    monkeypatch.setattr(
        review_tests,
        "seed_writeback_authority",
        lambda factory, patch: seed_original(factory, patch, separate=separate),
    )
    client, seed, _, factory = request.getfixturevalue("review_api")
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr("history-test-signing-secret-32-characters")
    )
    client.app.state.submission_enqueuer = lambda _: None
    seed.adapter.commit_hashes = ["b" * 40]
    refreshed = _run(factory, seed.product_id, seed.mapping_id)
    assert refreshed.state == "current"
    queued = create(factory, seed)
    reader = PreparedSource(seed)
    with factory() as session:
        from verboflex.models.repository import Repository

        for slug in session.scalars(select(Repository.repository_slug)):
            reader.heads[slug] = "b" * 40
        revisions = session.scalars(
            select(TranslationValueRevision).where(
                TranslationValueRevision.value_id == seed.value_ids[0]
            )
        ).all()
        assert {r.source_commit_hash for r in revisions} == {"a" * 40}
    asyncio.run(execute_submission_review(factory, review_id=queued.id, adapter=reader))
    ready = get(factory, seed, queued.id)
    assert ready.state == "ready"
    response = client.post(
        f"/api/v1/products/{seed.product_id}/submission-batches",
        json={
            "review_id": str(ready.id),
            "expected_review_attempt": ready.attempt,
            "expected_content_digest": ready.manifest_digest,
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code == 202, response.text
    group_id = response.json()["groups"][0]["id"]
    base = f"/api/v1/products/{seed.product_id}/change-sets/{group_id}"
    detail = client.get(base).json()
    assert detail["provenance_available"]
    assert {s["commit_hash"] for s in detail["sources"]} == {"b" * 40}
    assert {s["repository_side"] for s in detail["sources"]} == (
        {"keys", "translations"} if separate else {"direct"}
    )
    assert {s["import_execution_id"] for s in detail["sources"]} == {
        str(refreshed.active_baseline_execution_id)
    }
    for kind in ("values", "files"):
        projection = client.get(base + "/" + kind)
        assert projection.status_code == 200, projection.text
        assert {item["source"]["commit_hash"] for item in projection.json()["items"]} == {"b" * 40}


@pytest.mark.parametrize("legacy", [False, True])
def test_file_change_count_matches_review_with_noop_and_duplicate_physical_members(
    request, monkeypatch, legacy
):
    from uuid import uuid4

    from sqlalchemy import event
    from sqlalchemy.orm import Session

    import tests.api.test_submission_reviews as review_tests
    from verboflex.models.review import TranslationProposalValue
    from verboflex.models.submission import ChangeSetItem
    from verboflex.models.translation import TranslationValue

    original = review_tests.seed_writeback_authority

    def no_op_seed(factory, patch):
        seed = original(factory, patch)
        # Keep a complete Approved aggregate containing one unchanged member.
        with factory.begin() as session:
            member = session.scalars(
                select(TranslationProposalValue)
                .where(TranslationProposalValue.proposal_id == seed.proposal_id)
                .order_by(TranslationProposalValue.translation_value_id)
            ).first()
            member.proposed_text = session.get(
                TranslationValue, member.translation_value_id
            ).display_text
        return seed

    monkeypatch.setattr(review_tests, "seed_writeback_authority", no_op_seed)

    def remove_frozen_count(session, *_):
        if legacy:
            for item in session.new:
                if isinstance(item, ChangeSetItem):
                    item.members = [
                        {
                            key: value
                            for key, value in member.items()
                            if key != "file_changed_values"
                        }
                        for member in item.members
                    ]

    event.listen(Session, "before_flush", remove_frozen_count)
    try:
        ready, group_id = request.getfixturevalue("history_api")
    finally:
        event.remove(Session, "before_flush", remove_frozen_count)
    client, seed, factory, review, _, _ = ready
    base = f"/api/v1/products/{seed.product_id}"
    reviewed = client.get(f"{base}/submission-reviews/{review.id}/files").json()["items"][0]
    assert reviewed["changed_values"] == 1
    frozen = client.get(f"{base}/change-sets/{group_id}/files").json()["items"][0]
    assert frozen["changed_values"] == reviewed["changed_values"]
    with factory.begin() as session:
        item = session.scalars(select(ChangeSetItem)).one()
        session.add(
            ChangeSetItem(
                change_set_id=group_id,
                proposal_id=uuid4(),
                proposal_version=1,
                repository_id=item.repository_id,
                provider_repository_id=item.provider_repository_id,
                target_branch=item.target_branch,
                key_id=item.key_id,
                language=item.language,
                members=item.members,
            )
        )
    assert (
        client.get(f"{base}/change-sets/{group_id}/files").json()["items"][0]["changed_values"] == 1
    )
