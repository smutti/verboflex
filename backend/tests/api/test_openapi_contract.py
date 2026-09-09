"""Executable contract for the browser-facing FastAPI surface."""

from __future__ import annotations

import json
import re
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
PREVIEW_CONFIRMATION_PATH = "/api/v1/admin/preview-jobs/{job_id}/confirmation"

IMPORT_OPERATIONS = {
    ("/api/v1/admin/products/{product_id}/imports/{import_id}/duplicates", "get"): (
        "get_admin_import_duplicates",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
    ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get"): (
        "list_admin_published_mapping_imports",
        {"200", "401", "403", "404", "422"},
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
        "post",
    ): (
        "start_admin_published_mapping_import",
        {"202", "401", "403", "404", "409", "422", "503"},
    ),
    ("/api/v1/admin/products/{product_id}/imports/{import_id}", "get"): (
        "get_admin_import",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
        "/imports/{import_id}/rewrite-comparison",
        "get",
    ): (
        "get_admin_import_rewrite_comparison",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
        "/imports/{import_id}/rewrite-confirmation",
        "post",
    ): (
        "confirm_admin_import_rewrite_baseline",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
}

TRANSLATION_OPERATIONS = {
    ("/api/v1/translations/options", "get"): (
        "listTranslationOptions",
        {"200", "401", "403", "422", "503"},
    ),
    ("/api/v1/translations", "get"): (
        "searchTranslations",
        {"200", "401", "403", "422", "503"},
    ),
    ("/api/v1/translations/{translation_group_id}", "get"): (
        "getTranslationGroup",
        {"200", "401", "403", "404", "422", "503"},
    ),
    ("/api/v1/translations/{translation_group_id}/constraints/{language}", "put"): (
        "putTranslationConstraint",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
    ("/api/v1/translations/{translation_group_id}/constraints/{language}", "delete"): (
        "deleteTranslationConstraint",
        {"200", "401", "403", "404", "409", "422", "503"},
    ),
}

EXPECTED_OPERATIONS = {
    ("/api/v1/admin/products/{product_id}/imports/{import_id}/duplicates", "get"): (
        "get_admin_import_duplicates",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/preview-jobs/{job_id}/duplicates", "get"): (
        "get_admin_preview_duplicates",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/bitbucket", "get"): (
        "get_admin_bitbucket_status",
        {"200", "401", "403", "503"},
        True,
    ),
    ("/api/v1/admin/bitbucket/connect", "post"): (
        "connect_admin_bitbucket_oauth",
        {"200", "401", "403", "503"},
        True,
    ),
    ("/api/v1/admin/bitbucket/reconnect", "post"): (
        "reconnect_admin_bitbucket_oauth",
        {"200", "401", "403", "503"},
        True,
    ),
    ("/api/v1/admin/bitbucket/revoke", "post"): (
        "revoke_admin_bitbucket_connection_locally",
        {"200", "401", "403", "503"},
        True,
    ),
    ("/api/v1/admin/repositories", "get"): (
        "list_admin_repositories",
        {"200", "401", "403", "422"},
        True,
    ),
    ("/api/v1/admin/repositories", "post"): (
        "create_admin_repository",
        {"201", "401", "403", "409", "422"},
        True,
    ),
    ("/api/v1/admin/repositories/{repository_id}/branch", "get"): (
        "get_admin_repository_branch",
        {"200", "401", "403", "404", "409", "422", "503", "504"},
        True,
    ),
    ("/api/v1/admin/repositories/{repository_id}/branches", "get"): (
        "list_admin_repository_branches",
        {"200", "401", "403", "404", "409", "422", "503", "504"},
        True,
    ),
    ("/api/v1/admin/repositories/{repository_id}/sources", "get"): (
        "discover_admin_repository_sources",
        {"200", "401", "403", "404", "409", "422", "503", "504"},
        True,
    ),
    ("/api/v1/admin/repositories/{repository_id}", "get"): (
        "get_admin_repository",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    ("/api/v1/admin/products", "get"): (
        "list_admin_products",
        {"200", "401", "403", "422"},
        True,
    ),
    ("/api/v1/admin/products", "post"): (
        "create_admin_product",
        {"201", "401", "403", "409", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/candidate/mappings", "get"): (
        "list_admin_candidate_mappings",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/candidate/mappings", "post"): (
        "create_admin_candidate_mapping",
        {"201", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings",
        "get",
    ): (
        "list_admin_revision_mappings",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}",
        "patch",
    ): (
        "update_admin_candidate_mapping",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get"): (
        "list_admin_published_mapping_imports",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
        "post",
    ): (
        "start_admin_published_mapping_import",
        {"202", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/imports/{import_id}", "get"): (
        "get_admin_import",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
        "/imports/{import_id}/rewrite-comparison",
        "get",
    ): (
        "get_admin_import_rewrite_comparison",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
        "/imports/{import_id}/rewrite-confirmation",
        "post",
    ): (
        "confirm_admin_import_rewrite_baseline",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
        "post",
    ): (
        "create_admin_preview_job",
        {"202", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs/latest",
        "get",
    ): (
        "get_admin_latest_candidate_preview_job",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/preview-jobs/{job_id}", "get"): (
        "get_admin_preview_job",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/preview-jobs/{job_id}/confirmation", "post"): (
        "confirm_admin_preview_job",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/active-revision-revalidation-jobs/{job_id}", "get"): (
        "get_admin_active_revision_revalidation_job",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/active-revision-revalidation-jobs/{job_id}/confirmation",
        "post",
    ): (
        "confirm_admin_active_revision_revalidation",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}", "get"): (
        "get_admin_product",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}", "delete"): (
        "delete_admin_product",
        {"204", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}", "patch"): (
        "update_admin_product_candidate",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/deactivate", "post"): (
        "deactivate_admin_product",
        {"200", "401", "403", "404", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/publish", "post"): (
        "publish_admin_product_candidate",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/products/{product_id}/reactivate", "post"): (
        "reactivate_admin_product",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility",
        "get",
    ): (
        "get_admin_product_reactivation_eligibility",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
        "/mappings/{mapping_id}/revalidation-preview-jobs",
        "post",
    ): (
        "create_admin_active_revision_revalidation_job",
        {"202", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
        "/mappings/{mapping_id}/revalidation-preview-jobs/latest",
        "get",
    ): (
        "get_admin_latest_active_revision_revalidation_job",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/admin/users", "get"): (
        "list_admin_users",
        {"200", "401", "403", "422"},
        True,
    ),
    ("/api/v1/admin/users", "post"): (
        "create_admin_user",
        {"201", "401", "403", "409", "422"},
        True,
    ),
    ("/api/v1/admin/users/{user_id}", "patch"): (
        "update_admin_user",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/users/{user_id}/deactivate", "post"): (
        "deactivate_admin_user",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/users/{user_id}/reactivate", "post"): (
        "reactivate_admin_user",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
    ("/api/v1/admin/users/{user_id}/reset-password", "post"): (
        "reset_admin_user_password",
        {"200", "401", "403", "404", "409", "422"},
        True,
    ),
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
    ("/api/v1/translations/options", "get"): (
        "listTranslationOptions",
        {"200", "401", "403", "422", "503"},
        True,
    ),
    ("/api/v1/translations", "get"): (
        "searchTranslations",
        {"200", "401", "403", "422", "503"},
        True,
    ),
    ("/api/v1/translations/{translation_group_id}", "get"): (
        "getTranslationGroup",
        {"200", "401", "403", "404", "422", "503"},
        True,
    ),
    ("/api/v1/translations/{translation_group_id}/constraints/{language}", "put"): (
        "putTranslationConstraint",
        {"200", "401", "403", "404", "409", "422", "503"},
        True,
    ),
    ("/api/v1/translations/{translation_group_id}/constraints/{language}", "delete"): (
        "deleteTranslationConstraint",
        {"200", "401", "403", "404", "409", "422", "503"},
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


def _parameters_by_name(operation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {parameter["name"]: parameter for parameter in operation["parameters"]}


def _schema_references(value: Any) -> set[str]:
    if isinstance(value, dict):
        references = {
            reference.rsplit("/", maxsplit=1)[-1]
            for key, reference in value.items()
            if key == "$ref" and isinstance(reference, str)
        }
        return references.union(*(_schema_references(nested) for nested in value.values()))
    if isinstance(value, list):
        return set().union(*(_schema_references(nested) for nested in value))
    return set()


def _schema_property_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        properties = value.get("properties")
        names = set(properties) if isinstance(properties, dict) else set()
        return names.union(*(_schema_property_names(nested) for nested in value.values()))
    if isinstance(value, list):
        return set().union(*(_schema_property_names(nested) for nested in value))
    return set()


def _schema_variant(schema: dict[str, Any], *, type_name: str) -> dict[str, Any]:
    """Return one named nullable-schema variant without depending on its order."""
    return next(item for item in schema["anyOf"] if item.get("type") == type_name)


def _assert_admin_preview_base_language_contract(schema: dict[str, Any]) -> None:
    """Freeze the generated browser boundary for exact base-language confirmation."""
    schemas = schema["components"]["schemas"]
    operation = schema["paths"][PREVIEW_CONFIRMATION_PATH]["post"]
    request = schemas["AdminPreviewConfirmationRequest"]
    response = schemas["AdminPreviewConfirmationResponse"]

    assert operation["operationId"] == "confirm_admin_preview_job"
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert operation["requestBody"] == {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/AdminPreviewConfirmationRequest"}
            }
        },
    }
    assert _response_schema(operation, "200") == (
        "#/components/schemas/AdminPreviewConfirmationResponse"
    )
    assert _response_schema(operation, "409") == "#/components/schemas/ErrorResponse"

    assert request["additionalProperties"] is False
    assert set(request["properties"]) == {
        "preview_digest",
        "layout_candidate_id",
        "layout_candidate_version",
        "base_language",
    }
    assert set(request["required"]) == set(request["properties"])
    assert request["properties"]["base_language"]["anyOf"] == [
        {"type": "string", "maxLength": 64, "minLength": 1},
        {"type": "null"},
    ]

    assert response["additionalProperties"] is False
    assert set(response["required"]) == set(response["properties"])
    assert response["properties"]["base_language"] == {
        "type": "string",
        "maxLength": 64,
        "minLength": 1,
        "title": "Base Language",
    }

    public_preview_contract = {
        "paths": {path: value for path, value in schema["paths"].items() if "preview-jobs" in path},
        "schemas": {
            name: value for name, value in schemas.items() if name.startswith("AdminPreview")
        },
    }
    assert _schema_property_names(public_preview_contract).isdisjoint(
        {
            "access_token",
            "client_secret",
            "credentials",
            "provider_body",
            "provider_diagnostics",
            "raw_body",
            "refresh_token",
            "source_bytes",
            "source_file_content",
        }
    )


def test_admin_preview_base_language_openapi_is_exact_bounded_and_authorized() -> None:
    """Expose one closed generated contract without moving authority into the browser."""
    _assert_admin_preview_base_language_contract(app.openapi())


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
        ("/api/v1/admin/bitbucket", "get"): {"401", "403"},
        ("/api/v1/admin/bitbucket/connect", "post"): {"401", "403"},
        ("/api/v1/admin/bitbucket/reconnect", "post"): {"401", "403"},
        ("/api/v1/admin/bitbucket/revoke", "post"): {"401", "403"},
        ("/api/v1/admin/repositories", "get"): {"401", "403", "422"},
        ("/api/v1/admin/repositories", "post"): {"401", "403", "409", "422"},
        ("/api/v1/admin/repositories/{repository_id}", "get"): {
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/v1/admin/products", "get"): {"401", "403", "422"},
        ("/api/v1/admin/products", "post"): {"401", "403", "422"},
        ("/api/v1/admin/products/{product_id}/candidate/mappings", "get"): {
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/v1/admin/products/{product_id}/candidate/mappings", "post"): {
            "401",
            "403",
            "404",
            "422",
            "503",
        },
        (
            "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}",
            "patch",
        ): {"401", "403", "404", "422", "503"},
        (
            "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
            "post",
        ): {"401", "403", "404", "409", "422", "503"},
        ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get"): {
            "401",
            "403",
        },
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            "post",
        ): {"401", "403"},
        ("/api/v1/admin/products/{product_id}/imports/{import_id}", "get"): {
            "401",
            "403",
        },
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-comparison",
            "get",
        ): {"401", "403"},
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-confirmation",
            "post",
        ): {"401", "403"},
        ("/api/v1/admin/preview-jobs/{job_id}", "get"): {
            "401",
            "403",
            "404",
            "409",
            "422",
            "503",
        },
        ("/api/v1/admin/active-revision-revalidation-jobs/{job_id}", "get"): {
            "401",
            "403",
            "404",
            "409",
            "422",
            "503",
        },
        (
            "/api/v1/admin/active-revision-revalidation-jobs/{job_id}/confirmation",
            "post",
        ): {"401", "403", "404", "409", "422", "503"},
        (
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility",
            "get",
        ): {"401", "403", "404", "409", "422", "503"},
        (
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
            "/mappings/{mapping_id}/revalidation-preview-jobs",
            "post",
        ): {"401", "403", "404", "409", "422", "503"},
        ("/api/v1/admin/products/{product_id}", "get"): {"401", "403", "404", "422"},
        ("/api/v1/admin/products/{product_id}", "delete"): {
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/v1/admin/products/{product_id}", "patch"): {
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/v1/admin/users", "get"): {"401", "403", "422"},
        ("/api/v1/admin/users", "post"): {"401", "403", "409", "422"},
        ("/api/v1/admin/users/{user_id}", "patch"): {
            "401",
            "403",
            "404",
            "409",
            "422",
        },
        ("/api/v1/admin/users/{user_id}/deactivate", "post"): {
            "401",
            "403",
            "404",
            "409",
            "422",
        },
        ("/api/v1/admin/users/{user_id}/reactivate", "post"): {
            "401",
            "403",
            "404",
            "409",
            "422",
        },
        ("/api/v1/admin/users/{user_id}/reset-password", "post"): {
            "401",
            "403",
            "404",
            "409",
            "422",
        },
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

    import_error_response_codes = {
        ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get"): {
            "404",
            "422",
        },
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            "post",
        ): {"404", "409", "503"},
        ("/api/v1/admin/products/{product_id}/imports/{import_id}", "get"): {
            "404",
            "409",
            "503",
        },
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-comparison",
            "get",
        ): {"404", "409", "503"},
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-confirmation",
            "post",
        ): {"404", "409", "503"},
    }
    for key, status_codes in import_error_response_codes.items():
        for status_code in status_codes:
            assert _response_schema(operations[key], status_code) == (
                "#/components/schemas/AdminImportOperationErrorResponse"
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

    assert _response_schema(operations[("/api/v1/admin/products", "post")], "409") == (
        "#/components/schemas/AdminProductConflictResponse"
    )
    assert (
        _response_schema(operations[("/api/v1/admin/products/{product_id}", "patch")], "409")
        == "#/components/schemas/AdminProductConflictResponse"
    )
    assert (
        _response_schema(operations[("/api/v1/admin/products/{product_id}", "delete")], "409")
        == "#/components/schemas/AdminProductDeletionConflictResponse"
    )
    mapping_collection = "/api/v1/admin/products/{product_id}/candidate/mappings"
    mapping_detail = mapping_collection + "/{mapping_id}"
    assert _response_schema(operations[(mapping_collection, "post")], "409") == (
        "#/components/schemas/AdminMappingConflictResponse"
    )
    assert _response_schema(operations[(mapping_detail, "patch")], "409") == (
        "#/components/schemas/AdminMappingConflictResponse"
    )


def test_import_public_contract_is_closed_and_provider_source_history_free() -> None:
    schema = app.openapi()
    operations = _operation_entries(schema)
    paths = {
        ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get"),
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            "post",
        ),
        ("/api/v1/admin/products/{product_id}/imports/{import_id}", "get"),
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-comparison",
            "get",
        ),
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-confirmation",
            "post",
        ),
    }
    roots = set().union(*(_schema_references(operations[path]) for path in paths))
    components = schema["components"]["schemas"]
    pending = list(roots)
    import_schema_names: set[str] = set()
    while pending:
        name = pending.pop()
        if name in import_schema_names or name not in components:
            continue
        import_schema_names.add(name)
        pending.extend(_schema_references(components[name]) - import_schema_names)

    import_schemas = {
        name: components[name]
        for name in import_schema_names
        if name.startswith("AdminImport")
        or name.startswith("AdminPublishedMappingImport")
        or name in {"ImportDatasetStatus", "ImportParserIssue"}
    }
    assert set(import_schemas) == {
        "AdminImportBaselineResponse",
        "AdminImportOperationErrorResponse",
        "ImportDatasetStatus",
        "ImportParserIssue",
        "AdminImportRepositorySideResponse",
        "AdminImportRewriteComparisonResponse",
        "AdminImportRewriteConfirmationRequest",
        "AdminImportRewriteDeltaResponse",
        "AdminImportRewriteSideResponse",
        "AdminImportSourceReferenceResponse",
        "AdminPublishedMappingImportListResponse",
        "AdminPublishedMappingImportResponse",
    }
    forbidden = {
        "access_token",
        "attempt",
        "attempt_history",
        "attempts",
        "authorization",
        "ciphertext",
        "client_secret",
        "credential",
        "credentials",
        "execution_history",
        "provider_body",
        "provider_response",
        "provider_url",
        "raw_authority",
        "raw_source",
        "refresh_token",
        "source_bytes",
        "stack",
        "stack_trace",
        "task_id",
        "url",
    }
    assert forbidden.isdisjoint(_schema_property_names(import_schemas))
    assert "workspace" in _schema_property_names(components["AdminRepositoryResponse"])


