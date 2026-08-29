#!/usr/bin/env python3
"""Disposable, bounded, read-only Bitbucket Cloud smoke for Phase 2."""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import json
import os
import re
import stat
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, NoReturn, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener

import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
if str(BACKEND_SOURCE) not in sys.path:
    sys.path.insert(0, str(BACKEND_SOURCE))

from verboflex.core.config import Settings  # noqa: E402
from verboflex.integrations.bitbucket.client import (  # noqa: E402
    BitbucketCredentialLease,
    BitbucketHttpAdapter,
    BitbucketProviderReadError,
    BitbucketSourceEntry,
)
from verboflex.integrations.bitbucket.urls import (  # noqa: E402
    repository_branch_url,
    repository_metadata_url,
    validate_bitbucket_api_url,
)
from verboflex.services.bitbucket_oauth import (  # noqa: E402
    OAuthConnectionUnavailable,
    OAuthGenerationRejected,
)

EXACT_CONSUMER_AUTHORIZATION = "consumer verified"
EXACT_CALLBACK_URL = "http://localhost:8000/api/v1/admin/bitbucket/oauth/callback"
EXACT_SCOPE = "repository"
TOKEN_URL = "https://bitbucket.org/site/oauth2/access_token"
MAX_ENV_BYTES = 65_536
MAX_TOKEN_RESPONSE_BYTES = 65_536
MAX_TOKEN_CHARACTERS = 8_192
MAX_PROVIDER_PAGES = 50
MAX_PROVIDER_ENTRIES = 5_000
MAX_SOURCE_DEPTH = 12
MAX_RAW_FILE_BYTES = 1_048_576
TOKEN_TIMEOUT_SECONDS = 10
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
_REQUIRED_KEYS = (
    "VERBOFLEX_CONSUMER_VERIFIED",
    "BITBUCKET_CLIENT_ID",
    "BITBUCKET_CLIENT_SECRET",
    "BITBUCKET_CALLBACK_URL",
    "BITBUCKET_WORKSPACE",
    "BITBUCKET_REPOSITORY_SLUG",
    "BITBUCKET_BRANCH",
)


class LiveSmokeRejected(RuntimeError):
    """Reject a live run with one stable message that contains no provider data."""


