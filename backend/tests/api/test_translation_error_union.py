"""The generated 422 contract includes validation and domain errors already sent on wire."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from verboflex.api.v1.routes import translation_constraints as constraints
from verboflex.api.v1.routes import translations
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.core.config import get_settings
from verboflex.db.session import get_db_session
from verboflex.schemas.users import RoleName


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["get", "put", "delete"])
@pytest.mark.parametrize("failure", ["validation", "domain"])
async def test_translation_422_schema_covers_actual_http_response(monkeypatch, method, failure):
    app = FastAPI()
    app.include_router(translations.router, prefix="/api/v1")
    app.include_router(constraints.router, prefix="/api/v1")
    principal = Principal(uuid4(), "admin@example.test", "Admin", (RoleName.ADMIN,), False)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_db_session] = lambda: Mock()
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        jwt_secret_key=SecretStr("disposable-test-signing-key")
    )
    monkeypatch.setattr(constraints, "get_translation_group", Mock())
    domain = (
        Mock(side_effect=translations.InvalidTranslationCursor("private diagnostic"))
        if method == "get"
        else Mock(side_effect=constraints.ConstraintInputInvalid("private diagnostic"))
    )
    if method == "get":
        monkeypatch.setattr(translations, "search_translations", domain)
        path = schema_path = "/api/v1/translations"
        kwargs = {"params": {"page_size": "49"} if failure == "validation" else {"cursor": "bad"}}
        error_model = "TranslationErrorResponse"
        expected_message = "Invalid translation cursor"
    else:
        monkeypatch.setattr(constraints, f"{method}_translation_constraint_service", domain)
        path = f"/api/v1/translations/{uuid4()}/constraints/it"
        schema_path = "/api/v1/translations/{translation_group_id}/constraints/{language}"
        body = {"expected_version": "invalid" if failure == "validation" else 0}
        if method == "put":
            body["max_chars"] = 7
        kwargs = {"json": body}
        error_model = "TranslationConstraintErrorResponse"
        expected_message = "Invalid translation constraint input"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, path, **kwargs)
    assert response.status_code == 422
    if failure == "validation":
        assert isinstance(response.json()["detail"], list)
        assert response.json()["detail"][0]["loc"] == (
            ["query", "page_size"] if method == "get" else ["body", "expected_version"]
        )
        domain.assert_not_called()
    else:
        assert response.json() == {"detail": expected_message}
        domain.assert_called_once()
        assert "private diagnostic" not in response.text
    schema = app.openapi()
    documented = schema["paths"][schema_path][method]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]
    assert documented == {
        "anyOf": [
            {"$ref": f"#/components/schemas/{error_model}"},
            {"$ref": "#/components/schemas/HTTPValidationError"},
        ]
    }
    assert (
        schema["components"]["schemas"]["HTTPValidationError"]["properties"]["detail"]["type"]
        == "array"
    )
    assert schema["components"]["schemas"][error_model]["properties"]["detail"]["type"] == "string"