def test_import_operation_surface_is_exact_unique_and_bearer_protected() -> None:
    """Freeze the five browser operations before generated code consumes them."""
    schema = app.openapi()
    operations = _operation_entries(schema)
    import_operations = {
        key: operation
        for key, operation in operations.items()
        if "/imports" in key[0] or key[0].endswith("/mapping-imports")
    }

    assert set(import_operations) == set(IMPORT_OPERATIONS)
    operation_ids: list[str] = []
    for key, (operation_id, response_codes) in IMPORT_OPERATIONS.items():
        operation = import_operations[key]
        operation_ids.append(operation["operationId"])
        assert operation["operationId"] == operation_id
        assert set(operation["responses"]) == response_codes
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]

    assert len(operation_ids) == 6  # C4 adds the read-only duplicate report.
    assert len(set(operation_ids)) == 6

    list_operation = import_operations[
        ("/api/v1/admin/products/{product_id}/published/mapping-imports", "get")
    ]
    list_parameters = _parameters_by_name(list_operation)
    assert set(list_parameters) == {"product_id", "limit", "status", "cursor"}
    assert list_parameters["product_id"]["in"] == "path"
    assert list_parameters["product_id"]["required"] is True
    assert list_parameters["limit"]["schema"] == {
        "default": 50,
        "maximum": 100,
        "minimum": 1,
        "title": "Limit",
        "type": "integer",
    }
    assert list_parameters["status"]["schema"]["enum"] == ["all", "attention"]
    assert list_parameters["cursor"]["in"] == "query"
    assert list_parameters["cursor"]["required"] is False

    confirmation = import_operations[
        (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-confirmation",
            "post",
        )
    ]
    assert confirmation["requestBody"] == {
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/AdminImportRewriteConfirmationRequest"}
            }
        },
        "required": True,
    }
    for key, operation in import_operations.items():
        if key != (
            "/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}"
            "/imports/{import_id}/rewrite-confirmation",
            "post",
        ):
            assert "requestBody" not in operation


