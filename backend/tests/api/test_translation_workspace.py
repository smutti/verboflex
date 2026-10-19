"""Canonical multilingual pages through authenticated, disposable PostgreSQL."""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.orm import sessionmaker

from verboflex.auth.rate_limits import get_redis_client
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.product import Product
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
)
from verboflex.models.user import User
from verboflex.services.signed_cursor import SignedCursorCodec

WORK = importlib.import_module("tests.api.test_translation_work_filters")
SUPPORT = WORK.SUPPORT
SEARCH = WORK.SEARCH


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
    rates = importlib.import_module("tests.api.test_rate_limits")
    app.dependency_overrides[get_redis_client] = lambda: rates.CountingRedis()
    yield
    app.dependency_overrides.clear()


def request(token, **params):
    return asyncio.run(
        SUPPORT.SUPPORT._request(
            "GET", "/api/v1/translations/keys?" + urlencode(params, doseq=True), token=token
        )
    )


def seed_keys(factory, count=61):
    product, scope = SEARCH._seed_dataset(factory, name="Multilingual")
    identities = {}
    for index in range(count):
        key_id = None
        for language in ("en", "fr", "it"):
            group = SEARCH._add_group(
                factory,
                product_id=product,
                scope_id=scope,
                raw_key=f"key-{index:03d}" if key_id is None else f"temporary-{language}-{index}",
                language=language,
                values=(
                    {
                        "display_text": f"{language} {index}",
                        "source_text": f"en {index}" if language == "en" else None,
                        "translated_text": None if language == "en" else f"{language} {index}",
                    },
                ),
            )
            with factory.begin() as session:
                value = session.get_one(TranslationValue, group)
                if key_id is None:
                    key_id = value.translation_key_id
                else:
                    old_key = value.translation_key_id
                    locator = session.get_one(TranslationValueLocator, group)
                    locator_data = {
                        column.name: getattr(locator, column.name)
                        for column in TranslationValueLocator.__table__.columns
                    }
                    session.delete(locator)
                    session.flush()
                    value.translation_key_id = key_id
                    session.flush()
                    locator_data["translation_key_id"] = key_id
                    session.add(TranslationValueLocator(**locator_data))
                    session.flush()
                    session.execute(delete(TranslationKey).where(TranslationKey.id == old_key))
            identities[(index, language)] = group
    return product, scope, identities


def test_complete_multilingual_key_page_before_limit(factory):
    token = WORK.authority(factory, "viewer")
    product, scope, identities = seed_keys(factory)
    response = request(token, product_id=product, visible_languages=["en", "fr", "it", "de"])
    assert response.status_code == 200, response.text
    first = response.json()
    assert len(first["items"]) == 50
    assert first["visible_languages"] == ["en", "fr", "it", "de"]
    for index, item in enumerate(first["items"]):
        assert item["raw_key"] == f"key-{index:03d}"
        assert item["scope_id"] == str(scope)
        assert [slot["language"] for slot in item["slots"]] == ["en", "fr", "it"]
        for slot in item["slots"][:3]:
            assert slot["group_id"] == str(identities[(index, slot["language"])])
            assert slot["kind"] == "imported"
    second = request(
        token,
        product_id=product,
        visible_languages=["en", "fr", "it", "de"],
        cursor=first["next_cursor"],
    ).json()
    assert len(second["items"]) == 11
    assert second["next_cursor"] is None
    assert len({item["translation_key_id"] for item in first["items"] + second["items"]}) == 61
    matched = request(token, product_id=product, q="it 60", visible_languages=["en", "fr", "it"])
    assert matched.status_code == 200, matched.text
    assert len(matched.json()["items"]) == 1
    assert [slot["matches_filters"] for slot in matched.json()["items"][0]["slots"]] == [
        False,
        False,
        True,
    ]


def test_principal_releases_connection_before_workspace_read(factory):
    """One request must not hold authentication's lease while asking for a second."""
    token = WORK.authority(factory, "viewer")
    product, _, _ = seed_keys(factory, count=1)
    engine = create_engine(factory.kw["bind"].url, pool_size=1, max_overflow=0, pool_timeout=0.1)
    try:
        SUPPORT.SUPPORT._configure_dependencies(sessionmaker(engine, expire_on_commit=False))
        response = request(token, product_id=product, visible_languages=["en", "fr"])
        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 1
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def slots(body, index=0):
    return {slot["language"]: slot for slot in body["items"][index]["slots"]}


def seed_qt_base_catalog(factory):
    """Mixed source languages are not translations of the configured base locale."""
    import hashlib

    product, scope = SEARCH._seed_dataset(factory, name="Qt mixed source", base_language="it-IT")
    ids = []
    for index, source in enumerate(("Operazione completata", "Open the message")):
        group = SEARCH._add_group(
            factory,
            product_id=product,
            scope_id=scope,
            raw_key=f"message-{index}",
            language="it-IT",
            values=({"source_text": source, "translated_text": "", "display_text": ""},),
        )
        with factory.begin() as session:
            value = session.get_one(TranslationValue, group)
            value.selector_bytes = json.dumps(
                {"version": 1, "kind": "scalar", "fields": {}}
            ).encode()
            value.selector_digest = hashlib.sha256(value.selector_bytes).hexdigest()
            session.get_one(TranslationValueLocator, group).format = "qt_ts"
            WORK.revision(session, value, source=source, number=1)
        ids.append(group)
    return product, ids


