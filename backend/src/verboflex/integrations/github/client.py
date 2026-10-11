"""Bounded public GitHub reads; no credentials, redirects, clones or remote writes."""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.client import (
    BitbucketAncestry,
    BitbucketBranch,
    BitbucketCommitDelta,
    BitbucketFileDelta,
    BitbucketProviderReadError,
    BitbucketSourceEntry,
    BitbucketSourcePage,
    RepositorySide,
)
from verboflex.integrations.bitbucket.urls import (
    validate_provider_commit_hash,
    validate_repository_relative_path,
)


def github_identity(owner: str, repository: str) -> tuple[str, str]:
    owner, repository = owner.strip().lower(), repository.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", owner) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_.-]{0,99}", repository
    ):
        raise ValueError("Invalid GitHub repository identity")
    return owner, repository


class GitHubHttpAdapter:
    """Implement the existing source-read contract for public GitHub repositories."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=5),
            headers={"User-Agent": "VerboFlex", "Accept-Encoding": "identity"},
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        # Immutable tree metadata only, bounded per adapter; never cache branch heads.
        self._trees: OrderedDict[tuple[str, str], dict[str, dict[str, Any]]] = OrderedDict()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _base(self, workspace: str, repository_slug: str) -> str:
        try:
            owner, repo = github_identity(workspace, repository_slug)
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        return f"https://api.github.com/repos/{owner}/{repo}"

    async def _read(self, url: str, *, max_bytes: int, api: bool = True) -> bytes:
        # URLs are constructed exclusively below; provider-supplied URLs are never followed.
        headers = (
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}
            if api
            else {}
        )
        try:
            async with self._client.stream("GET", url, headers=headers) as response:
                code = response.status_code
                if code != 200:
                    if code == 429 or (
                        code == 403 and response.headers.get("x-ratelimit-remaining") == "0"
                    ):
                        kind = "rate_limited"
                    else:
                        kind = {
                            401: "permission_denied",
                            403: "permission_denied",
                            404: "not_found",
                        }.get(code, "unavailable")
                    raise BitbucketProviderReadError(kind=kind, provider_status=code)  # type: ignore[arg-type]
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise BitbucketProviderReadError(kind="limit_exceeded")
                return bytes(content)
        except httpx.TimeoutException:
            raise BitbucketProviderReadError(kind="timeout") from None
        except httpx.HTTPError:
            raise BitbucketProviderReadError(kind="unavailable") from None

    async def _json(self, url: str, *, max_bytes: int = 1_048_576) -> Any:
        try:
            return json.loads(await self._read(url, max_bytes=max_bytes))
        except ValueError, UnicodeError:
            raise BitbucketProviderReadError(kind="invalid_source") from None

    async def read_repository_metadata(
        self, session: Session, *, workspace: str, repository_slug: str
    ) -> dict[str, Any]:
        base = self._base(workspace, repository_slug)
        data = await self._json(base)
        if (
            not isinstance(data, dict)
            or data.get("private") is not False
            or not isinstance(data.get("full_name"), str)
            or data["full_name"].lower() != "/".join(github_identity(workspace, repository_slug))
            or not isinstance(data.get("default_branch"), str)
        ):
            raise BitbucketProviderReadError(kind="invalid_source")
        return data

    def _branch(self, data: object) -> BitbucketBranch:
        try:
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("name"), str)
                or not data["name"]
                or len(data["name"]) > 255
            ):
                raise ValueError
            sha = validate_provider_commit_hash(data["commit"]["sha"])
            return BitbucketBranch(data["name"], sha)
        except ValueError, TypeError, KeyError:
            raise BitbucketProviderReadError(kind="invalid_source") from None

    async def resolve_repository_branch(
        self, session: Session, *, workspace: str, repository_slug: str, branch: str
    ) -> BitbucketBranch:
        if (
            not isinstance(branch, str)
            or not branch
            or len(branch) > 255
            or not branch.isprintable()
            or branch in {".", ".."}
        ):
            raise BitbucketProviderReadError(kind="invalid_source")
        value = self._branch(
            await self._json(
                f"{self._base(workspace, repository_slug)}/branches/{quote(branch, safe='')}"
            )
        )
        if value.name != branch:
            raise BitbucketProviderReadError(kind="invalid_source")
        return value

    async def list_repository_branches(
        self, session: Session, *, workspace: str, repository_slug: str
    ) -> tuple[BitbucketBranch, ...]:
        result: list[BitbucketBranch] = []
        for page in range(1, 11):
            data = await self._json(
                f"{self._base(workspace, repository_slug)}/branches?per_page=100&page={page}"
            )
            if not isinstance(data, list) or len(data) > 100:
                raise BitbucketProviderReadError(kind="invalid_source")
            result.extend(self._branch(item) for item in data)
            if len(data) < 100:
                if len({item.name for item in result}) != len(result):
                    raise BitbucketProviderReadError(kind="invalid_source")
                return tuple(result)
        raise BitbucketProviderReadError(kind="limit_exceeded")

    async def _tree(
        self, workspace: str, repository_slug: str, commit_hash: str
    ) -> dict[str, dict[str, Any]]:
        try:
            sha = validate_provider_commit_hash(commit_hash)
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        base = self._base(workspace, repository_slug)
        key = base, sha
        if key in self._trees:
            self._trees.move_to_end(key)
            return self._trees[key]
        data = await self._json(f"{base}/git/trees/{sha}?recursive=1", max_bytes=7_340_032)
        if (
            not isinstance(data, dict)
            or data.get("truncated") is not False
            or not isinstance(data.get("tree"), list)
            or len(data["tree"]) > 100_000
        ):
            raise BitbucketProviderReadError(kind="limit_exceeded")
        entries: dict[str, dict[str, Any]] = {}
        for item in data["tree"]:
            try:
                path = validate_repository_relative_path(item["path"])
                if path in entries:
                    raise ValueError
                if item["type"] == "blob" and item["mode"] in {"100644", "100755"}:
                    if type(item.get("size")) is not int or item["size"] < 0:
                        raise ValueError
                    validate_provider_commit_hash(item["sha"])
                    entries[path] = item
                # Symlinks/submodules are never imported or dereferenced.
            except KeyError, TypeError, ValueError:
                raise BitbucketProviderReadError(kind="invalid_source") from None
        self._trees[key] = entries
        while len(self._trees) > 4:
            self._trees.popitem(last=False)
        return entries

    async def list_repository_source_page(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        directory_path: str | None,
        next_url: str | None = None,
        max_depth: int | None = None,
    ) -> BitbucketSourcePage:
        if next_url is not None:
            raise BitbucketProviderReadError(kind="invalid_source")
        try:
            prefix = (
                validate_repository_relative_path(directory_path) + "/" if directory_path else ""
            )
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        tree = await self._tree(workspace, repository_slug, commit_hash)
        # Return the complete scoped recursive listing in one bounded page, avoiding
        # a separate API request for every locale directory.
        entries = tuple(
            BitbucketSourceEntry(path, "file", item["size"], ())
            for path, item in sorted(tree.items())
            if path.startswith(prefix)
        )
        if len(entries) > 5_000:
            raise BitbucketProviderReadError(kind="limit_exceeded")
        return BitbucketSourcePage(entries, None)

    async def read_repository_source_file(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        commit_hash: str,
        path: str,
        max_bytes: int,
    ) -> bytes:
        try:
            path = validate_repository_relative_path(path)
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        tree = await self._tree(workspace, repository_slug, commit_hash)
        entry = tree.get(path)
        if entry is None:
            raise BitbucketProviderReadError(kind="not_found")
        if entry["size"] > max_bytes:
            raise BitbucketProviderReadError(kind="limit_exceeded")
        owner, repo = github_identity(workspace, repository_slug)
        content = await self._read(
            f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_hash}/"
            f"{quote(path, safe='/')}",
            max_bytes=max_bytes,
            api=False,
        )
        digest = hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content, usedforsecurity=False
        ).hexdigest()
        if len(content) != entry["size"] or digest != entry["sha"]:
            raise BitbucketProviderReadError(kind="invalid_source")
        return content

    async def compare_repository_ancestry(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
    ) -> BitbucketAncestry:
        try:
            old = validate_provider_commit_hash(old_commit_hash)
            new = validate_provider_commit_hash(new_commit_hash)
        except ValueError:
            raise BitbucketProviderReadError(kind="invalid_source") from None
        if old == new:
            return BitbucketAncestry(old, new, "equal", True)
        data = await self._json(
            f"{self._base(workspace, repository_slug)}/compare/{old}...{new}?per_page=1"
        )
        if not isinstance(data, dict) or data.get("status") not in {"ahead", "behind", "diverged"}:
            raise BitbucketProviderReadError(kind="invalid_source")
        if data["status"] == "ahead":
            if data.get("merge_base_commit", {}).get("sha") != old:
                raise BitbucketProviderReadError(kind="invalid_source")
            return BitbucketAncestry(old, new, "descendant", True)
        return BitbucketAncestry(old, new, "diverged", True)

    async def list_repository_diffstat(
        self,
        session: Session,
        *,
        workspace: str,
        repository_slug: str,
        old_commit_hash: str,
        new_commit_hash: str,
        repository_side: RepositorySide,
    ) -> BitbucketCommitDelta:
        old = await self._tree(workspace, repository_slug, old_commit_hash)
        new = await self._tree(workspace, repository_slug, new_commit_hash)
        files: list[BitbucketFileDelta] = []
        for path in sorted(old.keys() | new.keys()):
            if path not in new:
                change = "removed"
            elif path not in old:
                change = "added"
            elif old[path]["sha"] != new[path]["sha"]:
                change = "modified"
            else:
                continue
            files.append(BitbucketFileDelta(repository_side, len(files), change, path))  # type: ignore[arg-type]
            if len(files) > 5_000:
                raise BitbucketProviderReadError(kind="limit_exceeded")
        return BitbucketCommitDelta(old_commit_hash, new_commit_hash, tuple(files), True)
