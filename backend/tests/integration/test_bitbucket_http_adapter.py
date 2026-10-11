"""Security contract for the generation-bound Bitbucket REST transport."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from verboflex.core.config import Settings

ACCESS_TOKEN = "provider-access-token-must-never-leak"
PROVIDER_BODY = "provider-body-must-never-leak"


@dataclass
class FakeCredentialLeaseAuthority:
    """Expose one observable current generation without a provider dependency."""

    generation: int = 7
    acquired: int = 0
    validated: list[int] = field(default_factory=list)

    def acquire_repository_read_lease(self, _session: object) -> Any:
        """Return the adapter's opaque lease type with a backend-only token."""
        from verboflex.integrations.bitbucket.client import BitbucketCredentialLease

        self.acquired += 1
        return BitbucketCredentialLease(
            generation=self.generation,
            access_token=ACCESS_TOKEN,
        )

    def require_current_repository_read_lease(self, _session: object, lease: Any) -> None:
        """Reject a lease after a local reconnect or revoke generation change."""
        self.validated.append(lease.generation)
        if lease.generation != self.generation:
            from verboflex.services.bitbucket_oauth import OAuthGenerationRejected

            raise OAuthGenerationRejected("stale provider generation")


@pytest.mark.parametrize(
    ("status_code", "expected_kind"),
    [
        (401, "reauthorization_required"),
        (403, "permission_denied"),
        (404, "not_found"),
        (408, "timeout"),
        (429, "rate_limited"),
        (503, "unavailable"),
        (504, "timeout"),
    ],
)
def test_provider_status_failures_are_closed_and_one_attempt(
    status_code: int,
    expected_kind: str,
) -> None:
    """Each provider status has one closed result and cannot trigger a retry."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )
    from verboflex.integrations.bitbucket.urls import BitbucketOperation

    requests: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code, text=PROVIDER_BODY, request=request)

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=FakeCredentialLeaseAuthority(),
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        error = captured.value
        assert error.kind == expected_kind
        assert error.provider_status == status_code
        assert error.operation is BitbucketOperation.REPOSITORY_METADATA
        assert str(error) == "Bitbucket provider read failed"
        assert set(vars(error)) == {"kind", "operation", "provider_status"}
        assert error.__cause__ is None
        assert error.__context__ is None
        assert PROVIDER_BODY not in f"{error!r} {error} {vars(error)!r}"
        assert len(requests) == 1
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", ["connect", "timeout"])
def test_transport_failures_are_sanitized_after_one_attempt(failure: str) -> None:
    """Transport details and request coordinates are discarded without retry."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )

    requests: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(PROVIDER_BODY, request=request)
        raise httpx.ConnectError(PROVIDER_BODY, request=request)

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=FakeCredentialLeaseAuthority(),
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        error = captured.value
        assert error.kind == ("timeout" if failure == "timeout" else "unavailable")
        assert error.provider_status is None
        assert error.__cause__ is None
        assert error.__context__ is None
        assert PROVIDER_BODY not in f"{error!r} {error} {vars(error)!r}"
        assert len(requests) == 1
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("scope_header", "accepted"),
    [
        ("pullrequest:write, repository, pullrequest, repository:write", True),
        ("pullrequest:write,repository,pullrequest,repository:write", True),
        ("pullrequest:write repository pullrequest repository:write", True),
        ("repository, repository:write", False),
        ("pullrequest:write, account", False),
        ("pullrequest:write, repository, repository", False),
        ("pullrequest:write, pullrequest:write", False),
        ("", False),
    ],
)
def test_live_scope_header_delimiters_preserve_capability_boundary(
    scope_header: str, accepted: bool
) -> None:
    """Real comma-delimited headers must obey the same exact capability policy."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=FakeCredentialLeaseAuthority(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"full_name": "acme/mobile"},
                headers={"x-oauth-scopes": scope_header},
                request=request,
            )
        ),
    )

    async def exercise() -> None:
        try:
            if accepted:
                result = await adapter.read_repository_metadata(
                    object(), workspace="acme", repository_slug="mobile"
                )
                assert result["full_name"] == "acme/mobile"
            else:
                with pytest.raises(BitbucketProviderReadError) as captured:
                    await adapter.read_repository_metadata(
                        object(), workspace="acme", repository_slug="mobile"
                    )
                assert captured.value.kind == "permission_denied"
                assert captured.value.provider_status == 200
        finally:
            await adapter.aclose()

    asyncio.run(exercise())


def test_disconnected_lease_fails_as_bounded_provider_state_before_http() -> None:
    """A local revoke is a bounded disconnected read failure, never an HTTP 500."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )
    from verboflex.services.bitbucket_oauth import OAuthConnectionUnavailable

    class DisconnectedAuthority(FakeCredentialLeaseAuthority):
        def acquire_repository_read_lease(self, _session: object) -> Any:
            raise OAuthConnectionUnavailable("connection unavailable")

    requests: list[httpx.Request] = []
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=DisconnectedAuthority(),
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, request=request)
        ),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert captured.value.kind == "disconnected"
        assert requests == []
        await adapter.aclose()

    asyncio.run(exercise())