def test_qt_base_catalog_keeps_mixed_sources_separate_and_empty_translations_actionable(factory):
    token = WORK.authority(factory)
    product, groups = seed_qt_base_catalog(factory)
    filters = dict(product_id=product, language="it-IT", work_status="needs_translation")
    response = request(token, **filters)
    assert response.status_code == 200, response.text
    assert [item["source_text"] for item in response.json()["items"]] == [
        "Operazione completata",
        "Open the message",
    ]
    for item, group in zip(response.json()["items"], groups, strict=True):
        slot = item["slots"][0]
        assert slot["effective_text"] == ""
        assert slot["matches_filters"]
        assert slot["editable"] and slot["edit_field"] == "translated_text"
        assert slot["group_id"] == str(group)
    assert len(WORK.request(token, **filters).json()["items"]) == 2
    # Searching the embedded source must still find the empty Italian translation.
    assert request(token, **filters, q="Open the message").json()["items"][0]["source_text"] == (
        "Open the message"
    )
    member = WORK.request(token, f"/{groups[1]}").json()["values"][0]
    saved = asyncio.run(
        SUPPORT.SUPPORT._request(
            "PUT",
            f"/api/v1/translations/{groups[1]}/proposal",
            token=token,
            json={
                "expected_version": 0,
                "values": [
                    {
                        "translation_value_id": member["id"],
                        "selector_version": member["selector_version"],
                        "selector_digest": member["selector_digest"],
                        "basis_revision_number": member["history"][0]["revision_number"],
                        "basis_digest": member["history"][0]["revision_digest"],
                        "proposed_text": "Apri il messaggio",
                    }
                ],
            },
        )
    )
    assert saved.status_code == 200, saved.text
    assert len(request(token, **filters).json()["items"]) == 1
    assert len(WORK.request(token, **filters).json()["items"]) == 1
    translated = request(token, product_id=product, q="Open the message").json()["items"][0]
    assert translated["source_text"] == "Open the message"
    assert translated["slots"][0]["effective_text"] == "Apri il messaggio"
    assert request(token, product_id=product, language="it-IT", work_status="needs_review").json()[
        "items"
    ]
    # Rejected/stale proposals cannot hide a missing translation.
    with factory.begin() as session:
        session.scalar(select(TranslationProposal)).state = "rejected"
    assert len(request(token, **filters).json()["items"]) == 2
    with factory() as session:
        value = session.get_one(TranslationValue, groups[1])
        assert value.source_text == "Open the message" and value.translated_text == ""


def test_scope_read_projection_tracks_commits_and_rolls_back_with_values(factory):
    _, scope_id, ids = seed_keys(factory, count=1)
    with factory() as session:
        before = session.get_one(LocalizationScope, scope_id)
        epoch = before.read_version
        counts = before.language_counts
        assert counts == {"en": [1, 1], "fr": [1, 0], "it": [1, 0]}
    with factory() as session:
        value = session.get_one(TranslationValue, ids[0, "fr"])
        value.language = "de"
        value.source_text = "Embedded"
        session.flush()
        scope = session.get_one(LocalizationScope, scope_id)
        assert scope.read_version > epoch
        assert scope.language_counts == {"en": [1, 1], "de": [1, 1], "it": [1, 0]}
        session.rollback()
    with factory() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        assert scope.read_version == epoch and scope.language_counts == counts
    with factory.begin() as session:
        session.execute(
            text("UPDATE translation_values SET display_text='Changed' WHERE scope_id=:id"),
            {"id": scope_id},
        )
    with factory() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        # One bulk write advances the epoch once, rather than once per member.
        assert scope.read_version == epoch + 1
        assert scope.language_counts == counts


@pytest.mark.parametrize("role", ["viewer", "translator", "admin", "product_manager_reviewer"])
def test_authorized_current_scope_and_password_gate(factory, role):
    token = WORK.authority(factory, role)
    product, group, _ = WORK.seed(factory)
    assert request(token).status_code == 200
    assert request(None).status_code == 401
    with factory.begin() as session:
        principal = session.scalar(select(User))
        principal.must_change_password = True
    assert request(token).status_code == 403
    with factory.begin() as session:
        session.scalar(select(User)).must_change_password = False
        session.get_one(Product, product).is_active = False
    assert request(token).json()["items"] == []
    with factory.begin() as session:
        session.get_one(Product, product).is_active = True
        session.get_one(Product, product).active_revision_id = None
    assert request(token).json()["items"] == []


def test_conditions_and_focus_apply_within_one_locale_then_project_siblings(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory, count=1)
    with factory.begin() as session:
        french = session.get_one(TranslationValue, ids[0, "fr"])
        french.review_state = "approved"
        french.effective_max_chars = 500
        french.effective_constraint_source = "language_override"
        french.is_over_limit = False
        italian = session.get_one(TranslationValue, ids[0, "it"])
        italian.effective_max_chars = 1
        italian.effective_constraint_source = "language_override"
        italian.is_over_limit = True
    filters = dict(product_id=product, visible_languages=["fr", "it"])
    assert request(token, **filters, state="approved", violation="over_limit").json()["items"] == []
    match = request(token, **filters, state="draft", violation="over_limit").json()
    assert not slots(match)["fr"]["matches_filters"]
    assert slots(match)["it"]["matches_filters"]
    assert request(token, **filters, q="it 0", language="fr").json()["items"] == []
    assert request(token, **filters, q="it 0", language="it").json()["items"]


