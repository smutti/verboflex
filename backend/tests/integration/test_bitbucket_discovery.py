"""Provider-bound contracts for live Bitbucket repository discovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import (
    BitbucketHttpAdapter,
    BitbucketProviderReadError,
)
from verboflex.services.repositories import RepositoryRecord

ACCESS_TOKEN = "discovery-provider-token"


@dataclass
class FakeCredentialLeaseAuthority:
    """Expose one observable current generation without external credentials."""

    generation: int = 7
    acquired: int = 0
    validated: list[int] = field(default_factory=list)

    def acquire_repository_read_lease(self, _session: object) -> Any:
        from verboflex.integrations.bitbucket.client import BitbucketCredentialLease

        self.acquired += 1
        return BitbucketCredentialLease(generation=self.generation, access_token=ACCESS_TOKEN)

    def require_current_repository_read_lease(self, _session: object, lease: Any) -> None:
        self.validated.append(lease.generation)
        if lease.generation != self.generation:
            from verboflex.services.bitbucket_oauth import OAuthGenerationRejected

            raise OAuthGenerationRejected("stale provider generation")


def test_lists_exact_branches_with_validated_opaque_pagination() -> None:
    """Provider order and spelling survive pagelen=100 traversal without URL leakage."""
    requests: list[httpx.Request] = []
    second_page = (
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches"
        "?pagelen=100&after=opaque-provider-position"
    )

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("after") is None:
            payload = {
                "values": [
                    {"name": "Main", "target": {"hash": "a" * 40}},
                    {"name": "feature/ExactCase", "target": {"hash": "b" * 40}},
                ],
                "next": second_page,
            }
        else:
            payload = {
                "values": [
                    {"name": "release-Ä", "target": {"hash": "c" * 40}},
                ]
            }
        return httpx.Response(
            200,
            json=payload,
            headers={"x-oauth-scopes": "repository"},
            request=request,
        )

    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        branches = await adapter.list_repository_branches(
            object(),
            workspace="acme",
            repository_slug="mobile",
        )
        assert [branch.name for branch in branches] == [
            "Main",
            "feature/ExactCase",
            "release-Ä",
        ]
        assert [branch.commit_hash for branch in branches] == ["a" * 40, "b" * 40, "c" * 40]
        assert [str(request.url) for request in requests] == [
            "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches?pagelen=100",
            second_page,
        ]
        assert all(request.url.host == "api.bitbucket.org" for request in requests)

        requests_before_rejection = len(requests)

        def hostile_provider(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "values": [{"name": "main", "target": {"hash": "d" * 40}}],
                    "next": "https://attacker.example/steal-provider-token",
                },
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )

        hostile = BitbucketHttpAdapter(
            settings=Settings(),
            credential_leases=authority,
            transport=httpx.MockTransport(hostile_provider),
        )
        with pytest.raises(BitbucketProviderReadError) as captured:
            await hostile.list_repository_branches(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert str(captured.value) == "Bitbucket provider read failed"
        assert "attacker" not in repr(captured.value).lower()
        assert len(requests) == requests_before_rejection + 1
        await hostile.aclose()
        await adapter.aclose()

    asyncio.run(exercise())


def _repository() -> RepositoryRecord:
    return RepositoryRecord(
        id=uuid4(),
        workspace="acme",
        repository_slug="mobile",
        descriptive_name="Mobile",
    )


def test_resolves_commit_then_streams_exact_bounded_source_candidates() -> None:
    """Branch resolution precedes tree/raw reads and successful output contains no provider URL."""
    try:
        from verboflex.services.repository_discovery import (
            SOURCE_DISCOVERY_BUDGET,
            discover_repository_sources_for_record,
        )
    except ImportError:
        pytest.fail("commit-bound source discovery is not implemented", pytrace=False)

    commit_hash = "d" * 40
    requests: list[httpx.Request] = []
    root_next = (
        f"https://api.bitbucket.org/2.0/repositories/acme/mobile/src/{commit_hash}/"
        "?pagelen=100&after=opaque-tree-position"
    )
    raw_bodies = {
        "Root.strings": b'"hello" = "Hello";\n',
        "locales/en.json": b'{"hello":"Hello"}\n',
    }

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if "/refs/branches/" in path:
            payload = {"name": "Main", "target": {"hash": commit_hash}}
            return httpx.Response(
                200,
                json=payload,
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        if path.endswith(f"/src/{commit_hash}/") and request.url.params.get("after") is None:
            payload = {
                "values": [
                    {"path": "locales", "type": "commit_directory"},
                    {"path": "Root.strings", "type": "commit_file", "size": 20},
                ],
                "next": root_next,
            }
            return httpx.Response(
                200,
                json=payload,
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        if request.url.params.get("after") is not None:
            payload = {
                "values": [
                    {"path": "README.md", "type": "commit_file", "size": 7},
                ]
            }
            return httpx.Response(
                200,
                json=payload,
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        if path.endswith(f"/src/{commit_hash}/locales") and request.url.params:
            payload = {
                "values": [
                    {"path": "locales/en.json", "type": "commit_file", "size": 18},
                ]
            }
            return httpx.Response(
                200,
                json=payload,
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        relative_path = path.split(f"/src/{commit_hash}/", 1)[1]
        return httpx.Response(
            200,
            content=raw_bodies[relative_path],
            headers={
                "content-encoding": "identity",
                "x-oauth-scopes": "repository",
            },
            request=request,
        )

    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        snapshot = await discover_repository_sources_for_record(
            object(),
            repository=_repository(),
            branch="Main",
            adapter=adapter,
        )
        assert snapshot.commit_hash == commit_hash
        assert [(item.path, item.content) for item in snapshot.files] == [
            ("Root.strings", raw_bodies["Root.strings"]),
            ("locales/en.json", raw_bodies["locales/en.json"]),
        ]
        assert snapshot.total_bytes == sum(map(len, raw_bodies.values()))
        assert SOURCE_DISCOVERY_BUDGET.max_pages == 50
        assert SOURCE_DISCOVERY_BUDGET.max_entries == 5_000
        assert SOURCE_DISCOVERY_BUDGET.max_depth == 12
        assert SOURCE_DISCOVERY_BUDGET.max_candidate_files == 500
        assert SOURCE_DISCOVERY_BUDGET.max_file_bytes == 1_048_576
        assert SOURCE_DISCOVERY_BUDGET.max_total_bytes == 20_971_520

        urls = [str(request.url) for request in requests]
        branch_index = next(index for index, url in enumerate(urls) if "/refs/branches/" in url)
        tree_indexes = [
            index
            for index, url in enumerate(urls)
            if f"/src/{commit_hash}" in url and request_is_tree(url)
        ]
        raw_indexes = [
            index
            for index, url in enumerate(urls)
            if f"/src/{commit_hash}" in url and not request_is_tree(url)
        ]
        assert branch_index == 0
        assert tree_indexes and raw_indexes and max(tree_indexes) < min(raw_indexes)
        assert all("attacker" not in url for url in urls)
        assert authority.validated == [authority.generation] * (len(requests) * 2)
        await adapter.aclose()

    def request_is_tree(url: str) -> bool:
        return "pagelen=100" in url

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("mode", "expected_kind"),
    [
        ("path_traversal", "invalid_source"),
        ("invalid_next", "invalid_source"),
        ("redirect", "invalid_source"),
        ("compressed", "invalid_source"),
        ("oversized", "limit_exceeded"),
        ("revoked", "reauthorization_required"),
    ],
)
def test_hostile_source_reads_fail_closed_without_returning_provider_bytes(
    mode: str,
    expected_kind: str,
) -> None:
    """Traversal, SSRF, redirects, decoding, size and generation races return bounded states."""
    try:
        from verboflex.services.repository_discovery import (
            discover_repository_sources_for_record,
        )
    except ImportError:
        pytest.fail("commit-bound source discovery is not implemented", pytrace=False)

    commit_hash = "e" * 40
    marker = b"raw-provider-body-must-not-leak"
    requests: list[httpx.Request] = []
    authority = FakeCredentialLeaseAuthority()

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if "/refs/branches/" in path:
            return httpx.Response(
                200,
                json={"name": "main", "target": {"hash": commit_hash}},
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        if request.url.params.get("pagelen") == "100":
            entry_path = "../secret.json" if mode == "path_traversal" else "locale.json"
            payload: dict[str, object] = {
                "values": [{"path": entry_path, "type": "commit_file", "size": len(marker)}]
            }
            if mode == "invalid_next":
                payload["next"] = "https://attacker.example/steal"
            return httpx.Response(
                200,
                json=payload,
                headers={"x-oauth-scopes": "repository"},
                request=request,
            )
        if mode == "revoked":
            authority.generation += 1
        if mode == "redirect":
            return httpx.Response(
                302,
                headers={"location": "https://api.bitbucket.org/2.0/repositories/acme/mobile"},
                request=request,
            )
        headers = {"x-oauth-scopes": "repository"}
        if mode == "compressed":
            headers["content-encoding"] = "gzip"
        content = b"x" * (1_048_576 + 1) if mode == "oversized" else marker
        return httpx.Response(200, content=content, headers=headers, request=request)

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await discover_repository_sources_for_record(
                object(),
                repository=_repository(),
                branch="main",
                adapter=adapter,
            )
        assert captured.value.kind == expected_kind
        diagnostic = f"{captured.value!r} {captured.value}".encode()
        assert marker not in diagnostic
        assert b"attacker" not in diagnostic.lower()
        assert all(request.url.host == "api.bitbucket.org" for request in requests)
        if mode in {"path_traversal", "invalid_next"}:
            assert not any(request.url.path.endswith("locale.json") for request in requests)
        await adapter.aclose()

    asyncio.run(exercise())


def test_every_source_traversal_budget_blocks_instead_of_truncating() -> None:
    """Exact page, entry, depth, candidate, single-file and aggregate limits are closed."""
    try:
        from verboflex.integrations.bitbucket.client import (
            BitbucketBranch,
            BitbucketSourceEntry,
            BitbucketSourcePage,
        )
        from verboflex.services.repository_discovery import (
            discover_repository_sources_for_record,
        )
    except ImportError:
        pytest.fail("commit-bound source discovery is not implemented", pytrace=False)

    commit_hash = "f" * 40

    @dataclass
    class BoundaryAdapter:
        scenario: str
        page_calls: int = 0
        raw_calls: int = 0

        async def resolve_repository_branch(self, *_args: Any, **_kwargs: Any) -> Any:
            return BitbucketBranch(name="main", commit_hash=commit_hash)

        async def list_repository_source_page(self, *_args: Any, **kwargs: Any) -> Any:
            self.page_calls += 1
            if self.scenario == "pages":
                next_url = (
                    "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
                    f"{commit_hash}/?pagelen=100&after={self.page_calls}"
                )
                return BitbucketSourcePage(entries=(), next_url=next_url)
            if self.scenario == "entries":
                base = (self.page_calls - 1) * 100
                count = 101 if self.page_calls == 50 else 100
                entries = tuple(
                    BitbucketSourceEntry(path=f"docs/{base + index}.txt", kind="file", size=0)
                    for index in range(count)
                )
                next_url = (
                    "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
                    f"{commit_hash}/?pagelen=100&after={self.page_calls}"
                    if self.page_calls < 50
                    else None
                )
                return BitbucketSourcePage(entries=entries, next_url=next_url)
            if self.scenario == "depth":
                return BitbucketSourcePage(
                    entries=(
                        BitbucketSourceEntry(
                            path="/".join(["nested"] * 13) + "/messages.json",
                            kind="file",
                            size=2,
                        ),
                    ),
                    next_url=None,
                )
            if self.scenario == "candidates":
                return BitbucketSourcePage(
                    entries=tuple(
                        BitbucketSourceEntry(path=f"l/{index}.json", kind="file", size=0)
                        for index in range(501)
                    ),
                    next_url=None,
                )
            if self.scenario == "file":
                return BitbucketSourcePage(
                    entries=(
                        BitbucketSourceEntry(
                            path="oversized.json",
                            kind="file",
                            size=1_048_577,
                        ),
                    ),
                    next_url=None,
                )
            return BitbucketSourcePage(
                entries=tuple(
                    BitbucketSourceEntry(path=f"l/{index}.json", kind="file", size=0)
                    for index in range(21)
                ),
                next_url=None,
            )

        async def read_repository_source_file(self, *_args: Any, **kwargs: Any) -> bytes:
            self.raw_calls += 1
            content = b"x" * 1_048_576
            if len(content) > kwargs["max_bytes"]:
                raise BitbucketProviderReadError(kind="limit_exceeded")
            return content

    async def exercise(scenario: str) -> BoundaryAdapter:
        adapter = BoundaryAdapter(scenario=scenario)
        with pytest.raises(BitbucketProviderReadError) as captured:
            await discover_repository_sources_for_record(
                object(),
                repository=_repository(),
                branch="main",
                adapter=adapter,
            )
        assert captured.value.kind == "limit_exceeded"
        return adapter

    page_adapter = asyncio.run(exercise("pages"))
    assert page_adapter.page_calls == 50
    entry_adapter = asyncio.run(exercise("entries"))
    assert entry_adapter.page_calls == 50
    for scenario in ("depth", "candidates", "file"):
        adapter = asyncio.run(exercise(scenario))
        assert adapter.raw_calls == 0
    total_adapter = asyncio.run(exercise("total"))
    assert total_adapter.raw_calls == 20


@given(
    st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=12),
        min_size=1,
        max_size=12,
    )
)
def test_repository_relative_path_normalization_is_idempotent(parts: list[str]) -> None:
    """Safe repository paths round-trip while traversal spellings are always rejected."""
    try:
        from verboflex.services.repository_discovery import (
            normalize_repository_relative_path,
        )
    except ImportError:
        pytest.fail("repository path normalization is not implemented", pytrace=False)

    safe_path = "/".join(parts)
    assert normalize_repository_relative_path(safe_path) == safe_path
    assert (
        normalize_repository_relative_path(normalize_repository_relative_path(safe_path))
        == safe_path
    )
    for hostile in ("../secret.json", "/absolute.json", "a/../../b.json", r"a\..\b.json"):
        with pytest.raises(BitbucketProviderReadError) as captured:
            normalize_repository_relative_path(hostile)
        assert captured.value.kind == "invalid_source"
