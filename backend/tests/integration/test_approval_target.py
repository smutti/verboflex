"""Only verified target contents clear the badge for the exact approved version."""

# ruff: noqa: F811

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.test_branch_workflow import approve, run, save_draft, setup
from tests.integration.test_preview_jobs import (  # noqa: F401
    clean_preview_database,
    preview_session_factory,
)
from verboflex.integrations.bitbucket.client import BitbucketBranch, BitbucketProviderReadError
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.review import TranslationProposal
from verboflex.schemas.translation_workspace import TranslationKeySearchQuery
from verboflex.services.approval_target import refresh_approval_target
from verboflex.services.translation_search import (
    TranslationSearchFilters,
    get_translation_group,
    search_translations,
)
from verboflex.services.translation_workspace import search_translation_keys
from verboflex.worker.branch_tasks import dispatchable_jobs


def check(factory, remote, job):
    asyncio.run(refresh_approval_target(factory, job_id=job, reads=remote))


def target_at(remote, commit):
    async def branch(session, **kw):
        assert kw["branch"] == remote.target_branch
        return BitbucketBranch(kw["branch"], commit)

    remote.resolve_repository_branch = branch


def projections(factory, seed):
    with factory() as session:
        result = search_translations(
            session,
            principal_id=seed.actor_id,
            filters=TranslationSearchFilters(product_id=seed.product_id, language="it"),
            cursor=None,
            cursor_secret="synthetic cursor secret",
        )
        # A removed plural member can have been the group's representative UUID.
        # Resolve the current server-issued group before checking its detail.
        group = next(item for item in result.items if item.pending_change)
        summary = group.pending_change
        detail = get_translation_group(session, group_id=group.id).pending_change
    with factory() as session:
        page = search_translation_keys(
            session,
            principal_id=seed.actor_id,
            query=TranslationKeySearchQuery(product_id=seed.product_id, visible_languages=["it"]),
            cursor_secret="synthetic cursor secret",
        )
        slot = next(slot for item in page.items for slot in item.slots if slot.pending_change)
    return detail, summary, slot.pending_change