def test_fresh_complete_pending_text_and_imported_state_are_distinct(factory):
    token = WORK.authority(factory)
    product, group, _ = WORK.seed(factory, target_revision=False)
    SEARCH._seed_pending_context(factory, group_id=group)
    with factory.begin() as session:
        session.scalar(select(TranslationProposalValue)).proposed_text = "Ready"
    response = request(token, product_id=product, visible_languages=["en", "fr"])
    assert response.status_code == 200, response.text
    french = slots(response.json())["fr"]
    assert french["effective_text"] == "Ready"
    assert french["editable"]
    assert request(token, product_id=product, work_status="needs_translation").json()["items"] == []
    assert request(token, product_id=product, work_status="needs_review").json()["items"]
    with factory.begin() as session:
        session.scalar(select(TranslationProposal)).state = "approved"
    assert request(token, product_id=product, state="approved").json()["items"] == []
    assert request(token, product_id=product, work_status="needs_review").json()["items"] == []
    with factory.begin() as session:
        session.scalar(select(TranslationProposalValue)).basis_revision_number += 1
    stale = slots(request(token, product_id=product).json())["fr"]
    assert stale["effective_text"] == ""
    assert stale["pending_change"]["reconciliation_required"]
    assert request(token, product_id=product, work_status="needs_translation").json()["items"]


@pytest.mark.parametrize(
    "format,kind", [("android_xml", "scalar"), ("json", "json_path"), ("ios_strings", "scalar")]
)
@pytest.mark.parametrize("side", ["direct", "translations"])
def test_base_leaf_is_editable_and_save_preserves_exact_basis(factory, format, kind, side):
    token = WORK.authority(factory)
    product, target, source = WORK.seed(
        factory, format=format, kind=kind, separate=side == "translations"
    )
    if side == "translations":
        # Code-only keys have no base text; the base locale lives alongside
        # the target locales in the translations repository.
        with factory.begin() as session:
            base_locator = session.get_one(TranslationValueLocator, source)
            target_locator = session.get_one(TranslationValueLocator, target)
            for field in ("repository_side", "repository_id", "source_reference_position", "path"):
                setattr(base_locator, field, getattr(target_locator, field))
    base = slots(request(token, product_id=product).json())["en"]
    assert base["editable"] and base["edit_field"] == "source_text"
    assert base["group_id"] == str(source)
    detail = WORK.request(token, f"/{source}").json()
    member = detail["values"][0]
    latest = member["history"][0]
    payload = {
        "expected_version": 0,
        "values": [
            {
                "translation_value_id": member["id"],
                "selector_version": member["selector_version"],
                "selector_digest": member["selector_digest"],
                "basis_revision_number": latest["revision_number"],
                "basis_digest": latest["revision_digest"],
                "proposed_text": "Updated source",
            }
        ],
    }
    saved = asyncio.run(
        SUPPORT.SUPPORT._request(
            "PUT", f"/api/v1/translations/{source}/proposal", token=token, json=payload
        )
    )
    assert saved.status_code == 200, saved.text
    after = WORK.request(token, f"/{source}").json()
    pending = after["pending_change"]["values"][0]
    assert pending["translation_value_id"] == str(source)
    assert pending["basis_digest"] == latest["revision_digest"]
    assert pending["selector_digest"] == member["selector_digest"]
    assert after["values"][0]["source_text"] == "Original"
    assert (
        slots(request(token, product_id=product).json())["en"]["effective_text"] == "Updated source"
    )


@pytest.mark.parametrize(
    "format,content,path,layout",
    [
        (
            "android_xml",
            b'<resources><string name="hello">Original</string></resources>',
            "app/src/main/res/values/strings.xml",
            "app/src/main/res",
        ),
        (
            "json",
            b'{"hello":"Original","keep":"Unchanged"}',
            "locales/en.json",
            "json:flat-per-locale:locales/{locale}.json",
        ),
        (
            "ios_strings",
            b'"hello" = "Original";\n"keep" = "Unchanged";',
            "en.lproj/Localizable.strings",
            "ios-strings:{locale}.lproj/Localizable.strings",
        ),
        (
            "android_xml",
            b'<resources><string name="hello">Original</string></resources>',
            "shared/moko-resources/base/strings.xml",
            "shared/moko-resources",
        ),
    ],
)
@pytest.mark.parametrize("side", ["direct", "translations"])
def test_pure_writer_changes_base_source_leaf_preserving_identity(
    factory, format, content, path, layout, side
):
    writer = importlib.import_module("tests.unit.localization.writing._support")
    from verboflex.localization.importing.registry import parse_canonical_snapshot

    source = writer.snapshot(
        content, format=format, path=path, layout_identity=layout, repository_side=side
    )
    before = parse_canonical_snapshot(source.parser_input)
    assert not before.issues
    selected = next(value for value in before.values if value.logical_key == "hello")
    assert selected.display_text == "Original"
    if side == "direct":
        assert selected.source_text == "Original" and selected.translated_text is None
    else:
        # Parsing a translations-side file happens before the code-key join
        # promotes the base locale to source_text in the imported dataset.
        assert selected.translated_text == "Original"
    rendered = writer.render(source, writer.edit(source, "hello", "Updated source"))
    from dataclasses import replace

    after = parse_canonical_snapshot(replace(source.parser_input, content=rendered.content))
    assert not after.issues
    assert [(v.logical_key, v.language, v.selector) for v in before.values] == [
        (v.logical_key, v.language, v.selector) for v in after.values
    ]
    assert (
        next(v for v in after.values if v.logical_key == "hello").display_text == "Updated source"
    )
    assert all(v.display_text == "Unchanged" for v in after.values if v.logical_key == "keep")


