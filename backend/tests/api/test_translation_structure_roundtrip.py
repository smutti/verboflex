"""Parser-approved structure survives activation and authenticated detail intact."""

import asyncio

import pytest
from sqlalchemy import select

from tests.api.test_translations import _configure_dependencies, _create_authority, _request
from tests.integration.test_translation_import_activation import (
    _seed_running_direct_import,
    _stage_direct_manifest,
    activation_session_factory,
    clean_activation_database,
)
from tests.unit.localization.importing.test_structure_bounds import (
    android_input,
    ios_input,
    qt_input,
)
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.main import app
from verboflex.models.translation import TranslationValue
from verboflex.services.import_jobs import finish_import_execution

__all__ = ["activation_session_factory", "clean_activation_database"]


def test_xliff_pipeline_contract_is_closed_end_to_end() -> None:
    from verboflex.models.translation import _FORMAT_CHECK
    from verboflex.schemas.previews import AdminPreviewLayoutCandidateResponse
    from verboflex.schemas.translations import TranslationProvenanceResponse
    from verboflex.services.repository_discovery import _CANDIDATE_SUFFIXES

    assert _CANDIDATE_SUFFIXES[-2:] == (".xlf", ".xliff")
    assert "'xliff'" in _FORMAT_CHECK
    preview_format = AdminPreviewLayoutCandidateResponse.model_json_schema()["properties"]["format"]
    provenance_format = TranslationProvenanceResponse.model_json_schema()["properties"]["format"]
    assert "xliff" in preview_format["enum"]
    assert "xliff" in provenance_format["enum"]


def test_xliff_structure_survives_activation_and_authenticated_detail(
    activation_session_factory,
) -> None:
    parser_input = CanonicalParserInput(
        format="xliff",
        repository_side="direct",
        path="translations/app_it.xliff",
        content=(
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.1" '
            b'srcLang="en" trgLang="it"><file id="app"><unit id="welcome" '
            b'name="home.welcome"><segment id="main"><source>Hello</source>'
            b"<target>Ciao</target></segment></unit></file></xliff>"
        ),
        layout_identity="xliff:translations/app_{locale}.xliff",
        layout_version=1,
        base_language="en",
    )
    parsed = parse_canonical_mapping((parser_input,))
    assert parsed.issues == ()
    expected_structure = [node.to_mapping() for node in parsed.values[0].structure]
    identity, repository_id = _seed_running_direct_import(activation_session_factory)
    manifest, references = _stage_direct_manifest(
        activation_session_factory,
        identity=identity,
        repository_id=repository_id,
        result=parsed,
    )
    assert finish_import_execution(
        activation_session_factory,
        identity=identity,
        references=references,
        canonical_manifest_digest=manifest.digest,
    )
    with activation_session_factory() as session:
        value = session.scalars(select(TranslationValue)).one()
        group_id = value.id
        assert value.structure == expected_structure
        assert value.locator is not None and value.locator.format == "xliff"
    token = _create_authority(activation_session_factory, role_names=("viewer",))
    _configure_dependencies(activation_session_factory)
    try:
        response = asyncio.run(_request(f"/api/v1/translations/{group_id}", token=token))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    projected = response.json()["values"][0]
    assert projected["structure"] == expected_structure
    assert projected["provenance"]["format"] == "xliff"


@pytest.mark.parametrize("format", ["android_xml", "qt_ts", "ios_strings"])
def test_large_valid_structure_survives_activation_and_authenticated_detail(
    activation_session_factory, format
):
    factory = activation_session_factory
    parser_input = {"android_xml": android_input, "qt_ts": qt_input, "ios_strings": ios_input}[
        format
    ]()
    parsed = parse_canonical_mapping((parser_input,))
    assert parsed.issues == ()
    expected_structure = [node.to_mapping() for node in parsed.values[0].structure]
    assert len(expected_structure) > 128
    identity, repository_id = _seed_running_direct_import(factory)
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository_id, result=parsed
    )
    assert finish_import_execution(
        factory, identity=identity, references=references, canonical_manifest_digest=manifest.digest
    )
    with factory() as session:
        value = session.scalars(select(TranslationValue)).one()
        group_id = value.id
        assert value.structure == expected_structure
    token = _create_authority(factory, role_names=("viewer",))
    _configure_dependencies(factory)
    try:
        response = asyncio.run(_request(f"/api/v1/translations/{group_id}", token=token))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["values"][0]["structure"] == expected_structure
    assert response.json()["values"][0]["display_text"] == parsed.values[0].display_text