def test_target_contents_clear_badge_and_revert_restores_it(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Approved text")
    assert run(factory, remote, job) == ("committed", None)
    with factory() as session:
        approved_at = session.get_one(TranslationProposal, seed.proposal_id).updated_at
    check(factory, remote, job)
    for status in projections(factory, seed):
        assert status.state == "approved" and status.target_branch == "main"
        assert not status.target_integrated
    target_at(remote, remote.head)
    check(factory, remote, job)
    check(factory, remote, job)
    for status in projections(factory, seed):
        assert status.target_integrated and not status.reconciliation_required
    target_at(remote, "a" * 40)
    check(factory, remote, job)
    assert all(not status.target_integrated for status in projections(factory, seed))
    assert len(remote.commits) == 1 and not remote.prs
    with factory() as session:
        assert session.get_one(BranchJob, job).state == "committed"
        assert session.get_one(TranslationProposal, seed.proposal_id).updated_at == approved_at


@pytest.mark.parametrize(
    "replacement",
    [
        b'<resources><plurals name="hello"><item quantity="one">Approved text</item>'
        b'<item quantity="other">Different text</item></plurals></resources>',
        b'<resources><string name="hello">Approved text</string></resources>',
        b"<resources/>",
        b'<resources><plurals name="hello"><item quantity="one">Approved text</item>'
        b'</plurals><plurals name="hello"><item quantity="other">Approved text</item>'
        b"</plurals></resources>",
    ],
)
def test_partial_missing_or_ambiguous_target_stays_visible(
    preview_session_factory, monkeypatch, replacement
):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Approved text")
    run(factory, remote, job)
    remote.versions[remote.head]["app/res/values-it/strings.xml"] = replacement
    target_at(remote, remote.head)
    check(factory, remote, job)
    assert all(not status.target_integrated for status in projections(factory, seed))


def test_later_edit_during_target_read_is_not_marked_integrated(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "First text")
    run(factory, remote, job)
    target_at(remote, remote.head)
    original = remote.read_repository_source_file

    async def edit_during_read(session, **kw):
        save_draft(factory, seed, "New draft")
        return await original(session, **kw)

    remote.read_repository_source_file = edit_during_read
    check(factory, remote, job)
    for status in projections(factory, seed):
        assert status.state == "draft" and not status.target_integrated
        assert status.target_branch is None
    with factory.begin() as session:
        session.get_one(BranchJob, job).updated_at = datetime.now(UTC) - timedelta(minutes=2)
    with factory() as session:
        assert job not in dispatchable_jobs(session)


def test_provider_failure_keeps_last_observation_without_resending(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Approved text")
    run(factory, remote, job)
    target_at(remote, remote.head)
    check(factory, remote, job)

    async def unavailable(session, **kw):
        raise BitbucketProviderReadError()

    remote.resolve_repository_branch = unavailable
    check(factory, remote, job)
    with factory.begin() as session:
        row = session.get_one(BranchJob, job)
        assert row.state == "committed" and row.owner is None
        row.updated_at = datetime.now(UTC) - timedelta(minutes=2)
        assert session.get_one(TranslationProposal, seed.proposal_id).target_commit_hash
    with factory() as session:
        assert job in dispatchable_jobs(session)
    assert len(remote.commits) == 1 and not remote.prs


@pytest.mark.parametrize("integrated", [False, True])
def test_working_branch_reimport_preserves_approval_and_target_status(
    preview_session_factory, monkeypatch, integrated
):
    from tests.integration.test_confirmed_layout_refresh import _run

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch, work_branch="main", target_branch="release/stable")
    job = approve(factory, seed, "Approved text")
    run(factory, remote, job)
    if integrated:
        target_at(remote, remote.head)
    check(factory, remote, job)
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    for status in projections(factory, seed):
        assert status.state == "approved" and status.target_branch == "release/stable"
        assert status.target_integrated is integrated and not status.reconciliation_required
    assert len(remote.commits) == 1 and not remote.prs
    # Editing the reimported text starts a fresh pending version, retaining history.
    save_draft(factory, seed, "Next draft")
    for status in projections(factory, seed):
        assert status.state == "draft" and not status.target_integrated
    remote.resolve_repository_branch = type(remote).resolve_repository_branch.__get__(remote)
    second = approve(factory, seed, "Next approval")
    assert run(factory, remote, second) == ("committed", None)
    assert run(factory, remote, second) == ("committed", None)
    assert len(remote.commits) == 2 and not remote.prs
    assert remote.commits[1].branch.parent != remote.commits[0].branch.parent


def test_removed_target_file_restores_awaiting_badge(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch)
    job = approve(factory, seed, "Approved text")
    run(factory, remote, job)
    target_at(remote, remote.head)
    check(factory, remote, job)

    async def missing(session, **kw):
        raise BitbucketProviderReadError(kind="not_found", provider_status=404)

    remote.read_repository_source_metadata = missing
    check(factory, remote, job)
    assert all(not status.target_integrated for status in projections(factory, seed))


@pytest.mark.parametrize("drift", ["text", "removed_member"])
def test_working_branch_reimport_flags_changes_to_approved_values(
    preview_session_factory, monkeypatch, drift
):
    from tests.integration.test_confirmed_layout_refresh import _run

    factory = preview_session_factory
    seed, remote = setup(factory, monkeypatch, work_branch="main", target_branch="release/stable")
    job = approve(factory, seed, "Approved text")
    assert run(factory, remote, job) == ("committed", None)
    seed.adapter.files = dict(remote.versions[remote.head])
    path = "app/res/values-it/strings.xml"
    if drift == "text":
        seed.adapter.files[path] = seed.adapter.files[path].replace(
            b"Approved text", b"External edit", 1
        )
    else:
        seed.adapter.files[path] = seed.adapter.files[path].replace(
            b'<item quantity="other">Approved text</item>', b""
        )
    seed.adapter.commit_hashes = ["b" * 40]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    for status in projections(factory, seed):
        # Removing a member reopens the proposal through the import purge path.
        assert status.state == ("draft" if drift == "removed_member" else "approved")
        assert status.reconciliation_required and not status.target_integrated
    assert len(remote.commits) == 1 and not remote.prs