def test_reads_metadata_only_through_validated_current_generation() -> None:
    """One metadata read is bounded, host-locked, non-retrying, and secret-safe."""
    try:
        from verboflex.integrations.bitbucket.client import (
            BitbucketHttpAdapter,
            BitbucketProviderReadError,
        )
        from verboflex.integrations.bitbucket.urls import validate_bitbucket_api_url
    except ModuleNotFoundError:
        pytest.fail("safe Bitbucket HTTP adapter is not implemented", pytrace=False)

    requests: list[httpx.Request] = []
    attempts: dict[str, int] = {}

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        slug = request.url.path.rsplit("/", 1)[-1]
        attempts[slug] = attempts.get(slug, 0) + 1
        if slug == "redirected":
            return httpx.Response(
                302,
                headers={"location": "https://attacker.example/steal"},
                request=request,
            )
        if slug == "safe-redirect":
            return httpx.Response(
                302,
                headers={"location": "https://api.bitbucket.org/2.0/repositories/acme/mobile"},
                request=request,
            )
        if slug == "failure":
            return httpx.Response(503, text=PROVIDER_BODY, request=request)
        if slug == "retry":
            raise httpx.ConnectError(PROVIDER_BODY, request=request)
        if slug == "wrong-scope":
            return httpx.Response(
                200,
                json={"uuid": "{repository-uuid}"},
                headers={"x-oauth-scopes": "repository:write"},
                request=request,
            )
        if slug == "non-object":
            return httpx.Response(
                200,
                json=[{"uuid": "{repository-uuid}"}],
                headers={"x-oauth-scopes": "pullrequest:write"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "uuid": "{repository-uuid}",
                "workspace": {"slug": "acme"},
                "slug": slug,
            },
            headers={"x-oauth-scopes": "pullrequest:write"},
            request=request,
        )

    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        metadata = await adapter.read_repository_metadata(
            object(),
            workspace="acme",
            repository_slug="mobile",
        )
        assert metadata == {
            "uuid": "{repository-uuid}",
            "workspace": {"slug": "acme"},
            "slug": "mobile",
        }

        request = requests[-1]
        assert request.method == "GET"
        assert str(request.url) == "https://api.bitbucket.org/2.0/repositories/acme/mobile"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"] == {
            "connect": 3.0,
            "read": 10.0,
            "write": 10.0,
            "pool": 3.0,
        }
        assert authority.acquired == 1
        assert authority.validated == [7, 7]

        calls_before_invalid_urls = len(requests)
        invalid_urls = (
            "http://api.bitbucket.org/2.0/repositories/acme/mobile",
            (
                "https://user:"  # pragma: allowlist secret
                "password@api.bitbucket.org/2.0/repositories/acme/mobile"
            ),
            "https://api.bitbucket.org:443/2.0/repositories/acme/mobile",
            "https://api.bitbucket.org.attacker.example/2.0/repositories/acme/mobile",
            "https://attacker.example/2.0/repositories/acme/mobile",
        )
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
                validate_bitbucket_api_url(invalid_url)
        assert len(requests) == calls_before_invalid_urls

        for slug in (
            "redirected",
            "safe-redirect",
            "failure",
            "retry",
            "wrong-scope",
            "non-object",
        ):
            with pytest.raises(BitbucketProviderReadError) as captured:
                await adapter.read_repository_metadata(
                    object(),
                    workspace="acme",
                    repository_slug=slug,
                )
            diagnostic = f"{captured.value!r} {captured.value}"
            assert ACCESS_TOKEN not in diagnostic
            assert PROVIDER_BODY not in diagnostic

        assert attempts["redirected"] == 1
        assert attempts["safe-redirect"] == 1
        assert attempts["failure"] == 1
        assert attempts["retry"] == 1
        assert attempts["wrong-scope"] == 1
        assert attempts["non-object"] == 1
        assert all(request.url.host == "api.bitbucket.org" for request in requests)
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize("invalidate_at", ["before_request", "during_response"])
def test_reconnect_or_revoke_discards_stale_provider_results(invalidate_at: str) -> None:
    """A locally superseded credential can neither start nor finish a provider read."""
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )

    requests: list[httpx.Request] = []

    @dataclass
    class InvalidatingCredentialLeaseAuthority(FakeCredentialLeaseAuthority):
        invalidate_after_acquire: bool = False

        def acquire_repository_read_lease(self, session: object) -> Any:
            lease = super().acquire_repository_read_lease(session)
            if self.invalidate_after_acquire:
                self.generation += 1
            return lease

    authority = InvalidatingCredentialLeaseAuthority(
        invalidate_after_acquire=invalidate_at == "before_request"
    )

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if invalidate_at == "during_response":
            authority.generation += 1
        return httpx.Response(
            200,
            json={"uuid": "{stale-repository-uuid}"},
            headers={"x-oauth-scopes": "pullrequest:write"},
            request=request,
        )

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            await adapter.read_repository_metadata(
                object(),
                workspace="acme",
                repository_slug="mobile",
            )
        assert str(captured.value) == "Bitbucket provider read failed"
        assert captured.value.kind == "reauthorization_required"
        assert captured.value.provider_status is None
        assert "stale" not in f"{captured.value!r} {captured.value}".lower()
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None
        assert len(requests) == (0 if invalidate_at == "before_request" else 1)
        await adapter.aclose()

    asyncio.run(exercise())


