"""Immutable source and typed edit contracts for safe localization writes."""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import FrozenInstanceError, replace
from typing import Any
from uuid import uuid4

import pytest

from verboflex.localization.importing.core import (
    CanonicalLocator,
    CanonicalParserInput,
    CanonicalSelector,
)


def _core() -> Any:
    try:
        return importlib.import_module("verboflex.localization.writing.core")
    except ModuleNotFoundError:
        pytest.fail("Verified source snapshots and bounded write contracts are not implemented")


def _authority(content: bytes, **overrides: object) -> Any:
    fields = {
        "import_execution_id": uuid4(),
        "source_reference_position": 0,
        "repository_id": uuid4(),
        "repository_side": "direct",
        "configured_branch": "feature/localization",
        "commit_hash": "a" * 40,
        "path": "i18n/en.json",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    fields.update(overrides)
    return _core().SourceFileAuthority(**fields)


def _input(content: bytes) -> CanonicalParserInput:
    return CanonicalParserInput(
        format="json",
        repository_side="direct",
        path="i18n/en.json",
        content=content,
        layout_identity="json:flat-per-locale:i18n/{locale}.json",
        layout_version=1,
        base_language="en",
    )


def _edit(**overrides: object) -> Any:
    fields = {
        "logical_key": "hello",
        "language": "en",
        "selector": CanonicalSelector("json_path", (("parents", ()),)),
        "locator": CanonicalLocator(
            format="json",
            repository_side="direct",
            path="i18n/en.json",
            position=0,
            structural_address=("document", "hello", 0),
        ),
        "expected_text": "PRIVATE_OLD_TRANSLATION",
        "replacement_text": "PRIVATE_NEW_TRANSLATION",
    }
    fields.update(overrides)
    return _core().WriteEdit(**fields)


def test_verified_snapshot_is_immutable_and_keeps_exact_authority() -> None:
    core = _core()
    content = b'{"hello":"PRIVATE_OLD_TRANSLATION"}\r\n'
    authority = _authority(content)
    snapshot = core.SourceFileSnapshot(authority, _input(content), ())
    assert snapshot.parser_input.content is content
    assert snapshot.authority is authority
    with pytest.raises(FrozenInstanceError):
        snapshot.attributes = ("executable",)
    assert "PRIVATE_OLD_TRANSLATION" not in repr(snapshot)
    assert core.SourceFileSnapshot(authority, _input(content), None).attributes is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("import_execution_id", "not-a-uuid"),
        ("repository_id", None),
        ("source_reference_position", True),
        ("source_reference_position", -1),
        ("repository_side", "foreign"),
        ("configured_branch", ""),
        ("configured_branch", "branch\nsecret"),
        ("commit_hash", "short"),
        ("commit_hash", "g" * 40),
        ("path", "../outside"),
        ("path", "/absolute"),
        ("path", "i18n/../outside"),
        ("path", "i18n\\outside"),
        ("size_bytes", True),
        ("size_bytes", -1),
        ("sha256", "x" * 64),
    ],
)
def test_source_authority_rejects_invalid_coordinates(field: str, value: object) -> None:
    with pytest.raises(_core().WritebackRejected):
        _authority(b"{}", **{field: value})


@pytest.mark.parametrize(
    "change",
    [
        {"content": b'{"different":"bytes"}'},
        {"path": "i18n/it.json"},
        {"repository_side": "translations"},
    ],
)
def test_snapshot_rejects_foreign_or_changed_parser_input(change: dict[str, object]) -> None:
    core = _core()
    content = b'{"hello":"world"}'
    with pytest.raises(core.WritebackRejected) as error:
        core.SourceFileSnapshot(_authority(content), replace(_input(content), **change), ())
    assert error.value.reason in {
        core.WritebackReason.STALE_BASIS,
        core.WritebackReason.SOURCE_FILE_CHANGED,
    }


def test_snapshot_verifies_both_length_and_digest() -> None:
    core = _core()
    content = b"{}"
    for authority in (_authority(content, size_bytes=3), _authority(content, sha256="0" * 64)):
        with pytest.raises(core.WritebackRejected) as error:
            core.SourceFileSnapshot(authority, _input(content), ())
        assert error.value.reason == core.WritebackReason.SOURCE_FILE_CHANGED


def test_typed_edits_are_immutable_private_and_preserve_empty_text() -> None:
    edit = _edit()
    assert "PRIVATE_OLD_TRANSLATION" not in repr(edit)
    assert "PRIVATE_NEW_TRANSLATION" not in repr(edit)
    with pytest.raises(FrozenInstanceError):
        edit.replacement_text = "changed"
    assert _edit(replacement_text="").replacement_text == ""
    assert "PRIVATE_SOURCE_SENTENCE" not in repr(_edit(logical_key="PRIVATE_SOURCE_SENTENCE"))


@pytest.mark.parametrize(
    "fields",
    [
        {"logical_key": ""},
        {"language": "it_IT"},
        {"selector": {}},
        {"locator": {}},
        {"expected_text": None},
        {"replacement_text": 1},
        {"replacement_text": "\ud800"},
    ],
)
def test_invalid_edit_is_a_closed_failure(fields: dict[str, object]) -> None:
    with pytest.raises(_core().WritebackRejected):
        _edit(**fields)


def test_results_validate_every_retained_digest_and_hide_source_text() -> None:
    core = _core()
    original = b'{"hello":"PRIVATE_OLD_TRANSLATION"}'
    content = b'{"hello":"PRIVATE_NEW_TRANSLATION"}'
    fields = dict(
        authority=_authority(original),
        original_bytes=original,
        content=content,
        before_sha256=hashlib.sha256(original).hexdigest(),
        after_sha256=hashlib.sha256(content).hexdigest(),
        changed_edits=(_edit(),),
        attributes=(),
    )
    result = core.RenderedFile(**fields)
    assert result.content == content
    assert "PRIVATE_" not in repr(result)
    for name in ("before_sha256", "after_sha256"):
        with pytest.raises(core.WritebackRejected):
            core.RenderedFile(**(fields | {name: "0" * 64}))


def test_errors_expose_only_fixed_safe_messages() -> None:
    core = _core()
    for reason in core.WritebackReason:
        error = core.WritebackRejected(reason)
        assert error.reason is reason
        assert 0 < len(str(error)) < 256
    with pytest.raises((TypeError, ValueError)) as error:
        core.WritebackRejected("PRIVATE_PROVIDER_BODY")
    assert "PRIVATE_PROVIDER_BODY" not in str(error.value)
