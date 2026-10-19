"""Explicit per-product fallback with real PostgreSQL and synthetic Qt sources."""

import asyncio
import importlib
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from verboflex.models.audit import AuditEntry
from verboflex.models.source_fallback import SourceFallbackPolicy, SourceFallbackText
from verboflex.models.translation import TranslationValue, TranslationValueLocator

WORKSPACE = importlib.import_module("tests.api.test_translation_workspace")
WORK = WORKSPACE.WORK
factory = WORKSPACE.factory
clean_database = WORKSPACE.clean_database


def policy(token, product, body=None):
    return asyncio.run(
        WORK.SUPPORT.SUPPORT._request(
            "GET" if body is None else "PUT",
            f"/api/v1/admin/products/{product}/source-fallback",
            token=token,
            **({"json": body} if body is not None else {}),
        )
    )


def configuration(**changes):
    return {
        "expected_version": 0,
        "enabled": True,
        "language": "it-IT",
        "source_texts": ["Operazione completata"],
        **changes,
    }


def remaining(token, product):
    filters = dict(product_id=product, language="it-IT", work_status="needs_translation")
    for reader in (WORKSPACE.request, WORK.request):
        response = reader(token, **filters)
        assert response.status_code == 200, response.text
        yield len(response.json()["items"])


def test_explicit_fallback_changes_effective_text_and_both_queues_without_writing_values(factory):
    admin = WORK.authority(factory, "admin")
    product, groups = WORKSPACE.seed_qt_base_catalog(factory)
    before = policy(admin, product).json()
    assert before == dict(
        product_id=str(product),
        version=0,
        enabled=False,
        language=None,
        source_texts=[],
        available_languages=["it-IT"],
    )
    assert list(remaining(admin, product)) == [2, 2]
    saved = policy(admin, product, configuration())
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert list(remaining(admin, product)) == [1, 1]
    rows = WORKSPACE.request(admin, product_id=product).json()["items"]
    native, foreign = (row["slots"][0] for row in rows)
    assert native["effective_text"] == "Operazione completata"
    assert native["uses_source_fallback"] and native["editable"]
    assert native["edit_field"] == "translated_text"
    assert foreign["effective_text"] == "" and not foreign["uses_source_fallback"]
    assert WORKSPACE.request(admin, product_id=product, q="Operazione completata").json()["items"]
    with factory() as session:
        assert all(
            session.get_one(TranslationValue, group).translated_text == "" for group in groups
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEntry)
                .where(AuditEntry.entity_id == product, AuditEntry.action == "product.updated")
            )
            == 1
        )
    disabled = policy(admin, product, configuration(expected_version=1, enabled=False))
    assert disabled.status_code == 200
    assert list(remaining(admin, product)) == [2, 2]


@pytest.mark.parametrize("role", ["viewer", "translator", "product_manager_reviewer"])
def test_configuration_is_admin_only(factory, role):
    token = WORK.authority(factory, role)
    product, _ = WORKSPACE.seed_qt_base_catalog(factory)
    assert policy(token, product).status_code == 403
    assert policy(token, product, configuration()).status_code == 403
    assert policy(None, product).status_code == 401
    with factory() as session:
        assert session.get(SourceFallbackPolicy, product) is None


@pytest.mark.parametrize(
    "body, status",
    [
        ({"language": None}, 422),
        ({"language": "en"}, 409),
        ({"source_texts": ["Same", "Same"]}, 422),
        ({"source_texts": [" "]}, 422),
        ({"source_texts": ["null\x00byte"]}, 422),
        ({"source_texts": ["x" * 4097]}, 422),
        ({"source_texts": [str(i) + "x" * 4000 for i in range(70)]}, 422),
        ({"unexpected": True}, 422),
        ({"expected_version": 1}, 409),
    ],
)
def test_configuration_is_bounded_and_versioned(factory, body, status):
    admin = WORK.authority(factory, "admin")
    product, _ = WORKSPACE.seed_qt_base_catalog(factory)
    assert policy(admin, product, configuration(**body)).status_code == status
    assert policy(admin, product, configuration()).status_code == 200
    stale = policy(admin, product, configuration(source_texts=["Open the message"]))
    assert stale.status_code == 409
    assert policy(admin, product).json()["source_texts"] == ["Operazione completata"]
    assert policy(admin, uuid4()).status_code == 404


