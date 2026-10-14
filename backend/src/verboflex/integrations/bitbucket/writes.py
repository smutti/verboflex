"""Typed provider mutations driven only by persisted, generation-bound intents."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.urls import (
    BitbucketWriteOperation as Operation,
)
from verboflex.integrations.bitbucket.urls import (
    repository_metadata_url,
    repository_write_base_url,
    validate_bitbucket_write_url,
    validate_provider_commit_hash,
    validate_pull_request_url,
    validate_repository_relative_path,
)
from verboflex.services.bitbucket_oauth import (
    PULLREQUEST_WRITE_IMPLICATION_CLOSURE,
    PULLREQUEST_WRITE_SCOPE,
    BitbucketCredentialLease,
    OAuthConnectionUnavailable,
    OAuthGenerationRejected,
)

MAX_RESPONSE_BYTES = 1_048_576
MAX_FILES = 500
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 20 * 1_048_576
OutcomeState = Literal["not_sent", "verified", "unknown", "conflict"]


class WriteLeaseAuthority(Protocol):
    def acquire_repository_write_lease(
        self, session: Session, *, expected_generation: int
    ) -> BitbucketCredentialLease: ...


@dataclass(frozen=True, slots=True)
class WriteContext:
    repository_id: UUID
    workspace: str
    repository_slug: str
    change_set_id: UUID
    expected_generation: int
    work_branch: str | None = None

    @property
    def source_branch(self) -> str:
        return self.work_branch or f"verboflex/change-set-{self.change_set_id}"


@dataclass(frozen=True, slots=True)
class BranchIntent:
    context: WriteContext
    parent: str


@dataclass(frozen=True, slots=True)
class BranchReceipt:
    name: str
    commit_hash: str


@dataclass(frozen=True, slots=True)
class CommitFile:
    path: str
    content: bytes = field(repr=False)
    before_sha256: str
    attributes: tuple[str, ...] = ()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True, slots=True)
class CommitIntent:
    branch: BranchIntent
    manifest_digest: str
    files: tuple[CommitFile, ...]

    @property
    def message(self) -> str:
        return (
            "VerboFlex approved translations\n\n"
            f"VerboFlex-Change-Set: {self.branch.context.change_set_id}\n"
            f"VerboFlex-Manifest: {self.manifest_digest}\n"
        )


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    commit_hash: str
    parent: str
    branch: str
    manifest_digest: str


@dataclass(frozen=True, slots=True)
class PullRequestIntent:
    context: WriteContext
    source_commit: str
    target_branch: str
    target_head: str
    manifest_digest: str
    title: str = "VerboFlex approved translations"

    @property
    def description(self) -> str:
        return (
            "Approved translation changes.\n\n"
            f"VerboFlex-Change-Set: {self.context.change_set_id}\n"
            f"VerboFlex-Manifest: {self.manifest_digest}\n"
        )


@dataclass(frozen=True, slots=True)
class PullRequestReceipt:
    id: int
    url: str
    state: Literal["OPEN", "MERGED", "DECLINED", "SUPERSEDED"]
    repository_id: UUID
    source_branch: str
    source_commit: str
    target_branch: str
    target_commit: str


@dataclass(frozen=True, slots=True)
class WriteOutcome[T]:
    state: OutcomeState
    code: str
    receipt: T | None = None
    provider_status: int | None = None


@dataclass(slots=True)
class _PageEvidence:
    """A missing/contradictory page cannot establish a complete remote receipt."""

    count: int = 0
    size: int | None = None
    max_page_length: int = 100

    def observe(self, payload: dict[str, object], *, number: int, count: int) -> None:
        page = payload.get("page", number)
        pagelen = payload.get("pagelen", self.max_page_length)
        if (
            type(page) is not int
            or page != number
            or type(pagelen) is not int
            or not 1 <= pagelen <= self.max_page_length
            or count > pagelen
        ):
            raise _WireError("unknown", "incomplete_verification")
        if "size" in payload:
            size = payload["size"]
            if (
                type(size) is not int
                or not 0 <= size <= 5000
                or (self.size is not None and self.size != size)
            ):
                raise _WireError("unknown", "incomplete_verification")
            self.size = size
        self.count += count
        next_url = payload.get("next")
        if self.size is not None and (
            self.count > self.size or (next_url is None and self.count != self.size)
        ):
            raise _WireError("unknown", "incomplete_verification")
        if next_url is not None:
            if not isinstance(next_url, str):
                raise _WireError("unknown", "incomplete_verification")
            try:
                next_page = parse_qs(urlsplit(next_url).query).get("page")
            except ValueError:
                raise _WireError("unknown", "incomplete_verification") from None
            if next_page != [str(number + 1)]:
                raise _WireError("unknown", "incomplete_verification")


class _WireError(Exception):
    def __init__(self, state: OutcomeState, code: str, status: int | None = None) -> None:
        super().__init__("Bitbucket operation could not be verified")
        self.state, self.code, self.status = state, code, status


@dataclass(frozen=True, slots=True)
class _Reply:
    status: int
    body: bytes = field(repr=False)
    location: str | None = field(default=None, repr=False)


def _sha(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid commit identity")
    return validate_provider_commit_hash(value).lower()


def _object(payload: bytes) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(payload, object_pairs_hook=unique)
        if isinstance(value, dict):
            return cast(dict[str, object], value)
    except ValueError, RecursionError, UnicodeError:
        pass
    raise _WireError("unknown", "invalid_provider_response")


def _repository(value: object, expected: UUID) -> None:
    raw = value.get("uuid") if isinstance(value, dict) else None
    try:
        if isinstance(raw, str) and UUID(raw) == expected:
            return
    except ValueError:
        pass
    raise _WireError("unknown", "repository_mismatch")


class BitbucketWriteAdapter:
    """Borrow the installed read adapter's bounded, no-redirect HTTPX pool."""

    def __init__(self, *, reads: BitbucketHttpAdapter) -> None:
        self.reads = reads

    async def create_pull_request(
        self,
        session: Session,
        *,
        intent: PullRequestIntent,
        before_send: Callable[[], bool] | None = None,
    ) -> WriteOutcome[PullRequestReceipt]:
        """One ledger-authorized attempt; uncertain sends must only reconcile."""
        sent = False
        try:
            self._validate_pull_request(intent)
            context = intent.context
            source = await self._named_branch(session, context, context.source_branch)
            target = await self._named_branch(session, context, intent.target_branch)
            if source is None or target is None:
                return WriteOutcome("not_sent", "branch_missing")
            if (
                source.commit_hash != intent.source_commit
                or target.commit_hash != intent.target_head
            ):
                return WriteOutcome("conflict", "branch_advanced")
            url = self._base(context) + "/pullrequests"
            repository = {"uuid": "{" + str(context.repository_id) + "}"}
            sent = True
            reply = await self._wire(
                session,
                context=context,
                operation=Operation.CREATE_PULL_REQUEST,
                before_send=before_send,
                method="POST",
                url=url,
                expected_url=url,
                json_body={
                    "title": intent.title,
                    "description": intent.description,
                    "source": {
                        "repository": repository,
                        "branch": {"name": context.source_branch},
                        "commit": {"hash": intent.source_commit},
                    },
                    "destination": {
                        "repository": repository,
                        "branch": {"name": intent.target_branch},
                    },
                    "close_source_branch": False,
                },
            )
            if reply.status != 201:
                return WriteOutcome("unknown", "unexpected_status", provider_status=reply.status)
            receipt = await self._pull_request_receipt(session, _object(reply.body), intent)
            if reply.location is not None:
                expected = url + f"/{receipt.id}"
                location = self._bind_alias(context, reply.location)
                try:
                    validate_bitbucket_write_url(
                        location,
                        operation=Operation.READ_PULL_REQUEST,
                        method="GET",
                        expected_url=expected,
                    )
                except ValueError:
                    raise _WireError("unknown", "location_rejected", reply.status) from None
            return WriteOutcome("verified", "pull_request_verified", receipt, reply.status)
        except ValueError:
            return WriteOutcome("unknown" if sent else "not_sent", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                error.state if sent else "not_sent", error.code, provider_status=error.status
            )

    async def reconcile_pull_request(
        self, session: Session, *, intent: PullRequestIntent
    ) -> WriteOutcome[PullRequestReceipt]:
        """Exhaust bounded all-state pages; zero results never authorize another POST."""
        try:
            self._validate_pull_request(intent)
            context = intent.context
            query = urlencode(
                {
                    "pagelen": 50,
                    "state": ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"],
                    "q": f'source.branch.name = "{context.source_branch}"',
                },
                doseq=True,
            )
            first = self._base(context) + "/pullrequests?" + query
            url = first
            seen: set[str] = set()
            matches: list[PullRequestReceipt] = []
            pages = _PageEvidence(max_page_length=50)
            for number in range(1, 51):
                bound_url = self._bind_alias(context, url)
                if bound_url in seen:
                    return WriteOutcome("unknown", "incomplete_verification")
                seen.add(bound_url)
                reply = await self._wire(
                    session,
                    context=context,
                    operation=Operation.LIST_PULL_REQUESTS,
                    method="GET",
                    url=url,
                    expected_url=first,
                )
                if reply.status != 200:
                    return WriteOutcome(
                        "unknown", "incomplete_verification", provider_status=reply.status
                    )
                payload = _object(reply.body)
                values = payload.get("values")
                if not isinstance(values, list) or len(values) > 50:
                    return WriteOutcome("unknown", "incomplete_verification")
                pages.observe(payload, number=number, count=len(values))
                for value in values:
                    if not isinstance(value, dict):
                        return WriteOutcome("unknown", "invalid_provider_response")
                    if self._has_pr_marker(value.get("description"), intent):
                        matches.append(await self._pull_request_receipt(session, value, intent))
                        if len(matches) > 1:
                            return WriteOutcome("conflict", "multiple_pull_requests")
                next_url = payload.get("next")
                if next_url is None:
                    break
                if not isinstance(next_url, str):
                    return WriteOutcome("unknown", "incomplete_verification")
                url = next_url
            else:
                return WriteOutcome("unknown", "incomplete_verification")
            if not matches:
                return WriteOutcome("unknown", "pull_request_not_observed")
            return WriteOutcome("verified", "pull_request_verified", matches[0])
        except ValueError:
            return WriteOutcome("unknown", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                "conflict" if error.state == "conflict" else "unknown",
                error.code,
                provider_status=error.status,
            )

    async def read_pull_request(
        self,
        session: Session,
        *,
        intent: PullRequestIntent,
        pull_request_id: int,
        allow_rebased: bool = False,
    ) -> WriteOutcome[PullRequestReceipt]:
        """Refresh an existing identity even when its source branch no longer exists."""
        try:
            self._validate_pull_request(intent)
            if (
                type(pull_request_id) is not int
                or not 1 <= pull_request_id <= 9_007_199_254_740_991
            ):
                raise ValueError("Invalid pull request identity")
            url = self._base(intent.context) + f"/pullrequests/{pull_request_id}"
            reply = await self._wire(
                session,
                context=intent.context,
                operation=Operation.READ_PULL_REQUEST,
                method="GET",
                url=url,
                expected_url=url,
            )
            if reply.status != 200:
                return WriteOutcome(
                    "unknown", "pull_request_unavailable", provider_status=reply.status
                )
            receipt = await self._pull_request_receipt(
                session, _object(reply.body), intent, allow_rebased=allow_rebased
            )
            if receipt.id != pull_request_id:
                return WriteOutcome("conflict", "pull_request_mismatch")
            return WriteOutcome("verified", "pull_request_verified", receipt)
        except ValueError:
            return WriteOutcome("unknown", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                "conflict" if error.state == "conflict" else "unknown",
                error.code,
                provider_status=error.status,
            )

    @classmethod
    def _validate_pull_request(cls, intent: PullRequestIntent) -> None:
        if type(intent) is not PullRequestIntent:
            raise ValueError("Invalid intent")
        cls._validate_branch(BranchIntent(intent.context, intent.target_head))
        if (
            _sha(intent.source_commit) != intent.source_commit
            or intent.source_commit == intent.target_head
            or not isinstance(intent.target_branch, str)
            or not 1 <= len(intent.target_branch) <= 255
            or not intent.target_branch.isprintable()
            or "\\" in intent.target_branch
            or intent.target_branch == intent.context.source_branch
            or not isinstance(intent.manifest_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", intent.manifest_digest)
            or not isinstance(intent.title, str)
            or not 1 <= len(intent.title) <= 200
            or not intent.title.isprintable()
        ):
            raise ValueError("Invalid intent")

    @staticmethod
    def _has_pr_marker(description: object, intent: PullRequestIntent) -> bool:
        if not isinstance(description, str) or len(description) > 8192:
            return False
        lines = description.splitlines()
        return (
            lines.count(f"VerboFlex-Change-Set: {intent.context.change_set_id}") == 1
            and lines.count(f"VerboFlex-Manifest: {intent.manifest_digest}") == 1
        )

    async def _pull_request_receipt(
        self,
        session: Session,
        payload: dict[str, object],
        intent: PullRequestIntent,
        *,
        allow_rebased: bool = False,
    ) -> PullRequestReceipt:
        identity, state = payload.get("id"), payload.get("state")
        source, target = payload.get("source"), payload.get("destination")
        if (
            type(identity) is not int
            or not 1 <= identity <= 9_007_199_254_740_991
            or state not in ("OPEN", "MERGED", "DECLINED", "SUPERSEDED")
            or not self._has_pr_marker(payload.get("description"), intent)
            or not isinstance(source, dict)
            or not isinstance(target, dict)
        ):
            raise _WireError("conflict", "pull_request_mismatch")
        context = intent.context
        _repository(source.get("repository"), context.repository_id)
        _repository(target.get("repository"), context.repository_id)
        source_branch, target_branch = source.get("branch"), target.get("branch")
        source_commit, target_commit = source.get("commit"), target.get("commit")
        if (
            not isinstance(source_branch, dict)
            or source_branch.get("name") != context.source_branch
            or not isinstance(target_branch, dict)
            or target_branch.get("name") != intent.target_branch
            or not isinstance(source_commit, dict)
            or not isinstance(target_commit, dict)
        ):
            raise _WireError("conflict", "pull_request_mismatch")
        observed_source = await self._pull_request_commit(
            session, context, source_commit.get("hash")
        )
        if not allow_rebased and observed_source != intent.source_commit:
            raise _WireError("conflict", "pull_request_mismatch")
        observed_target = await self._pull_request_commit(
            session, context, target_commit.get("hash")
        )
        links = payload.get("links")
        html = links.get("html") if isinstance(links, dict) else None
        url = html.get("href") if isinstance(html, dict) else None
        try:
            if not isinstance(url, str):
                raise ValueError
            validate_pull_request_url(
                url,
                workspace=context.workspace,
                repository_slug=context.repository_slug,
                pull_request_id=identity,
            )
        except ValueError:
            raise _WireError("conflict", "pull_request_mismatch") from None
        return PullRequestReceipt(
            identity,
            url,
            state,
            context.repository_id,
            context.source_branch,
            observed_source,
            intent.target_branch,
            observed_target,
        )

    async def _pull_request_commit(
        self, session: Session, context: WriteContext, value: object
    ) -> str:
        """Resolve Bitbucket's abbreviated PR hashes before comparing full identities.

        Never trust a prefix match alone or follow a commit URL from the response.
        The UUID-bound commit endpoint must resolve it to one full repository commit.
        """
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{12,40}", value):
            raise _WireError("conflict", "pull_request_mismatch")
        if len(value) == 40:
            return _sha(value)
        url = self._base(context) + "/commit/" + value
        reply = await self._wire(
            session,
            context=context,
            operation=Operation.RESOLVE_PR_COMMIT,
            method="GET",
            url=url,
            expected_url=url,
        )
        if reply.status != 200:
            raise _WireError("unknown", "commit_unavailable", reply.status)
        payload = _object(reply.body)
        _repository(payload.get("repository"), context.repository_id)
        try:
            resolved = _sha(payload.get("hash"))
        except ValueError:
            raise _WireError("unknown", "invalid_provider_response") from None
        if not resolved.startswith(value):
            raise _WireError("conflict", "pull_request_mismatch")
        return resolved

    async def create_branch(
        self,
        session: Session,
        *,
        intent: BranchIntent,
        before_send: Callable[[], bool] | None = None,
    ) -> WriteOutcome[BranchReceipt]:
        sent = False
        try:
            self._validate_branch(intent)
            existing = await self._branch(session, intent)
            if existing is not None:
                return self._branch_result(existing, intent)
            context = intent.context
            repository_url = self._base(context)
            metadata = await self._wire(
                session,
                context=context,
                operation=Operation.READ_REPOSITORY,
                method="GET",
                url=repository_url,
                expected_url=repository_url,
            )
            _repository(_object(metadata.body), context.repository_id)
            url = self._base(context) + "/refs/branches"
            sent = True
            reply = await self._wire(
                session,
                context=context,
                operation=Operation.CREATE_BRANCH,
                before_send=before_send,
                url=url,
                expected_url=url,
                method="POST",
                expect_json=False,
                json_body={"name": context.source_branch, "target": {"hash": intent.parent}},
            )
            if reply.status not in {201, 409}:
                raise _WireError("unknown", "unexpected_status", reply.status)
            result = await self.reconcile_branch(session, intent=intent)
            return WriteOutcome(result.state, result.code, result.receipt, reply.status)
        except ValueError:
            return WriteOutcome("unknown" if sent else "not_sent", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                error.state if sent else "not_sent", error.code, provider_status=error.status
            )

    async def reconcile_branch(
        self, session: Session, *, intent: BranchIntent
    ) -> WriteOutcome[BranchReceipt]:
        """Read only; current credentials may capture evidence for an older intent."""
        try:
            self._validate_branch(intent)
            existing = await self._branch(session, intent)
            if existing is None:
                return WriteOutcome("unknown", "branch_missing")
            return self._branch_result(existing, intent)
        except ValueError:
            return WriteOutcome("not_sent", "invalid_intent")
        except _WireError as error:
            return WriteOutcome("unknown", error.code, provider_status=error.status)

    @staticmethod
    def _branch_result(receipt: BranchReceipt, intent: BranchIntent) -> WriteOutcome[BranchReceipt]:
        if receipt.commit_hash != intent.parent:
            return WriteOutcome("conflict", "branch_advanced")
        return WriteOutcome("verified", "branch_verified", receipt)

    async def create_commit(
        self,
        session: Session,
        *,
        intent: CommitIntent,
        before_send: Callable[[], bool] | None = None,
    ) -> WriteOutcome[CommitReceipt]:
        """Send once. The ledger must route uncertain sends to reconcile_commit."""
        sent = False
        try:
            self._validate_commit(intent)
            existing = await self._branch(session, intent.branch)
            if existing is None:
                return WriteOutcome("not_sent", "branch_missing")
            if existing.commit_hash != intent.branch.parent:
                return await self.reconcile_commit(session, intent=intent)
            context = intent.branch.context
            url = self._base(context) + "/src"
            sent = True
            reply = await self._wire(
                session,
                context=context,
                operation=Operation.CREATE_COMMIT,
                before_send=before_send,
                method="POST",
                url=url,
                expected_url=url,
                expect_json=False,
                data={
                    "branch": context.source_branch,
                    "parents": intent.branch.parent,
                    "message": intent.message,
                },
                files=[
                    (
                        "/" + item.path,
                        (item.path.rsplit("/", 1)[-1], item.content, "application/octet-stream"),
                    )
                    for item in intent.files
                ],
            )
            if reply.status not in {201, 409}:
                raise _WireError("unknown", "unexpected_status", reply.status)
            result = await self.reconcile_commit(session, intent=intent)
            return WriteOutcome(result.state, result.code, result.receipt, reply.status)
        except ValueError:
            return WriteOutcome("unknown" if sent else "not_sent", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                error.state if sent else "not_sent", error.code, provider_status=error.status
            )

    async def reconcile_commit(
        self, session: Session, *, intent: CommitIntent
    ) -> WriteOutcome[CommitReceipt]:
        """No automatic resend, including a missing branch or delayed original send."""
        try:
            self._validate_commit(intent)
            existing = await self._branch(session, intent.branch)
            if existing is None:
                return WriteOutcome("unknown", "branch_missing")
            if existing.commit_hash == intent.branch.parent:
                return WriteOutcome("unknown", "commit_not_observed")
            receipt = await self._verify_commit(session, intent, existing.commit_hash)
            return WriteOutcome("verified", "commit_verified", receipt)
        except ValueError:
            return WriteOutcome("not_sent", "invalid_intent")
        except _WireError as error:
            return WriteOutcome(
                "conflict" if error.state == "conflict" else "unknown",
                error.code,
                provider_status=error.status,
            )

    async def _verify_commit(
        self, session: Session, intent: CommitIntent, commit: str
    ) -> CommitReceipt:
        context = intent.branch.context
        url = self._base(context) + "/commit/" + commit
        payload = _object(
            (
                await self._wire(
                    session,
                    context=context,
                    operation=Operation.READ_COMMIT,
                    method="GET",
                    url=url,
                    expected_url=url,
                )
            ).body
        )
        _repository(payload.get("repository"), context.repository_id)
        parents = payload.get("parents")
        if (
            payload.get("hash") != commit
            or payload.get("message") != intent.message
            or not isinstance(parents, list)
            or len(parents) != 1
            or not isinstance(parents[0], dict)
            or parents[0].get("hash") != intent.branch.parent
        ):
            raise _WireError("conflict", "commit_mismatch")
        await self.verify_commit_files(session, intent=intent, commit=commit)
        return CommitReceipt(
            commit, intent.branch.parent, context.source_branch, intent.manifest_digest
        )

    async def verify_commit_files(
        self, session: Session, *, intent: CommitIntent, commit: str
    ) -> None:
        """Verify the complete diff and bytes at immutable heads; never perform a write."""
        context = intent.branch.context
        expected = {item.path for item in intent.files if item.sha256 != item.before_sha256}
        query = urlencode({"pagelen": 100, "renames": "false", "topic": "false"})
        first = f"{self._base(context)}/diffstat/{commit}..{intent.branch.parent}?{query}"
        url = first
        seen_urls: set[str] = set()
        paths: set[str] = set()
        pages = _PageEvidence()
        for number in range(1, 51):
            if url in seen_urls:
                raise _WireError("unknown", "incomplete_verification")
            seen_urls.add(url)
            page = _object(
                (
                    await self._wire(
                        session,
                        context=context,
                        operation=Operation.READ_DIFFSTAT,
                        method="GET",
                        url=url,
                        expected_url=first,
                    )
                ).body
            )
            values = page.get("values")
            if not isinstance(values, list) or len(values) > 100:
                raise _WireError("unknown", "invalid_provider_response")
            pages.observe(page, number=number, count=len(values))
            for value in values:
                if not isinstance(value, dict) or value.get("status") != "modified":
                    raise _WireError("conflict", "changed_files_mismatch")
                old, new = value.get("old"), value.get("new")
                path = new.get("path") if isinstance(new, dict) else None
                if (
                    not isinstance(old, dict)
                    or old.get("type") != "commit_file"
                    or not isinstance(new, dict)
                    or new.get("type") != "commit_file"
                    or not isinstance(path, str)
                    or old.get("path") != path
                    or path not in expected
                    or path in paths
                    or len(paths) >= MAX_FILES
                ):
                    raise _WireError("conflict", "changed_files_mismatch")
                paths.add(path)
            next_url = page.get("next")
            if next_url is None:
                break
            if not isinstance(next_url, str):
                raise _WireError("unknown", "invalid_provider_response")
            url = next_url
        else:
            raise _WireError("unknown", "incomplete_verification")
        if paths != expected:
            raise _WireError("conflict", "changed_files_mismatch")
        for item in intent.files:
            path = "/".join(quote(part, safe="") for part in item.path.split("/"))
            file_url = f"{self._base(context)}/src/{commit}/{path}"
            metadata_url = file_url + "?format=meta"
            metadata = _object(
                (
                    await self._wire(
                        session,
                        context=context,
                        operation=Operation.READ_METADATA,
                        method="GET",
                        url=metadata_url,
                        expected_url=metadata_url,
                    )
                ).body
            )
            metadata_commit = metadata.get("commit")
            if (
                metadata.get("type") != "commit_file"
                or metadata.get("path") != item.path
                or type(metadata.get("size")) is not int
                or metadata.get("size") != len(item.content)
                or metadata.get("attributes") != list(item.attributes)
                or not isinstance(metadata_commit, dict)
                or metadata_commit.get("hash") != commit
            ):
                raise _WireError("conflict", "written_file_mismatch")
            raw = await self._wire(
                session,
                context=context,
                operation=Operation.READ_FILE,
                method="GET",
                url=file_url,
                expected_url=file_url,
                expect_json=False,
                max_bytes=len(item.content),
            )
            if raw.body != item.content:
                raise _WireError("conflict", "written_file_mismatch")

    async def read_rebase_file(
        self,
        session: Session,
        *,
        context: WriteContext,
        commit: str,
        path: str,
        attributes: tuple[str, ...],
        max_bytes: int,
    ) -> bytes:
        validate_repository_relative_path(path)
        _sha(commit)
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        url = f"{self._base(context)}/src/{commit}/{encoded}"
        meta_url = url + "?format=meta"
        meta = _object(
            (
                await self._wire(
                    session,
                    context=context,
                    operation=Operation.READ_METADATA,
                    method="GET",
                    url=meta_url,
                    expected_url=meta_url,
                )
            ).body
        )
        meta_commit = meta.get("commit")
        size = meta.get("size")
        if (
            meta.get("type") != "commit_file"
            or meta.get("path") != path
            or meta.get("attributes") != list(attributes)
            or not isinstance(meta_commit, dict)
            or meta_commit.get("hash") != commit
            or type(size) is not int
            or not 0 <= size <= min(MAX_FILE_BYTES, max_bytes)
        ):
            raise _WireError("conflict", "written_file_mismatch")
        raw = await self._wire(
            session,
            context=context,
            operation=Operation.READ_FILE,
            method="GET",
            url=url,
            expected_url=url,
            expect_json=False,
            max_bytes=size,
        )
        if len(raw.body) != size:
            raise _WireError("unknown", "incomplete_verification")
        return raw.body

    async def read_pr_merge_status(
        self,
        session: Session,
        *,
        context: WriteContext,
        pull_request_id: int,
    ) -> Literal["clean", "conflicts", "unknown"]:
        url = self._base(context) + f"/pullrequests/{pull_request_id}/mergeability/checks"
        payload = _object(
            (
                await self._wire(
                    session,
                    context=context,
                    operation=Operation.READ_MERGEABILITY,
                    method="GET",
                    url=url,
                    expected_url=url,
                )
            ).body
        )
        values = payload.get("values")
        if not isinstance(values, list) or len(values) > 100 or payload.get("next"):
            return "unknown"
        checks = [
            v for v in values if isinstance(v, dict) and v.get("type") == "git_mergeability_check"
        ]
        if len(checks) != 1:
            return "unknown"
        check = checks[0]
        if check.get("status") == "FAILED" and check.get("reason") == "conflicts":
            return "conflicts"
        if (
            check.get("status") == "PASSED"
            and check.get("reason") == "clean"
            and check.get("blocking") is False
        ):
            return "clean"
        return "unknown"

    @staticmethod
    def _base(context: WriteContext) -> str:
        return repository_write_base_url(
            workspace=context.workspace, repository_id=context.repository_id
        )

    @classmethod
    def _validate_branch(cls, intent: BranchIntent) -> None:
        if type(intent) is not BranchIntent or type(intent.context) is not WriteContext:
            raise ValueError("Invalid intent")
        context = intent.context
        if context.work_branch is not None:
            from verboflex.services.branch_workflow import validate_branch

            validate_branch(context.work_branch)
        if (
            type(context.repository_id) is not UUID
            or type(context.change_set_id) is not UUID
            or not isinstance(context.workspace, str)
            or not isinstance(context.repository_slug, str)
            or type(context.expected_generation) is not int
            or context.expected_generation < 1
            or _sha(intent.parent) != intent.parent
        ):
            raise ValueError("Invalid intent")
        cls._base(context)
        repository_metadata_url(
            workspace=context.workspace, repository_slug=context.repository_slug
        )

    @classmethod
    def _validate_commit(cls, intent: CommitIntent) -> None:
        if type(intent) is not CommitIntent:
            raise ValueError("Invalid intent")
        cls._validate_branch(intent.branch)
        if (
            not isinstance(intent.manifest_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", intent.manifest_digest)
            or type(intent.files) is not tuple
            or not 1 <= len(intent.files) <= MAX_FILES
        ):
            raise ValueError("Invalid intent")
        paths: set[str] = set()
        total = 0
        for item in intent.files:
            if type(item) is not CommitFile:
                raise ValueError("Invalid intent")
            validate_repository_relative_path(item.path)
            if (
                item.path in paths
                # HTTPX escapes quotes in multipart field names as %22; do not
                # risk uploading an unintended sibling path at the provider.
                or '"' in item.path
                or type(item.content) is not bytes
                or len(item.content) > MAX_FILE_BYTES
                or item.attributes not in ((), ("binary",))
                or not isinstance(item.before_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", item.before_sha256)
            ):
                raise ValueError("Invalid intent")
            paths.add(item.path)
            total += len(item.content)
        if total > MAX_TOTAL_BYTES or all(
            item.sha256 == item.before_sha256 for item in intent.files
        ):
            raise ValueError("Invalid intent")

    async def _branch(self, session: Session, intent: BranchIntent) -> BranchReceipt | None:
        return await self._named_branch(session, intent.context, intent.context.source_branch)

    async def _named_branch(
        self, session: Session, context: WriteContext, branch: str
    ) -> BranchReceipt | None:
        url = f"{self._base(context)}/refs/branches/{quote(branch, safe='')}"
        reply = await self._wire(
            session,
            context=context,
            operation=Operation.READ_BRANCH,
            method="GET",
            url=url,
            expected_url=url,
        )
        if reply.status == 404:
            return None
        payload = _object(reply.body)
        target = payload.get("target")
        if payload.get("name") != branch or not isinstance(target, dict):
            raise _WireError("unknown", "branch_mismatch")
        _repository(target.get("repository"), context.repository_id)
        try:
            commit = _sha(target.get("hash"))
        except ValueError:
            raise _WireError("unknown", "invalid_provider_response") from None
        return BranchReceipt(branch, commit)

    @classmethod
    def _bind_alias(cls, context: WriteContext, url: str) -> str:
        alias = repository_metadata_url(
            workspace=context.workspace, repository_slug=context.repository_slug
        )
        return cls._base(context) + url[len(alias) :] if url.startswith(alias + "/") else url

    async def _wire(
        self,
        session: Session,
        *,
        context: WriteContext,
        before_send: Callable[[], bool] | None = None,
        operation: Operation,
        method: str,
        url: str,
        expected_url: str,
        expect_json: bool = True,
        max_bytes: int = MAX_RESPONSE_BYTES,
        json_body: dict[str, object] | None = None,
        data: dict[str, str] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    ) -> _Reply:
        # Provider pagination may emit the captured canonical slug. Never send
        # credentials to that mutable alias: rebind its exact resource to UUID.
        if operation in {Operation.READ_DIFFSTAT, Operation.LIST_PULL_REQUESTS}:
            url = self._bind_alias(context, url)
        try:
            validate_bitbucket_write_url(
                url, operation=operation, method=method, expected_url=expected_url
            )
        except ValueError:
            raise _WireError("not_sent", "provider_url_rejected") from None
        sent = False
        status: int | None = None
        failure = _WireError("not_sent", "provider_unavailable")
        try:
            authority = self.reads._credential_leases
            if method == "POST":
                lease = cast(WriteLeaseAuthority, authority).acquire_repository_write_lease(
                    session, expected_generation=context.expected_generation
                )
                if lease.generation != context.expected_generation:
                    raise OAuthGenerationRejected("generation rejected")
            else:
                lease = authority.acquire_repository_read_lease(session)
            authority.require_current_repository_read_lease(session, lease)
            if method == "POST" and before_send is not None and not before_send():
                raise _WireError("not_sent", "authority_changed")
            sent = True
            async with self.reads._client.stream(
                method,
                url,
                headers={"Authorization": f"Bearer {lease.access_token}"},
                json=json_body,
                data=data,
                files=files,
            ) as response:
                status = response.status_code
                if response.is_redirect:
                    raise _WireError("unknown", "redirect_rejected", status)
                # Exact not-found reads and CAS conflict are inspected by callers.
                if (method == "GET" and status == 404) or (method == "POST" and status == 409):
                    authority.require_current_repository_read_lease(session, lease)
                    return _Reply(status, b"")
                if not 200 <= status < 300:
                    definitive = method == "POST" and status in {
                        400,
                        401,
                        403,
                        404,
                        405,
                        413,
                        415,
                        422,
                        429,
                    }
                    raise _WireError(
                        "not_sent" if definitive else "unknown", "provider_rejected", status
                    )
                raw_scopes = response.headers.get("x-oauth-scopes", "").replace(",", " ").split()
                scopes = frozenset(raw_scopes)
                if (
                    PULLREQUEST_WRITE_SCOPE not in scopes
                    or not scopes.issubset(PULLREQUEST_WRITE_IMPLICATION_CLOSURE)
                    or len(scopes) != len(raw_scopes)
                ):
                    raise _WireError("unknown", "scope_rejected", status)
                if response.headers.get("content-encoding") not in {None, "identity"}:
                    raise _WireError("unknown", "encoding_rejected", status)
                if (
                    expect_json
                    and response.headers.get("content-type", "").split(";", 1)[0]
                    != "application/json"
                ):
                    raise _WireError("unknown", "invalid_provider_response", status)
                declared = response.headers.get("content-length")
                if declared is not None and (
                    not declared.isascii()
                    or not declared.isdecimal()
                    or len(declared) > 12
                    or int(declared) > max_bytes
                ):
                    raise _WireError("unknown", "response_limit", status)
                chunks: list[bytes] = []
                count = 0
                if response.is_stream_consumed:
                    if len(response.content) > max_bytes:
                        raise _WireError("unknown", "response_limit", status)
                    chunks.append(response.content)
                else:
                    async for chunk in response.aiter_raw():
                        count += len(chunk)
                        if count > max_bytes:
                            raise _WireError("unknown", "response_limit", status)
                        chunks.append(chunk)
                body = b"".join(chunks)
                location = response.headers.get("location")
                if location is not None and len(location) > 4096:
                    raise _WireError("unknown", "response_limit", status)
            authority.require_current_repository_read_lease(session, lease)
            return _Reply(status, body, location)
        except _WireError:
            raise
        except OAuthGenerationRejected, OAuthConnectionUnavailable:
            failure = _WireError("unknown" if sent else "not_sent", "authority_changed", status)
        except httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout:
            failure = _WireError("not_sent", "connection_failed", status)
        except httpx.TimeoutException:
            failure = _WireError("unknown", "timeout", status)
        except Exception:
            failure = _WireError("unknown" if sent else "not_sent", "provider_unavailable", status)
        raise failure