def test_provider_url_boundary_allows_only_integrated_read_families() -> None:
    """Excluded Bitbucket endpoint families fail before any credential can be sent."""
    from verboflex.integrations.bitbucket.urls import (
        repository_metadata_url,
        validate_bitbucket_api_url,
    )

    allowed_urls = (
        "https://api.bitbucket.org/2.0/repositories/acme/mobile",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches?pagelen=100",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches/feature%2Fone",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
        "0123456789abcdef0123456789abcdef01234567/?pagelen=100",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/src/"
        "0123456789abcdef0123456789abcdef01234567/locales/en.json",
    )
    for allowed_url in allowed_urls:
        assert validate_bitbucket_api_url(allowed_url) == allowed_url

    excluded_urls = (
        "https://api.bitbucket.org/2.0/repositories",
        "https://api.bitbucket.org/2.0/user",
        "https://api.bitbucket.org/2.0/workspaces/acme/members",
        "https://api.bitbucket.org/2.0/workspaces/acme/projects",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/tags",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/commits",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/diff/abc..def",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/commit/abc/statuses",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/pullrequests",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/hooks",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/permissions-config",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/branch-restrictions",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/deploy-keys",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/pipelines",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/deployments",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/issues",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/downloads",
        "https://api.bitbucket.org/2.0/repositories/acme/mobile/wiki",
        "https://api.bitbucket.org/2.0/snippets/acme",
        "https://api.bitbucket.org/2.0/workspaces/acme/search/code",
        "https://bitbucket.org/site/oauth2/revoke",
    )
    for excluded_url in excluded_urls:
        with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
            validate_bitbucket_api_url(excluded_url)

    structurally_invalid_urls: tuple[object, ...] = (
        None,
        "",
        "https://api.bitbucket.org\\2.0\\repositories\\acme\\mobile",
        "https://api.bitbucket.org:not-a-port/2.0/repositories/acme/mobile",
    )
    for invalid_url in structurally_invalid_urls:
        with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
            validate_bitbucket_api_url(invalid_url)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Bitbucket provider URL rejected"):
        repository_metadata_url(workspace="Acme", repository_slug="mobile")