@pytest.mark.parametrize("change", ["source", "format", "plural", "language", "source_only"])
def test_fallback_is_exact_scalar_qt_base_only(factory, change):
    admin = WORK.authority(factory, "admin")
    product, groups = WORKSPACE.seed_qt_base_catalog(factory)
    assert policy(admin, product, configuration()).status_code == 200
    with factory.begin() as session:
        value = session.get_one(TranslationValue, groups[0])
        if change == "source":
            value.source_text += "!"
        elif change == "format":
            session.get_one(TranslationValueLocator, value.id).format = "android_xml"
        elif change == "plural":
            value.selector_kind = "qt_numerus"
        elif change == "language":
            value.language = "fr"
        else:
            value.translated_text = None
    rows = WORKSPACE.request(admin, product_id=product).json()["items"]
    assert not any(slot["uses_source_fallback"] for row in rows for slot in row["slots"])


def test_actual_translation_and_proposal_override_fallback(factory):
    admin = WORK.authority(factory, "admin")
    product, groups = WORKSPACE.seed_qt_base_catalog(factory)
    assert policy(admin, product, configuration()).status_code == 200
    member = WORK.request(admin, f"/{groups[0]}").json()["values"][0]
    response = asyncio.run(
        WORK.SUPPORT.SUPPORT._request(
            "PUT",
            f"/api/v1/translations/{groups[0]}/proposal",
            token=admin,
            json={
                "expected_version": 0,
                "values": [
                    {
                        "translation_value_id": member["id"],
                        "selector_version": member["selector_version"],
                        "selector_digest": member["selector_digest"],
                        "basis_revision_number": member["history"][0]["revision_number"],
                        "basis_digest": member["history"][0]["revision_digest"],
                        "proposed_text": "Operazione terminata",
                    }
                ],
            },
        )
    )
    assert response.status_code == 200, response.text
    slot = WORKSPACE.request(admin, product_id=product).json()["items"][0]["slots"][0]
    assert slot["effective_text"] == "Operazione terminata" and not slot["uses_source_fallback"]
    # Rejected proposals revert to the explicitly confirmed source, not a missing value.
    with factory.begin() as session:
        proposal = session.scalar(select(WORKSPACE.TranslationProposal))
        proposal.state = "rejected"
    assert list(remaining(admin, product)) == [1, 1]
    with factory.begin() as session:
        value = session.get_one(TranslationValue, groups[0])
        value.translated_text = value.display_text = "Traduzione dal repository"
    slot = WORKSPACE.request(admin, product_id=product).json()["items"][0]["slots"][0]
    assert slot["effective_text"] == "Traduzione dal repository"
    assert not slot["uses_source_fallback"]


def test_policy_change_invalidates_both_search_cursors_and_is_product_scoped(factory):
    admin = WORK.authority(factory, "admin")
    other, _ = WORKSPACE.seed_qt_base_catalog(factory)
    product, _, _ = WORKSPACE.seed_keys(factory)
    readers = (WORKSPACE.request, WORK.request)
    cursors = [reader(admin, product_id=product).json()["next_cursor"] for reader in readers]
    assert all(cursors)
    assert policy(admin, product, configuration(language="en")).status_code == 200
    for reader, cursor in zip(readers, cursors, strict=True):
        assert reader(admin, product_id=product, cursor=cursor).status_code == 422
    assert list(remaining(admin, other)) == [2, 2]
    with factory() as session:
        assert session.get(SourceFallbackPolicy, other) is None
        assert session.scalar(select(func.count()).select_from(SourceFallbackText)) == 1