def test_import_schema_literals_requirements_and_bounds_are_frozen() -> None:
    """Keep state, readiness, reconciliation, cursor, and baseline shapes closed."""
    schemas = app.openapi()["components"]["schemas"]
    published = schemas["AdminPublishedMappingImportResponse"]
    listing = schemas["AdminPublishedMappingImportListResponse"]
    repository_side = schemas["AdminImportRepositorySideResponse"]
    source = schemas["AdminImportSourceReferenceResponse"]
    baseline = schemas["AdminImportBaselineResponse"]
    comparison = schemas["AdminImportRewriteComparisonResponse"]
    comparison_side = schemas["AdminImportRewriteSideResponse"]
    delta = schemas["AdminImportRewriteDeltaResponse"]
    confirmation = schemas["AdminImportRewriteConfirmationRequest"]
    operation_error = schemas["AdminImportOperationErrorResponse"]
    dataset_status = schemas["ImportDatasetStatus"]
    parser_issue = schemas["ImportParserIssue"]
    product = schemas["AdminProductResponse"]

    for contract in (
        published,
        listing,
        repository_side,
        source,
        baseline,
        comparison,
        comparison_side,
        delta,
        confirmation,
        operation_error,
        parser_issue,
        product,
    ):
        assert contract["additionalProperties"] is False

    assert set(published["required"]) == set(published["properties"]) - {"duplicate_report_summary"}
    summary = schemas["DuplicateReportSummaryResponse"]
    assert summary["additionalProperties"] is False
    assert set(summary["required"]) == {
        "complete",
        "group_count",
        "repeated_occurrences",
    }
    assert summary["properties"]["group_count"]["maximum"] == 50_000
    assert summary["properties"]["repeated_occurrences"]["maximum"] == 50_000
    assert published["properties"]["state"]["enum"] == [
        "not_imported",
        "queued",
        "running",
        "current",
        "may_be_stale",
        "review_required",
        "import_failed",
    ]
    assert published["properties"]["action"]["enum"] == [
        "run_import",
        "refresh_import",
        "retry_import",
        "import_in_progress",
        "review_baseline_change",
    ]
    assert published["properties"]["capability"]["enum"] == [
        "ready",
        "reauthorization_required",
        "unavailable",
    ]
    error_category = _schema_variant(published["properties"]["error_category"], type_name="string")
    assert error_category["enum"] == [
        "connection_required",
        "permission_denied",
        "rate_limited",
        "source_not_found",
        "timeout",
        "provider_unavailable",
        "bounded_failure",
    ]
    assert published["properties"]["repository_sides"]["minItems"] == 1
    assert published["properties"]["repository_sides"]["maxItems"] == 2
    assert published["properties"]["dataset_status"]["$ref"] == (
        "#/components/schemas/ImportDatasetStatus"
    )
    assert dataset_status["enum"] == ["not_created", "active", "retained"]
    assert published["properties"]["parser_issues"]["maxItems"] == 5
    assert published["properties"]["parser_issues"]["items"]["$ref"] == (
        "#/components/schemas/ImportParserIssue"
    )
    assert published["properties"]["parser_issue_remaining_count"] == {
        "maximum": 495,
        "minimum": 0,
        "title": "Parser Issue Remaining Count",
        "type": "integer",
    }
    assert parser_issue["additionalProperties"] is False
    assert set(parser_issue["required"]) == set(parser_issue["properties"])
    assert set(parser_issue["properties"]) == {
        "issue_code",
        "repository_side",
        "path",
        "line",
        "column",
        "message_key",
    }
    assert parser_issue["properties"]["issue_code"]["enum"] == [
        "malformed_file",
        "ambiguous_structure",
        "unsupported_structure",
        "duplicate_key",
        "base_language_required",
    ]
    assert parser_issue["properties"]["repository_side"]["enum"] == [
        "direct",
        "keys",
        "translations",
    ]
    assert parser_issue["properties"]["path"]["minLength"] == 1
    assert parser_issue["properties"]["path"]["maxLength"] == 4096
    for coordinate in ("line", "column"):
        bounded_coordinate = _schema_variant(
            parser_issue["properties"][coordinate], type_name="integer"
        )
        assert bounded_coordinate["minimum"] == 1
        assert bounded_coordinate["maximum"] == 2_147_483_647
    assert parser_issue["properties"]["message_key"]["enum"] == [
        "import.parser.malformed_file",
        "import.parser.ambiguous_structure",
        "import.parser.unsupported_structure",
        "import.parser.duplicate_key",
        "import.parser.base_language_required",
    ]
    assert published["properties"]["retry_count"]["minimum"] == 0
    assert (
        _schema_variant(published["properties"]["execution_number"], type_name="integer")["minimum"]
        == 1
    )
    error_message = _schema_variant(published["properties"]["error_message"], type_name="string")
    assert error_message["minLength"] == 1
    assert error_message["maxLength"] == 256

    assert listing["required"] == ["items"]
    assert listing["properties"]["items"]["maxItems"] == 100
    next_cursor = _schema_variant(listing["properties"]["next_cursor"], type_name="string")
    assert next_cursor["minLength"] == 1
    assert next_cursor["maxLength"] == 2048

    assert set(repository_side["required"]) == set(repository_side["properties"])
    assert repository_side["properties"]["role"]["enum"] == [
        "direct",
        "keys",
        "translations",
    ]
    assert repository_side["properties"]["source_branch"]["minLength"] == 1
    assert repository_side["properties"]["source_branch"]["maxLength"] == 255

    assert set(source["required"]) == set(source["properties"])
    assert source["properties"]["commit_hash"]["pattern"] == "^[0-9a-f]{40}$"
    assert source["properties"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert source["properties"]["size_bytes"]["minimum"] == 0
    assert source["properties"]["size_bytes"]["maximum"] == 1_048_576
    assert source["properties"]["path"]["maxLength"] == 4096
    assert set(baseline["required"]) == set(baseline["properties"])
    assert baseline["properties"]["source_references"]["maxItems"] == 500

    assert set(comparison["required"]) == set(comparison["properties"])
    assert comparison["properties"]["topology"]["enum"] == ["direct", "separate"]
    assert comparison["properties"]["confirmable"]["const"] is True
    assert comparison["properties"]["sides"]["minItems"] == 1
    assert comparison["properties"]["sides"]["maxItems"] == 2
    assert comparison["properties"]["files"]["maxItems"] == 500
    assert comparison["properties"]["proposal_digest"]["pattern"] == "^[0-9a-f]{64}$"

    assert set(comparison_side["required"]) == set(comparison_side["properties"])
    for count in ("added_count", "modified_count", "removed_count"):
        assert comparison_side["properties"][count]["minimum"] == 0
        assert comparison_side["properties"][count]["maximum"] == 500
    assert set(delta["required"]) == set(delta["properties"])
    assert delta["properties"]["change"]["enum"] == [
        "added",
        "modified",
        "removed",
    ]
    assert delta["properties"]["position"]["minimum"] == 0
    assert delta["properties"]["position"]["maximum"] == 499
    assert delta["properties"]["path"]["maxLength"] == 4096

    assert set(confirmation["required"]) == set(confirmation["properties"])
    assert confirmation["properties"]["proposal_digest"]["pattern"] == ("^[0-9a-f]{64}$")
    assert operation_error["required"] == ["detail"]
    assert operation_error["properties"]["detail"]["enum"] == [
        "Published import unavailable",
        "Published import already in progress",
        "Published import requires review",
        "Published import conflict",
        "Published import connection unavailable",
        "Import rewrite proposal stale",
        "Invalid import cursor",
    ]

    assert "affected_mapping_count" in product["required"]
    assert product["properties"]["affected_mapping_count"] == {
        "minimum": 0.0,
        "title": "Affected Mapping Count",
        "type": "integer",
    }


def test_translation_operation_surface_is_exact_unique_and_bearer_protected() -> None:
    """Freeze three reads and two constraint mutations as the sole translation surface."""
    schema = app.openapi()
    operations = _operation_entries(schema)
    translation_operations = {
        key: operation
        for key, operation in operations.items()
        if key[0].startswith("/api/v1/translations")
    }

    assert set(translation_operations) == set(TRANSLATION_OPERATIONS)
    operation_ids: list[str] = []
    for key, (operation_id, response_codes) in TRANSLATION_OPERATIONS.items():
        operation = translation_operations[key]
        operation_ids.append(operation["operationId"])
        assert operation["operationId"] == operation_id
        assert set(operation["responses"]) == response_codes
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]

    assert len(operation_ids) == 5
    assert len(set(operation_ids)) == 5

    options = translation_operations[("/api/v1/translations/options", "get")]
    search = translation_operations[("/api/v1/translations", "get")]
    detail = translation_operations[("/api/v1/translations/{translation_group_id}", "get")]
    constraint_path = "/api/v1/translations/{translation_group_id}/constraints/{language}"
    put_constraint = translation_operations[(constraint_path, "put")]
    delete_constraint = translation_operations[(constraint_path, "delete")]

    assert _response_schema(options, "200") == ("#/components/schemas/TranslationOptionsResponse")
    assert _response_schema(search, "200") == ("#/components/schemas/TranslationSearchPageResponse")
    assert _response_schema(detail, "200") == (
        "#/components/schemas/TranslationGroupDetailResponse"
    )
    for operation in (put_constraint, delete_constraint):
        assert _response_schema(operation, "200") == (
            "#/components/schemas/TranslationConstraintMutationResponse"
        )
    for operation in (options, search, detail, put_constraint, delete_constraint):
        for status_code in ("401", "403"):
            assert _response_schema(operation, status_code) == (
                "#/components/schemas/ErrorResponse"
            )
    for operation, status_codes in (
        (options, ("503",)),
        (search, ("503",)),
        (detail, ("404", "503")),
    ):
        for status_code in status_codes:
            assert _response_schema(operation, status_code) == (
                "#/components/schemas/TranslationErrorResponse"
            )
    assert _response_schema(detail, "422") == ("#/components/schemas/HTTPValidationError")
    for operation in (put_constraint, delete_constraint):
        for status_code in ("404", "409", "503"):
            assert _response_schema(operation, status_code) == (
                "#/components/schemas/TranslationConstraintErrorResponse"
            )

    for operation, domain_error in (
        (search, "TranslationErrorResponse"),
        (put_constraint, "TranslationConstraintErrorResponse"),
        (delete_constraint, "TranslationConstraintErrorResponse"),
    ):
        assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
            "anyOf": [
                {"$ref": f"#/components/schemas/{domain_error}"},
                {"$ref": "#/components/schemas/HTTPValidationError"},
            ]
        }

    option_parameters = _parameters_by_name(options)
    assert set(option_parameters) == {"product_id"}
    assert option_parameters["product_id"]["required"] is False
    assert option_parameters["product_id"]["in"] == "query"
    search_parameters = _parameters_by_name(search)
    assert set(search_parameters) == {
        "q",
        "product_id",
        "language",
        "state",
        "violation",
        "deleted",
        "page_size",
        "cursor",
    }
    assert all(parameter["in"] == "query" for parameter in search_parameters.values())
    assert all(parameter["required"] is False for parameter in search_parameters.values())
    assert _schema_variant(search_parameters["q"]["schema"], type_name="string") == {
        "type": "string",
        "maxLength": 256,
    }
    assert _schema_variant(search_parameters["product_id"]["schema"], type_name="string") == {
        "type": "string",
        "format": "uuid",
    }
    language = _schema_variant(search_parameters["language"]["schema"], type_name="string")
    assert language["minLength"] == 2
    assert language["maxLength"] == 64
    assert language["pattern"] == ("^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$")
    assert _schema_variant(search_parameters["state"]["schema"], type_name="string")["enum"] == [
        "draft",
        "approved",
        "rejected",
    ]
    assert _schema_variant(search_parameters["violation"]["schema"], type_name="string")[
        "enum"
    ] == ["over_limit", "within_limit", "no_max"]
    assert search_parameters["deleted"]["schema"] == {
        "type": "string",
        "enum": ["active", "deleted", "all"],
        "default": "active",
        "title": "Deleted",
    }
    assert search_parameters["page_size"]["schema"] == {
        "type": "integer",
        "const": 50,
        "default": 50,
        "title": "Page Size",
    }
    cursor = _schema_variant(search_parameters["cursor"]["schema"], type_name="string")
    assert cursor["minLength"] == 1
    assert cursor["maxLength"] == 2048

    for operation in (detail, put_constraint, delete_constraint):
        parameters = _parameters_by_name(operation)
        group_id = parameters["translation_group_id"]
        assert group_id["in"] == "path"
        assert group_id["required"] is True
        assert group_id["schema"] == {
            "type": "string",
            "format": "uuid",
            "title": "Translation Group Id",
        }
    for operation in (put_constraint, delete_constraint):
        language_parameter = _parameters_by_name(operation)["language"]
        assert language_parameter["in"] == "path"
        assert language_parameter["required"] is True
        assert language_parameter["schema"]["type"] == "string"
        assert language_parameter["schema"]["minLength"] == 2
        assert language_parameter["schema"]["maxLength"] == 64

    for operation in (options, search, detail):
        assert "requestBody" not in operation
    assert put_constraint["requestBody"] == {
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/PutTranslationConstraintRequest"}
            }
        },
        "required": True,
    }
    assert delete_constraint["requestBody"] == {
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/DeleteTranslationConstraintRequest"}
            }
        },
        "required": True,
    }