def test_embedded_source_and_keys_side_cannot_be_used_as_mutation_targets(factory):
    token = WORK.authority(factory)
    product, group, _ = WORK.seed(factory, format="qt_ts", base=False, embedded=True)
    response = request(token, product_id=product, visible_languages=["en", "fr", "it"])
    assert response.status_code == 200, response.text
    projected = slots(response.json())
    assert projected["en"]["kind"] == "source_context"
    assert projected["en"]["group_id"] is None
    assert not projected["en"]["editable"]
    assert projected["fr"]["group_id"] == str(group)
    assert projected["fr"]["edit_field"] == "translated_text"
    assert "it" not in projected
    linked, _, source = WORK.seed(factory, separate=True, name="Linked source")
    base = slots(request(token, product_id=linked).json())["en"]
    assert base["group_id"] == str(source)
    assert base["read_only_reason"] == "keys_repository"
    assert not base["editable"]


def test_source_only_products_have_real_source_rows_and_no_target_work(factory):
    token = WORK.authority(factory)
    product, scope = SEARCH._seed_dataset(factory, name="Source only")
    group = SEARCH._add_group(
        factory,
        product_id=product,
        scope_id=scope,
        raw_key="source-only",
        language="en",
        values=({"display_text": "Only source", "source_text": "Only source"},),
    )
    response = request(token, product_id=product, visible_languages=["en", "fr"])
    assert response.status_code == 200, response.text
    assert slots(response.json())["en"]["group_id"] == str(group)
    assert "fr" not in slots(response.json())
    assert request(token, product_id=product, work_status="needs_translation").json()["items"] == []


@pytest.mark.parametrize("filtered", [False, True])
def test_language_rows_use_each_repository_support_in_product_and_global_search(factory, filtered):
    token = WORK.authority(factory)
    first, first_scope = SEARCH._seed_dataset(factory, name="Regional repository")
    second, second_scope = SEARCH._seed_dataset(factory, name="Generic repository")
    for product, scope, languages in (
        (first, first_scope, ("en", "de-DE", "fr-FR")),
        (second, second_scope, ("en", "de", "it")),
    ):
        for language in languages:
            SEARCH._add_group(
                factory,
                product_id=product,
                scope_id=scope,
                raw_key=f"shared-{language}",
                language=language,
                values=({"display_text": language, "translated_text": language},),
            )
    selected = ["de", "de-DE", "en", "fr-FR", "it", "es"]
    query = {"q": "shared"} if filtered else {}
    for product_id in (None, first, second):
        params = {**query, "visible_languages": selected}
        if product_id is not None:
            params["product_id"] = product_id
        response = request(token, **params)
        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == (6 if product_id is None else 3)
        for item in response.json()["items"]:
            expected = (
                ["de-DE", "en", "fr-FR"] if item["product_id"] == str(first) else ["de", "en", "it"]
            )
            assert [slot["language"] for slot in item["slots"]] == expected
            # A supported language missing on this key still offers an absent slot.
            assert sum(slot["kind"] == "absent" for slot in item["slots"]) == 2
    assert request(token, product_id=first, visible_languages=["de"]).json()["items"] == []


def test_cursor_binds_principal_filters_import_and_proposal_even_in_all(factory):
    token = WORK.authority(factory)
    other = WORK.authority(factory, "viewer")
    product, scope, ids = seed_keys(factory)
    filters = dict(product_id=product, visible_languages=["fr", "it"])
    cursor = request(token, **filters).json()["next_cursor"]
    for changed in (
        {"token": other},
        {"visible_languages": ["fr"]},
        {"state": "draft"},
        {"q": "key"},
        {"language": "fr"},
    ):
        arguments = {"token": token, **filters, "cursor": cursor, **changed}
        result = request(**arguments)
        assert result.status_code == 422, result.text
        assert result.json() == {"detail": "Invalid translation cursor"}
    with factory.begin() as session:
        session.get_one(LocalizationScope, scope).dataset_version += 1
    assert request(token, **filters, cursor=cursor).status_code == 422
    cursor = request(token, **filters).json()["next_cursor"]
    SEARCH._seed_pending_context(factory, group_id=ids[0, "fr"])
    assert request(token, **filters, cursor=cursor).status_code == 422
    for field, value in (("version", 2), ("state", "approved"), ("reconciliation_required", True)):
        cursor = request(token, **filters).json()["next_cursor"]
        with factory.begin() as session:
            if field == "reconciliation_required":
                session.scalar(select(TranslationProposal)).state = "draft"
            setattr(session.scalar(select(TranslationProposal)), field, value)
        assert request(token, **filters, cursor=cursor).status_code == 422


