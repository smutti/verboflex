"""Stateful protocol evidence for exact owned branches and conditional commits."""

import asyncio
import hashlib
import json
import math
from dataclasses import replace
from email.parser import BytesParser
from email.policy import default
from uuid import UUID

import httpx
import pytest

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.writes import (
    BitbucketWriteAdapter,
    BranchIntent,
    CommitFile,
    CommitIntent,
    WriteContext,
)
from verboflex.services.bitbucket_oauth import BitbucketCredentialLease

REPOSITORY = UUID("00000000-0000-4000-8000-000000000007")
CHANGE_SET = UUID("00000000-0000-4000-8000-000000000008")
PARENT = "a" * 40
COMMIT = "b" * 40
SCOPE = {"x-oauth-scopes": "pullrequest:write,repository,repository:write,pullrequest"}


class Credentials:
    generation = 7
    acquired = 0

    def acquire_repository_read_lease(self, session):
        self.acquired += 1
        return BitbucketCredentialLease(self.generation, "private-test-token")

    def acquire_repository_write_lease(self, session, *, expected_generation):
        from verboflex.services.bitbucket_oauth import OAuthGenerationRejected

        if expected_generation != self.generation:
            raise OAuthGenerationRejected("generation rejected")
        return self.acquire_repository_read_lease(session)

    def require_current_repository_read_lease(self, session, lease):
        from verboflex.services.bitbucket_oauth import OAuthGenerationRejected

        if lease.generation != self.generation:
            raise OAuthGenerationRejected("generation rejected")


def branch_intent():
    return BranchIntent(WriteContext(REPOSITORY, "acme", "mobile", CHANGE_SET, 7), PARENT)


def test_branch_creates_exact_owned_name_at_recorded_parent():
    intent = branch_intent()
    branches = {}
    posts = []

    def provider(request):
        if request.method == "GET" and len(request.url.path.strip("/").split("/")) == 4:
            return httpx.Response(200, headers=SCOPE, json={"uuid": str(REPOSITORY)})
        if request.method == "POST":
            import json

            body = json.loads(request.content)
            posts.append(body)
            branches[body["name"]] = body["target"]["hash"]
            return httpx.Response(201, headers=SCOPE)
        head = branches.get(intent.context.source_branch)
        if head is None:
            return httpx.Response(404, headers=SCOPE)
        return httpx.Response(
            200,
            headers=SCOPE,
            json={
                "name": intent.context.source_branch,
                "target": {"hash": head, "repository": {"uuid": str(REPOSITORY)}},
            },
        )

    async def exercise():
        reads = BitbucketHttpAdapter(
            settings=Settings(),
            credential_leases=Credentials(),
            transport=httpx.MockTransport(provider),
        )
        try:
            result = await BitbucketWriteAdapter(reads=reads).create_branch(object(), intent=intent)
            assert result.state == "verified"
            assert result.receipt.commit_hash == PARENT
            assert posts == [{"name": intent.context.source_branch, "target": {"hash": PARENT}}]
        finally:
            await reads.aclose()

    asyncio.run(exercise())


def commit_intent(path="locales/it.json"):
    return CommitIntent(
        branch_intent(),
        "f" * 64,
        (CommitFile(path, b'{"hello":"ciao"}\n', hashlib.sha256(b"old\n").hexdigest()),),
    )