def test_translation_schemas_are_closed_bounded_and_non_leaking() -> None:
    """Freeze every generated search/detail/constraint distinction recursively."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    schema_names = {
        "DeleteTranslationConstraintRequest",
        "PutTranslationConstraintRequest",
        "TranslationConstraintErrorResponse",
        "TranslationConstraintMutationResponse",
        "TranslationConstraintMutationValueResponse",
        "TranslationConstraintProjectionResponse",
        "TranslationErrorResponse",
        "TranslationGroupDetailResponse",
        "TranslationGroupSummaryResponse",
        "TranslationLanguageOptionResponse",
        "TranslationOptionsResponse",
        "TranslationProductOptionResponse",
        "TranslationProvenanceResponse",
        "TranslationSearchPageResponse",
        "TranslationValueResponse",
    }
    public_schemas = {name: schemas[name] for name in schema_names}
    for contract in public_schemas.values():
        assert contract["additionalProperties"] is False

    options = schemas["TranslationOptionsResponse"]
    assert set(options["required"]) == {"products", "languages"}
    assert options["properties"]["products"]["maxItems"] == 500
    assert options["properties"]["languages"]["maxItems"] == 500
    assert schemas["TranslationProductOptionResponse"]["properties"]["id"]["format"] == "uuid"
    assert schemas["TranslationProductOptionResponse"]["properties"]["name"] == {
        "type": "string",
        "maxLength": 120,
        "minLength": 1,
        "title": "Name",
    }
    language_option = schemas["TranslationLanguageOptionResponse"]
    assert language_option["properties"]["code"]["minLength"] == 2
    assert language_option["properties"]["code"]["maxLength"] == 64
    assert language_option["properties"]["label"]["maxLength"] == 128

    page = schemas["TranslationSearchPageResponse"]
    assert page["required"] == ["items"]
    assert page["properties"]["items"]["maxItems"] == 50
    next_cursor = _schema_variant(page["properties"]["next_cursor"], type_name="string")
    assert next_cursor["minLength"] == 1
    assert next_cursor["maxLength"] == 2048

    summary = schemas["TranslationGroupSummaryResponse"]
    assert set(summary["required"]) == set(summary["properties"])
    assert summary["properties"]["id"]["format"] == "uuid"
    assert summary["properties"]["product_id"]["format"] == "uuid"
    assert summary["properties"]["raw_key"]["minLength"] == 1
    assert summary["properties"]["raw_key"]["maxLength"] == 1_048_576
    for text_field in ("source_text", "translated_text"):
        assert (
            _schema_variant(summary["properties"][text_field], type_name="string")["maxLength"]
            == 1_048_576
        )
        assert {item.get("type") for item in summary["properties"][text_field]["anyOf"]} == {
            "string",
            "null",
        }
    assert summary["properties"]["rank"]["minimum"] == 0
    assert summary["properties"]["rank"]["maximum"] == 3
    assert summary["properties"]["value_count"]["minimum"] == 1
    assert summary["properties"]["selector_kinds"]["minItems"] == 1
    assert summary["properties"]["selector_kinds"]["maxItems"] == 6
    assert summary["properties"]["selector_kinds"]["items"]["enum"] == [
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
    ]
    assert (
        _schema_variant(summary["properties"]["source_language"], type_name="string")["maxLength"]
        == 64
    )
    provenance = schemas["TranslationSummaryProvenanceResponse"]
    assert provenance["additionalProperties"] is False
    assert set(provenance["properties"]) == {"repository_name", "branch", "path"}
    assert provenance["properties"]["path"]["maxLength"] == 4096
    for count in ("over_limit_count", "within_limit_count", "no_max_count"):
        assert summary["properties"][count]["minimum"] == 0
    assert summary["properties"]["states"]["minItems"] == 1
    assert summary["properties"]["states"]["maxItems"] == 3
    assert summary["properties"]["states"]["items"]["enum"] == [
        "draft",
        "approved",
        "rejected",
    ]
    assert summary["properties"]["state_summary"]["enum"] == [
        "draft",
        "approved",
        "rejected",
        "mixed",
    ]

    detail = schemas["TranslationGroupDetailResponse"]
    assert set(detail["properties"]) == {
        "base_language",
        "explicit_maximum",
        "constraint_version",
        "base_maximum",
        "id",
        "product_id",
        "product_name",
        "raw_key",
        "language",
        "language_label",
        "states",
        "state_summary",
        "is_deleted",
        "values",
        "pending_change",
        "comments",
    }
    assert set(detail["required"]) == set(detail["properties"]) - {"pending_change"}
    assert detail["properties"]["values"]["minItems"] == 1
    assert detail["properties"]["values"]["maxItems"] == 10_000
    assert detail["properties"]["pending_change"]["type"] == "null"
    assert detail["properties"]["comments"]["maxItems"] == 0

    value = schemas["TranslationValueResponse"]
    assert value["properties"]["history"]["maxItems"] == 50
    assert schemas["TranslationHistoryResponse"]["additionalProperties"] is False
    assert schemas["TranslationSelectorFieldResponse"]["additionalProperties"] is False
    assert set(value["required"]) == set(value["properties"])
    assert value["properties"]["id"]["format"] == "uuid"
    assert value["properties"]["selector_version"]["const"] == 1
    assert value["properties"]["selector_kind"]["enum"] == [
        "scalar",
        "android_quantity",
        "android_array_item",
        "qt_numerus",
        "qt_length_variant",
        "json_path",
    ]
    assert value["properties"]["selector_digest"]["pattern"] == "^[0-9a-f]{64}$"
    assert value["properties"]["structure"]["maxItems"] == 16_384
    assert value["properties"]["review_state"]["enum"] == [
        "draft",
        "approved",
        "rejected",
    ]
    assert value["properties"]["grapheme_count"]["minimum"] == 0
    assert {item.get("type") for item in value["properties"]["deleted_at"]["anyOf"]} == {
        "string",
        "null",
    }
    assert value["properties"]["deleted_at"]["anyOf"][0]["format"] == "date-time"
    assert _schema_references(value["properties"]["provenance"]) == {
        "TranslationProvenanceResponse"
    }

    projection = schemas["TranslationConstraintProjectionResponse"]
    assert set(projection["required"]) == set(projection["properties"])
    assert projection["properties"]["actual"]["minimum"] == 0
    maximum = _schema_variant(projection["properties"]["maximum"], type_name="integer")
    assert maximum["minimum"] == 0
    assert maximum["maximum"] == 1_048_576
    assert projection["properties"]["source"]["enum"] == [
        "none",
        "base_default",
        "language_override",
    ]
    assert projection["properties"]["status"]["enum"] == [
        "no_max",
        "within_limit",
        "over_limit",
    ]
    assert _schema_variant(projection["properties"]["overage"], type_name="integer")["minimum"] == 0

    put_request = schemas["PutTranslationConstraintRequest"]
    delete_request = schemas["DeleteTranslationConstraintRequest"]
    assert set(put_request["required"]) == {"max_chars", "expected_version"}
    assert set(put_request["properties"]) == {"max_chars", "expected_version"}
    assert put_request["properties"]["max_chars"]["minimum"] == 0
    assert put_request["properties"]["max_chars"]["maximum"] == 1_048_576
    assert put_request["properties"]["expected_version"]["minimum"] == 0
    assert delete_request["required"] == ["expected_version"]
    assert set(delete_request["properties"]) == {"expected_version"}
    assert delete_request["properties"]["expected_version"]["minimum"] == 0

    mutation = schemas["TranslationConstraintMutationResponse"]
    assert set(mutation["required"]) == set(mutation["properties"])
    assert mutation["properties"]["translation_group_id"]["format"] == "uuid"
    explicit_maximum = _schema_variant(
        mutation["properties"]["explicit_maximum"], type_name="integer"
    )
    assert explicit_maximum["minimum"] == 0
    assert explicit_maximum["maximum"] == 1_048_576
    assert _schema_variant(mutation["properties"]["version"], type_name="integer")["minimum"] == 1
    assert mutation["properties"]["violating_count"]["minimum"] == 0
    assert mutation["properties"]["total_count"]["minimum"] == 0
    assert mutation["properties"]["values"]["minItems"] == 1
    assert mutation["properties"]["values"]["maxItems"] == 10_000

    provenance = schemas["TranslationProvenanceResponse"]
    assert set(provenance["required"]) == set(provenance["properties"])
    for identifier in ("repository_id", "execution_id"):
        assert provenance["properties"][identifier]["format"] == "uuid"
    assert provenance["properties"]["repository_side"]["enum"] == [
        "direct",
        "keys",
        "translations",
    ]
    assert provenance["properties"]["format"]["enum"] == [
        "android_xml",
        "qt_ts",
        "json",
        "ios_strings",
        "xliff",
    ]
    assert provenance["properties"]["branch"]["maxLength"] == 255
    assert provenance["properties"]["path"]["maxLength"] == 4096
    assert provenance["properties"]["commit_hash"]["pattern"] == "^[0-9a-f]{40}$"
    for coordinate in ("line", "column"):
        bounded = _schema_variant(provenance["properties"][coordinate], type_name="integer")
        assert bounded["minimum"] == 1
        assert bounded["maximum"] == 2_147_483_647

    assert schemas["TranslationErrorResponse"]["properties"]["detail"]["enum"] == [
        "Invalid translation cursor",
        "Translation unavailable",
        "Translation search unavailable",
    ]
    assert schemas["TranslationConstraintErrorResponse"]["properties"]["detail"]["enum"] == [
        "Translation unavailable",
        "Translation constraint conflict",
        "Invalid translation constraint input",
        "Translation constraint unavailable",
    ]

    public_contract = {
        "paths": {
            path: value
            for path, value in schema["paths"].items()
            if path.startswith("/api/v1/translations")
        },
        "schemas": {
            **public_schemas,
            "ImportDatasetStatus": schemas["ImportDatasetStatus"],
            "ImportParserIssue": schemas["ImportParserIssue"],
            "AdminPublishedMappingImportResponse": schemas["AdminPublishedMappingImportResponse"],
        },
    }
    forbidden = {
        "access_token",
        "authorization",
        "celery_result",
        "ciphertext",
        "client_secret",
        "correlation_id",
        "credential",
        "credentials",
        "database_query",
        "exception",
        "exception_message",
        "parser_exception",
        "provider_body",
        "provider_response",
        "queue_name",
        "raw_body",
        "raw_source",
        "refresh_token",
        "source_bytes",
        "source_file_content",
        "sql",
        "stack",
        "stack_trace",
        "staging_path",
        "task_id",
    }
    assert forbidden.isdisjoint(_schema_property_names(public_contract))


def test_import_generated_client_matches_the_canonical_operation_and_type_set() -> None:
    """Fail until pinned generation carries every canonical Phase 3 import shape."""
    sdk_source = (GENERATED_CLIENT / "sdk.gen.ts").read_text()
    index_source = (GENERATED_CLIENT / "index.ts").read_text()
    types_source = (GENERATED_CLIENT / "types.gen.ts").read_text()
    operation_exports = (
        "listAdminPublishedMappingImports",
        "startAdminPublishedMappingImport",
        "getAdminImport",
        "getAdminImportRewriteComparison",
        "confirmAdminImportRewriteBaseline",
    )

    for operation in operation_exports:
        assert sdk_source.count(f"export const {operation} =") == 1
        assert len(re.findall(rf"\b{re.escape(operation)}\b", index_source)) == 1

    for generated_type in (
        "AdminImportRewriteComparisonResponse",
        "AdminImportRewriteConfirmationRequest",
        "AdminImportRewriteDeltaResponse",
        "AdminImportRewriteSideResponse",
    ):
        assert f"export type {generated_type}" in types_source
        assert len(re.findall(rf"\b{re.escape(generated_type)}\b", index_source)) == 1

    assert "affected_mapping_count: number" in types_source


def test_admin_bitbucket_openapi_is_closed_bounded_and_secret_free() -> None:
    """Expose only approved lifecycle state and closed capability readiness."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    connection_status = schemas["AdminBitbucketStatusResponse"]
    integration_error = schemas["AdminBitbucketErrorResponse"]

    assert "AdminBitbucketAuthorizationResponse" not in schemas
    assert connection_status["additionalProperties"] is False
    assert set(connection_status["properties"]) == {
        "status",
        "scope_profile",
        "scope_label",
        "capability_profile",
        "connected_at",
        "expires_at",
        "revoked_at",
    }
    assert connection_status["properties"]["status"]["enum"] == [
        "Disconnected",
        "Connected",
        "Reauthorization required",
        "Unavailable",
    ]
    assert connection_status["properties"]["scope_profile"]["const"] == (
        "repository_and_pull_request"
    )
    assert connection_status["properties"]["scope_label"]["const"] == (
        "Repository and pull-request access"
    )
    capability_profile = schemas["AdminBitbucketCapabilityProfile"]
    assert capability_profile["additionalProperties"] is False
    assert set(capability_profile["properties"]) == {
        "source_read",
        "source_write",
        "pull_request",
        "evaluated_at",
    }
    for field in ("source_read", "source_write", "pull_request"):
        assert capability_profile["properties"][field]["enum"] == [
            "disconnected",
            "ready",
            "ready_for_later_phase",
            "reauthorization_required",
            "unavailable",
        ]
    assert integration_error["additionalProperties"] is False
    assert integration_error["properties"]["detail"]["const"] == (
        "Bitbucket connection unavailable"
    )

    bitbucket_paths = {
        path: value
        for path, value in schema["paths"].items()
        if path.startswith("/api/v1/admin/bitbucket")
    }
    assert set(bitbucket_paths) == {
        "/api/v1/admin/bitbucket",
        "/api/v1/admin/bitbucket/connect",
        "/api/v1/admin/bitbucket/reconnect",
        "/api/v1/admin/bitbucket/revoke",
    }
    assert {
        operation["operationId"]
        for path_item in bitbucket_paths.values()
        for operation in path_item.values()
    } == {
        "get_admin_bitbucket_status",
        "connect_admin_bitbucket_oauth",
        "reconnect_admin_bitbucket_oauth",
        "revoke_admin_bitbucket_connection_locally",
    }

    bitbucket_contract = json.dumps(
        {
            "paths": bitbucket_paths,
            "schemas": {
                name: value for name, value in schemas.items() if name.startswith("AdminBitbucket")
            },
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "access_token",
        "authorization_url",
        "callback",
        "ciphertext",
        "client_id",
        "refresh_token",
        "encryption_key",
        "client_secret",
        "provider_body",
        "source_generation",
        "raw_scope",
        "effective_scope",
        "repository:write",
        "pullrequest",
        "webhook",
        "provider_revoke",
        "state_expires_in",
        "workspace",
    ):
        assert forbidden not in bitbucket_contract


def test_admin_discovery_openapi_is_commit_bound_bounded_and_body_free() -> None:
    """Expose exact branch/source metadata without raw provider bytes or provider URLs."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    source = schemas["AdminSourceDiscoveryResponse"]
    source_file = schemas["AdminSourceFileResponse"]
    discovery_error = schemas["AdminDiscoveryErrorResponse"]

    assert source["additionalProperties"] is False
    assert set(source["properties"]) == {"commit_hash", "files", "total_bytes"}
    assert source_file["additionalProperties"] is False
    assert set(source_file["properties"]) == {"path", "size"}
    assert discovery_error["additionalProperties"] is False
    assert discovery_error["properties"]["state"]["enum"] == [
        "disconnected",
        "reauthorization_required",
        "permission_denied",
        "not_found",
        "rate_limited",
        "unavailable",
        "timeout",
        "invalid_source",
        "limit_exceeded",
    ]

    discovery_contract = json.dumps(
        {
            "paths": {
                path: value
                for path, value in schema["paths"].items()
                if path.startswith("/api/v1/admin/repositories/")
                and (path.endswith("/branches") or path.endswith("/sources"))
            },
            "schemas": {
                name: value
                for name, value in schemas.items()
                if name.startswith("AdminBranch")
                or name.startswith("AdminSource")
                or name == "AdminDiscoveryErrorResponse"
            },
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "provider_url",
        "provider_body",
        "access_token",
        "refresh_token",
        "file_content",
        "file_bytes",
        "raw_bytes",
        "repository:write",
        "pullrequest",
    ):
        assert forbidden not in discovery_contract


def test_revision_mapping_and_exact_branch_openapi_contract_is_structurally_frozen() -> None:
    """Freeze owned revision IDs, opaque branch queries, cursors, and closed schemas."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    revision_path = "/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings"
    branch_path = "/api/v1/admin/repositories/{repository_id}/branch"
    revision_operation = schema["paths"][revision_path]["get"]
    branch_operation = schema["paths"][branch_path]["get"]

    assert revision_operation["operationId"] == "list_admin_revision_mappings"
    revision_parameters = _parameters_by_name(revision_operation)
    assert set(revision_parameters) == {"product_id", "revision_id", "limit", "cursor"}
    assert {
        name: (parameter["in"], parameter["required"])
        for name, parameter in revision_parameters.items()
    } == {
        "product_id": ("path", True),
        "revision_id": ("path", True),
        "limit": ("query", False),
        "cursor": ("query", False),
    }
    for name in ("product_id", "revision_id"):
        assert revision_parameters[name]["schema"] == {
            "type": "string",
            "format": "uuid",
            "title": " ".join(part.title() for part in name.split("_")),
        }
    assert revision_parameters["limit"]["schema"] == {
        "type": "integer",
        "maximum": 100,
        "minimum": 1,
        "default": 50,
        "title": "Limit",
    }
    assert revision_parameters["cursor"]["schema"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert _response_schema(revision_operation, "200") == (
        "#/components/schemas/AdminMappingListResponse"
    )

    assert branch_operation["operationId"] == "get_admin_repository_branch"
    branch_parameters = _parameters_by_name(branch_operation)
    assert set(branch_parameters) == {"repository_id", "branch_name"}
    assert branch_parameters["repository_id"]["in"] == "path"
    assert branch_parameters["repository_id"]["required"] is True
    assert branch_parameters["branch_name"]["in"] == "query"
    assert branch_parameters["branch_name"]["required"] is True
    assert branch_parameters["branch_name"]["schema"] == {
        "type": "string",
        "maxLength": 255,
        "minLength": 1,
        "title": "Branch Name",
    }
    assert _response_schema(branch_operation, "200") == ("#/components/schemas/AdminBranchResponse")
    assert not any("{branch" in path for path in schema["paths"])

    for list_schema_name, item_schema_name in (
        ("AdminRepositoryListResponse", "AdminRepositoryResponse"),
        ("AdminBranchListResponse", "AdminBranchResponse"),
        ("AdminMappingListResponse", "AdminMappingResponse"),
    ):
        list_schema = schemas[list_schema_name]
        assert list_schema["additionalProperties"] is False
        assert set(list_schema["properties"]) == {"items", "next_cursor"}
        assert set(list_schema["required"]) == {"items", "next_cursor"}
        assert list_schema["properties"]["items"]["items"]["$ref"] == (
            f"#/components/schemas/{item_schema_name}"
        )
        assert list_schema["properties"]["next_cursor"]["anyOf"] == [
            {"type": "string"},
            {"type": "null"},
        ]

    public_operation_schemas = {
        name
        for operation in (revision_operation, branch_operation)
        for name in _schema_references(operation["responses"])
    }
    assert public_operation_schemas == {
        "AdminBranchResponse",
        "AdminDiscoveryErrorResponse",
        "AdminMappingListResponse",
        "ErrorResponse",
    }
    for schema_name in public_operation_schemas:
        assert schemas[schema_name]["additionalProperties"] is False

    public_contract_schemas = {
        name: value
        for name, value in schemas.items()
        if name.startswith(("AdminBranch", "AdminDiscovery", "AdminMapping"))
        or name in {"AdminRepositoryListResponse", "AdminBitbucketStatusResponse"}
    }
    assert _schema_property_names(public_contract_schemas).isdisjoint(
        {
            "access_token",
            "authorization_url",
            "ciphertext",
            "client_secret",
            "credentials",
            "next",
            "next_url",
            "provider_next",
            "provider_next_url",
            "provider_url",
            "refresh_token",
        }
    )
    assert "workspace" not in schemas["AdminBitbucketStatusResponse"]["properties"]


def test_admin_preview_openapi_is_closed_current_and_source_free() -> None:
    """Freeze durable attempt metadata while excluding source/provider/worker payloads."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    create_request = schemas["AdminPreviewJobCreateRequest"]
    response = schemas["AdminPreviewJobResponse"]
    result = schemas["AdminPreviewJobResultResponse"]
    repository_side = schemas["AdminPreviewRepositorySideResponse"]
    layout_candidate = schemas["AdminPreviewLayoutCandidateResponse"]
    preview_sample = schemas["AdminPreviewSampleResponse"]
    confirmation_request = schemas["AdminPreviewConfirmationRequest"]
    confirmation_response = schemas["AdminPreviewConfirmationResponse"]
    latest_path = (
        "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs/latest"
    )

    assert schema["paths"][latest_path]["get"]["operationId"] == (
        "get_admin_latest_candidate_preview_job"
    )
    assert schema["paths"][latest_path]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/AdminPreviewJobResponse"}

    assert create_request["additionalProperties"] is False
    assert set(create_request["properties"]) == {"expected_candidate_version", "commits"}
    assert response["additionalProperties"] is False
    assert set(response["properties"]) == {
        "id",
        "input_digest",
        "attempt",
        "state",
        "product_id",
        "candidate_revision_id",
        "candidate_revision_version",
        "mapping_id",
        "connection_generation",
        "detector_version",
        "repository_sides",
        "result",
        "error_code",
        "diagnostic_code",
        "duplicate_report_summary",
        "is_current",
        "created_at",
        "started_at",
        "finished_at",
    }
    assert result["additionalProperties"] is False
    assert set(result["properties"]) == {"detector_version", "digest", "layout_candidates"}
    assert result["properties"]["layout_candidates"]["maxItems"] == 500
    assert layout_candidate["additionalProperties"] is False
    assert set(layout_candidate["properties"]) == {
        "id",
        "version",
        "repository_side",
        "format",
        "layout_identity",
        "confidence",
        "files",
        "languages",
        "keys",
        "samples",
        "samples_are_partial",
    }
    assert "maxItems" not in layout_candidate["properties"]["languages"]
    assert layout_candidate["properties"]["keys"]["maxItems"] == 100
    assert layout_candidate["properties"]["samples"]["maxItems"] == 100
    assert layout_candidate["properties"]["samples_are_partial"]["const"] is True
    assert preview_sample["additionalProperties"] is False
    assert set(preview_sample["properties"]) == {"language", "key", "translation"}
    assert repository_side["additionalProperties"] is False
    assert confirmation_request["additionalProperties"] is False
    assert set(confirmation_request["properties"]) == {
        "preview_digest",
        "layout_candidate_id",
        "layout_candidate_version",
        "base_language",
    }
    assert set(confirmation_request["required"]) == set(confirmation_request["properties"])
    assert confirmation_request["properties"]["preview_digest"]["pattern"] == "^[0-9a-f]{64}$"
    assert confirmation_request["properties"]["layout_candidate_version"]["const"] == 1
    base_language_request = confirmation_request["properties"]["base_language"]["anyOf"]
    assert base_language_request == [
        {"type": "string", "maxLength": 64, "minLength": 1},
        {"type": "null"},
    ]
    assert confirmation_response["additionalProperties"] is False
    assert set(confirmation_response["properties"]) == {
        "job_id",
        "mapping_id",
        "preview_digest",
        "layout_candidate_id",
        "layout_candidate_version",
        "base_language",
        "confirmed_by",
        "confirmed_at",
    }
    assert confirmation_response["properties"]["base_language"]["minLength"] == 1
    assert confirmation_response["properties"]["base_language"]["maxLength"] == 64

    preview_contract = json.dumps(
        {
            "paths": {
                path: value for path, value in schema["paths"].items() if "preview-jobs" in path
            },
            "schemas": {
                name: value for name, value in schemas.items() if name.startswith("AdminPreview")
            },
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "source_bytes",
        "access_token",
        "provider_body",
        "celery_result",
        "canonical_translation",
        "source_file_content",
    ):
        assert forbidden not in preview_contract


def test_active_revision_revalidation_openapi_is_exact_bounded_and_source_free() -> None:
    """Freeze the four recovery operations and their active-revision vocabulary."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    eligibility_path = (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility"
    )
    create_path = (
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
        "/mappings/{mapping_id}/revalidation-preview-jobs"
    )
    latest_path = f"{create_path}/latest"
    job_path = "/api/v1/admin/active-revision-revalidation-jobs/{job_id}"
    confirmation_path = f"{job_path}/confirmation"
    operation_ids = {
        schema["paths"][eligibility_path]["get"]["operationId"],
        schema["paths"][create_path]["post"]["operationId"],
        schema["paths"][latest_path]["get"]["operationId"],
        schema["paths"][job_path]["get"]["operationId"],
        schema["paths"][confirmation_path]["post"]["operationId"],
    }
    assert operation_ids == {
        "get_admin_product_reactivation_eligibility",
        "create_admin_active_revision_revalidation_job",
        "get_admin_latest_active_revision_revalidation_job",
        "get_admin_active_revision_revalidation_job",
        "confirm_admin_active_revision_revalidation",
    }

    eligibility_parameters = _parameters_by_name(schema["paths"][eligibility_path]["get"])
    assert set(eligibility_parameters) == {
        "product_id",
        "revision_id",
        "expected_active_revision_version",
    }
    assert eligibility_parameters["expected_active_revision_version"]["required"] is True
    assert eligibility_parameters["expected_active_revision_version"]["schema"]["minimum"] == 1

    create_request = schemas["AdminActiveRevisionRevalidationJobCreateRequest"]
    confirmation_request = schemas["AdminActiveRevisionRevalidationConfirmationRequest"]
    job_response = schemas["AdminActiveRevisionRevalidationJobResponse"]
    confirmation_response = schemas["AdminActiveRevisionRevalidationConfirmationResponse"]
    eligibility_response = schemas["AdminProductReactivationEligibilityResponse"]
    mapping_response = schemas["AdminProductReactivationMappingResponse"]
    expected_properties = {
        "AdminActiveRevisionRevalidationJobCreateRequest": {
            "expected_active_revision_version",
            "commits",
        },
        "AdminActiveRevisionRevalidationConfirmationRequest": {
            "active_revision_id",
            "active_revision_version",
            "mapping_id",
            "connection_generation",
            "commits",
            "preview_digest",
            "layout_candidate_id",
            "layout_candidate_version",
            "base_language",
        },
        "AdminActiveRevisionRevalidationJobResponse": {
            "id",
            "input_digest",
            "attempt",
            "state",
            "product_id",
            "active_revision_id",
            "active_revision_version",
            "mapping_id",
            "connection_generation",
            "detector_version",
            "repository_sides",
            "result",
            "error_code",
            "diagnostic_code",
            "duplicate_report_summary",
            "is_current",
            "created_at",
            "started_at",
            "finished_at",
        },
        "AdminActiveRevisionRevalidationConfirmationResponse": {
            "job_id",
            "product_id",
            "active_revision_id",
            "active_revision_version",
            "mapping_id",
            "connection_generation",
            "commits",
            "preview_digest",
            "layout_candidate_id",
            "layout_candidate_version",
            "base_language",
            "confirmed_by",
            "confirmed_at",
        },
        "AdminProductReactivationEligibilityResponse": {
            "product_id",
            "active_revision_id",
            "active_revision_version",
            "eligible",
            "blocker_codes",
            "mappings",
        },
        "AdminProductReactivationMappingResponse": {
            "mapping_id",
            "is_current",
            "blocker_codes",
        },
    }
    for schema_name, properties in expected_properties.items():
        contract = schemas[schema_name]
        assert contract["additionalProperties"] is False
        assert set(contract["properties"]) == properties
        optional = (
            {"duplicate_report_summary"}
            if schema_name == "AdminActiveRevisionRevalidationJobResponse"
            else set()
        )
        assert set(contract["required"]) == properties - optional

    assert create_request["properties"]["commits"]["minItems"] == 1
    assert create_request["properties"]["commits"]["maxItems"] == 2
    assert confirmation_request["properties"]["commits"]["maxItems"] == 2
    assert confirmation_request["properties"]["preview_digest"]["pattern"] == ("^[0-9a-f]{64}$")
    assert confirmation_request["properties"]["layout_candidate_version"]["const"] == 1
    assert confirmation_request["properties"]["base_language"]["anyOf"] == [
        {"type": "string", "maxLength": 64, "minLength": 1},
        {"type": "null"},
    ]
    assert job_response["properties"]["repository_sides"]["maxItems"] == 2
    assert confirmation_response["properties"]["commits"]["maxItems"] == 2
    assert confirmation_response["properties"]["base_language"]["minLength"] == 1
    assert confirmation_response["properties"]["base_language"]["maxLength"] == 64
    assert eligibility_response["properties"]["mappings"]["maxItems"] == 500
    assert mapping_response["properties"]["blocker_codes"]["maxItems"] == 6

    error_code = job_response["properties"]["error_code"]["anyOf"][0]
    assert "stale_active_revision" in error_code["enum"]
    assert "stale_candidate" not in error_code["enum"]
    active_contract = json.dumps(
        {
            "paths": {
                path: schema["paths"][path]
                for path in (
                    eligibility_path,
                    create_path,
                    job_path,
                    confirmation_path,
                )
            },
            "schemas": {name: schemas[name] for name in expected_properties},
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "access_token",
        "candidate_revision_id",
        "candidate_revision_version",
        "client_secret",
        "credentials",
        "provider_body",
        "provider_write",
        "raw_body",
        "refresh_token",
        "repository:write",
        "source_bytes",
        "source_file_content",
    ):
        assert forbidden not in active_contract


def test_admin_product_openapi_is_closed_to_exact_lifecycle_operations() -> None:
    """Expose only typed product lifecycle actions over publication authority."""
    schema = app.openapi()
    product = schema["components"]["schemas"]["AdminProductResponse"]
    revision = schema["components"]["schemas"]["AdminProductRevisionSummary"]
    conflict = schema["components"]["schemas"]["AdminProductConflictResponse"]
    lifecycle_conflict = schema["components"]["schemas"]["AdminProductLifecycleConflictResponse"]
    publish_request = schema["components"]["schemas"]["AdminProductPublishRequest"]
    reactivate_request = schema["components"]["schemas"]["AdminProductReactivateRequest"]

    assert product["additionalProperties"] is False
    assert set(product["properties"]) == {
        "id",
        "name",
        "is_active",
        "affected_mapping_count",
        "active_revision",
        "candidate_revision",
    }
    assert revision["additionalProperties"] is False
    assert set(revision["properties"]) == {
        "id",
        "version",
        "name",
        "description",
        "is_published",
    }
    assert conflict["additionalProperties"] is False
    assert set(conflict["properties"]) == {"detail", "field"}
    assert lifecycle_conflict["additionalProperties"] is False
    assert set(lifecycle_conflict["properties"]) == {"detail", "blockers"}
    assert publish_request["additionalProperties"] is False
    assert set(publish_request["properties"]) == {
        "candidate_revision_id",
        "expected_candidate_version",
    }
    assert reactivate_request["additionalProperties"] is False
    assert set(reactivate_request["properties"]) == {
        "active_revision_id",
        "expected_active_version",
    }
    assert lifecycle_conflict["properties"]["blockers"]["items"]["enum"] == [
        "mappings_required",
        "mapping_configuration_invalid",
        "target_configuration_invalid",
        "layout_required",
        "preview_confirmation_required",
    ]
    lifecycle_paths = {
        path
        for path in schema["paths"]
        if path.startswith("/api/v1/admin/products/{product_id}/")
        and path.rsplit("/", maxsplit=1)[-1] in {"publish", "deactivate", "reactivate"}
    }
    assert lifecycle_paths == {
        "/api/v1/admin/products/{product_id}/deactivate",
        "/api/v1/admin/products/{product_id}/publish",
        "/api/v1/admin/products/{product_id}/reactivate",
    }
    revision_paths = {path for path in schema["paths"] if "/revisions/" in path}
    assert revision_paths == {
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings",
        ("/api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility"),
        (
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
            "/mappings/{mapping_id}/revalidation-preview-jobs"
        ),
        (
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
            "/mappings/{mapping_id}/revalidation-preview-jobs/latest"
        ),
    }
    assert set(
        schema["paths"]["/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings"]
    ) == {"get"}
    assert set(
        schema["paths"][
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}/reactivation-eligibility"
        ]
    ) == {"get"}
    assert set(
        schema["paths"][
            "/api/v1/admin/products/{product_id}/revisions/{revision_id}"
            "/mappings/{mapping_id}/revalidation-preview-jobs"
        ]
    ) == {"post"}
    lifecycle_contract = json.dumps(
        {path: schema["paths"][path] for path in sorted(lifecycle_paths)},
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "access_token",
        "canonical_translation",
        "commit_create",
        "provider_write",
        "pull_request_create",
        "refresh_token",
        "webhook_create",
    ):
        assert forbidden not in lifecycle_contract


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


def test_admin_user_openapi_keeps_temporary_credentials_on_one_time_responses_only() -> None:
    """Ordinary list/update/deactivate contracts cannot project credential material."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    ordinary = schemas["AdminUserResponse"]["properties"]
    listed = schemas["AdminUserListResponse"]["properties"]
    credential = schemas["AdminUserCredentialResponse"]["properties"]

    assert "temporary_password" not in ordinary
    assert "temporary_password" not in listed
    assert "temporary_password" in credential
    assert "hashed_password" not in json.dumps(schemas)

    operations = _operation_entries(schema)
    credential_paths = {
        ("/api/v1/admin/users", "post"),
        ("/api/v1/admin/users/{user_id}/reactivate", "post"),
        ("/api/v1/admin/users/{user_id}/reset-password", "post"),
    }
    for key, operation in operations.items():
        if not key[0].startswith("/api/v1/admin/users"):
            continue
        success_code = "201" if key == ("/api/v1/admin/users", "post") else "200"
        reference = _response_schema(operation, success_code)
        if key in credential_paths:
            assert reference == "#/components/schemas/AdminUserCredentialResponse"
        elif key != ("/api/v1/admin/users", "get"):
            assert reference == "#/components/schemas/AdminUserResponse"


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


def test_openapi_exposes_xliff_in_preview_and_translation_formats() -> None:
    schemas = app.openapi()["components"]["schemas"]
    preview = schemas["AdminPreviewLayoutCandidateResponse"]["properties"]["format"]
    provenance = schemas["TranslationProvenanceResponse"]["properties"]["format"]

    assert preview["enum"] == ["android_xml", "qt_ts", "json", "ios_strings", "xliff"]
    assert provenance["enum"] == ["android_xml", "qt_ts", "json", "ios_strings", "xliff"]