def test_oauth_credential_lease_authority_fails_closed_for_unreadable_rows() -> None:
    """The real lease authority decrypts only readable rows and rechecks generation."""
    from verboflex.security.secret_box import SecretBoxDecryptionError
    from verboflex.services.bitbucket_oauth import (
        BitbucketOAuthService,
        OAuthConnectionUnavailable,
        OAuthGenerationRejected,
    )

    @dataclass
    class FakeSession:
        connection: object | None

        def begin(self) -> Any:
            return nullcontext()

        def execute(self, _statement: object) -> Any:
            return SimpleNamespace(scalar_one_or_none=lambda: self.connection)

        def get(self, _model: object, _identity: int) -> object | None:
            return self.connection

    class ReadableSecretBox:
        def decrypt(self, ciphertext: str) -> str:
            assert ciphertext == "encrypted-access-token"
            return ACCESS_TOKEN

    service = object.__new__(BitbucketOAuthService)
    service._secret_box = ReadableSecretBox()
    now = datetime.now(UTC)
    service._clock = lambda: now
    connection = SimpleNamespace(
        generation=7,
        revoked_at=None,
        scope_profile="pullrequest:write",
        access_token_ciphertext="encrypted-access-token",
        refresh_token_ciphertext=None,
        provider_expires_at=now + timedelta(hours=1),
    )
    session = FakeSession(connection)
    lease = service.acquire_repository_read_lease(session)  # type: ignore[arg-type]
    assert lease.generation == 7
    assert lease.access_token == ACCESS_TOKEN
    service.require_current_repository_read_lease(session, lease)  # type: ignore[arg-type]

    connection.generation = 8
    with pytest.raises(OAuthGenerationRejected, match="generation rejected"):
        service.require_current_repository_read_lease(session, lease)  # type: ignore[arg-type]

    unreadable_connections = (
        None,
        SimpleNamespace(**{**vars(connection), "revoked_at": object()}),
        SimpleNamespace(**{**vars(connection), "scope_profile": "repository"}),
        SimpleNamespace(**{**vars(connection), "scope_profile": "repository:write"}),
        SimpleNamespace(**{**vars(connection), "access_token_ciphertext": None}),
        SimpleNamespace(**{**vars(connection), "refresh_token_ciphertext": "legacy-refresh-token"}),
    )
    for unreadable_connection in unreadable_connections:
        with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
            service.acquire_repository_read_lease(  # type: ignore[arg-type]
                FakeSession(unreadable_connection)
            )

    class RejectingSecretBox:
        def decrypt(self, _ciphertext: str) -> str:
            raise SecretBoxDecryptionError("invalid ciphertext")

    service._secret_box = RejectingSecretBox()
    connection.generation = 7
    with pytest.raises(OAuthConnectionUnavailable, match="connection unavailable"):
        service.acquire_repository_read_lease(FakeSession(connection))  # type: ignore[arg-type]


def test_equal_commit_ancestry_short_circuits_without_provider_read() -> None:
    """Exact equality is authoritative and never spends provider or lease budget."""
    from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter

    requests: list[httpx.Request] = []
    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(500, request=request)
        ),
    )
    commit_hash = "a" * 40

    async def exercise() -> None:
        result = await adapter.compare_repository_ancestry(
            object(),
            workspace="acme",
            repository_slug="mobile",
            old_commit_hash=commit_hash,
            new_commit_hash=commit_hash,
        )
        assert result.old_commit_hash == commit_hash
        assert result.new_commit_hash == commit_hash
        assert result.relation == "equal"
        assert result.complete is True
        assert requests == []
        assert authority.acquired == 0
        assert authority.validated == []
        await adapter.aclose()

    asyncio.run(exercise())