class Provider:
    """Independent multipart parser and mutable remote graph; never calls app parsers."""

    def __init__(self, intent=None):
        self.intent = intent or commit_intent()
        self.credentials = Credentials()
        self.head = PARENT
        self.branch_posts = 0
        self.commit_posts = 0
        self.commits = 0
        self.fault = ""
        self.outputs = {}
        self.fields = {}
        self.requests = []
        self.repo = REPOSITORY

    def reply(self, status=200, payload=None, **kwargs):
        if payload is not None:
            return httpx.Response(status, json=payload, headers=SCOPE, **kwargs)
        return httpx.Response(status, headers=SCOPE, **kwargs)

    def __call__(self, request):
        self.requests.append((request.method, str(request.url)))
        parts = request.url.path.strip("/").split("/", 4)
        path = "/" + parts[4] if len(parts) > 4 else ""
        if request.method == "GET" and path == "":
            return self.reply(payload={"uuid": str(self.repo)})
        if request.method == "POST":
            if self.fault == "connect":
                raise httpx.ConnectError("private provider details", request=request)
            if self.fault == "redirect":
                return httpx.Response(
                    307, headers={**SCOPE, "Location": "https://evil.example/steal"}
                )
            if self.fault in {"401", "403", "429", "503"}:
                return self.reply(int(self.fault))
            if path == "/refs/branches":
                self.branch_posts += 1
                body = json.loads(request.content)
                assert body == {
                    "name": self.intent.branch.context.source_branch,
                    "target": {"hash": PARENT},
                }
                self.head = PARENT
            elif path == "/src":
                self.commit_posts += 1
                message = BytesParser(policy=default).parsebytes(
                    b"Content-Type: "
                    + request.headers["content-type"].encode()
                    + b"\r\n\r\n"
                    + request.content
                )
                self.fields = {}
                self.outputs = {}
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    raw = part.get_payload(decode=True)
                    if part.get_filename() is None:
                        self.fields[name] = raw.decode()
                    else:
                        assert name.startswith("/")
                        self.outputs[name[1:]] = raw
                assert self.fields == {
                    "branch": self.intent.branch.context.source_branch,
                    "parents": PARENT,
                    "message": self.intent.message,
                }
                if self.fault == "cas":
                    self.head = "c" * 40
                    return self.reply(409)
                if self.head != self.fields["parents"]:
                    return self.reply(409)
                if self.fault == "delayed":
                    raise httpx.ReadTimeout("private provider details", request=request)
                self.commits += 1
                self.head = COMMIT
            else:
                raise AssertionError("unexpected mutation")
            if self.fault == "rotation":
                self.credentials.generation += 1
            if self.fault == "lost":
                raise httpx.ReadTimeout("private provider details", request=request)
            if self.fault == "large":
                return self.reply(201, content=b"x" * (1_048_576 + 1))
            if self.fault == "json":
                return self.reply(201, {"hash": self.head})
            return self.reply(201)
        if path.startswith("/refs/branches/"):
            if self.fault == "verification-connect" and self.head == COMMIT:
                raise httpx.ConnectError("private provider details", request=request)
            if self.head is None:
                return self.reply(404)
            return self.reply(
                payload={
                    "name": self.intent.branch.context.source_branch,
                    "target": {"hash": self.head, "repository": {"uuid": str(self.repo)}},
                }
            )
        if path.startswith("/commit/"):
            return self.reply(
                payload={
                    "hash": self.head,
                    "repository": {"uuid": str(self.repo)},
                    "message": "foreign"
                    if self.fault in {"marker", "cas"}
                    else self.intent.message,
                    "parents": [{"hash": "c" * 40 if self.fault == "parent" else PARENT}],
                }
            )
        if path.startswith("/diffstat/"):
            paths = list(self.outputs)
            if self.fault == "extra":
                paths.append("unrelated.txt")
            values = [
                {
                    "status": "modified",
                    "old": {"path": p, "type": "commit_file"},
                    "new": {"path": p, "type": "commit_file"},
                }
                for p in paths
            ]
            if self.fault == "foreign-next":
                return self.reply(payload={"values": values, "next": "https://evil.example/steal"})
            return self.reply(payload={"values": values})
        if path.startswith("/src/"):
            file_path = path.split("/", 3)[3]
            raw = self.outputs[file_path]
            if request.url.query == b"format=meta":
                attrs = (
                    ["executable"]
                    if self.fault == "attributes"
                    else list(
                        next(
                            item.attributes for item in self.intent.files if item.path == file_path
                        )
                    )
                )
                return self.reply(
                    payload={
                        "type": "commit_file",
                        "path": file_path,
                        "size": len(raw),
                        "attributes": attrs,
                        "commit": {"hash": COMMIT},
                    }
                )
            if self.fault == "bytes":
                raw = b"x" * len(raw)
            return self.reply(content=raw)
        raise AssertionError("unexpected resource")


async def with_provider(provider, callback):
    reads = BitbucketHttpAdapter(
        settings=Settings(),
        credential_leases=provider.credentials,
        transport=httpx.MockTransport(provider),
    )
    try:
        return await callback(BitbucketWriteAdapter(reads=reads))
    finally:
        await reads.aclose()


