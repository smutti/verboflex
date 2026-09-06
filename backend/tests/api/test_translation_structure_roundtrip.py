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
from tests.unit.localization.importing.test_structure_bounds import android_input, ios_input, qt_input
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.main import app
from verboflex.models.translation import TranslationValue
from verboflex.services.import_jobs import finish_import_execution

__all__ = ["activation_session_factory", "clean_activation_database"]


@pytest.mark.parametrize("format", ["android_xml", "qt_ts", "ios_strings"])
def test_large_valid_structure_survives_activation_and_authenticated_detail(
    activation_session_factory, format
):
    factory = activation_session_factory
    parser_input = {"android_xml": android_input, "qt_ts": qt_input, "ios_strings": ios_input}[format]()
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
