"""Phase 2 fail-closed architecture and product-scope exclusions."""

from __future__ import annotations

import ast
from pathlib import Path

from verboflex.main import create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src" / "verboflex"
FRONTEND_SOURCE = REPOSITORY_ROOT / "frontend" / "src"

FORBIDDEN_RESOURCE_SEGMENTS = {
    "/pull-requests",
}
PHASE5_COMMENT_OPERATIONS = {
    (
        "/api/v1/translations/{translation_group_id}/comments",
        "get",
    ): "listTranslationComments",
    (
        "/api/v1/translations/{translation_group_id}/comments",
        "post",
    ): "createTranslationComment",
    (
        "/api/v1/translations/{translation_group_id}/comments/anchor",
        "get",
    ): "getTranslationCommentAnchor",
    (
        "/api/v1/translations/{translation_group_id}/comments/{comment_id}",
        "put",
    ): "updateTranslationComment",
    (
        "/api/v1/translations/{translation_group_id}/comments/{comment_id}",
        "delete",
    ): "deleteTranslationComment",
    (
        "/api/v1/translations/{translation_group_id}/comments/{comment_id}/versions",
        "get",
    ): "listTranslationCommentVersions",
}
FORBIDDEN_PROVIDER_TOKENS = {
    "branch_create",
    "commit_create",
    "issue",
    "merge",
    "pipeline",
    "pull_request",
    "source_write",
    "tag",
    "webhook",
    "wiki",
}
EXPECTED_MODEL_MODULES = {
    "branch_workflow.py",
    "source_fallback.py",
    "screenshot.py",
    "audit.py",
    "authoring.py",
    "glossary.py",
    "duplicate_report.py",
    "auth_session.py",
    "bitbucket_connection.py",
    "import_job.py",
    "preview_job.py",
    "product.py",
    "product_mapping.py",
    "product_member.py",
    "review.py",
    "repository.py",
    "role.py",
    "user.py",
    "translation.py",
    "translation_constraint.py",
    "submission.py",
    "mcp_oauth.py",
}


def test_openapi_has_no_deferred_resource_or_provider_write_surface() -> None:
    """The assembled API cannot grow still-deferred resources or provider writes."""
    schema = create_app().openapi()
    paths = set(schema["paths"])
    assert not {
        path for path in paths if any(segment in path for segment in FORBIDDEN_RESOURCE_SEGMENTS)
    }
    comment_operations = {
        (path, method): operation["operationId"]
        for path, path_item in schema["paths"].items()
        if "/comments" in path
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "delete", "patch"}
    }
    assert comment_operations == PHASE5_COMMENT_OPERATIONS
    provider_operation_ids = {
        operation["operationId"].casefold()
        for path, path_item in schema["paths"].items()
        if "/bitbucket" in path or "/repositories" in path
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert not {
        operation_id
        for operation_id in provider_operation_ids
        if any(token in operation_id for token in FORBIDDEN_PROVIDER_TOKENS)
    }


def test_phase2_persists_configuration_and_preview_authority_only() -> None:
    """Only approved configuration, canonical translation and review models persist."""
    model_modules = {
        path.name for path in (BACKEND_SOURCE / "models").glob("*.py") if path.name != "__init__.py"
    }
    assert model_modules == EXPECTED_MODEL_MODULES

    metadata = create_app().openapi()["components"]["schemas"]
    forbidden_schema_tokens = {"CanonicalTranslation", "ReviewComment", "StringConstraint"}
    assert forbidden_schema_tokens.isdisjoint(metadata)


def test_provider_integration_contains_no_dynamic_or_mutating_http_verbs() -> None:
    """Discovery remains read-only; Phase 7 owns the separately guarded write transport."""
    integration_root = BACKEND_SOURCE / "integrations" / "bitbucket"
    violations: list[str] = []
    for source_path in sorted(integration_root.glob("*.py")):
        if source_path.name == "writes.py":
            # Its exact dynamic transport and URL validation are checked by the
            # current gap-closure guard and test_bitbucket_write_urls/adapter.
            from tests.architecture.test_phase2_gap_closure import (
                _assert_guarded_provider_transports,
            )

            _assert_guarded_provider_transports()
            continue
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in {"put", "patch", "delete"}:
                violations.append(f"{source_path.name}:{node.lineno}:{node.func.attr}")
            if node.func.attr in {"request", "stream"}:
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    violations.append(f"{source_path.name}:{node.lineno}:dynamic-method")
                elif node.args[0].value != "GET":
                    violations.append(f"{source_path.name}:{node.lineno}:{node.args[0].value}")
    assert violations == []


def test_frontend_routes_expose_only_approved_admin_configuration_destinations() -> None:
    """Deferred review and write-back features have no hidden browser route."""
    router_source = (FRONTEND_SOURCE / "router.tsx").read_text()
    assert "/comments" not in router_source
    assert not any(segment in router_source for segment in FORBIDDEN_RESOURCE_SEGMENTS)
    assert 'path="/admin/*"' in router_source
    for approved in ("bitbucket", "mappings", "previews", "products", "repositories", "users"):
        assert approved in router_source
