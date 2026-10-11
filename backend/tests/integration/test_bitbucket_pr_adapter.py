"""Independent provider evidence for exact PR creation and read-only recovery."""

import asyncio
import copy
import json
from dataclasses import replace
from urllib.parse import urlencode
from uuid import UUID

import httpx
import pytest

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    PullRequestIntent,
    WriteContext,
)
from verboflex.services.bitbucket_oauth import (
    BitbucketCredentialLease,
    OAuthGenerationRejected,
)

REPOSITORY = UUID("00000000-0000-4000-8000-000000000017")
CHANGE_SET = UUID("00000000-0000-4000-8000-000000000018")
SOURCE = "b" * 40
TARGET = "a" * 40
SCOPE = {"x-oauth-scopes": "pullrequest:write,repository,repository:write,pullrequest"}


class Credentials:
    generation = 7

    def acquire_repository_read_lease(self, session):
        return BitbucketCredentialLease(self.generation, "private-pr-test-token")

    def acquire_repository_write_lease(self, session, *, expected_generation):
        if expected_generation != self.generation:
            raise OAuthGenerationRejected("generation rejected")
        return self.acquire_repository_read_lease(session)

    def require_current_repository_read_lease(self, session, lease):
        if lease.generation != self.generation:
            raise OAuthGenerationRejected("generation rejected")


def pr_intent():
    return PullRequestIntent(
        WriteContext(REPOSITORY, "acme", "mobile", CHANGE_SET, 7),
        SOURCE,
        "release/1",
        TARGET,
        "f" * 64,
    )


def next_page_url(*, page=2, omit=None, changes=None):
    query = {
        "pagelen": 50,
        "q": f'source.branch.name = "{pr_intent().context.source_branch}"',
        "state": ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"],
        "page": page,
    }
    if omit:
        query.pop(omit)
    query.update(changes or {})
    return "https://api.bitbucket.org/2.0/repositories/acme/mobile/pullrequests?" + urlencode(
        query, doseq=True
    )


def receipt(intent, *, identity=41, state="OPEN", target_commit=TARGET):
    return {
        "id": identity,
        "state": state,
        "description": intent.description,
        "source": {
            "repository": {"uuid": str(REPOSITORY)},
            "branch": {"name": intent.context.source_branch},
            "commit": {"hash": SOURCE},
        },
        "destination": {
            "repository": {"uuid": str(REPOSITORY)},
            "branch": {"name": intent.target_branch},
            "commit": {"hash": target_commit},
        },
        "links": {"html": {"href": f"https://bitbucket.org/acme/mobile/pull-requests/{identity}"}},
    }


