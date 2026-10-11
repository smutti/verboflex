"""Work queues and actual source history through authenticated PostgreSQL reads."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.import_job import ImportSourceReference
from verboflex.models.product import Product
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.translation import (
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.models.user import User

SUPPORT = importlib.import_module("tests.api.test_translation_reviews")
SEARCH = importlib.import_module("tests.integration.test_translation_search")


@pytest.fixture(scope="module")
def factory():
    with SUPPORT._review_database() as result:
        yield result


@pytest.fixture(autouse=True)
def clean_database(factory):
    app.dependency_overrides.clear()
    with factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    SUPPORT.SUPPORT._configure_dependencies(factory)
    rate_support = importlib.import_module("tests.api.test_rate_limits")
    app.dependency_overrides[get_redis_client] = lambda: rate_support.CountingRedis()
    yield
    app.dependency_overrides.clear()


def request(token, suffix="", **params):
    from urllib.parse import urlencode

    path = f"/api/v1/translations{suffix}"
    if params:
        path += "?" + urlencode(params)
    return asyncio.run(SUPPORT.SUPPORT._request("GET", path, token=token))


def authority(factory, role="translator"):
    return SUPPORT.SUPPORT._create_authority(factory, role_names=(role,))


def revision(session, value, *, source, number):
    locator = session.get_one(TranslationValueLocator, value.id)
    session.add(
        TranslationValueRevision(
            value_id=value.id,
            translation_key_id=value.translation_key_id,
            revision_number=number,
            revision_digest=hashlib.sha256(f"{value.id}:{number}".encode()).hexdigest(),
            import_job_id=locator.import_job_id,
            import_execution_id=locator.import_execution_id,
            source_reference_position=locator.source_reference_position,
            source_commit_hash="a" * 40,
            source_text=source,
            translated_text=value.translated_text,
            display_text=source or value.translated_text or "",
            structure=value.structure,
            review_state=value.review_state,
            is_deleted=value.is_deleted,
            deleted_at=value.deleted_at,
        )
    )


def seed(
    factory,
    *,
    format="android_xml",
    text_value="",
    name="Source",
    base=True,
    kind="scalar",
    source_fields=None,
    target_fields=None,
    embedded=False,
    target_revision=True,
    separate=False,
):
    product_id, scope_id = SEARCH._seed_dataset(factory, name=name, separate=separate)
    group_id = SEARCH._add_group(
        factory,
        product_id=product_id,
        scope_id=scope_id,
        raw_key="greeting",
        language="fr",
        values=(
            {
                "translated_text": text_value,
                "display_text": text_value,
                "source_text": "Original" if embedded else None,
            },
        ),
    )
    with factory.begin() as session:
        target = session.get_one(TranslationValue, group_id)
        target.selector_kind = kind
        target.selector_bytes = json.dumps(
            {"version": 1, "kind": kind, "fields": target_fields or {}}
        ).encode()
        target.selector_digest = hashlib.sha256(target.selector_bytes).hexdigest()
        locator = session.get_one(TranslationValueLocator, group_id)
        locator.format = format
        if target_revision:
            revision(session, target, source=target.source_text, number=1)
        source_id = target.id if embedded else None
        if base:
            selector = json.dumps(
                {"version": 1, "kind": kind, "fields": source_fields or {}}
            ).encode()
            source = TranslationValue(
                id=uuid4(),
                scope_id=scope_id,
                translation_key_id=target.translation_key_id,
                language="en",
                selector_version=1,
                selector_kind=kind,
                selector_bytes=selector,
                selector_digest=hashlib.sha256(selector).hexdigest(),
                source_text="Original",
                translated_text=None,
                display_text="Original",
                structure=[],
                review_state="draft",
                grapheme_count=8,
                effective_constraint_source="none",
                is_over_limit=False,
                is_deleted=False,
            )
            session.add(source)
            session.flush()
            source_ref = session.get_one(
                ImportSourceReference, (locator.import_execution_id, 1 if separate else 0)
            )
            session.add(
                TranslationValueLocator(
                    value_id=source.id,
                    translation_key_id=source.translation_key_id,
                    import_job_id=locator.import_job_id,
                    import_execution_id=locator.import_execution_id,
                    source_reference_position=source_ref.position,
                    repository_side=source_ref.repository_side,
                    repository_id=source_ref.repository_id,
                    configured_branch="main",
                    source_commit_hash="a" * 40,
                    format=format,
                    path=source_ref.path,
                    position=0,
                    structural_address=["source"],
                    line=1,
                    column=1,
                )
            )
            session.flush()
            revision(session, source, source="Original", number=1)
            if not embedded:
                source_id = source.id
    return product_id, group_id, source_id


@pytest.mark.parametrize(
    "format,kind,fields",
    [
        ("android_xml", "scalar", {}),
        ("ios_strings", "scalar", {}),
        ("json", "json_path", {"parents": ["screen"]}),
    ],
)
def test_split_source_is_resolved_and_base_only_changes_are_detected(factory, format, kind, fields):
    token = authority(factory)
    product, group, source = seed(
        factory, format=format, kind=kind, source_fields=fields, target_fields=fields
    )
    listed = request(token, language="fr", product_id=product)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["source_text"] == "Original"
    detail = request(token, f"/{group}").json()
    assert detail["values"][0]["source_text"] == "Original"
    assert detail["values"][0]["source_resolution"] == "matched"
    assert detail["values"][0]["source_comparison"] is None
    assert detail["source_context"][0]["source_value_id"] == str(source)
    assert detail["source_context"][0]["provenance"]["repository_side"] == "direct"
    assert request(token, work_status="source_changed", language="fr").json()["items"] == []
    with factory.begin() as session:
        value = session.get_one(TranslationValue, source)
        value.source_text = "Updated source only"
        revision(session, value, source=value.source_text, number=2)
    changed = request(token, work_status="source_changed", language="fr")
    assert [row["id"] for row in changed.json()["items"]] == [str(group)]
    assert request(token, q="updated source", language="fr").json()["items"][0]["id"] == str(group)
    detail = request(token, f"/{group}").json()
    comparison = detail["values"][0]["source_comparison"]
    assert comparison["previous_text"] == "Original"
    assert comparison["current_text"] == "Updated source only"
    assert comparison["source_value_id"] == str(source)
    assert comparison["changed"] is True
    assert [entry["revision_number"] for entry in detail["values"][0]["history"]] == [1]


@pytest.mark.parametrize("blank", ["", " \t\n", "\u00a0\u2007\u202f\u3000"])
def test_missing_text_queue_excludes_source_groups(factory, blank):
    token = authority(factory)
    _, group, _ = seed(factory, text_value=blank)
    response = request(token, work_status="needs_translation")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [str(group)]


def test_fresh_pending_text_and_review_queue_require_exact_current_members(factory):
    token = authority(factory)
    _, group, _ = seed(factory, target_revision=False)
    SEARCH._seed_pending_context(factory, group_id=group)
    with factory.begin() as session:
        session.scalar(select(TranslationProposalValue)).proposed_text = "Filled proposal"
    assert request(token, work_status="needs_translation").json()["items"] == []
    assert request(token, work_status="needs_review").json()["items"][0]["id"] == str(group)
    with factory.begin() as session:
        proposal = session.scalar(select(TranslationProposal))
        proposal.state = "approved"
    assert request(token, work_status="needs_review").json()["items"] == []
    with factory.begin() as session:
        pending = session.scalar(select(TranslationProposalValue))
        pending.basis_revision_number += 1
    assert request(token, work_status="needs_translation").json()["items"][0]["id"] == str(group)


def test_qt_embedded_source_precedence_and_bounded_full_text_comparison(factory):
    token = authority(factory)
    _, group, source = seed(factory, format="qt_ts", embedded=True)
    with factory.begin() as session:
        value = session.get_one(TranslationValue, source)
        value.source_text = "A" * 5000
        revision(session, value, source=value.source_text, number=2)
        value.source_text += "changed beyond excerpt"
        revision(session, value, source=value.source_text, number=3)
    detail = request(token, f"/{group}").json()
    assert detail["values"][0]["source_resolution"] == "embedded"
    assert len(detail["source_context"]) == 1
    comparison = detail["values"][0]["source_comparison"]
    assert comparison["changed"] is True
    assert comparison["previous_text"] == comparison["current_text"] == "A" * 4096
    assert comparison["previous_truncated"] and comparison["current_truncated"]
    assert comparison["previous_revision_number"] == 2
    assert comparison["current_revision_number"] == 3


@pytest.mark.parametrize("key_deleted", [False, True])
def test_tombstoned_embedded_source_remains_readable_and_searchable_only_in_deleted_modes(
    factory, key_deleted
):
    token = authority(factory)
    product, group, _ = seed(factory, format="qt_ts", embedded=True, text_value="Traduction")
    with factory.begin() as session:
        target = session.get_one(TranslationValue, group)
        target.source_text = "Removed source phrase"
        revision(session, target, source=target.source_text, number=2)
    before = request(token, f"/{group}").json()
    with factory.begin() as session:
        target = session.get_one(TranslationValue, group)
        target.is_deleted = True
        target.deleted_at = datetime.now(UTC)
        key = session.get_one(TranslationKey, target.translation_key_id)
        key.is_deleted = key_deleted
        key.deleted_at = target.deleted_at if key_deleted else None
        revision(session, target, source=target.source_text, number=3)
    # Another live key/scope with the same raw key must not replace retained source.
    seed(factory, name="Other live product")
    detail = request(token, f"/{group}").json()
    member = detail["values"][0]
    assert detail["is_deleted"] and member["is_deleted"]
    assert not detail["mutation_eligible"]
    assert member["source_text"] == "Removed source phrase"
    assert member["source_value_id"] == str(group)
    assert member["source_resolution"] == "embedded"
    assert member["provenance"] == before["values"][0]["provenance"]
    assert member["source_comparison"] is None
    assert len(detail["source_context"]) == 1
    context = detail["source_context"][0]
    assert context["source_text"] == "Removed source phrase"
    assert context["source_value_id"] == str(group)
    assert context["provenance"] == before["source_context"][0]["provenance"]
    assert context["source_comparison"] is None
    for mode in ("deleted", "all"):
        response = request(
            token, product_id=product, language="fr", deleted=mode, q="Removed source phrase"
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [str(group)]
        assert response.json()["items"][0]["source_text"] == "Removed source phrase"
    assert (
        request(token, product_id=product, language="fr", q="Removed source phrase").json()["items"]
        == []
    )
    for work in ("needs_translation", "needs_review", "source_changed"):
        assert (
            request(
                token, product_id=product, language="fr", deleted="all", work_status=work
            ).json()["items"]
            == []
        )


def test_deleted_split_target_does_not_reconnect_to_a_live_base_source(factory):
    token = authority(factory)
    product, group, _ = seed(factory)
    with factory.begin() as session:
        target = session.get_one(TranslationValue, group)
        target.is_deleted = True
        target.deleted_at = datetime.now(UTC)
        revision(session, target, source=None, number=2)
    detail = request(token, f"/{group}").json()
    assert detail["source_context"] == []
    assert detail["values"][0]["source_text"] is None
    assert detail["values"][0]["source_value_id"] is None
    assert detail["values"][0]["source_comparison"] is None
    assert (
        request(token, product_id=product, language="fr", deleted="all", q="Original").json()[
            "items"
        ]
        == []
    )


def test_unmatched_plural_keeps_group_source_without_fabricated_pairing(factory):
    token = authority(factory)
    _, group, source = seed(
        factory,
        kind="android_quantity",
        source_fields={"quantity": "one"},
        target_fields={"quantity": "few"},
    )
    detail = request(token, f"/{group}").json()
    assert detail["values"][0]["source_text"] is None
    assert detail["values"][0]["source_resolution"] == "unmatched"
    assert detail["source_context"][0]["source_text"] == "Original"
    with factory.begin() as session:
        value = session.get_one(TranslationValue, source)
        revision(session, value, source="New plural", number=2)
    assert request(token, work_status="source_changed", language="fr").json()["items"][0][
        "id"
    ] == str(group)


def test_source_never_leaks_from_another_scope_and_missing_is_explicit(factory):
    token = authority(factory)
    _, group, _ = seed(factory, base=False)
    seed(factory, name="Other", text_value="Different")
    detail = request(token, f"/{group}").json()
    assert detail["values"][0]["source_text"] is None
    assert detail["values"][0]["source_resolution"] == "unavailable"
    assert detail["source_context"] == []


@pytest.mark.parametrize("role", ["admin", "translator", "product_manager_reviewer", "viewer"])
def test_roles_can_read_but_unauthenticated_or_inactive_cannot(factory, role):
    token = authority(factory, role)
    product, group, _ = seed(factory)
    assert request(token, work_status="needs_translation").status_code == 200
    assert request(None, f"/{group}").status_code == 401
    with factory.begin() as session:
        session.get_one(Product, product).is_active = False
    assert request(token, f"/{group}").status_code == 404
    assert request(token, work_status="needs_translation").json()["items"] == []


def test_invalid_work_status_is_closed(factory):
    assert request(authority(factory), work_status="all").status_code == 422


def test_linked_keys_repository_is_the_actual_source(factory):
    token = authority(factory)
    _, group, source = seed(factory, separate=True)
    detail = request(token, f"/{group}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["values"][0]["source_text"] == "Original"
    context = detail.json()["source_context"][0]
    assert context["source_value_id"] == str(source)
    assert context["provenance"]["repository_side"] == "keys"
    assert (
        context["provenance"]["repository_id"]
        != detail.json()["values"][0]["provenance"]["repository_id"]
    )


def test_ambiguous_compatible_sources_are_context_only(factory):
    token = authority(factory)
    _, group, source_id = seed(factory)
    with factory.begin() as session:
        original = session.get_one(TranslationValue, source_id)
        duplicate = TranslationValue(
            scope_id=original.scope_id,
            translation_key_id=original.translation_key_id,
            language="en",
            selector_version=1,
            selector_kind="scalar",
            selector_bytes=b'{"version": 1, "kind": "scalar", "fields": { }}',
            selector_digest="f" * 64,
            source_text="Ambiguous source",
            translated_text=None,
            display_text="Ambiguous source",
            structure=[],
            review_state="draft",
            grapheme_count=16,
            effective_constraint_source="none",
            is_over_limit=False,
            is_deleted=False,
        )
        session.add(duplicate)
    detail = request(token, f"/{group}").json()
    assert detail["values"][0]["source_resolution"] == "ambiguous"
    assert detail["values"][0]["source_text"] is None
    assert len(detail["source_context"]) == 2