@pytest.mark.parametrize("fault", ["", "json"])
def test_commit_empty_or_json_201_is_verified_from_exact_remote_files(fault):
    provider = Provider(commit_intent("message"))
    provider.fault = fault

    async def exercise(adapter):
        result = await adapter.create_commit(object(), intent=provider.intent)
        assert result.state == "verified"
        assert result.receipt.commit_hash == COMMIT
        assert provider.outputs == {"message": provider.intent.files[0].content}
        assert provider.commits == provider.commit_posts == 1
        again = await adapter.create_commit(object(), intent=provider.intent)
        assert again == replace(result, provider_status=None)
        assert provider.commits == provider.commit_posts == 1

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize("fault", ["marker", "parent", "extra", "bytes", "attributes", "cas"])
def test_commit_refuses_foreign_or_modified_result(fault):
    provider = Provider()
    provider.fault = fault
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "conflict"
    assert result.receipt is None
    assert provider.commits == (0 if fault == "cas" else 1)


def test_commit_foreign_pagination_after_send_remains_unknown_without_leaking_token():
    provider = Provider()
    provider.fault = "foreign-next"
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "unknown"
    assert provider.commits == 1
    assert all(url.startswith("https://api.bitbucket.org/") for _, url in provider.requests)


@pytest.mark.parametrize(
    "fault, state",
    [("connect", "not_sent"), ("lost", "unknown"), ("rotation", "unknown"), ("large", "unknown")],
)
def test_branch_transport_failure_preserves_ambiguous_effect(fault, state):
    provider = Provider()
    provider.head = None
    provider.fault = fault
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert result.state == state
    assert "private" not in repr(result)
    assert provider.branch_posts == (0 if fault == "connect" else 1)


@pytest.mark.parametrize("head, state", [(PARENT, "verified"), ("c" * 40, "conflict")])
def test_branch_collision_never_posts_or_overwrites(head, state):
    provider = Provider()
    provider.head = head
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert result.state == state
    assert provider.branch_posts == 0 and provider.head == head


def test_branch_generation_rotation_before_send_blocks_mutation():
    provider = Provider()
    provider.head = None
    provider.credentials.generation = 8
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert result.state == "not_sent" and result.code == "authority_changed"
    assert provider.branch_posts == 0


def test_branch_wrong_repository_never_adopts_or_posts():
    provider = Provider()
    provider.repo = CHANGE_SET
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert result.state == "not_sent" and result.code == "repository_mismatch"
    assert provider.branch_posts == 0


def test_branch_missing_in_replaced_repository_never_posts():
    provider = Provider()
    provider.repo = CHANGE_SET
    provider.head = None
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert provider.branch_posts == 0
    assert result.state == "not_sent" and result.code == "repository_mismatch"


def test_commit_verification_connection_failure_after_201_stays_unknown():
    provider = Provider()
    provider.fault = "verification-connect"
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert provider.commits == provider.commit_posts == 1
    assert result.state == "unknown" and result.code == "connection_failed"


def test_commit_lost_reply_is_read_only_reconciled_and_never_recreated_when_missing():
    provider = Provider()
    provider.fault = "lost"

    async def exercise(adapter):
        result = await adapter.create_commit(object(), intent=provider.intent)
        assert result.state == "unknown" and provider.commits == 1
        provider.fault = ""
        provider.head = None
        missing = await adapter.reconcile_commit(object(), intent=provider.intent)
        assert missing.state == "unknown" and missing.code == "branch_missing"
        assert provider.commit_posts == 1 and provider.branch_posts == 0
        provider.head = COMMIT
        adopted = await adapter.reconcile_commit(object(), intent=provider.intent)
        assert adopted.state == "verified" and provider.commit_posts == 1

    asyncio.run(with_provider(provider, exercise))


def test_commit_delayed_original_at_old_parent_does_not_blindly_resend():
    provider = Provider()
    provider.fault = "delayed"

    async def exercise(adapter):
        assert (await adapter.create_commit(object(), intent=provider.intent)).state == "unknown"
        assert (await adapter.reconcile_commit(object(), intent=provider.intent)).state == "unknown"
        assert provider.commit_posts == 1 and provider.commits == 0
        provider.head = COMMIT
        provider.commits = 1
        provider.fault = ""
        assert (
            await adapter.reconcile_commit(object(), intent=provider.intent)
        ).state == "verified"
        assert provider.commit_posts == provider.commits == 1

    asyncio.run(with_provider(provider, exercise))