class Provider:
    """An independent mutable provider, with observable requests and remote PRs."""

    def __init__(self):
        self.intent = pr_intent()
        self.credentials = Credentials()
        self.requests = []
        self.posts = []
        self.prs = []
        self.fault = ""
        self.response_edit = lambda value: value
        self.source_head = SOURCE
        self.target_head = TARGET
        self.missing_branches = False
        self.pages = None
        self.list_states = set()
        self.commit_responses = {}

    @staticmethod
    def reply(payload, status=200):
        return httpx.Response(status, headers=SCOPE, json=payload)

    def __call__(self, request):
        self.requests.append((request.method, str(request.url)))
        assert request.url.host == "api.bitbucket.org"
        assert request.url.raw_path.startswith(
            f"/2.0/repositories/acme/%7B{REPOSITORY}%7D".encode()
        )
        parts = request.url.path.strip("/").split("/", 4)
        path = "/" + parts[4] if len(parts) > 4 else ""
        if request.method == "GET" and not path:
            return self.reply({"uuid": str(REPOSITORY)})
        if request.method == "GET" and path.startswith("/commit/"):
            prefix = path.removeprefix("/commit/")
            if prefix in self.commit_responses:
                return self.commit_responses[prefix]
            commit = next(value for value in (SOURCE, TARGET) if value.startswith(prefix))
            return self.reply({"hash": commit, "repository": {"uuid": str(REPOSITORY)}})
        if request.method == "GET" and path.startswith("/refs/branches/"):
            if self.missing_branches:
                return httpx.Response(404, headers=SCOPE)
            branch = path.removeprefix("/refs/branches/")
            assert branch in {self.intent.context.source_branch, self.intent.target_branch}
            return self.reply(
                {
                    "name": branch,
                    "target": {
                        "hash": self.source_head
                        if branch == self.intent.context.source_branch
                        else self.target_head,
                        "repository": {"uuid": str(REPOSITORY)},
                    },
                }
            )
        if request.method == "POST" and path == "/pullrequests":
            self.posts.append(json.loads(request.content))
            if self.fault == "connect":
                raise httpx.ConnectError("private provider details", request=request)
            if self.fault == "delayed":
                raise httpx.ReadTimeout("private provider details", request=request)
            if self.fault in {"401", "403", "429", "503"}:
                return httpx.Response(int(self.fault), headers=SCOPE)
            self.prs.append(receipt(self.intent))
            if self.fault == "rotation":
                self.credentials.generation += 1
            if self.fault == "lost":
                raise httpx.ReadTimeout("private provider details", request=request)
            if self.fault == "redirect":
                return httpx.Response(
                    307, headers={**SCOPE, "Location": "https://evil.example/steal"}
                )
            if self.fault == "malformed":
                return httpx.Response(
                    201, headers={**SCOPE, "Content-Type": "application/json"}, content=b"{"
                )
            if self.fault == "large":
                return httpx.Response(
                    201,
                    headers={**SCOPE, "Content-Type": "application/json"},
                    content=b"x" * 1_048_577,
                )
            if self.fault == "location":
                return httpx.Response(
                    201, headers={**SCOPE, "Location": "https://evil.example/steal"}
                )
            return self.reply(self.response_edit(copy.deepcopy(self.prs[-1])), 201)
        if request.method == "GET" and path == "/pullrequests":
            if int(request.url.params.get("pagelen", "10")) > 50:
                return self.reply({"error": {"message": "Invalid pagelen"}}, 400)
            self.list_states.update(request.url.params.get_list("state"))
            page = int(request.url.params.get("page", "1"))
            if self.pages is not None:
                return self.reply(self.pages[page - 1])
            return self.reply({"values": self.prs})
        if request.method == "GET" and path.startswith("/pullrequests/"):
            identity = int(path.removeprefix("/pullrequests/"))
            found = next((item for item in self.prs if item["id"] == identity), None)
            if found is None:
                return httpx.Response(404, headers=SCOPE)
            return self.reply(self.response_edit(copy.deepcopy(found)))
        raise AssertionError("unexpected provider operation")


async def with_provider(provider, callback):
    protocol_errors = []

    def checked_request(request):
        try:
            return provider(request)
        except AssertionError as error:
            protocol_errors.append(str(error))
            raise

    reads = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=provider.credentials,
        transport=httpx.MockTransport(checked_request),
    )
    try:
        return await callback(BitbucketWriteAdapter(reads=reads))
    finally:
        await reads.aclose()
        assert not protocol_errors, protocol_errors


def test_create_sends_exact_source_and_explicit_destination_and_verifies_receipt():
    provider = Provider()

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state == "verified"
        assert result.provider_status == 201
        assert result.receipt.id == 41
        assert result.receipt.url == "https://bitbucket.org/acme/mobile/pull-requests/41"
        assert result.receipt.source_commit == SOURCE
        assert result.receipt.target_commit == TARGET
        assert result.receipt.target_branch == "release/1"
        assert len(provider.posts) == 1
        body = provider.posts[0]
        assert body["title"] == provider.intent.title
        assert body["description"] == provider.intent.description
        assert UUID(body["source"]["repository"]["uuid"]) == REPOSITORY
        assert UUID(body["destination"]["repository"]["uuid"]) == REPOSITORY
        assert body["source"]["branch"] == {"name": provider.intent.context.source_branch}
        assert body["source"]["commit"] == {"hash": SOURCE}
        assert body["destination"]["branch"] == {"name": "release/1"}

    asyncio.run(with_provider(provider, exercise))