def test_generated_workspace_contract_is_published(factory):
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    document = json.loads((frontend / "openapi.json").read_text())
    operation = document["paths"].get("/api/v1/translations/keys", {}).get("get")
    assert operation is not None, "The checked-in key page contract must be generated"
    assert operation["operationId"] == "searchTranslationKeys"
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert set(operation["responses"]) == {"200", "401", "403", "422", "503"}
    schemas = document["components"]["schemas"]
    page = schemas["TranslationKeyPageResponse"]
    assert page["additionalProperties"] is False
    assert page["properties"]["items"]["maxItems"] == 50
    assert schemas["TranslationKeySummary"]["properties"]["slots"]["maxItems"] == 20
    assert schemas["TranslationKeySummary"]["properties"]["raw_key"]["maxLength"] == 1024
    assert schemas["TranslationLanguageSlot"]["additionalProperties"] is False
    assert "searchTranslationKeys" in (frontend / "src/api/client/sdk.gen.ts").read_text()


@pytest.mark.parametrize(
    "query",
    [
        {"visible_languages": ["en"] * 21},
        {"visible_languages": ["fr", "fr"]},
        {"visible_languages": ["EN"]},
        {"visible_languages": ["en_US"]},
        {"visible_languages": [""]},
        {"visible_languages": ["x" * 65]},
        {"q": "x" * 257},
        {"cursor": "x" * 2049},
        {"cursor": ""},
        {"state": "verified"},
        {"deleted": "everything"},
        {"page_size": "51"},
        {"language": "EN"},
        {"unexpected_filter": "value"},
    ],
)
def test_query_bounds_are_closed(factory, query):
    assert request(WORK.authority(factory), **query).status_code == 422


def test_forged_anchor_tampering_and_cross_endpoint_cursor_fail_uniformly(factory):
    token = WORK.authority(factory)
    product, _, _ = seed_keys(factory)
    cursor = request(token, product_id=product).json()["next_cursor"]
    codec = SignedCursorCodec(SUPPORT.SUPPORT.SIGNING_SECRET, max_cursor_chars=2048)
    body = codec.decode_payload(cursor, required_keys=frozenset({"v", "binding", "last"}))
    body["last"] = [3, str(uuid4())]
    forged = codec.encode_payload(body)
    old_cursor = WORK.request(token, product_id=product).json()["next_cursor"]
    for invalid in (forged, old_cursor, "x" + cursor[1:], "malformed"):
        response = request(token, product_id=product, cursor=invalid)
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": "Invalid translation cursor"}
    assert WORK.request(token, cursor=cursor).status_code == 422


def test_default_language_cap_and_explicit_missing_languages(factory):
    token = WORK.authority(factory)
    product, scope = SEARCH._seed_dataset(factory, name="Many locales")
    languages = [
        "en",
        "fr",
        "it",
        "de",
        "es",
        "pt",
        "nl",
        "sv",
        "da",
        "no",
        "fi",
        "pl",
        "cs",
        "sk",
        "ro",
        "hu",
        "bg",
        "hr",
        "sl",
        "el",
        "tr",
        "ja",
    ]
    for language in languages:
        SEARCH._add_group(
            factory,
            product_id=product,
            scope_id=scope,
            raw_key=f"key-{language}",
            language=language,
            values=({"display_text": language, "translated_text": language},),
        )
    response = request(token, product_id=product)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["visible_languages"]) == 20
    assert body["visible_languages"][0] == "en"
    assert body["default_selection_capped"]
    assert len(body["available_languages"]) == 22
    assert body["language_selection_limit"] == 20
    explicit = request(
        token, product_id=product, visible_languages=["ja", "kkj"], language="ja"
    ).json()
    assert explicit["visible_languages"] == ["ja", "kkj"]
    assert not explicit["default_selection_capped"]
    assert "kkj" not in slots(explicit)


def test_bounded_previews_literal_wildcards_and_exact_product_identity(factory):
    token = WORK.authority(factory)
    product, _, source = WORK.seed(factory, text_value="100%_literal", name="First")
    other, _, _ = WORK.seed(factory, text_value="100XXliteral", name="Other")
    assert len(request(token, q="greeting").json()["items"]) == 2
    response = request(token, q="%_")
    assert response.status_code == 200, response.text
    assert [item["product_id"] for item in response.json()["items"]] == [str(product)]
    with factory.begin() as session:
        base = session.get_one(TranslationValue, source)
        base.source_text = "S" * 4096
        base.display_text = base.source_text
        base.grapheme_count = 4096
        key = session.get_one(TranslationKey, base.translation_key_id)
        key.raw_key = "K" * 4096
    bounded = request(token, product_id=product).json()["items"][0]
    assert len(bounded["raw_key"]) == len(bounded["source_text"]) == 1024
    assert bounded["key_truncated"] and bounded["source_truncated"]
    assert slots({"items": [bounded]})["en"]["text_truncated"]
    assert len(slots({"items": [bounded]})["en"]["provenance"]["path"]) <= 1024
    assert request(token, product_id=other, q="S" * 100).json()["items"] == []


