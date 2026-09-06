"""Worker parser inputs come only from one current, complete preview authority."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from verboflex.localization.preview.core import build_layout_candidate
from verboflex.models.product import ProductRevision
from verboflex.services import import_jobs


def authority(monkeypatch, *, separate=False):
    selected_side = "translations" if separate else "direct"
    candidate = build_layout_candidate(
        format="json",
        repository_side=selected_side,
        layout_identity="json:locale-rooted:locales.json",
        files=("locales.json",),
        values={"en": {"hello": "Hello"}, "it": {"hello": "Ciao"}},
    )
    keys = build_layout_candidate(
        format="json",
        repository_side="keys",
        layout_identity="json:locale-rooted:keys.json",
        files=("keys.json",),
        values={"en": {"hello": "Hello"}},
    )
    roles = ("keys", "translations") if separate else ("direct",)
    identity = SimpleNamespace(
        revision_id=uuid4(),
        mapping_id=uuid4(),
        repository_sides=tuple(SimpleNamespace(role=role) for role in roles),
    )
    mapping = SimpleNamespace(
        base_language="en",
        confirmed_preview_job_id=uuid4(),
        selected_layout_candidate_id=candidate.id,
        selected_layout_version=1,
        topology="separate" if separate else "direct",
    )
    revision = SimpleNamespace()
    preview = SimpleNamespace(
        result={
            "layout_candidates": [candidate.to_mapping()]
            + ([keys.to_mapping()] if separate else [])
        }
    )
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = mapping
    session.get.side_effect = lambda model, identifier: (
        revision if model is ProductRevision else preview
    )
    monkeypatch.setattr(import_jobs, "is_current_preview_confirmation", lambda *args: True)
    contents = {(selected_side, "locales.json"): b'{"en":{"hello":"Hello"},"it":{"hello":"Ciao"}}'}
    if separate:
        contents[("keys", "keys.json")] = b'{"en":{"hello":"Hello"}}'
    return session, identity, mapping, revision, preview, contents


@pytest.mark.parametrize("separate", [False, True])
def test_worker_builds_exact_direct_or_paired_inputs(monkeypatch, separate):
    session, identity, mapping, _, _, contents = authority(monkeypatch, separate=separate)
    result = import_jobs._confirmed_parser_inputs(
        session, identity=identity, source_contents=contents
    )
    assert len(result) == (2 if separate else 1)
    assert {(item.repository_side, item.path): item.content for item in result} == contents
    assert all(
        item.base_language == mapping.base_language
        and item.layout_version == 1
        and item.format == "json"
        for item in result
    )


@pytest.mark.parametrize("separate", [False, True])
@pytest.mark.parametrize(
    ("format", "layout", "old_path", "current_paths", "outside"),
    [
        (
            "android_xml",
            "app/res",
            "app/res/values/old.xml",
            ("app/res/values/moved.xml", "app/res/values-fr/new.xml"),
            "other/res/values/a.xml",
        ),
        (
            "json",
            "json:flat-per-locale:locales/{locale}.json",
            "locales/en.json",
            ("locales/en.json", "locales/fr.json"),
            "other/fr.json",
        ),
        (
            "qt_ts",
            "qt-ts:translations/app_{locale}.ts",
            "translations/app_en.ts",
            ("translations/app_en.ts", "translations/app_fr.ts"),
            "translations/other_fr.ts",
        ),
        (
            "ios_strings",
            "ios-strings:app/{locale}.lproj/Localizable.strings",
            "app/en.lproj/Localizable.strings",
            ("app/en.lproj/Localizable.strings", "app/fr.lproj/Localizable.strings"),
            "other/fr.lproj/Localizable.strings",
        ),
    ],
)
def test_current_snapshot_membership_uses_confirmed_layout_not_old_files(
    monkeypatch, separate, format, layout, old_path, current_paths, outside
):
    session, identity, mapping, _, preview, _ = authority(monkeypatch, separate=separate)
    side = "translations" if separate else "direct"
    selected = build_layout_candidate(
        format=format,
        repository_side=side,
        layout_identity=layout,
        files=(old_path,),
        values={"en": {"hello": "Hello"}},
    )
    candidates = [selected]
    if separate:
        candidates.append(
            build_layout_candidate(
                format=format,
                repository_side="keys",
                layout_identity=layout,
                files=(old_path,),
                values={"en": {"hello": "Hello"}},
            )
        )
    mapping.selected_layout_candidate_id = selected.id
    preview.result["layout_candidates"] = [candidate.to_mapping() for candidate in candidates]
    # Deliberately opaque: discovery must not rerun the narrower preview grammar.
    contents = {
        (role, path): b"canonical parser owns validation"
        for role in (("keys", side) if separate else (side,))
        for path in (*current_paths, outside)
    }
    result = import_jobs._confirmed_parser_inputs(
        session, identity=identity, source_contents=contents
    )
    assert {(item.repository_side, item.path) for item in result} == {
        (role, path) for role in (("keys", side) if separate else (side,)) for path in current_paths
    }
    assert all(item.layout_identity == layout and item.format == format for item in result)


@pytest.mark.parametrize(
    "defect",
    [
        "revision",
        "mapping",
        "base",
        "confirmation",
        "candidate",
        "version",
        "stale",
        "preview",
        "result",
        "shape",
        "malformed",
        "no-selected",
        "duplicate-selected",
        "side",
        "language",
        "missing-content",
        "missing-side",
    ],
)
def test_incomplete_or_stale_authority_never_yields_partial_parser_inputs(monkeypatch, defect):
    session, identity, mapping, revision, preview, contents = authority(monkeypatch)
    if defect == "revision":
        revision = None
    elif defect == "mapping":
        session.execute.return_value.scalar_one_or_none.return_value = None
    elif defect == "base":
        mapping.base_language = None
    elif defect == "confirmation":
        mapping.confirmed_preview_job_id = None
    elif defect == "candidate":
        mapping.selected_layout_candidate_id = None
    elif defect == "version":
        mapping.selected_layout_version = 2
    elif defect == "stale":
        monkeypatch.setattr(import_jobs, "is_current_preview_confirmation", lambda *args: False)
    elif defect == "preview":
        preview = None
    elif defect == "result":
        preview.result = None
    elif defect == "shape":
        preview.result = {"layout_candidates": {}}
    elif defect == "malformed":
        preview.result = {"layout_candidates": [{}]}
    elif defect == "no-selected":
        mapping.selected_layout_candidate_id = uuid4()
    elif defect == "duplicate-selected":
        preview.result["layout_candidates"] *= 2
    elif defect == "side":
        mapping.topology = "separate"
    elif defect == "language":
        mapping.base_language = "de"
    elif defect == "missing-content":
        contents.clear()
    elif defect == "missing-side":
        identity.repository_sides = (SimpleNamespace(role="keys"),)
    session.get.side_effect = lambda model, identifier: (
        revision if model is ProductRevision else preview
    )
    assert (
        import_jobs._confirmed_parser_inputs(session, identity=identity, source_contents=contents)
        == ()
    )


@pytest.mark.parametrize("defect", ["no-keys", "missing-keys-file", "duplicate-keys"])
def test_paired_inputs_require_one_complete_matching_keys_candidate(monkeypatch, defect):
    session, identity, _, _, preview, contents = authority(monkeypatch, separate=True)
    if defect == "no-keys":
        preview.result["layout_candidates"].pop()
    elif defect == "duplicate-keys":
        preview.result["layout_candidates"].append(preview.result["layout_candidates"][-1])
    else:
        contents.pop(("keys", "keys.json"))
    assert (
        import_jobs._confirmed_parser_inputs(session, identity=identity, source_contents=contents)
        == ()
    )


@pytest.mark.parametrize(
    "defect",
    ["unknown-code", "unknown-side", "path", "position", "line", "column", "foreign-side", "count"],
)
def test_persisted_parser_issues_remain_bounded_and_content_free(defect):
    issue = SimpleNamespace(
        issue_code="malformed_file",
        repository_side="direct",
        path="locales.json",
        position=0,
        line=1,
        column=1,
    )
    changes = {
        "unknown-code": ("issue_code", "secret:raw-source"),
        "unknown-side": ("repository_side", "foreign"),
        "path": ("path", "../escape"),
        "position": ("position", -1),
        "line": ("line", 0),
        "column": ("column", 0),
        "foreign-side": ("repository_side", "keys"),
    }
    if defect in changes:
        setattr(issue, *changes[defect])
    session = Mock()
    session.scalars.return_value = [issue] * (10001 if defect == "count" else 1)
    with pytest.raises(import_jobs.ImportConflict, match="persisted parser issues rejected"):
        import_jobs._parser_issue_projection(
            session,
            job=SimpleNamespace(id=uuid4(), state="import_failed"),
            current_execution=SimpleNamespace(id=uuid4(), state="failed"),
            expected_sides=(SimpleNamespace(role="direct"),),
        )


def test_active_dataset_cannot_claim_an_unfinished_execution():
    execution_id, job_id = uuid4(), uuid4()
    with pytest.raises(import_jobs.ImportConflict, match="persisted active dataset rejected"):
        import_jobs._dataset_status(
            scope=SimpleNamespace(active_execution_id=execution_id, active_import_job_id=job_id),
            job=SimpleNamespace(id=job_id, state="running"),
            current_execution=SimpleNamespace(id=execution_id, state="running"),
        )