def test_create_rejects_receipt_identity_outside_lossless_json_integer_range():
    provider = Provider()
    provider.response_edit = lambda _: receipt(provider.intent, identity=2**53)
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_pull_request(object(), intent=provider.intent)
        )
    )
    assert result.state in {"unknown", "conflict"}
    assert result.receipt is None


def altered(path, replacement):
    def change(value):
        current = value
        for key in path[:-1]:
            current = current[key]
        if replacement is None:
            current.pop(path[-1])
        else:
            current[path[-1]] = replacement
        return value

    return change


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("destination",), None),
        (("destination", "branch"), None),
        (("destination", "branch", "name"), "main"),
        (("destination", "repository", "uuid"), "00000000-0000-4000-8000-000000000099"),
        (("source", "repository", "uuid"), "00000000-0000-4000-8000-000000000099"),
        (("source", "branch", "name"), "main"),
        (("source", "commit", "hash"), "c" * 40),
        (("destination", "commit", "hash"), "abcdef"),
        (("id",), True),
        (("id",), 0),
        (("id",), "41"),
        (("state",), "UNKNOWN"),
        (("description",), "Foreign PR"),
        (("links",), None),
    ],
)
def test_create_rejects_incomplete_or_mismatched_receipt(path, replacement):
    provider = Provider()
    provider.response_edit = altered(path, replacement)

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert len(provider.posts) == 1

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "url",
    [
        "http://bitbucket.org/acme/mobile/pull-requests/41",
        "https://bitbucket.org.evil.example/acme/mobile/pull-requests/41",
        "https://user:secret@bitbucket.org/acme/mobile/pull-requests/41",
        "https://bitbucket.org:8443/acme/mobile/pull-requests/41",
        "https://bitbucket.org/acme/other/pull-requests/41",
        "https://bitbucket.org/acme/mobile/pull-requests/42",
        "https://bitbucket.org/acme/mobile/pull-requests/41?redirect=evil",
        "https://bitbucket.org/acme/mobile/pull-requests/41#fragment",
        "https://bitbucket.org/acme/mobile/pull-requests/%34%31",
        "https://bitbucket.org/acme/mobile/pull-requests/41/../42",
    ],
)
def test_create_never_adopts_untrusted_receipt_link(url):
    provider = Provider()
    provider.response_edit = altered(("links", "html", "href"), url)

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert len(provider.posts) == 1

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("side", ["source", "target"])
def test_create_refuses_changed_branch_head_before_send(side):
    provider = Provider()
    setattr(provider, f"{side}_head", "c" * 40)

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state in {"not_sent", "conflict"}
        assert result.receipt is None
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "fault", ["redirect", "malformed", "large", "location", "lost", "rotation", "503"]
)
def test_create_ambiguous_send_is_unknown_and_never_reposts(fault):
    provider = Provider()
    provider.fault = fault

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state == "unknown"
        assert result.receipt is None
        assert len(provider.posts) == 1
        assert all("evil.example" not in url for _, url in provider.requests)
        assert "private" not in repr(result)

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("fault", ["connect", "401", "403", "429"])
def test_create_known_not_sent_failure_remains_distinct(fault):
    provider = Provider()
    provider.fault = fault

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state == "not_sent"
        assert result.receipt is None
        assert provider.prs == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("state", ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"])
def test_reconcile_all_states_adopts_exact_receipt_even_when_source_branch_deleted(state):
    provider = Provider()
    provider.missing_branches = True
    provider.credentials.generation += 1
    provider.prs = [receipt(provider.intent, state=state, target_commit="c" * 40)]

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state == "verified"
        assert result.receipt.state == state
        assert result.receipt.target_commit == "c" * 40
        assert result.receipt.source_commit == SOURCE
        assert provider.list_states == {"OPEN", "MERGED", "DECLINED", "SUPERSEDED"}
        assert all(method == "GET" for method, _ in provider.requests)

    asyncio.run(with_provider(provider, exercise))


def test_reconcile_later_page_rebinds_captured_slug_to_repository_uuid():
    provider = Provider()
    next_url = next_page_url()
    provider.pages = [{"values": [], "next": next_url}, {"values": [receipt(provider.intent)]}]

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state == "verified"
        assert result.receipt.id == 41
        assert len([url for _, url in provider.requests if "page=2" in url]) == 1
        assert all(method == "GET" for method, _ in provider.requests)

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "metadata",
    [{"size": 2}, {"size": 0}, {"size": True}, {"page": 2}, {"pagelen": 0}, {"pagelen": 100}],
)
def test_reconcile_contradictory_page_metadata_cannot_prove_unique_pr(metadata):
    provider = Provider()
    provider.pages = [{"values": [receipt(provider.intent)], **metadata}]
    result = asyncio.run(
        with_provider(
            provider,
            lambda adapter: adapter.reconcile_pull_request(object(), intent=provider.intent),
        )
    )
    assert result.state == "unknown" and result.receipt is None
    assert provider.posts == []


