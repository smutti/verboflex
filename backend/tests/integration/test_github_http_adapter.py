"""Real HTTP contract boundaries for public GitHub source reads."""

import asyncio
import hashlib

import httpx
import pytest

from verboflex.integrations.bitbucket.client import BitbucketProviderReadError
from verboflex.integrations.github.client import GitHubHttpAdapter, github_identity

COMMIT = "a" * 40
NEXT = "b" * 40
CONTENT = b'{"hello":"Hello"}'
BLOB = hashlib.sha1(b"blob " + str(len(CONTENT)).encode() + b"\0" + CONTENT).hexdigest()


def tree_entry(path="locales/en.json", **overrides):
    return {
        "path": path,
        "type": "blob",
        "mode": "100644",
        "sha": BLOB,
        "size": len(CONTENT),
        **overrides,
    }


def test_scoped_tree_and_content_are_pinned_and_integrity_checked():
    requests = []

    def handler(request):
        requests.append(request)
        assert "authorization" not in request.headers
        assert request.method == "GET"
        if request.url.host == "raw.githubusercontent.com":
            assert f"/{COMMIT}/locales/en.json" in request.url.path
            return httpx.Response(200, content=CONTENT)
        assert f"/git/trees/{COMMIT}" in request.url.path
        return httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    tree_entry(),
                    tree_entry("elsewhere/en.json"),
                    tree_entry("locales/link.json", mode="120000"),
                ],
            },
        )

    async def run():
        adapter = GitHubHttpAdapter(transport=httpx.MockTransport(handler))
        page = await adapter.list_repository_source_page(
            None,
            workspace="Owner",
            repository_slug="repo.name",
            commit_hash=COMMIT,
            directory_path="locales",
        )
        assert [entry.path for entry in page.entries] == ["locales/en.json"]
        assert page.next_url is None
        content = await adapter.read_repository_source_file(
            None,
            workspace="owner",
            repository_slug="repo.name",
            commit_hash=COMMIT,
            path="locales/en.json",
            max_bytes=100,
        )
        assert content == CONTENT
        assert len(requests) == 2  # Scoped listing and file read share immutable tree metadata.
        with pytest.raises(BitbucketProviderReadError):
            await adapter.read_repository_source_file(
                None,
                workspace="owner",
                repository_slug="repo.name",
                commit_hash=COMMIT,
                path="locales/link.json",
                max_bytes=100,
            )
        await adapter.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "identity",
    [
        ("evil/owner", "repo"),
        ("owner", "../repo"),
        ("owner", "repo?secret"),
        ("https://evil.test", "repo"),
    ],
)
def test_identity_cannot_inject_provider_urls(identity):
    with pytest.raises(ValueError):
        github_identity(*identity)


@pytest.mark.parametrize(
    "metadata",
    [
        {"private": True, "full_name": "owner/repo", "default_branch": "main"},
        {"private": False, "full_name": "other/repo", "default_branch": "main"},
        {"full_name": "owner/repo", "default_branch": "main"},
    ],
)
def test_private_or_wrong_repository_is_not_registered(metadata):
    async def run():
        adapter = GitHubHttpAdapter(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=metadata))
        )
        with pytest.raises(BitbucketProviderReadError):
            await adapter.read_repository_metadata(None, workspace="owner", repository_slug="repo")
        await adapter.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "response,kind",
    [
        (httpx.Response(302, headers={"location": "https://evil.test"}), "unavailable"),
        (httpx.Response(403, headers={"x-ratelimit-remaining": "0"}), "rate_limited"),
        (httpx.Response(404), "not_found"),
        (httpx.Response(200, content=b"not-json"), "invalid_source"),
    ],
)
def test_provider_failures_are_bounded_and_redirects_are_not_followed(response, kind):
    requests = []

    def handler(request):
        requests.append(request)
        return response

    async def run():
        adapter = GitHubHttpAdapter(transport=httpx.MockTransport(handler))
        with pytest.raises(BitbucketProviderReadError) as failure:
            await adapter.read_repository_metadata(None, workspace="owner", repository_slug="repo")
        assert failure.value.kind == kind
        assert len(requests) == 1
        await adapter.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "tree",
    [
        {"truncated": True, "tree": []},
        {"truncated": False, "tree": [tree_entry("../escape.json")]},
        {"truncated": False, "tree": [tree_entry(), tree_entry()]},
    ],
)
def test_truncated_or_malformed_tree_cannot_activate_partial_baseline(tree):
    async def run():
        adapter = GitHubHttpAdapter(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=tree))
        )
        with pytest.raises(BitbucketProviderReadError):
            await adapter.list_repository_source_page(
                None,
                workspace="owner",
                repository_slug="repo",
                commit_hash=COMMIT,
                directory_path=None,
            )
        await adapter.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("content", [b"wrong", b"x" * 101])
def test_wrong_or_oversize_blob_is_rejected(content):
    def handler(request):
        return (
            httpx.Response(200, content=content)
            if request.url.host == "raw.githubusercontent.com"
            else httpx.Response(200, json={"truncated": False, "tree": [tree_entry()]})
        )

    async def run():
        adapter = GitHubHttpAdapter(transport=httpx.MockTransport(handler))
        with pytest.raises(BitbucketProviderReadError):
            await adapter.read_repository_source_file(
                None,
                workspace="owner",
                repository_slug="repo",
                commit_hash=COMMIT,
                path="locales/en.json",
                max_bytes=100,
            )
        await adapter.aclose()

    asyncio.run(run())


def test_exact_branch_with_slash_and_refresh_compare():
    def handler(request):
        if "/branches/" in request.url.path:
            assert "feature%2Ftranslations" in str(request.url)
            return httpx.Response(
                200, json={"name": "feature/translations", "commit": {"sha": COMMIT}}
            )
        return httpx.Response(200, json={"status": "ahead", "merge_base_commit": {"sha": COMMIT}})

    async def run():
        adapter = GitHubHttpAdapter(transport=httpx.MockTransport(handler))
        branch = await adapter.resolve_repository_branch(
            None, workspace="owner", repository_slug="repo", branch="feature/translations"
        )
        assert branch.commit_hash == COMMIT
        comparison = await adapter.compare_repository_ancestry(
            None,
            workspace="owner",
            repository_slug="repo",
            old_commit_hash=COMMIT,
            new_commit_hash=NEXT,
        )
        assert comparison.relation == "descendant" and comparison.complete
        await adapter.aclose()

    asyncio.run(run())


def test_divergence_uses_complete_tree_delta_without_inferred_rename():
    def handler(request):
        if "/compare/" in request.url.path:
            return httpx.Response(200, json={"status": "diverged"})
        path = "old/en.json" if COMMIT in request.url.path else "new/en.json"
        return httpx.Response(200, json={"truncated": False, "tree": [tree_entry(path)]})

    async def run():
        adapter = GitHubHttpAdapter(transport=httpx.MockTransport(handler))
        comparison = await adapter.compare_repository_ancestry(
            None,
            workspace="owner",
            repository_slug="repo",
            old_commit_hash=COMMIT,
            new_commit_hash=NEXT,
        )
        assert comparison.relation == "diverged"
        delta = await adapter.list_repository_diffstat(
            None,
            workspace="owner",
            repository_slug="repo",
            old_commit_hash=COMMIT,
            new_commit_hash=NEXT,
            repository_side="direct",
        )
        assert [(item.change, item.path) for item in delta.files] == [
            ("added", "new/en.json"),
            ("removed", "old/en.json"),
        ]
        assert delta.complete
        await adapter.aclose()

    asyncio.run(run())