@pytest.mark.parametrize(
    "fault,state",
    [
        ("redirect", "unknown"),
        ("401", "not_sent"),
        ("403", "not_sent"),
        ("429", "not_sent"),
        ("503", "unknown"),
    ],
)
def test_branch_redirect_and_provider_status_never_follow_or_blind_retry(fault, state):
    provider = Provider()
    provider.head = None
    provider.fault = fault
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_branch(object(), intent=provider.intent.branch)
        )
    )
    assert result.state == state
    assert len([method for method, _ in provider.requests if method == "POST"]) == 1
    assert all(url.startswith("https://api.bitbucket.org/") for _, url in provider.requests)


@pytest.mark.parametrize(
    "invalid",
    [
        "empty",
        "too-many",
        "big-file",
        "big-total",
        "executable",
        "unknown-mode",
        "traversal",
        "duplicate",
        "unchanged",
        "digest",
    ],
)
def test_commit_invalid_or_excessive_scope_never_acquires_credentials(invalid):
    original = commit_intent()
    item = original.files[0]
    files = original.files
    if invalid == "empty":
        files = ()
    elif invalid == "too-many":
        files = tuple(replace(item, path=f"file-{i}") for i in range(501))
    elif invalid == "big-file":
        files = (replace(item, content=b"x" * (1_048_576 + 1)),)
    elif invalid == "big-total":
        files = tuple(replace(item, path=f"file-{i}", content=b"x" * 1_048_576) for i in range(21))
    elif invalid in {"executable", "unknown-mode"}:
        files = (replace(item, attributes=(invalid,)),)
    elif invalid == "traversal":
        files = (replace(item, path="../outside"),)
    elif invalid == "duplicate":
        files = (item, item)
    elif invalid == "unchanged":
        files = (replace(item, before_sha256=item.sha256),)
    provider = Provider(
        replace(
            original,
            files=files,
            manifest_digest="bad" if invalid == "digest" else original.manifest_digest,
        )
    )
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "not_sent" and result.code == "invalid_intent"
    assert provider.credentials.acquired == 0 and provider.requests == []


def test_commit_binary_classified_regular_file_preserves_bytes_and_attributes():
    original = commit_intent("it.lproj/Localizable.strings")
    item = replace(
        original.files[0],
        content=b"\xff\xfe" + '"key"="ciao";'.encode("utf-16-le"),
        attributes=("binary",),
    )
    provider = Provider(replace(original, files=(item,)))
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "verified"
    assert provider.outputs[item.path] == item.content


class PaginatedProvider(Provider):
    page_fault = ""

    def __call__(self, request):
        response = super().__call__(request)
        if request.method != "GET" or "/diffstat/" not in request.url.path:
            return response
        values = json.loads(response.content)["values"]
        per_page = 100 if len(values) > 2 else 1
        page = int(request.url.params.get("page", "1"))
        pages = math.ceil(len(values) / per_page)
        result = {"values": values[(page - 1) * per_page : page * per_page]}
        if self.page_fault == "duplicate" and page == 2:
            result["values"] = values[:1]
        if self.page_fault == "extra" and page == 2:
            result["values"] = [
                {
                    "status": "modified",
                    "old": {"type": "commit_file", "path": "extra"},
                    "new": {"type": "commit_file", "path": "extra"},
                }
            ]
        if page < pages and self.page_fault != "missing":
            result["next"] = str(request.url.copy_set_param("page", str(page + 1)))
        if self.page_fault == "cycle":
            result["next"] = str(request.url)
        if self.page_fault == "slug-next" and "next" in result:
            result["next"] = result["next"].replace(f"%7B{REPOSITORY}%7D", "mobile")
        return self.reply(payload=result)


def test_commit_diffstat_advertised_missing_files_cannot_verify_receipt():
    class IncompleteDiffstat(Provider):
        def __call__(self, request):
            response = super().__call__(request)
            if request.method == "GET" and "/diffstat/" in request.url.path:
                payload = json.loads(response.content)
                payload["size"] = len(payload["values"]) + 1
                return self.reply(payload=payload)
            return response

    provider = IncompleteDiffstat()
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "unknown" and result.receipt is None
    assert provider.commits == 1


