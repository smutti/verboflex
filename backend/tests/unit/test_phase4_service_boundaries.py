"""Fail-closed service inputs and malformed stored projections remain bounded."""

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from verboflex.services import translation_constraints as constraints
from verboflex.services import translation_imports as imports
from verboflex.services import translation_search as search


@pytest.mark.parametrize(
    "values",
    [
        {"language": ""},
        {"language": "x" * 65},
        {"state": "done"},
        {"violation": "bad"},
        {"deleted": "gone"},
        {"page_size": 49},
    ],
)
def test_direct_search_callers_cannot_bypass_public_filter_bounds(values):
    with pytest.raises(search.TranslationSearchInputError):
        search.TranslationSearchFilters(**values)


def signed_cursor(payload):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    return encode(body) + "." + encode(hmac.digest(b"secret", body, "sha256"))


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "version",
        "filters",
        "last-type",
        "last-count",
        "rank",
        "noncanonical",
        "empty",
        "oversized",
    ],
)
def test_signed_cursor_still_requires_exact_closed_authority(change):
    filters = search.TranslationSearchFilters()
    payload = {
        "filters": hashlib.sha256(
            json.dumps(
                search._canonical_filter(filters), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        "last": [0, "en", str(uuid4())],
        "scope": "scope",
        "v": 2,
    }
    assert (
        search._decode_cursor(
            signed_cursor(payload), scope_digest="scope", filters=filters, cursor_secret="secret"
        ).rank
        == 0
    )
    if change == "extra":
        payload["extra"] = "ignored?"
    elif change == "version":
        payload["v"] = 1
    elif change == "filters":
        payload["filters"] = {}
    elif change == "last-type":
        payload["last"] = "position"
    elif change == "last-count":
        payload["last"] = []
    elif change == "rank":
        payload["last"][0] = 4
    cursor = signed_cursor(payload)
    if change == "noncanonical":
        cursor = cursor.replace(".", "=.")
    elif change == "empty":
        cursor = ""
    elif change == "oversized":
        cursor = "x" * 2049
    with pytest.raises(search.InvalidTranslationCursor, match="invalid translation cursor"):
        search._decode_cursor(cursor, scope_digest="scope", filters=filters, cursor_secret="secret")


def test_cursor_emission_and_unsigned_search_are_bounded():
    filters = search.TranslationSearchFilters(query="ﬃ" * 256)
    position = search._CursorPosition(0, "en", uuid4())
    cursor = search._encode_cursor(
        scope_digest="scope",
        filters=filters,
        position=position,
        cursor_secret="secret",
    )
    assert len(cursor) <= search.MAX_CURSOR_CHARS
    assert (
        search._decode_cursor(cursor, scope_digest="scope", filters=filters, cursor_secret="secret")
        == position
    )
    session = Mock()
    with pytest.raises(search.TranslationSearchInputError, match="signing secret"):
        search.search_translations(
            session,
            principal_id=uuid4(),
            filters=search.TranslationSearchFilters(),
            cursor=None,
            cursor_secret="",
        )
    session.execute.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "kind": "scalar", "fields": {}},
        {"version": 1, "kind": "json_path", "fields": {}},
        {"version": 1, "kind": "scalar", "fields": []},
        {"version": 1, "kind": "scalar", "fields": {str(i): i for i in range(129)}},
        {},
    ],
)
def test_malformed_legacy_selector_metadata_is_absent_not_fabricated(payload):
    assert search._selector_fields(json.dumps(payload).encode(), "scalar") is None
    assert search._provenance({"repository_id": None}) is None


def test_oversized_database_projections_are_rejected_before_rendering():
    session = Mock()
    session.execute.return_value.mappings.return_value.all.return_value = [{}] * 10001
    with pytest.raises(search.TranslationSearchInputError, match="group exceeds"):
        search.get_translation_group(session, group_id=uuid4())
    session.execute.return_value.mappings.return_value.all.return_value = [
        {"option_kind": 1, "language": str(i)} for i in range(501)
    ]
    with pytest.raises(search.TranslationSearchInputError, match="options exceed"):
        search.get_translation_options(session)


@pytest.mark.parametrize(
    "group,language", [("not-uuid", "en"), (uuid4(), ""), (uuid4(), "invalid language")]
)
def test_constraint_owner_inputs_fail_before_database_access(group, language):
    session = Mock()
    with pytest.raises(constraints.ConstraintInputInvalid):
        constraints._lock_mutation_group(session, translation_group_id=group, language=language)
    session.get.assert_not_called()


def test_constraint_actor_and_missing_scope_are_not_assumed():
    session = Mock()
    with pytest.raises(constraints.ConstraintInputInvalid, match="actor_id"):
        constraints.put_translation_constraint(
            session,
            translation_group_id=uuid4(),
            language="en",
            max_chars=5,
            expected_version=0,
            actor_id="admin",
        )
    session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(constraints.ConstraintAuthorityUnavailable, match="scope"):
        constraints._lock_scope_authority(session, scope_id=uuid4(), base_language=None)


