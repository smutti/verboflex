"""Fail-closed architecture checks for the Bitbucket provider capability boundary."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import httpx
import pytest

from verboflex.core.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CLIENT_PATH = (
    REPOSITORY_ROOT / "backend" / "src" / "verboflex" / "integrations" / "bitbucket" / "client.py"
)
COVERAGE_PATH = (
    REPOSITORY_ROOT / ".planning" / "phases" / "03-bitbucket-import-integration" / "COVERAGE.md"
)

EXPECTED_INTEGRATED_CAPABILITIES = {
    "branch-create",
    "oauth-client-credentials-acquisition",
    "oauth-client-credentials-reacquisition",
    "oauth-effective-scope-inspection",
    "oauth-legacy-read-only-generation-detection",
    "repository-metadata-by-workspace-and-slug",
    "branch-listing-with-provider-pagination",
    "branch-to-commit-resolution",
    "commit-ancestry-comparison",
    "commit-diffstat-between-source-commits",
    "source-tree-directory-pagination",
    "raw-source-file-read-at-commit",
    "source-file-create-update",
    "source-commit-create",
    "source-file-reference-metadata",
    "provider-next-url-validation",
    "pull-request-create",
}
EXPECTED_OPTED_OUT_CAPABILITIES = {
    "account-profile-and-email",
    "branch-delete",
    "branch-restrictions-and-merge-checks-admin",
    "branch-update",
    "code-search",
    "commit-history-listing-and-search",
    "commit-patch-and-raw-diff-read",
    "commit-status-read-and-write",
    "deploy-keys-access-keys-and-ssh-keys-admin",
    "deployments-and-environments",
    "downloads-list-and-read",
    "downloads-upload-and-delete",
    "issues-create-update-delete-and-comments",
    "issues-list-and-read",
    "oauth-authorization-code-callback-and-refresh-token-flows",
    "oauth-provider-side-token-revocation",
    "pipelines-list-and-read",
    "pipelines-run-stop-and-manage",
    "project-listing-and-metadata",
    "pull-request-approve",
    "pull-request-comments-tasks-and-activity",
    "pull-request-decline",
    "pull-request-diff-and-diffstat",
    "pull-request-list-and-read",
    "pull-request-merge",
    "pull-request-participants-and-default-reviewers",
    "pull-request-update",
    "repository-delete",
    "repository-listing-and-search",
    "repository-settings-and-permissions-admin",
    "repository-webhook-create-update-delete",
    "repository-webhook-list-and-read",
    "snippets-read-and-write",
    "source-file-delete",
    "tag-create-update-delete",
    "tag-listing-and-other-ref-discovery",
    "wiki-read-and-write",
    "workspace-and-project-administration",
    "workspace-membership-and-permissions",
}
EXPECTED_OPERATION_VALUES = {
    "branch-create",
    "branch-listing-with-provider-pagination",
    "branch-to-commit-resolution",
    "commit-ancestry-comparison",
    "commit-diffstat-between-source-commits",
    "pull-request-create",
    "raw-source-file-read-at-commit",
    "repository-metadata-by-workspace-and-slug",
    "source-commit-create",
    "source-tree-directory-pagination",
}
ALLOWED_ADAPTER_METHODS = {
    "aclose",
    "compare_repository_ancestry",
    "list_repository_branches",
    "list_repository_diffstat",
    "list_repository_source_page",
    "read_repository_metadata",
    "read_repository_source_file",
    "resolve_repository_branch",
}
MUTATING_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _coverage_decisions() -> list[tuple[str, str]]:
    decisions: list[tuple[str, str]] = []
    for line in COVERAGE_PATH.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in {"INTEGRATE", "OPT-OUT"}:
            decisions.append((cells[0].strip("`"), cells[1]))
    return decisions


def _client_tree() -> ast.Module:
    return ast.parse(CLIENT_PATH.read_text(), filename=str(CLIENT_PATH))


def test_phase_three_coverage_accounts_for_all_56_capabilities_exactly_once() -> None:
    """The reviewed capability ledger remains the exact provider authority manifest."""
    rows = _coverage_decisions()
    decisions = dict(rows)
    assert len(rows) == len(decisions) == 56
    assert {name for name, decision in decisions.items() if decision == "INTEGRATE"} == (
        EXPECTED_INTEGRATED_CAPABILITIES
    )
    assert {name for name, decision in decisions.items() if decision == "OPT-OUT"} == (
        EXPECTED_OPTED_OUT_CAPABILITIES
    )


def test_operation_vocabulary_separates_phase_three_reads_from_phase_eight_writes() -> None:
    """Only approved reads execute now; the three future mutations remain declarations."""
    from verboflex.integrations.bitbucket.client import (
        PHASE_3_READ_OPERATIONS,
        PHASE_8_WRITE_OPERATIONS,
        BitbucketOperation,
    )

    assert {operation.value for operation in BitbucketOperation} == EXPECTED_OPERATION_VALUES
    assert {operation.value for operation in PHASE_3_READ_OPERATIONS} == {
        "branch-listing-with-provider-pagination",
        "branch-to-commit-resolution",
        "commit-ancestry-comparison",
        "commit-diffstat-between-source-commits",
        "raw-source-file-read-at-commit",
        "repository-metadata-by-workspace-and-slug",
        "source-tree-directory-pagination",
    }
    assert {operation.value for operation in PHASE_8_WRITE_OPERATIONS} == {
        "branch-create",
        "pull-request-create",
        "source-commit-create",
    }
    assert PHASE_3_READ_OPERATIONS.isdisjoint(PHASE_8_WRITE_OPERATIONS)


def test_operation_and_url_are_rejected_before_credential_acquisition() -> None:
    """No future write, unknown operation, or mismatched URL can acquire authority."""
    from verboflex.integrations.bitbucket.client import (
        PHASE_8_WRITE_OPERATIONS,
        BitbucketHttpAdapter,
        BitbucketOperation,
    )
    from verboflex.integrations.bitbucket.urls import validate_bitbucket_api_url

    class CredentialSpy:
        acquired = 0

        def acquire_repository_read_lease(self, _session: object) -> object:
            self.acquired += 1
            raise AssertionError("credentials must not be acquired")

        def require_current_repository_read_lease(
            self,
            _session: object,
            _lease: object,
        ) -> None:
            raise AssertionError("credentials must not be checked")

    requests: list[httpx.Request] = []
    credentials = CredentialSpy()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=credentials,  # type: ignore[arg-type]
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, request=request)
        ),
    )
    metadata_url = "https://api.bitbucket.org/2.0/repositories/acme/mobile"

    async def exercise() -> None:
        for operation in PHASE_8_WRITE_OPERATIONS:
            with pytest.raises(ValueError, match="Bitbucket provider operation rejected"):
                await adapter._read_bounded_bytes(
                    object(),
                    operation=operation,
                    url=metadata_url,
                    max_bytes=1,
                    expect_json=False,
                )
        with pytest.raises(ValueError, match="Bitbucket provider operation rejected"):
            await adapter._read_bounded_bytes(
                object(),
                operation="merge",  # type: ignore[arg-type]
                url=metadata_url,
                max_bytes=1,
                expect_json=False,
            )
        await adapter.aclose()

    asyncio.run(exercise())

    rejected_pairs = (
        (BitbucketOperation.BRANCH_LIST, metadata_url),
        (
            BitbucketOperation.REPOSITORY_METADATA,
            "https://api.bitbucket.org/2.0/repositories/acme/mobile#fragment",
        ),
        (
            BitbucketOperation.REPOSITORY_METADATA,
            "http://api.bitbucket.org/2.0/repositories/acme/mobile",
        ),
        (
            BitbucketOperation.REPOSITORY_METADATA,
            "https://user:password@api.bitbucket.org/2.0/repositories/acme/mobile",
        ),
    )
    for operation, url in rejected_pairs:
        with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
            validate_bitbucket_api_url(url, operation=operation)

    assert credentials.acquired == 0
    assert requests == []


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


def test_http_adapter_pool_disables_redirects_proxies_and_retries() -> None:
    """The pooled transport cannot regain ambient proxy, redirect, or retry behavior."""
    tree = _client_tree()
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    transport_call = next(
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "httpx"
        and call.func.attr == "AsyncHTTPTransport"
    )
    assert {
        keyword.arg: keyword.value.value
        for keyword in transport_call.keywords
        if isinstance(keyword.value, ast.Constant)
    } == {"retries": 0}

    client_call = next(
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "httpx"
        and call.func.attr == "AsyncClient"
    )
    client_constants = {
        keyword.arg: keyword.value.value
        for keyword in client_call.keywords
        if isinstance(keyword.value, ast.Constant)
    }
    assert client_constants["follow_redirects"] is False
    assert client_constants["trust_env"] is False


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