def test_partial_or_rejected_plural_cannot_conceal_empty_imported_member(factory):
    token = WORK.authority(factory)
    product, scope = SEARCH._seed_dataset(factory)
    group = SEARCH._add_group(
        factory,
        product_id=product,
        scope_id=scope,
        raw_key="plural",
        language="fr",
        values=(
            {"selector_kind": "android_quantity", "display_text": "", "translated_text": ""},
            {
                "selector_kind": "android_quantity",
                "display_text": "many",
                "translated_text": "many",
                "state": "approved",
            },
        ),
    )
    SEARCH._seed_pending_context(factory, group_id=group)
    with factory.begin() as session:
        for pending in session.scalars(select(TranslationProposalValue)):
            pending.proposed_text = "Completed"
    assert request(token, work_status="needs_translation").json()["items"] == []
    current = slots(request(token).json())["fr"]
    assert current["group_id"] == str(group)
    assert current["preview_kind"] == "aggregate" and current["value_count"] == 2
    assert current["states"] == ["approved", "draft"]
    with factory.begin() as session:
        session.scalar(select(TranslationProposal)).state = "rejected"
    assert request(token, work_status="needs_translation").json()["items"]
    with factory.begin() as session:
        session.scalar(select(TranslationProposal)).state = "draft"
        session.delete(session.scalar(select(TranslationProposalValue)))
    incomplete = slots(request(token).json())["fr"]
    assert incomplete["pending_change"]["reconciliation_required"]
    assert request(token, work_status="needs_translation").json()["items"]
    assert request(token, work_status="needs_review").json()["items"] == []


def test_retained_embedded_tombstone_and_split_source_only_update(factory):
    token = WORK.authority(factory)
    product, target, source = WORK.seed(factory, format="qt_ts", embedded=True, base=False)
    with factory.begin() as session:
        value = session.get_one(TranslationValue, target)
        value.is_deleted = True
        value.deleted_at = datetime.now(UTC)
        value.source_text = "Retained embedded source"
        WORK.revision(session, value, source=value.source_text, number=2)
    assert request(token, product_id=product).json()["items"] == []
    for mode in ("deleted", "all"):
        response = request(token, product_id=product, deleted=mode, q="Retained embedded")
        assert response.status_code == 200, response.text
        assert response.json()["items"][0]["source_text"] == "Retained embedded source"
        assert slots(response.json())["en"]["kind"] == "source_context"
        assert slots(response.json())["en"]["is_deleted"] is True
        assert slots(response.json())["en"]["matches_filters"] is True
        assert slots(response.json())["en"]["group_id"] is None
        assert slots(response.json())["en"]["editable"] is False
        assert slots(response.json())["fr"]["read_only_reason"] == "deleted"
        explicit = request(
            token, product_id=product, deleted=mode, visible_languages=["en", "fr", "it"]
        )
        assert explicit.status_code == 200, explicit.text
        assert "it" not in slots(explicit.json())
        assert (
            request(token, product_id=product, deleted=mode, work_status="source_changed").json()[
                "items"
            ]
            == []
        )
    split, _, source = WORK.seed(factory, name="Split")
    with factory.begin() as session:
        value = session.get_one(TranslationValue, source)
        value.source_text = "Base changed independently"
        WORK.revision(session, value, source=value.source_text, number=2)
    changed = request(token, product_id=split, work_status="source_changed").json()
    assert slots(changed)["fr"]["source_changed"]
    assert slots(changed)["fr"]["matches_filters"]
    assert not slots(changed)["en"]["matches_filters"]