def test_reconcile_cannot_skip_page_containing_second_matching_pr():
    provider = Provider()
    provider.pages = [
        {"values": [receipt(provider.intent)], "next": next_page_url(page=3)},
        {"values": [receipt(provider.intent, identity=42)]},
        {"values": []},
    ]
    result = asyncio.run(
        with_provider(
            provider,
            lambda adapter: adapter.reconcile_pull_request(object(), intent=provider.intent),
        )
    )
    assert result.state == "unknown" and result.receipt is None
    assert provider.posts == []
    assert not any("page=3" in url for _, url in provider.requests)


@pytest.mark.parametrize("last_size", [1, 2])
def test_reconcile_complete_pages_require_consistent_total_when_supplied(last_size):
    provider = Provider()
    provider.pages = [
        {"values": [], "page": 1, "pagelen": 50, "size": 1, "next": next_page_url()},
        {"values": [receipt(provider.intent)], "page": 2, "pagelen": 50, "size": last_size},
    ]
    result = asyncio.run(
        with_provider(
            provider,
            lambda adapter: adapter.reconcile_pull_request(object(), intent=provider.intent),
        )
    )
    assert result.state == ("verified" if last_size == 1 else "unknown")
    assert provider.posts == []


@pytest.mark.parametrize("count", [0, 2])
def test_reconcile_zero_or_multiple_matches_never_grants_resend(count):
    provider = Provider()
    provider.prs = [receipt(provider.intent, identity=41 + index) for index in range(count)]

    async def exercise(adapter):
        for _ in range(2):
            result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
            assert result.state in {"unknown", "conflict"}
            assert result.receipt is None
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.example/steal",
        "https://api.bitbucket.org/2.0/repositories/acme/other/pullrequests?page=2",
        next_page_url(changes={"state": ["OPEN"]}),
        next_page_url(page=1),
        next_page_url(omit="pagelen"),
        next_page_url(changes={"pagelen": 1000}),
        next_page_url(omit="q"),
        next_page_url(changes={"q": 'source.branch.name = "foreign"'}),
    ],
)
def test_reconcile_incomplete_or_foreign_pagination_cannot_adopt_match(next_url):
    provider = Provider()
    provider.pages = [{"values": [receipt(provider.intent)], "next": next_url}]

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert provider.posts == []
        assert all("evil.example" not in url for _, url in provider.requests)
        assert len(provider.requests) <= 4

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("source", "repository", "uuid"), "00000000-0000-4000-8000-000000000099"),
        (("destination", "repository", "uuid"), "00000000-0000-4000-8000-000000000099"),
        (("source", "branch", "name"), "other-branch"),
        (("destination", "branch", "name"), "main"),
        (("source", "commit", "hash"), "c" * 40),
        (("description",), pr_intent().description.replace("f" * 64, "a" * 64)),
        (("description",), pr_intent().description + f"VerboFlex-Change-Set: {CHANGE_SET}\n"),
        (
            ("description",),
            "quoted "
            + pr_intent().description.replace("VerboFlex-Change-Set", "> VerboFlex-Change-Set"),
        ),
    ],
)
def test_reconcile_marker_alone_or_inexact_marker_cannot_adopt(path, replacement):
    provider = Provider()
    provider.prs = [altered(path, replacement)(receipt(provider.intent))]

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "payload", [{}, {"values": None}, {"values": {}}, {"values": [], "next": 42}]
)
def test_reconcile_malformed_page_is_unresolved_without_any_write(payload):
    provider = Provider()
    provider.pages = [payload]

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("fault", ["lost", "delayed"])
def test_reconcile_lost_or_late_original_send_never_creates_a_second_pr(fault):
    provider = Provider()
    provider.fault = fault

    async def exercise(adapter):
        first = await adapter.create_pull_request(object(), intent=provider.intent)
        assert first.state == "unknown"
        if fault == "delayed":
            missing = await adapter.reconcile_pull_request(object(), intent=provider.intent)
            assert missing.state == "unknown"
            provider.prs.append(receipt(provider.intent))
        for _ in range(2):
            recovered = await adapter.reconcile_pull_request(object(), intent=provider.intent)
            assert recovered.state == "verified"
            assert recovered.receipt.id == 41
        assert len(provider.posts) == 1
        assert len(provider.prs) == 1

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("state", ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"])
def test_read_known_receipt_retains_exact_identity_after_target_advance_and_branch_deletion(state):
    provider = Provider()
    provider.missing_branches = True
    provider.prs = [receipt(provider.intent, state=state, target_commit="d" * 40)]

    async def exercise(adapter):
        result = await adapter.read_pull_request(
            object(), intent=provider.intent, pull_request_id=41
        )
        assert result.state == "verified"
        assert result.receipt.state == state
        assert result.receipt.target_commit == "d" * 40
        assert len(provider.requests) == 1
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


def test_read_known_receipt_missing_or_changed_identity_stays_unresolved():
    provider = Provider()

    async def exercise(adapter):
        missing = await adapter.read_pull_request(
            object(), intent=provider.intent, pull_request_id=41
        )
        assert missing.state == "unknown"
        assert missing.receipt is None
        provider.prs = [receipt(provider.intent)]
        provider.response_edit = altered(("id",), 42)
        changed = await adapter.read_pull_request(
            object(), intent=provider.intent, pull_request_id=41
        )
        assert changed.state in {"unknown", "conflict"}
        assert changed.receipt is None
        assert provider.posts == []

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "field,value",
    [("target_branch", ""), ("source_commit", "abcdef"), ("manifest_digest", "short")],
)
def test_create_invalid_intent_does_not_contact_provider(field, value):
    provider = Provider()
    provider.intent = replace(provider.intent, **{field: value})

    async def exercise(adapter):
        result = await adapter.create_pull_request(object(), intent=provider.intent)
        assert result.state == "not_sent"
        assert provider.requests == []

    asyncio.run(with_provider(provider, exercise))