class _RejectRedirects(HTTPRedirectHandler):
    """Keep the client credential on the exact token endpoint."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: IO[bytes],
        code: int,
        message: str,
        headers: HTTPMessage,
        new_url: str,
    ) -> Request | None:
        return None


def _reject() -> NoReturn:
    raise LiveSmokeRejected("live provider smoke rejected")


def _parse_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        _reject()
    if value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except SyntaxError, ValueError:
            _reject()
        if not isinstance(parsed, str) or not parsed:
            _reject()
        return parsed
    if any(character.isspace() for character in value) or "#" in value:
        _reject()
    return value


def _read_secure_dotenv(path: Path) -> dict[str, str]:
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.getuid()
            or metadata.st_size > MAX_ENV_BYTES
        ):
            _reject()
        text = path.read_text(encoding="utf-8")
    except OSError, UnicodeError:
        _reject()
    if "\x00" in text:
        _reject()
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            _reject()
        name, raw_value = line.split("=", 1)
        if _ENV_NAME.fullmatch(name) is None or name in values:
            _reject()
        values[name] = _parse_dotenv_value(raw_value)
    return values


@dataclass(frozen=True, slots=True)
class LiveSmokeConfig:
    """Exact authorization and one disposable repository target."""

    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    callback_url: str
    workspace: str
    repository_slug: str
    branch: str

    @classmethod
    def from_dotenv(cls, path: Path) -> LiveSmokeConfig:
        values = _read_secure_dotenv(path)
        if any(not values.get(name) for name in _REQUIRED_KEYS):
            _reject()
        if values["VERBOFLEX_CONSUMER_VERIFIED"] != EXACT_CONSUMER_AUTHORIZATION:
            _reject()
        if values["BITBUCKET_CALLBACK_URL"] != EXACT_CALLBACK_URL:
            _reject()
        workspace = values["BITBUCKET_WORKSPACE"]
        repository_slug = values["BITBUCKET_REPOSITORY_SLUG"]
        branch = values["BITBUCKET_BRANCH"]
        try:
            repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
            repository_branch_url(
                workspace=workspace,
                repository_slug=repository_slug,
                branch=branch,
            )
        except ValueError:
            _reject()
        return cls(
            client_id=values["BITBUCKET_CLIENT_ID"],
            client_secret=values["BITBUCKET_CLIENT_SECRET"],
            callback_url=values["BITBUCKET_CALLBACK_URL"],
            workspace=workspace,
            repository_slug=repository_slug,
            branch=branch,
        )


@dataclass(slots=True)
class ProviderReadAudit:
    """Count only request methods; retain no URL, header, or response body."""

    get_requests: int = 0
    mutation_attempts: int = 0


class ReadOnlyAuditTransport(httpx.AsyncBaseTransport):
    """Fail before delegation unless one validated Bitbucket REST GET is requested."""

    def __init__(
        self,
        *,
        inner: httpx.AsyncBaseTransport,
        audit: ProviderReadAudit,
    ) -> None:
        self._inner = inner
        self._audit = audit

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            self._audit.mutation_attempts += 1
            _reject()
        try:
            validate_bitbucket_api_url(str(request.url))
        except ValueError:
            _reject()
        self._audit.get_requests += 1
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


@dataclass(slots=True)
class LiveCredentialAuthority:
    """One memory-only provider credential generation for a disposable smoke."""

    access_token: str = field(repr=False)
    generation: int = 1
    is_revoked: bool = False

    def acquire_repository_read_lease(self, _session: object) -> BitbucketCredentialLease:
        if self.is_revoked or not self.access_token:
            raise OAuthConnectionUnavailable("connection unavailable")
        return BitbucketCredentialLease(
            generation=self.generation,
            access_token=self.access_token,
        )

    def require_current_repository_read_lease(
        self,
        _session: object,
        lease: BitbucketCredentialLease,
    ) -> None:
        if self.is_revoked or not self.access_token or lease.generation != self.generation:
            raise OAuthGenerationRejected("generation rejected")

    def revoke_local(self) -> None:
        self.generation += 1
        self.access_token = ""
        self.is_revoked = True


@dataclass(frozen=True, slots=True)
class LiveSmokeResult:
    """Non-secret measurements permitted by the Phase 2 checkpoint."""

    repository_identity_digest: str
    commit_identity_digest: str
    branch_count: int
    tree_page_count: int
    tree_entry_count: int
    raw_byte_count: int
    raw_content_digest: str
    provider_get_count: int
    duration_milliseconds: int

    def render(self) -> str:
        return (
            "phase2 live provider read-only smoke: PASS\n"
            f"repository_identity_digest={self.repository_identity_digest}\n"
            f"commit_identity_digest={self.commit_identity_digest}\n"
            f"branches={self.branch_count} tree_pages={self.tree_page_count} "
            f"tree_entries={self.tree_entry_count} raw_bytes={self.raw_byte_count}\n"
            f"raw_content_digest={self.raw_content_digest}\n"
            f"provider_gets={self.provider_get_count} provider_writes=0 "
            "oauth_token_exchanges=1 local_generation_revoke=PASS\n"
            f"duration_ms={self.duration_milliseconds}"
        )


def _exchange_client_credentials(
    config: LiveSmokeConfig,
    *,
    opener: OpenerDirector | None = None,
) -> str:
    credentials = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode()).decode(
        "ascii"
    )
    request = Request(
        TOKEN_URL,
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with (opener or build_opener(_RejectRedirects())).open(
            request,
            timeout=TOKEN_TIMEOUT_SECONDS,
        ) as response:
            payload = response.read(MAX_TOKEN_RESPONSE_BYTES + 1)
    except HTTPError, URLError, OSError, TimeoutError:
        _reject()
    if len(payload) > MAX_TOKEN_RESPONSE_BYTES:
        _reject()
    try:
        decoded = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        _reject()
    if not isinstance(decoded, dict):
        _reject()
    token = decoded.get("access_token")
    token_type = decoded.get("token_type")
    if (
        not isinstance(token, str)
        or not token
        or len(token) > MAX_TOKEN_CHARACTERS
        or not isinstance(token_type, str)
        or token_type.casefold() != "bearer"
        or decoded.get("scope") != EXACT_SCOPE
    ):
        _reject()
    return token


def _record_entry(
    entry: BitbucketSourceEntry,
    *,
    seen_paths: set[str],
) -> tuple[str | None, tuple[str, int] | None]:
    if entry.path in seen_paths or len(entry.path.split("/")) > MAX_SOURCE_DEPTH:
        _reject()
    seen_paths.add(entry.path)
    if entry.kind == "directory":
        return entry.path, None
    if entry.size is None or entry.size > MAX_RAW_FILE_BYTES:
        return None, None
    return None, (entry.path, entry.size)


async def _run_live_reads(
    config: LiveSmokeConfig,
    *,
    authority: LiveCredentialAuthority,
    audit: ProviderReadAudit,
) -> LiveSmokeResult:
    started = time.monotonic()
    transport = ReadOnlyAuditTransport(
        inner=httpx.AsyncHTTPTransport(retries=0),
        audit=audit,
    )
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=transport,
    )
    session = cast(object, None)
    try:
        metadata = await adapter.read_repository_metadata(
            session,
            workspace=config.workspace,
            repository_slug=config.repository_slug,
        )
        repository_uuid = metadata.get("uuid")
        if not isinstance(repository_uuid, str) or not repository_uuid:
            _reject()

        branches = await adapter.list_repository_branches(
            session,
            workspace=config.workspace,
            repository_slug=config.repository_slug,
        )
        if not branches or len(branches) > MAX_PROVIDER_ENTRIES:
            _reject()
        resolved = await adapter.resolve_repository_branch(
            session,
            workspace=config.workspace,
            repository_slug=config.repository_slug,
            branch=config.branch,
        )

        directories: deque[str | None] = deque([None])
        seen_paths: set[str] = set()
        tree_page_count = 0
        selected_file: tuple[str, int] | None = None
        while directories and selected_file is None:
            directory_path = directories.popleft()
            next_url: str | None = None
            visited_pages: set[str] = set()
            while selected_file is None:
                if tree_page_count >= MAX_PROVIDER_PAGES:
                    _reject()
                page = await adapter.list_repository_source_page(
                    session,
                    workspace=config.workspace,
                    repository_slug=config.repository_slug,
                    commit_hash=resolved.commit_hash,
                    directory_path=directory_path,
                    next_url=next_url,
                )
                tree_page_count += 1
                for entry in page.entries:
                    if len(seen_paths) >= MAX_PROVIDER_ENTRIES:
                        _reject()
                    directory, candidate = _record_entry(entry, seen_paths=seen_paths)
                    if directory is not None:
                        directories.append(directory)
                    if selected_file is None and candidate is not None:
                        selected_file = candidate
                if selected_file is not None or page.next_url is None:
                    break
                if page.next_url in visited_pages:
                    _reject()
                visited_pages.add(page.next_url)
                next_url = page.next_url
        if selected_file is None:
            _reject()
        selected_path, declared_size = selected_file
        raw_content = await adapter.read_repository_source_file(
            session,
            workspace=config.workspace,
            repository_slug=config.repository_slug,
            commit_hash=resolved.commit_hash,
            path=selected_path,
            max_bytes=MAX_RAW_FILE_BYTES,
        )
        if len(raw_content) > MAX_RAW_FILE_BYTES or len(raw_content) != declared_size:
            _reject()
        duration = max(0, int((time.monotonic() - started) * 1000))
        return LiveSmokeResult(
            repository_identity_digest=hashlib.sha256(repository_uuid.encode()).hexdigest(),
            commit_identity_digest=hashlib.sha256(resolved.commit_hash.encode()).hexdigest(),
            branch_count=len(branches),
            tree_page_count=tree_page_count,
            tree_entry_count=len(seen_paths),
            raw_byte_count=len(raw_content),
            raw_content_digest=hashlib.sha256(raw_content).hexdigest(),
            provider_get_count=audit.get_requests,
            duration_milliseconds=duration,
        )
    except BitbucketProviderReadError, ValueError:
        _reject()
    finally:
        await adapter.aclose()


def run(path: Path) -> LiveSmokeResult:
    config = LiveSmokeConfig.from_dotenv(path)
    access_token = _exchange_client_credentials(config)
    authority = LiveCredentialAuthority(access_token=access_token)
    initial_lease = authority.acquire_repository_read_lease(object())
    audit = ProviderReadAudit()
    try:
        result = asyncio.run(_run_live_reads(config, authority=authority, audit=audit))
        if audit.mutation_attempts != 0 or audit.get_requests < 5:
            _reject()
    finally:
        authority.revoke_local()
        access_token = ""
    if not authority.is_revoked or authority.access_token:
        _reject()
    try:
        authority.require_current_repository_read_lease(object(), initial_lease)
    except OAuthGenerationRejected:
        pass
    else:
        _reject()
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("phase2-live error: secure environment file is required", file=sys.stderr)
        return 2
    try:
        result = run(Path(sys.argv[1]))
    except LiveSmokeRejected:
        print("phase2-live error: read-only smoke rejected", file=sys.stderr)
        return 1
    print(result.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
