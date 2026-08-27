"""Fail-closed architecture checks for the Bitbucket provider capability boundary."""

from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CLIENT_PATH = (
    REPOSITORY_ROOT / "backend" / "src" / "verboflex" / "integrations" / "bitbucket" / "client.py"
)
COVERAGE_PATH = REPOSITORY_ROOT / ".planning" / "phases" / "02-admin-configuration" / "COVERAGE.md"

EXPECTED_INTEGRATED_CAPABILITIES = {
    "oauth-authorization-code-start",
    "oauth-authorization-code-exchange",
    "oauth-refresh-token-exchange-and-rotation",
    "oauth-effective-scope-inspection",
    "repository-metadata-by-workspace-and-slug",
    "branch-listing-with-provider-pagination",
    "branch-to-commit-resolution",
    "source-tree-directory-pagination",
    "raw-source-file-read-at-commit",
    "provider-next-url-validation",
}
ALLOWED_ADAPTER_METHODS = {"read_repository_metadata", "aclose"}
MUTATING_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _coverage_decisions() -> dict[str, str]:
    decisions: dict[str, str] = {}
    for line in COVERAGE_PATH.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in {"INTEGRATE", "OPT-OUT"}:
            decisions[cells[0].strip("`")] = cells[1]
    return decisions


def _client_tree() -> ast.Module:
    return ast.parse(CLIENT_PATH.read_text(), filename=str(CLIENT_PATH))


def test_coverage_integrates_only_the_ten_approved_provider_capabilities() -> None:
    """The reviewed capability ledger remains the exact provider authority manifest."""
    decisions = _coverage_decisions()
    assert {name for name, decision in decisions.items() if decision == "INTEGRATE"} == (
        EXPECTED_INTEGRATED_CAPABILITIES
    )
    assert {name for name, decision in decisions.items() if decision == "OPT-OUT"}


def test_http_adapter_exports_only_current_read_capabilities_and_get_transport() -> None:
    """No public adapter method or dynamic verb can grow a provider mutation surface."""
    tree = _client_tree()
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BitbucketHttpAdapter"
    )
    public_methods = {
        node.name
        for node in adapter.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_methods == ALLOWED_ADAPTER_METHODS

    stream_calls = [
        node
        for node in ast.walk(adapter)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "stream"
    ]
    assert stream_calls
    assert all(
        call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "GET"
        for call in stream_calls
    )
    assert not {
        node.value
        for node in ast.walk(adapter)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in MUTATING_HTTP_METHODS
    }


def test_http_adapter_has_no_excluded_provider_operation_names() -> None:
    """Provider opt-outs cannot appear as callable public adapter operations."""
    tree = _client_tree()
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BitbucketHttpAdapter"
    )
    public_method_tokens = {
        token
        for node in adapter.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
        for token in node.name.split("_")
    }
    excluded_operation_tokens = {
        "account",
        "admin",
        "branch-create",
        "delete",
        "deployment",
        "diff",
        "download",
        "email",
        "hook",
        "issue",
        "merge",
        "permission",
        "pipeline",
        "profile",
        "project",
        "pullrequest",
        "search",
        "snippet",
        "tag",
        "update",
        "webhook",
        "wiki",
        "write",
    }
    assert public_method_tokens.isdisjoint(excluded_operation_tokens)