def test_query_count_and_snapshot_remain_constant_during_concurrent_source_change(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory)
    engine = factory.kw["bind"]
    statements = []
    changed = False

    def observe(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if statement.lstrip().startswith("WITH current AS"):
            statements.append(statement)
        if "AS authority" in statement and not changed:
            changed = True
            with factory.begin() as writer:
                source = writer.get_one(TranslationValue, ids[0, "en"])
                source.source_text = "Changed during the read"
                source.display_text = source.source_text
                WORK.revision(writer, source, source=source.source_text, number=1)

    event.listen(engine, "after_cursor_execute", observe)
    try:
        response = request(token, product_id=product)
    finally:
        event.remove(engine, "after_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert len(statements) == 2
    assert slots(response.json())["en"]["effective_text"] == "en 0"
    cursor = response.json()["next_cursor"]
    assert request(token, product_id=product, cursor=cursor).status_code == 422
    assert (
        slots(request(token, product_id=product).json())["en"]["effective_text"]
        == "Changed during the read"
    )


def test_matching_key_beyond_first_page_cannot_borrow_foreign_or_deleted_metadata(factory):
    token = WORK.authority(factory)
    product, scope, _ = seed_keys(factory)
    before = request(token, product_id=product).json()
    foreign, foreign_scope = SEARCH._seed_dataset(factory, name="Foreign")
    deleted, deleted_scope = SEARCH._seed_dataset(factory, name="Deleted")
    for other, other_scope in ((foreign, foreign_scope), (deleted, deleted_scope)):
        SEARCH._add_group(
            factory,
            product_id=other,
            scope_id=other_scope,
            raw_key="key-060",
            language="de",
            values=({"display_text": "Foreign-only text", "translated_text": "Foreign-only text"},),
        )
    with factory.begin() as session:
        removed = session.get_one(Product, deleted)
        actor_id = session.scalar(select(User.id))
        removed.is_active = False
        removed.deleted_at = datetime.now(UTC)
        removed.deleted_by = actor_id
    selected = request(
        token,
        product_id=product,
        q="it 60",
        language="it",
        state="draft",
        violation="no_max",
        visible_languages=["en", "fr", "it", "de"],
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    assert [item["raw_key"] for item in body["items"]] == ["key-060"]
    assert body["items"][0]["scope_id"] == str(scope)
    assert slots(body)["it"]["matches_filters"]
    assert "de" not in slots(body)
    assert [option["code"] for option in body["available_languages"]] == ["en", "fr", "it"]
    continuation = request(token, product_id=product, cursor=before["next_cursor"])
    assert continuation.status_code == 200, continuation.text
    assert len(continuation.json()["items"]) == 11
    assert request(token, product_id=product, q="Foreign-only text").json()["items"] == []
    global_result = request(token, q="Foreign-only text").json()
    assert [item["product_id"] for item in global_result["items"]] == [str(foreign)]


def test_effective_length_follows_pending_text_and_current_limit(factory):
    token = WORK.authority(factory)
    product, group, _ = WORK.seed(factory, target_revision=False)
    SEARCH._seed_pending_context(factory, group_id=group)
    with factory.begin() as session:
        member = session.get_one(TranslationValue, group)
        member.effective_max_chars = 4
        member.effective_constraint_source = "language_override"
        member.is_over_limit = False
        pending = session.scalar(select(TranslationProposalValue))
        pending.proposed_text = "Ready"
        pending.grapheme_count = 5

    def french():
        response = request(token, product_id=product, visible_languages=["fr"])
        assert response.status_code == 200, response.text
        return slots(response.json())["fr"]

    assert french()["effective_text"] == "Ready"
    assert french()["over_limit_count"] == 0
    assert french()["effective_over_limit_count"] == 1
    with factory.begin() as session:
        session.get_one(TranslationValue, group).effective_max_chars = 5
    assert french()["effective_over_limit_count"] == 0
    with factory.begin() as session:
        session.get_one(TranslationValue, group).effective_max_chars = 4
        session.scalar(select(TranslationProposal)).state = "rejected"
    assert french()["effective_text"] == ""
    assert french()["effective_over_limit_count"] == 0
    with factory.begin() as session:
        session.scalar(select(TranslationProposal)).state = "draft"
        session.scalar(select(TranslationProposalValue)).basis_revision_number += 1
    assert french()["pending_change"]["reconciliation_required"]
    assert french()["effective_over_limit_count"] == 0


def test_deleted_language_rows_disappear_but_other_languages_remain(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory, count=1)
    with factory.begin() as session:
        value = session.get_one(TranslationValue, ids[0, "fr"])
        value.is_deleted = True
        value.deleted_at = datetime.now(UTC)
    response = request(token, product_id=product, visible_languages=["en", "fr", "it", "de"])
    assert response.status_code == 200, response.text
    assert list(slots(response.json())) == ["en", "it"]
    assert request(token, product_id=product, language="fr").json()["items"] == []
    assert slots(request(token, product_id=product, deleted="all").json())["fr"]["is_deleted"]


def test_retired_member_does_not_disable_live_member_or_enter_saved_proposal(factory):
    token = WORK.authority(factory)
    product, scope = SEARCH._seed_dataset(factory)
    group = SEARCH._add_group(
        factory,
        product_id=product,
        scope_id=scope,
        raw_key="retired-form",
        language="fr",
        values=(
            {"source_text": "Source", "translated_text": "Old", "display_text": "Old"},
            {"source_text": "Source", "translated_text": "Current", "display_text": "Current"},
        ),
    )
    with factory.begin() as session:
        members = list(session.scalars(select(TranslationValue).order_by(TranslationValue.id)))
        # Retire the stable group anchor, so its identity must remain usable.
        members[0].is_deleted = True
        members[0].deleted_at = datetime.now(UTC)
        for member in members:
            WORK.revision(session, member, source=member.source_text, number=1)
        live_id = members[1].id
    result = request(token, product_id=product).json()
    current = slots(result)["fr"]
    assert current["group_id"] == str(group)
    assert current["value_count"] == 1
    assert current["editable"] and current["read_only_reason"] is None
    detail = WORK.request(token, f"/{group}").json()
    assert [value["id"] for value in detail["values"]] == [str(live_id)]
    member = detail["values"][0]
    payload = {
        "expected_version": 0,
        "values": [
            {
                "translation_value_id": member["id"],
                "selector_version": member["selector_version"],
                "selector_digest": member["selector_digest"],
                "basis_revision_number": member["history"][0]["revision_number"],
                "basis_digest": member["history"][0]["revision_digest"],
                "proposed_text": "Updated",
            }
        ],
    }
    saved = asyncio.run(
        SUPPORT.SUPPORT._request(
            "PUT",
            f"/api/v1/translations/{group}/proposal",
            token=token,
            json=payload,
        )
    )
    assert saved.status_code == 200, saved.text
    assert slots(request(token, product_id=product).json())["fr"]["effective_text"] == "Updated"
    reloaded = WORK.request(token, f"/{group}").json()
    assert not reloaded["pending_change"]["reconciliation_required"]
    with factory() as session:
        assert session.get_one(TranslationValue, group).is_deleted


def test_needs_translation_includes_absent_locales_and_empty_imported_values(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory, count=3)
    with factory.begin() as session:
        session.execute(
            delete(TranslationValue).where(
                TranslationValue.id.in_(
                    [
                        ids[0, "fr"],
                        ids[1, "it"],
                    ]
                )
            )
        )
        empty = session.get_one(TranslationValue, ids[2, "fr"])
        empty.translated_text = empty.display_text = ""
    filters = dict(product_id=product, work_status="needs_translation")
    response = request(token, **filters)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["raw_key"] for item in body["items"]] == ["key-000", "key-001", "key-002"]
    french = slots(body)["fr"]
    assert french["kind"] == "absent" and french["matches_filters"]
    assert french["group_id"] is None and not french["editable"]
    assert french["read_only_reason"] == "absent"
    assert not slots(body)["en"]["matches_filters"]
    assert not slots(body)["it"]["matches_filters"]
    assert slots(body, 1)["it"]["matches_filters"]
    assert slots(body, 2)["fr"]["kind"] == "imported"
    assert slots(body, 2)["fr"]["matches_filters"]
    assert [
        item["raw_key"] for item in request(token, **filters, language="fr").json()["items"]
    ] == ["key-000", "key-002"]
    assert [
        item["raw_key"]
        for item in request(token, **filters, visible_languages=["it"]).json()["items"]
    ] == ["key-001"]
    assert request(token, **filters, language="en").json()["items"] == []
    assert request(token, **filters, visible_languages=["es"]).json()["items"] == []
    assert request(token, **filters, language="fr", visible_languages=["en"]).json()["items"]
    for condition in ({"state": "draft"}, {"violation": "no_max"}):
        assert [
            item["raw_key"] for item in request(token, **filters, **condition).json()["items"]
        ] == ["key-002"]
    for query in ("key-000", "en 0"):
        found = request(token, **filters, q=query).json()
        assert [item["raw_key"] for item in found["items"]] == ["key-000"]
        assert slots(found)["fr"]["matches_filters"]
    assert request(token, **filters, q="it 1").json()["items"] == []
    assert request(token, **filters, deleted="deleted").json()["items"] == []
    assert len(request(token, **filters, deleted="all").json()["items"]) == 3


def test_absent_translation_queue_does_not_reintroduce_tombstones_or_foreign_locales(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory, count=2)
    other, other_scope = SEARCH._seed_dataset(factory, name="Other locales")
    SEARCH._add_group(
        factory,
        product_id=other,
        scope_id=other_scope,
        raw_key="other",
        language="de",
        values=({"display_text": "German", "translated_text": "German"},),
    )
    with factory.begin() as session:
        deleted = session.get_one(TranslationValue, ids[0, "fr"])
        deleted.is_deleted = True
        deleted.deleted_at = datetime.now(UTC)
        key = session.get_one(TranslationKey, deleted.translation_key_id)
        key.is_deleted = True
        key.deleted_at = datetime.now(UTC)
        removed = session.get_one(TranslationValue, ids[1, "fr"])
        removed.is_deleted = True
        removed.deleted_at = datetime.now(UTC)
    for mode in ("active", "all", "deleted"):
        assert (
            request(
                token, product_id=product, work_status="needs_translation", deleted=mode
            ).json()["items"]
            == []
        )
    assert (
        request(token, work_status="needs_translation", visible_languages=["de"]).json()["items"]
        == []
    )


def test_absent_translation_queue_paginates_unique_keys_and_keeps_authority(factory):
    token = WORK.authority(factory)
    product, _, ids = seed_keys(factory, count=62)
    with factory.begin() as session:
        session.execute(
            delete(TranslationValue).where(
                TranslationValue.id.in_(
                    [
                        value
                        for (index, language), value in ids.items()
                        if language == "fr" and index < 61
                    ]
                )
            )
        )
    filters = dict(
        product_id=product, work_status="needs_translation", visible_languages=["en", "fr", "it"]
    )
    first_response = request(token, **filters)
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()
    assert len(first["items"]) == 50 and first["next_cursor"]
    second = request(token, **filters, cursor=first["next_cursor"]).json()
    assert len(second["items"]) == 11 and second["next_cursor"] is None
    items = first["items"] + second["items"]
    assert len({item["translation_key_id"] for item in items}) == 61
    assert [item["raw_key"] for item in items] == [f"key-{index:03d}" for index in range(61)]
    assert all(
        next(slot for slot in item["slots"] if slot["language"] == "fr")["matches_filters"]
        for item in items
    )
    assert request(token, **filters, cursor=first["next_cursor"], language="it").status_code == 422
    with factory.begin() as session:
        session.get_one(Product, product).is_active = False
    assert request(token, **filters).json()["items"] == []