@pytest.mark.parametrize("key", [None, SimpleNamespace(scope_id=uuid4())])
def test_future_edit_recomputation_requires_the_values_exact_scope(key):
    session = Mock()
    session.get.return_value = key
    with pytest.raises(constraints.ConstraintAuthorityUnavailable):
        constraints.recompute_after_translation_edit(
            session, value=SimpleNamespace(translation_key_id=uuid4(), scope_id=uuid4())
        )
    session.flush.assert_not_called()


@pytest.mark.parametrize("digest", [None, "a" * 63, "A" * 64, "g" * 64])
def test_staged_manifest_rejects_invalid_digest_before_database_reads(digest):
    session = Mock()
    with pytest.raises(imports.TranslationImportRejected, match="manifest digest"):
        imports.require_complete_staged_manifest(
            session, identity=SimpleNamespace(), manifest_digest=digest
        )
    session.scalars.assert_not_called()


@pytest.mark.parametrize(
    "references",
    [
        [],
        (
            SimpleNamespace(
                position=0,
                repository_side="direct",
                repository_id=uuid4(),
                source_branch="main",
                commit_hash="a" * 40,
                sha256="b" * 64,
                size_bytes=1,
                path="../escape",
            ),
        ),
    ],
)
def test_staged_references_cannot_escape_the_execution_scope(references):
    with pytest.raises(imports.TranslationImportRejected, match="source references"):
        imports._validate_references(
            identity=SimpleNamespace(repository_sides=()), references=references
        )


def test_qt_deletion_flag_ignores_malformed_metadata():
    value = SimpleNamespace(structure=[{"kind": "qt_ts:translation", "fields": "deleted"}])
    assert imports._staged_value_is_deleted(value) is False


def test_existing_staging_is_not_silently_overwritten():
    session = Mock()
    session.scalar.return_value = uuid4()
    with pytest.raises(imports.TranslationImportRejected, match="already exists"):
        imports._reject_existing_staging(session, execution_id=uuid4())
    session.add.assert_not_called()


def test_invalid_parse_results_and_correlation_are_rejected_before_transaction():
    from verboflex.localization.importing.core import CanonicalParseResult

    factory = Mock()
    with pytest.raises(imports.TranslationImportRejected, match="parser result"):
        imports.stage_translation_parse(
            factory, identity=SimpleNamespace(), references=(), result=object()
        )
    with pytest.raises(imports.TranslationImportRejected, match="correlation"):
        imports.stage_translation_parse(
            factory,
            identity=SimpleNamespace(),
            references=(),
            result=CanonicalParseResult(),
            correlation_references={"untrusted": "x" * 257},
        )
    factory.begin.assert_not_called()


def test_reconciliation_cannot_assume_base_language_or_scope():
    session = Mock()
    identity = SimpleNamespace(mapping_id=uuid4(), product_id=uuid4())
    session.get.return_value = None
    with pytest.raises(imports.TranslationImportRejected, match="base language"):
        imports.reconcile_canonical_translations(
            session, identity=identity, scope=SimpleNamespace(), manifest_digest="a" * 64
        )
    session.get.return_value = SimpleNamespace(base_language="en", identity_key="mapping")
    with pytest.raises(imports.TranslationImportRejected, match="scope authority"):
        imports.reconcile_canonical_translations(
            session,
            identity=identity,
            scope=SimpleNamespace(product_id=uuid4()),
            manifest_digest="a" * 64,
        )
    session.flush.assert_not_called()


def test_tombstone_requires_matching_repository_provenance():
    with pytest.raises(imports.TranslationImportRejected, match="tombstone provenance"):
        imports._tombstone_reference({}, value=SimpleNamespace(locator=None))


def test_staged_manifest_requires_complete_execution_owned_rows():
    session = Mock()
    session.scalars.side_effect = [(), (), ()]
    with pytest.raises(imports.TranslationImportRejected, match="incomplete"):
        imports.require_complete_staged_manifest(
            session, identity=SimpleNamespace(execution_id=uuid4()), manifest_digest="a" * 64
        )
    session.flush.assert_not_called()


def test_activation_rejects_the_wrong_execution_before_any_pointer_write():
    session = Mock()
    with pytest.raises(imports.TranslationImportRejected, match="activation authority"):
        imports.activate_translation_dataset(
            session,
            identity=SimpleNamespace(import_id=uuid4()),
            scope=SimpleNamespace(),
            job=SimpleNamespace(id=uuid4()),
            execution=SimpleNamespace(),
            manifest_digest="a" * 64,
        )
    session.flush.assert_not_called()
