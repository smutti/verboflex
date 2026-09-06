"""C1: independent file, mapping-value and encoded-output budgets."""

from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping


def mapping_inputs(count: int) -> tuple[CanonicalParserInput, ...]:
    return tuple(
        CanonicalParserInput(
            format="android_xml",
            repository_side="direct",
            path=f"app/res/values/part{offset}.xml",
            content=(
                "<resources>"
                + "".join(
                    f'<string name="key{i}">Value {i}</string>'
                    for i in range(offset, min(offset + 5000, count))
                )
                + "</resources>"
            ).encode(),
            layout_identity="app/res",
            layout_version=1,
            base_language="en",
        )
        for offset in range(0, count, 5000)
    )


def test_mapping_capacity_accepts_fifty_thousand_without_expanding_file_limit() -> None:
    result = parse_canonical_mapping(mapping_inputs(50_000))
    assert result.issues == ()
    assert len(result.values) == 50_000
    assert {value.logical_key for value in result.values} == {f"key{i}" for i in range(50_000)}
    assert (
        next(value for value in result.values if value.logical_key == "key49999").display_text
        == "Value 49999"
    )


def test_mapping_capacity_rejects_one_over_atomically() -> None:
    result = parse_canonical_mapping(mapping_inputs(50_001))
    assert result.values == ()
    assert [issue.code for issue in result.issues] == ["unsupported_structure"]


def test_mapping_result_trust_boundary_keeps_per_file_and_encoded_limits(monkeypatch):
    from dataclasses import replace

    from verboflex.localization.importing import core

    result = parse_canonical_mapping(mapping_inputs(5001))
    forged = core.CanonicalParseResult(
        values=tuple(
            sorted(
                (
                    replace(value, locator=replace(value.locator, path="app/res/values/one.xml"))
                    for value in result.values
                ),
                key=core.canonical_value_order,
            )
        )
    )
    assert not core.canonical_result_is_valid(forged, mapping=True)
    monkeypatch.setattr(core, "MAX_CANONICAL_MAPPING_OUTPUT_BYTES", 1)
    assert not core.canonical_result_is_valid(result, mapping=True)


def test_manifest_encoding_never_materializes_the_complete_value_graph(monkeypatch) -> None:
    import hashlib
    import json
    from uuid import uuid4

    from verboflex.services.import_jobs import ImportExecutionIdentity
    from verboflex.services.translation_imports import _manifest_digest

    identity = ImportExecutionIdentity(
        import_id=uuid4(),
        execution_id=uuid4(),
        sequence=1,
        product_id=uuid4(),
        revision_id=uuid4(),
        mapping_id=uuid4(),
        connection_generation=3,
        repository_sides=(),
    )
    repository_id = uuid4()
    values = [
        {
            "repository_id": repository_id,
            "selector_bytes": b"{}",
            "display_text": "日本語",
            "position": i,
        }
        for i in range(501)
    ]
    expected = {
        "authority": {
            key: str(getattr(identity, key))
            for key in ("execution_id", "import_id", "mapping_id", "product_id", "revision_id")
        },
        "issues": [],
        "references": [],
        "values": [
            {**value, "repository_id": str(repository_id), "selector_bytes": "{}"}
            for value in values
        ],
        "version": 1,
    }
    expected["authority"].update(sequence=1, connection_generation=3)
    original = json.dumps
    digest = hashlib.sha256(
        original(expected, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()

    def bounded_dump(value, **kwargs):
        assert not isinstance(value, dict) or "values" not in value, "full graph encoded at once"
        return original(value, **kwargs)

    monkeypatch.setattr(json, "dumps", bounded_dump)
    assert (
        _manifest_digest(identity=identity, references=(), values=iter(values), issues=[]) == digest
    )
