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
    (
        "/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
        "post",
    ): (
        "create_admin_preview_job",
        {"202", "401", "403", "404", "409", "422", "503"},
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
    ("/api/v1/admin/products/{product_id}", "get"): (
        "get_admin_product",
        {"200", "401", "403", "404", "422"},
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
        ("/api/v1/admin/preview-jobs/{job_id}", "get"): {
            "401",
            "403",
            "404",
            "409",
            "422",
            "503",
        },
        ("/api/v1/admin/products/{product_id}", "get"): {"401", "403", "404", "422"},
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
    mapping_collection = "/api/v1/admin/products/{product_id}/candidate/mappings"
    mapping_detail = mapping_collection + "/{mapping_id}"
    assert _response_schema(operations[(mapping_collection, "post")], "409") == (
        "#/components/schemas/AdminMappingConflictResponse"
    )
    assert _response_schema(operations[(mapping_detail, "patch")], "409") == (
        "#/components/schemas/AdminMappingConflictResponse"
    )


def test_admin_bitbucket_openapi_is_closed_bounded_and_secret_free() -> None:
    """Expose only approved lifecycle state and exact repository read scope."""
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
    assert connection_status["properties"]["scope_profile"]["const"] == "repository"
    assert connection_status["properties"]["scope_label"]["const"] == (
        "Read-only repository access"
    )
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
    assert layout_candidate["properties"]["languages"]["maxItems"] == 32
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
    }
    assert confirmation_request["properties"]["preview_digest"]["pattern"] == "^[0-9a-f]{64}$"
    assert confirmation_request["properties"]["layout_candidate_version"]["const"] == 1
    assert confirmation_response["additionalProperties"] is False
    assert set(confirmation_response["properties"]) == {
        "job_id",
        "mapping_id",
        "preview_digest",
        "layout_candidate_id",
        "layout_candidate_version",
        "confirmed_by",
        "confirmed_at",
    }

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
        and any(action in path for action in ("publish", "deactivate", "reactivate"))
    }
    assert lifecycle_paths == {
        "/api/v1/admin/products/{product_id}/deactivate",
        "/api/v1/admin/products/{product_id}/publish",
        "/api/v1/admin/products/{product_id}/reactivate",
    }
    revision_paths = {path for path in schema["paths"] if "/revisions/" in path}
    assert revision_paths == {
        "/api/v1/admin/products/{product_id}/revisions/{revision_id}/mappings"
    }
    assert set(schema["paths"][revision_paths.pop()]) == {"get"}
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
