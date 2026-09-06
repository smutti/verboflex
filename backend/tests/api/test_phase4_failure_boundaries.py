"""Real HTTP regressions for translation request and failure boundaries."""

import asyncio

from sqlalchemy.orm import Session, sessionmaker

from tests.api.test_translations import (
    TRANSLATIONS_PATH,
    _configure_dependencies,
    _create_authority,
    _request,
    _seed_visible_group,
    clean_translation_api_database,
    translation_api_session_factory,
)
from verboflex.main import app

# Reuse the isolated PostgreSQL fixture without collecting its source module's tests.
__all__ = ["clean_translation_api_database", "translation_api_session_factory"]


def test_explicit_http_page_size_preserves_fixed_contract(
    translation_api_session_factory: sessionmaker[Session],
) -> None:
    product_id, group_id = _seed_visible_group(translation_api_session_factory)
    token = _create_authority(translation_api_session_factory, role_names=("viewer",))
    _configure_dependencies(translation_api_session_factory)
    params = {"product_id": str(product_id), "language": "it", "page_size": "50"}

    response = asyncio.run(_request(TRANSLATIONS_PATH, token=token, params=params))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(group_id)]
    assert response.json()["next_cursor"] is None
    for invalid in ("49", "51", "050", "+50", "50.0", "5e1", " 50", "50 ", "", "true"):
        rejected = asyncio.run(
            _request(TRANSLATIONS_PATH, token=token, params={**params, "page_size": invalid})
        )
        assert rejected.status_code == 422, invalid
        assert rejected.json()["detail"][0]["loc"] == ["query", "page_size"]

    parameters = app.openapi()["paths"][TRANSLATIONS_PATH]["get"]["parameters"]
    page_size = next(item["schema"] for item in parameters if item["name"] == "page_size")
    assert page_size["type"] == "integer"
    assert page_size["const"] == 50
    assert page_size["default"] == 50