@pytest.mark.parametrize("count", [1, 2, 500])
def test_commit_verifies_every_page_up_to_exact_file_limit(count):
    original = commit_intent()
    files = tuple(replace(original.files[0], path=f"locales/file-{i}.json") for i in range(count))
    provider = PaginatedProvider(replace(original, files=files))
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "verified"
    assert provider.outputs == {item.path: item.content for item in files}
    metadata_reads = [
        url for method, url in provider.requests if method == "GET" and "format=meta" in url
    ]
    assert len(metadata_reads) == count


@pytest.mark.parametrize(
    "fault, state",
    [
        ("cycle", "unknown"),
        ("duplicate", "conflict"),
        ("extra", "conflict"),
        ("missing", "conflict"),
    ],
)
def test_commit_incomplete_or_conflicting_later_page_never_becomes_receipt(fault, state):
    original = commit_intent()
    files = (original.files[0], replace(original.files[0], path="second.json"))
    provider = PaginatedProvider(replace(original, files=files))
    provider.page_fault = fault
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == state and result.receipt is None
    assert provider.commits == 1


def test_commit_quoted_multipart_field_path_is_rejected_before_send():
    original = commit_intent('locales/quoted"name.json')
    provider = Provider(original)
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "not_sent" and provider.requests == []


@pytest.mark.parametrize("operation", ["branch", "commit"])
def test_mutation_uses_repository_uuid_despite_concurrent_slug_reassignment(operation):
    class ReassignedSlugProvider(Provider):
        foreign_writes = 0

        def __call__(self, request):
            # A mutable slug now denotes a replacement; UUID still reaches the original.
            if (
                request.method == "POST"
                and request.url.path.split("/")[4] != "{" + str(REPOSITORY) + "}"
            ):
                self.foreign_writes += 1
            return super().__call__(request)

    provider = ReassignedSlugProvider()
    provider.head = None if operation == "branch" else PARENT

    async def exercise(adapter):
        if operation == "branch":
            return await adapter.create_branch(object(), intent=provider.intent.branch)
        return await adapter.create_commit(object(), intent=provider.intent)

    result = asyncio.run(with_provider(provider, exercise))
    assert result.state == "verified" and provider.foreign_writes == 0
    assert all(f"/%7B{REPOSITORY}%7D" in url for _, url in provider.requests)


def test_canonical_slug_pagination_is_rebound_to_frozen_uuid_before_credentials():
    original = commit_intent()
    files = (original.files[0], replace(original.files[0], path="second.json"))
    provider = PaginatedProvider(replace(original, files=files))
    provider.page_fault = "slug-next"
    result = asyncio.run(
        with_provider(
            provider, lambda adapter: adapter.create_commit(object(), intent=provider.intent)
        )
    )
    assert result.state == "verified"
    assert all(f"/%7B{REPOSITORY}%7D" in url for _, url in provider.requests)


@pytest.mark.parametrize("fault", ["", "extra", "bytes", "attributes", "foreign-next"])
def test_rebase_diff_and_file_verification_is_read_only_and_rejects_unapproved_changes(fault):
    from verboflex.integrations.bitbucket.writes import _WireError

    provider = Provider()
    provider.head = COMMIT
    provider.outputs = {f.path: f.content for f in provider.intent.files}
    provider.fault = fault

    async def exercise(adapter):
        if fault:
            with pytest.raises(_WireError):
                await adapter.verify_commit_files(object(), intent=provider.intent, commit=COMMIT)
        else:
            await adapter.verify_commit_files(object(), intent=provider.intent, commit=COMMIT)
            item = provider.intent.files[0]
            assert (
                await adapter.read_rebase_file(
                    object(),
                    context=provider.intent.branch.context,
                    commit=COMMIT,
                    path=item.path,
                    attributes=item.attributes,
                    max_bytes=1_048_576,
                )
                == item.content
            )
        assert all(method == "GET" for method, _ in provider.requests)
        assert provider.commit_posts == provider.branch_posts == 0

    asyncio.run(with_provider(provider, exercise))
