"""Executable contract for the browser-facing FastAPI surface."""

from __future__ import annotations

import json
import runpy
import subprocess
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from verboflex.main import app
from verboflex.scripts import export_openapi

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CHECKED_IN_SCHEMA = REPOSITORY_ROOT / "frontend" / "openapi.json"
FRONTEND_SOURCE = REPOSITORY_ROOT / "frontend" / "src"
GENERATED_CLIENT = FRONTEND_SOURCE / "api" / "client"

EXPECTED_OPERATIONS = {
    ("/api/v1/auth/change-password", "post"): (
        "change_password",
        {"204", "400", "401", "422", "429", "503"},
        True,
    ),
    ("/api/v1/auth/logout", "post"): (
        "logout",
        {"204", "403", "422", "429"},
        False,
    ),
    ("/api/v1/auth/refresh", "post"): (
        "refresh_access_token",
        {"200", "401", "403", "422", "429", "503"},
        False,
    ),
    ("/api/v1/auth/token", "post"): (
        "issue_token",
        {"200", "401", "422", "429", "503"},
        False,
    ),
    ("/api/v1/health", "get"): ("read_health", {"200", "429"}, False),
    ("/api/v1/system/status", "get"): (
        "read_system_status",
        {"200", "401", "403", "429"},
        True,
    ),
    ("/api/v1/users/me", "get"): (
        "read_current_user",
        {"200", "401", "403", "429"},
        True,
    ),
}


def _operation_entries(schema: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (path, method): operation
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"delete", "get", "patch", "post", "put"}
    }


def _response_schema(operation: dict[str, Any], status_code: str) -> str | None:
    schema = (
        operation["responses"][status_code]
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    reference = schema.get("$ref")
    return reference if isinstance(reference, str) else None


def test_openapi_surface_is_exact_and_security_is_not_accidental() -> None:
    """Freeze every approved method, operation id, response, and bearer boundary."""
    schema = app.openapi()
    operations = _operation_entries(schema)

    assert set(operations) == set(EXPECTED_OPERATIONS)
    for key, (operation_id, response_codes, requires_bearer) in EXPECTED_OPERATIONS.items():
        operation = operations[key]
        assert operation["operationId"] == operation_id
        assert set(operation["responses"]) == response_codes
        assert operation.get("security") == (
            [{"OAuth2PasswordBearer": []}] if requires_bearer else None
        )

    error_response_codes = {
        ("/api/v1/auth/change-password", "post"): {"400", "401", "422", "429", "503"},
        ("/api/v1/auth/logout", "post"): {"403", "429"},
        ("/api/v1/auth/refresh", "post"): {"401", "403", "429", "503"},
        ("/api/v1/auth/token", "post"): {"401", "429", "503"},
        ("/api/v1/health", "get"): {"429"},
        ("/api/v1/system/status", "get"): {"401", "403", "429"},
        ("/api/v1/users/me", "get"): {"401", "403", "429"},
    }
    for key, status_codes in error_response_codes.items():
        for status_code in status_codes:
            assert _response_schema(operations[key], status_code) == (
                "#/components/schemas/ErrorResponse"
            )

    assert schema["components"]["securitySchemes"] == {
        "OAuth2PasswordBearer": {
            "flows": {
                "password": {
                    "scopes": {},
                    "tokenUrl": "/api/v1/auth/token",
                }
            },
            "type": "oauth2",
        }
    }


def test_export_is_canonical_and_matches_the_checked_in_schema() -> None:
    """Two exports are byte-identical and equal the tracked frontend input."""
    command = ["uv", "run", "python", "-m", "verboflex.scripts.export_openapi"]
    first = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT / "backend",
        check=True,
        capture_output=True,
    ).stdout
    second = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT / "backend",
        check=True,
        capture_output=True,
    ).stdout

    assert first == second
    assert first == CHECKED_IN_SCHEMA.read_bytes()
    assert (
        first
        == (
            json.dumps(
                json.loads(first),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
    )


def test_export_entrypoint_is_exercised_in_process() -> None:
    """Keep both import and executable entrypoint paths inside coverage accounting."""
    direct_output = StringIO()
    with redirect_stdout(direct_output):
        export_openapi.main()

    entrypoint_output = StringIO()
    with redirect_stdout(entrypoint_output):
        runpy.run_path(
            str(REPOSITORY_ROOT / "backend/src/verboflex/scripts/export_openapi.py"),
            run_name="__main__",
        )

    assert entrypoint_output.getvalue() == direct_output.getvalue()
    assert json.loads(entrypoint_output.getvalue()) == app.openapi()


def test_authentication_credential_fields_have_explicit_maximum_lengths() -> None:
    """Publish the exact input bounds enforced before identity or Argon2 work."""
    schemas = app.openapi()["components"]["schemas"]
    login_fields = schemas["Body_issue_token"]["properties"]
    change_fields = schemas["ChangePasswordRequest"]["properties"]

    assert login_fields["username"]["maxLength"] == 320
    assert login_fields["password"]["maxLength"] == 128
    assert change_fields["current_password"]["maxLength"] == 128
    assert change_fields["new_password"]["maxLength"] == 128


def _handwritten_api_type_declarations(source: str) -> set[str]:
    generated_names = {
        "AccessTokenResponse",
        "ChangePasswordRequest",
        "CurrentUserResponse",
        "ErrorResponse",
        "RoleName",
        "SystemStatusResponse",
    }
    return {
        name
        for name in generated_names
        if f"interface {name}" in source or f"type {name} =" in source
    }


def test_generated_client_configuration_is_central_and_contract_types_are_not_duplicated() -> None:
    """Use one credentialed runtime config and reject handwritten wire-type copies."""
    config = (FRONTEND_SOURCE / "api" / "config.ts").read_text()
    generated_entrypoint = (GENERATED_CLIENT / "client.gen.ts").read_text()
    handwritten_source = "\n".join(
        path.read_text()
        for path in sorted(FRONTEND_SOURCE.rglob("*.ts*"))
        if GENERATED_CLIENT not in path.parents
    )

    assert 'credentials: "include"' in config
    assert 'configuredBaseUrl || "/"' in config
    assert "import { createClientConfig } from '../config.ts';" in generated_entrypoint
    assert _handwritten_api_type_declarations(handwritten_source) == set()


def test_duplicate_type_guard_rejects_a_known_bad_declaration() -> None:
    """Prove the narrow handwritten-contract checker reaches its failure seam."""
    known_bad = "export interface AccessTokenResponse { access_token: string }"

    assert _handwritten_api_type_declarations(known_bad) == {"AccessTokenResponse"}
