"""Worker parser inputs come only from one current, complete preview authority."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.localization.preview.core import build_layout_candidate
from verboflex.localization.preview.moko_xml import detect_moko_layouts
from verboflex.models.product import ProductRevision
from verboflex.services import import_jobs
from verboflex.services.repository_discovery import RepositorySourceFile


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


@pytest.mark.parametrize("base_language", ["en-US", "it-IT", "fr-FR"])
@pytest.mark.parametrize("separate", [False, True])
def test_every_confirmed_layout_is_imported_regardless_of_base_language(
    monkeypatch, base_language, separate
):
    session, identity, mapping, _, preview, _ = authority(monkeypatch, separate=separate)
    role = "translations" if separate else "direct"
    candidates = []
    contents = {}
    # A separate candidate per locale, as produced by existing Qt repositories.
    for index, language in enumerate(("en-US", "it-IT", "fr-FR")):
        root = f"src/resources/bundle{index}/translations"
        path = f"{root}/maxi_{language.split('-')[0]}.ts"
        candidate = build_layout_candidate(
            format="qt_ts",
            repository_side=role,
            layout_identity=f"qt-ts:{root}/maxi_{{locale}}.ts",
            files=(path,),
            values={language: {"hello": f"Hello {language}"}},
        )
        candidates.append(candidate)
        contents[(role, path)] = (
            f'<TS version="2.1" language="{language}" sourcelanguage="en">'
            '<context><name>Main</name><message id="hello"><source>Hello</source>'
            f"<translation>Hello {language}</translation></message></context></TS>"
        ).encode()
        if language == base_language:
            mapping.selected_layout_candidate_id = candidate.id
    if separate:
        path = "src/resources/keys/maxi_en.ts"
        candidates.append(
            build_layout_candidate(
                format="qt_ts",
                repository_side="keys",
                layout_identity="qt-ts:src/resources/keys/maxi_{locale}.ts",
                files=(path,),
                values={"en-US": {"hello": "Hello"}},
            )
        )
        contents[("keys", path)] = (
            b'<TS version="2.1" language="en_US"><context><name>Main</name>'
            b'<message id="hello"><source>Hello</source><translation>Hello</translation>'
            b"</message></context></TS>"
        )
    mapping.base_language = base_language
    preview.result["layout_candidates"] = [item.to_mapping() for item in candidates]

    inputs = import_jobs._confirmed_parser_inputs(
        session, identity=identity, source_contents=contents
    )
    assert {(item.repository_side, item.path) for item in inputs} == set(contents)
    parsed = parse_canonical_mapping(inputs)
    assert not parsed.issues, parsed.issues
    assert {
        value.language for value in parsed.values if value.locator.repository_side != "keys"
    } == {"en-US", "it-IT", "fr-FR"}


@pytest.mark.parametrize("defect", ["missing-layout-file", "overlapping-layout"])
def test_all_layout_authority_never_silently_imports_only_a_subset(monkeypatch, defect):
    session, identity, _, _, preview, contents = authority(monkeypatch)
    extra = build_layout_candidate(
        format="json",
        repository_side="direct",
        layout_identity=(
            "json:flat-per-locale:{locale}.json"
            if defect == "overlapping-layout"
            else "json:locale-rooted:other.json"
        ),
        files=("locales.json" if defect == "overlapping-layout" else "other.json",),
        values={"fr": {"hello": "Bonjour"}},
    )
    preview.result["layout_candidates"].append(extra.to_mapping())
    assert (
        import_jobs._confirmed_parser_inputs(session, identity=identity, source_contents=contents)
        == ()
    )


def test_confirmed_formats_keep_all_languages_in_one_complete_import(monkeypatch):
    session, identity, _, _, preview, contents = authority(monkeypatch)
    path = "res/values-fr/strings.xml"
    extra = build_layout_candidate(
        format="android_xml",
        repository_side="direct",
        layout_identity="res",
        files=(path,),
        values={"fr": {"android_label": "Bonjour"}},
    )
    preview.result["layout_candidates"].append(extra.to_mapping())
    contents[("direct", path)] = (
        b'<resources><string name="android_label">Bonjour</string></resources>'
    )
    parsed = parse_canonical_mapping(
        import_jobs._confirmed_parser_inputs(session, identity=identity, source_contents=contents)
    )
    assert not parsed.issues, parsed.issues
    assert {value.language for value in parsed.values} == {"en", "it", "fr"}
    assert {value.locator.format for value in parsed.values} == {"json", "android_xml"}


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
            "android_xml",
            "shared/moko-resources",
            "shared/moko-resources/base/strings.xml",
            (
                "shared/moko-resources/base/strings.xml",
                "shared/moko-resources/fr/strings.xml",
            ),
            "other/moko-resources/fr/strings.xml",
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
        (
            "xliff",
            "xliff:translations/{locale}/messages.xliff",
            "translations/en/messages.xliff",
            ("translations/en/messages.xliff", "translations/fr/messages.xliff"),
            "other/fr/messages.xliff",
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


@pytest.mark.parametrize("base_language", ["fr", "en"])
def test_moko_preview_builds_complete_canonical_worker_inputs(monkeypatch, base_language):
    session, identity, mapping, _, preview, _ = authority(monkeypatch)
    paths = ("shared/moko-resources/base/strings.xml", "shared/moko-resources/fr/strings.xml")
    content = b'<resources><string name="hello">Hello</string></resources>'
    detected = detect_moko_layouts(
        tuple(RepositorySourceFile(path=path, content=content) for path in paths),
        repository_side="direct",
    )
    assert len(detected.candidates) == 1
    candidate = detected.candidates[0]
    mapping.base_language = base_language
    mapping.selected_layout_candidate_id = candidate.id
    preview.result["layout_candidates"] = [candidate.to_mapping()]
    inputs = import_jobs._confirmed_parser_inputs(
        session,
        identity=identity,
        source_contents={("direct", path): content for path in paths},
    )
    assert {item.path for item in inputs} == set(paths)
    assert all(item.layout_identity == "shared/moko-resources" for item in inputs)
    assert all(item.base_language == base_language for item in inputs)


@pytest.mark.parametrize(
    "invalid_peer", ["zz_invalid/strings.xml", "fr/extra.xml", "fr/nested/strings.xml"]
)
def test_moko_current_invalid_peer_reaches_canonical_validation(monkeypatch, invalid_peer):
    session, identity, mapping, _, preview, _ = authority(monkeypatch)
    root = "shared/moko-resources"
    old_path = f"{root}/base/strings.xml"
    candidate = build_layout_candidate(
        format="android_xml",
        repository_side="direct",
        layout_identity=root,
        files=(old_path,),
        values={"en": {"hello": "Hello"}},
    )
    mapping.selected_layout_candidate_id = candidate.id
    preview.result["layout_candidates"] = [candidate.to_mapping()]
    content = b'<resources><string name="hello">Hello</string></resources>'
    invalid_path = f"{root}/{invalid_peer}"
    contents = {
        ("direct", old_path): content,
        ("direct", invalid_path): content,
        ("direct", "shared/moko-resources-extra/fr/strings.xml"): content,
        ("direct", "other/moko-resources/fr/strings.xml"): content,
    }
    inputs = import_jobs._confirmed_parser_inputs(
        session, identity=identity, source_contents=contents
    )
    assert {item.path for item in inputs} == {old_path, invalid_path}
    parsed = parse_canonical_mapping(inputs)
    assert not parsed.values
    assert any(issue.path == invalid_path for issue in parsed.issues)


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
