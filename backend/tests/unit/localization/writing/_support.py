from __future__ import annotations

import hashlib
import importlib
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import SourceFileAuthority, SourceFileSnapshot, WriteEdit


def snapshot(content: bytes, **changes: Any) -> SourceFileSnapshot:
    parser_input = replace(
        CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path="app/src/main/res/values/strings.xml",
            content=content,
            layout_identity="app/src/main/res",
            layout_version=1,
            base_language="en",
        ),
        **changes,
    )
    return SourceFileSnapshot(
        SourceFileAuthority(
            import_execution_id=uuid4(),
            source_reference_position=0,
            repository_id=uuid4(),
            repository_side=parser_input.repository_side,
            configured_branch="master",
            commit_hash="a" * 40,
            path=parser_input.path,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        parser_input,
        (),
    )


def edit(source: SourceFileSnapshot, key: str, text: str, **selector_fields: object) -> WriteEdit:
    parsed = parse_canonical_snapshot(source.parser_input)
    assert not parsed.issues, parsed.issues
    values = [
        v
        for v in parsed.values
        if v.logical_key == key
        and all(dict(v.selector.fields).get(k) == item for k, item in selector_fields.items())
    ]
    assert len(values) == 1, [(v.logical_key, v.selector) for v in values]
    value = values[0]
    return WriteEdit(key, value.language, value.selector, value.locator, value.display_text, text)


def render(source: SourceFileSnapshot, *edits: WriteEdit) -> Any:
    try:
        registry = importlib.import_module("verboflex.localization.writing.registry")
    except ModuleNotFoundError:
        pytest.fail("Format-aware write-back with complete preservation proof is not implemented")
    return registry.render_file(source, tuple(edits))