def abbreviated_receipt(value):
    for side in ("source", "destination"):
        value[side]["commit"]["hash"] = value[side]["commit"]["hash"][:12]
        value[side]["commit"]["links"] = {"self": {"href": "https://evil.example/steal"}}
    return value


@pytest.mark.parametrize("operation", ["create", "reconcile", "read"])
def test_pr_abbreviated_hashes_are_resolved_to_full_repository_commits(operation):
    provider = Provider()
    provider.response_edit = abbreviated_receipt
    if operation != "create":
        provider.prs = [abbreviated_receipt(receipt(provider.intent))]
        provider.missing_branches = True

    async def exercise(adapter):
        if operation == "create":
            result = await adapter.create_pull_request(object(), intent=provider.intent)
        elif operation == "reconcile":
            result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        else:
            result = await adapter.read_pull_request(
                object(), intent=provider.intent, pull_request_id=41
            )
        assert result.state == "verified"
        assert result.receipt.source_commit == SOURCE
        assert result.receipt.target_commit == TARGET
        resolved = [url for method, url in provider.requests if "/commit/" in url]
        assert len(resolved) == 2
        assert all("evil.example" not in url for _, url in provider.requests)
        assert len(provider.posts) == (1 if operation == "create" else 0)

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "side,fault",
    [
        (side, fault)
        for side in ("source", "destination")
        for fault in ("404", "redirect", "repository", "prefix", "short")
    ]
    + [("source", "collision")],
)
def test_pr_prefix_resolution_never_adopts_unproven_commit(side, fault):
    provider = Provider()
    provider.prs = [abbreviated_receipt(receipt(provider.intent))]
    full = SOURCE if side == "source" else TARGET
    payload = {"hash": full, "repository": {"uuid": str(REPOSITORY)}}
    if fault == "repository":
        payload["repository"]["uuid"] = str(CHANGE_SET)
    elif fault == "prefix":
        payload["hash"] = "c" * 40
    elif fault == "short":
        payload["hash"] = full[:12]
    elif fault == "collision":
        payload["hash"] = full[:12] + "c" * 28
    response = provider.reply(payload)
    if fault == "404":
        response = httpx.Response(404, headers=SCOPE)
    elif fault == "redirect":
        response = httpx.Response(302, headers={**SCOPE, "Location": "https://evil.example/"})
    provider.commit_responses[full[:12]] = response

    async def exercise(adapter):
        result = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert result.state in {"unknown", "conflict"}
        assert result.receipt is None
        assert provider.posts == []
        assert all("evil.example" not in url for _, url in provider.requests)

    asyncio.run(with_provider(provider, exercise))