def test_ancestry_and_diffstat_preserve_complete_provider_order() -> None:
    """Reachability and rewrite rows use exact commits and safe provider pagination."""
    from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter

    old_commit = "1" * 40
    new_commit = "2" * 40
    middle_commit = "3" * 40
    ancestry_next = (
        f"https://api.bitbucket.org/2.0/repositories/acme/mobile/commits/{new_commit}"
        "?pagelen=100&page=2"
    )
    diffstat_next = (
        f"https://api.bitbucket.org/2.0/repositories/acme/mobile/diffstat/"
        f"{new_commit}..{old_commit}?pagelen=100&page=2"
    )
    requests: list[httpx.Request] = []

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "/commits/" in request.url.path:
            payload = (
                {"values": [{"hash": new_commit}, {"hash": middle_commit}], "next": ancestry_next}
                if request.url.params.get("page") is None
                else {"values": [{"hash": old_commit}]}
            )
        elif request.url.params.get("page") is None:
            payload = {
                "values": [
                    {
                        "status": "added",
                        "old": None,
                        "new": {"path": "locales/en.json", "type": "commit_file"},
                    },
                    {
                        "status": "modified",
                        "old": {"path": "README.md", "type": "commit_file"},
                        "new": {"path": "README.md", "type": "commit_file"},
                    },
                    {
                        "status": "modified",
                        "old": {"path": "qt/app.ts", "type": "commit_file"},
                        "new": {"path": "qt/app.ts", "type": "commit_file"},
                    },
                ],
                "next": diffstat_next,
            }
        else:
            payload = {
                "values": [
                    {
                        "status": "removed",
                        "old": {"path": "ios/Localizable.strings", "type": "commit_file"},
                        "new": None,
                    },
                    {
                        "status": "modified",
                        "old": {"path": "android/strings.xml", "type": "commit_file"},
                        "new": {"path": "android/strings.xml", "type": "commit_file"},
                    },
                ]
            }
        return httpx.Response(
            200,
            json=payload,
            headers={"x-oauth-scopes": "pullrequest:write"},
            request=request,
        )

    authority = FakeCredentialLeaseAuthority()
    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        ancestry = await adapter.compare_repository_ancestry(
            object(),
            workspace="acme",
            repository_slug="mobile",
            old_commit_hash=old_commit,
            new_commit_hash=new_commit,
        )
        assert ancestry.relation == "descendant"
        assert ancestry.complete is True

        delta = await adapter.list_repository_diffstat(
            object(),
            workspace="acme",
            repository_slug="mobile",
            old_commit_hash=old_commit,
            new_commit_hash=new_commit,
            repository_side="direct",
        )
        assert delta.old_commit_hash == old_commit
        assert delta.new_commit_hash == new_commit
        assert delta.complete is True
        assert [
            (row.repository_side, row.ordinal, row.change, row.path) for row in delta.files
        ] == [
            ("direct", 0, "added", "locales/en.json"),
            ("direct", 1, "modified", "qt/app.ts"),
            ("direct", 2, "removed", "ios/Localizable.strings"),
            ("direct", 3, "modified", "android/strings.xml"),
        ]
        assert set(vars(delta)) == {"complete", "files", "new_commit_hash", "old_commit_hash"}
        assert all(
            set(vars(row)) == {"change", "ordinal", "path", "repository_side"}
            for row in delta.files
        )
        assert all(request.method == "GET" for request in requests)
        assert all(request.url.host == "api.bitbucket.org" for request in requests)
        assert [request.url.path for request in requests] == [
            f"/2.0/repositories/acme/mobile/commits/{new_commit}",
            f"/2.0/repositories/acme/mobile/commits/{new_commit}",
            f"/2.0/repositories/acme/mobile/diffstat/{new_commit}..{old_commit}",
            f"/2.0/repositories/acme/mobile/diffstat/{new_commit}..{old_commit}",
        ]
        assert authority.acquired == 4
        assert authority.validated == [authority.generation] * 8
        await adapter.aclose()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "scenario",
    [
        "malformed_commit",
        "repeated_ancestry_cursor",
        "cross_repository_ancestry",
        "ancestry_page_budget",
        "malformed_diffstat",
        "repeated_diffstat_cursor",
        "cross_spec_diffstat",
        "diffstat_row_budget",
        "diffstat_path_budget",
        "diffstat_byte_budget",
        "generation_drift",
    ],
)
def test_ancestry_and_diffstat_incomplete_or_ambiguous_results_fail_closed(
    scenario: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No malformed, stale, cross-resource, repeated, or truncated result is complete."""
    import verboflex.integrations.bitbucket.client as client_module
    from verboflex.integrations.bitbucket.client import (
        BitbucketHttpAdapter,
        BitbucketProviderReadError,
    )

    old_commit = "4" * 40
    new_commit = "5" * 40
    requests: list[httpx.Request] = []
    authority = FakeCredentialLeaseAuthority()
    repeated_ancestry = (
        f"https://api.bitbucket.org/2.0/repositories/acme/mobile/commits/{new_commit}"
        "?pagelen=100&page=2"
    )
    repeated_diffstat = (
        f"https://api.bitbucket.org/2.0/repositories/acme/mobile/diffstat/"
        f"{new_commit}..{old_commit}?pagelen=100&page=2"
    )
    if scenario == "ancestry_page_budget":
        monkeypatch.setattr(client_module, "MAX_ANCESTRY_PAGES", 1)
    if scenario == "diffstat_row_budget":
        monkeypatch.setattr(client_module, "MAX_DIFFSTAT_ROWS", 0)
    if scenario == "diffstat_path_budget":
        monkeypatch.setattr(client_module, "MAX_DIFFSTAT_PATH_LENGTH", 3)
    if scenario == "diffstat_byte_budget":
        monkeypatch.setattr(client_module, "MAX_DIFFSTAT_PATH_BYTES", 3)

    def provider(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if scenario == "generation_drift":
            authority.generation += 1
        if "/commits/" in request.url.path:
            value_hash = "not-a-commit" if scenario == "malformed_commit" else new_commit
            payload: dict[str, object] = {"values": [{"hash": value_hash}]}
            if scenario in {"repeated_ancestry_cursor", "ancestry_page_budget"}:
                payload["next"] = repeated_ancestry
            elif scenario == "cross_repository_ancestry":
                payload["next"] = (
                    f"https://api.bitbucket.org/2.0/repositories/acme/other/commits/{new_commit}"
                    "?pagelen=100&page=2"
                )
        else:
            old_path = "locale.json"
            new_path = "other.json" if scenario == "malformed_diffstat" else old_path
            payload = {
                "values": [
                    {
                        "status": "modified",
                        "old": {"path": old_path, "type": "commit_file"},
                        "new": {"path": new_path, "type": "commit_file"},
                    }
                ]
            }
            if scenario == "repeated_diffstat_cursor":
                payload["next"] = repeated_diffstat
            elif scenario == "cross_spec_diffstat":
                payload["next"] = (
                    "https://api.bitbucket.org/2.0/repositories/acme/mobile/diffstat/"
                    f"{'6' * 40}..{old_commit}?pagelen=100&page=2"
                )
        return httpx.Response(
            200,
            json=payload,
            headers={"x-oauth-scopes": "pullrequest:write"},
            request=request,
        )

    adapter = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=authority,
        transport=httpx.MockTransport(provider),
    )

    async def exercise() -> None:
        with pytest.raises(BitbucketProviderReadError) as captured:
            if scenario.startswith("ancestry") or scenario in {
                "malformed_commit",
                "repeated_ancestry_cursor",
                "cross_repository_ancestry",
                "generation_drift",
            }:
                await adapter.compare_repository_ancestry(
                    object(),
                    workspace="acme",
                    repository_slug="mobile",
                    old_commit_hash=old_commit,
                    new_commit_hash=new_commit,
                )
            else:
                await adapter.list_repository_diffstat(
                    object(),
                    workspace="acme",
                    repository_slug="mobile",
                    old_commit_hash=old_commit,
                    new_commit_hash=new_commit,
                    repository_side="keys",
                )
        assert captured.value.kind in {
            "invalid_source",
            "limit_exceeded",
            "reauthorization_required",
        }
        assert str(captured.value) == "Bitbucket provider read failed"
        assert "locale.json" not in f"{captured.value!r} {captured.value}"
        assert all(request.method == "GET" for request in requests)
        assert len(requests) <= 2
        await adapter.aclose()

    asyncio.run(exercise())
