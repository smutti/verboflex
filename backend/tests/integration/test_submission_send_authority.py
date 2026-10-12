"""Current actor authority at the actual provider POST, after adapter preflight reads."""

# ruff: noqa: F811

import asyncio

import httpx
import pytest
from sqlalchemy import select

from tests.integration.test_bitbucket_pr_adapter import Provider as PullRequestProvider
from tests.integration.test_bitbucket_pr_adapter import with_provider as with_pr_provider
from tests.integration.test_bitbucket_write_adapter import SCOPE, Credentials
from tests.integration.test_bitbucket_write_adapter import Provider as CommitProvider
from tests.integration.test_bitbucket_write_adapter import with_provider as with_commit_provider
from tests.integration.test_preview_jobs import (
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.integration.test_submission_jobs import accepted
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter
from verboflex.integrations.bitbucket.writes import BitbucketWriteAdapter
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.role import Role
from verboflex.models.submission import ChangeSet
from verboflex.models.user import User
from verboflex.services.submission_jobs import execute_change_set


@pytest.mark.parametrize("mutation", ["disabled", "token", "role", "fence"])
def test_actor_revoked_during_adapter_preflight_never_reaches_provider_post(
    preview_session_factory, monkeypatch, mutation
):
    factory = preview_session_factory
    seed, reader, identity = accepted(factory, monkeypatch)
    with factory() as session:
        row = session.get(ChangeSet, identity)
        repository_id, source = row.provider_repository_id, row.source_branch
        generation = session.get(BitbucketConnection, 1).generation
    credentials = Credentials()
    credentials.generation = generation
    created = False
    revoked = False
    posts = []

    def provider(request):
        nonlocal created, revoked
        if request.method == "GET" and "/refs/branches/" in request.url.path:
            if not revoked:
                # This is inside create_branch's first awaited provider GET,
                # after the worker committed send_intent and released its locks.
                with factory.begin() as session:
                    actor = session.get(User, seed.actor_id)
                    if mutation == "disabled":
                        actor.is_active = False
                    elif mutation == "token":
                        actor.token_version += 1
                    elif mutation == "role":
                        actor.roles = [session.scalar(select(Role).where(Role.name == "viewer"))]
                        mirror_fixture_role(session, actor.id)
                    else:
                        session.get(ChangeSet, identity).execution_fence += 1
                revoked = True
            if not created:
                return httpx.Response(404, headers=SCOPE)
            return httpx.Response(
                200,
                headers=SCOPE,
                json={
                    "name": source,
                    "target": {"hash": "a" * 40, "repository": {"uuid": str(repository_id)}},
                },
            )
        if request.method == "GET":
            return httpx.Response(200, headers=SCOPE, json={"uuid": str(repository_id)})
        if request.method == "POST":
            with factory() as session:
                posts.append({"actor_active": session.get(User, seed.actor_id).is_active})
            created = True
            return httpx.Response(201, headers=SCOPE)
        raise AssertionError("unexpected provider operation")

    async def run():
        wire = BitbucketHttpAdapter(
            settings=Settings(),
            credential_leases=credentials,
            transport=httpx.MockTransport(provider),
        )
        try:
            await execute_change_set(
                factory,
                change_set_id=identity,
                reads=reader,
                writes=BitbucketWriteAdapter(reads=wire),
            )
        finally:
            await wire.aclose()

    asyncio.run(run())
    assert revoked
    assert posts == [], "new external mutation ran after independent actor revocation"
    with factory() as session:
        row = session.get(ChangeSet, identity)
        assert row.status in ({"running"} if mutation == "fence" else {"blocked", "failed"})
        assert row.branch_commit is None


@pytest.mark.parametrize("operation", ["branch", "commit", "pull_request"])
def test_each_real_adapter_mutation_checks_guard_after_reads_and_before_post(operation):
    provider = PullRequestProvider() if operation == "pull_request" else CommitProvider()
    if operation == "branch":
        provider.head = None
    observed = []

    def before_send():
        observed.append(tuple(provider.requests))
        return False

    async def run(adapter):
        if operation == "branch":
            result = await adapter.create_branch(
                object(), intent=provider.intent.branch, before_send=before_send
            )
        elif operation == "commit":
            result = await adapter.create_commit(
                object(), intent=provider.intent, before_send=before_send
            )
        else:
            result = await adapter.create_pull_request(
                object(), intent=provider.intent, before_send=before_send
            )
        assert result.state == "not_sent"
        assert result.code == "authority_changed"
        assert result.receipt is None
        assert len(observed) == 1 and observed[0], "guard must follow actual preflight reads"
        assert all(method == "GET" for method, _ in provider.requests)

    asyncio.run(
        with_pr_provider(provider, run)
        if operation == "pull_request"
        else with_commit_provider(provider, run)
    )