def test_known_pr_tracking_accepts_full_rebased_head_but_creation_recovery_stays_strict():
    provider = Provider()
    changed = receipt(provider.intent)
    changed["source"]["commit"]["hash"] = "c" * 40
    provider.prs = [changed]

    async def exercise(adapter):
        strict = await adapter.read_pull_request(
            object(), intent=provider.intent, pull_request_id=41
        )
        assert strict.state == "conflict"
        tracked = await adapter.read_pull_request(
            object(),
            intent=provider.intent,
            pull_request_id=41,
            allow_rebased=True,
        )
        assert tracked.state == "verified"
        assert tracked.receipt.source_commit == "c" * 40
        recovery = await adapter.reconcile_pull_request(object(), intent=provider.intent)
        assert recovery.state == "conflict"
        assert not provider.posts

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("mutation", ["id", "repository", "branch", "target", "marker", "url"])
def test_rebased_tracking_still_rejects_changed_pr_identity(mutation):
    provider = Provider()
    changed = receipt(provider.intent)
    changed["source"]["commit"]["hash"] = "c" * 40
    provider.prs = [changed]

    def alter(value):
        if mutation == "id":
            value["id"] = 42
        elif mutation == "repository":
            value["source"]["repository"]["uuid"] = str(CHANGE_SET)
        elif mutation == "branch":
            value["source"]["branch"]["name"] = "other"
        elif mutation == "target":
            value["destination"]["branch"]["name"] = "main"
        elif mutation == "marker":
            value["description"] = "unrelated"
        elif mutation == "url":
            value["links"]["html"]["href"] = "https://evil.example/41"
        return value

    provider.response_edit = alter

    async def exercise(adapter):
        result = await adapter.read_pull_request(
            object(),
            intent=provider.intent,
            pull_request_id=41,
            allow_rebased=True,
        )
        assert result.state == ("unknown" if mutation == "repository" else "conflict")

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "status,reason,blocking,expected",
    [
        ("PASSED", "clean", False, "clean"),
        ("FAILED", "conflicts", True, "conflicts"),
        ("PENDING", "clean", False, "unknown"),
        ("PASSED", "clean", True, "unknown"),
        ("FAILED", "other", True, "unknown"),
    ],
)
def test_mergeability_is_explicit_and_fail_closed(status, reason, blocking, expected):
    class Checks(Provider):
        def __call__(self, request):
            if request.url.path.endswith("/mergeability/checks"):
                assert request.method == "GET"
                return self.reply(
                    {
                        "values": [
                            {
                                "type": "git_mergeability_check",
                                "status": status,
                                "reason": reason,
                                "blocking": blocking,
                            }
                        ]
                    }
                )
            return super().__call__(request)

    provider = Checks()

    async def exercise(adapter):
        assert (
            await adapter.read_pr_merge_status(
                object(),
                context=provider.intent.context,
                pull_request_id=41,
            )
            == expected
        )

    asyncio.run(with_provider(provider, exercise))
