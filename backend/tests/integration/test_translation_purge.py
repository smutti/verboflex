"""Permanent deletion, rollback and surviving proposals on owned PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from tests.api import test_translation_workspace as workspace
from tests.integration.test_translation_import_activation import (
    _json_result,
    _qt_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
    _start_refresh_execution,
)
from verboflex.localization.importing.core import CanonicalParseResult
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.review import (
    ReviewActivity,
    TranslationComment,
    TranslationCommentMention,
    TranslationCommentVersion,
    TranslationProposal,
    TranslationProposalValue,
)
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.models.user import User
from verboflex.services import import_jobs, translation_purge
from verboflex.services.bitbucket_oauth import PULLREQUEST_WRITE_SCOPE

SEARCH, WORK = workspace.SEARCH, workspace.WORK
factory, clean_database = workspace.factory, workspace.clean_database


@pytest.fixture(autouse=True)
def connected(factory, clean_database):
    with factory.begin() as session:
        connection = session.get_one(BitbucketConnection, 1)
        connection.generation = 9
        connection.access_token_ciphertext = "encrypted-access"
        connection.scope_profile = PULLREQUEST_WRITE_SCOPE
        connection.provider_expires_at = datetime.now(UTC) + timedelta(hours=1)
        connection.connected_at = datetime.now(UTC)
        connection.revoked_at = None


def activate(factory, identity, repository, result, commit="a"):
    manifest, references = _stage_direct_manifest(
        factory,
        identity=identity,
        repository_id=repository,
        result=result,
        commit_hash=commit * 40,
    )
    assert import_jobs.finish_import_execution(
        factory, identity=identity, references=references, canonical_manifest_digest=manifest.digest
    )


@pytest.mark.parametrize("format", ["json", "qt"])
def test_successful_refresh_erases_values_keys_history_and_staging(factory, format):
    identity, repository = _seed_running_direct_import(factory)
    result = _json_result() if format == "json" else _qt_result(deleted=False)
    activate(factory, identity, repository, result)
    with factory() as session:
        old_ids = set(session.scalars(select(TranslationValue.id)))
        assert old_ids
        assert session.scalar(text("SELECT count(*) FROM staged_translation_values")) == 0
    successor = _start_refresh_execution(factory, identity)
    removed = CanonicalParseResult() if format == "json" else _qt_result(deleted=True)
    activate(factory, successor, repository, removed, "b")
    with factory() as session:
        for table in (
            "translation_values",
            "translation_keys",
            "translation_value_revisions",
            "translation_value_locators",
            "staged_translation_values",
        ):
            assert session.scalar(text(f"SELECT count(*) FROM {table}")) == 0, table
        assert session.scalar(select(LocalizationScope.language_counts)) == {}
    restored = _start_refresh_execution(factory, successor)
    activate(factory, restored, repository, result, "c")
    with factory() as session:
        assert old_ids.isdisjoint(session.scalars(select(TranslationValue.id)))
        assert (
            session.scalar(text("SELECT max(revision_number) FROM translation_value_revisions"))
            == 1
        )


def test_purge_failure_rolls_back_deleted_content_and_activation(factory, monkeypatch):
    identity, repository = _seed_running_direct_import(factory)
    activate(factory, identity, repository, _json_result())
    with factory() as session:
        ids = set(session.scalars(select(TranslationValue.id)))
        scope = session.scalar(select(LocalizationScope))
        before = (scope.read_version, scope.language_counts, scope.active_execution_id)
    original = translation_purge.purge_retired_translations

    def fail_after_purge(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected after physical purge")

    monkeypatch.setattr(translation_purge, "purge_retired_translations", fail_after_purge)
    successor = _start_refresh_execution(factory, identity)
    activate(factory, successor, repository, CanonicalParseResult(), "b")
    with factory() as session:
        assert set(session.scalars(select(TranslationValue.id))) == ids
        assert session.scalar(text("SELECT count(*) FROM translation_values WHERE is_deleted")) == 0
        scope = session.scalar(select(LocalizationScope))
        assert (scope.read_version, scope.language_counts, scope.active_execution_id) == before


def seed_proposal(session, members, actor):
    proposal = TranslationProposal(
        scope_id=members[0].scope_id,
        translation_key_id=members[0].translation_key_id,
        language=members[0].language,
        version=1,
        state="approved",
        created_by=actor,
        updated_by=actor,
    )
    session.add(proposal)
    session.flush()
    for member in members:
        WORK.revision(session, member, source=member.source_text, number=1)
        session.add(
            TranslationProposalValue(
                proposal_id=proposal.id,
                translation_key_id=member.translation_key_id,
                language=member.language,
                translation_value_id=member.id,
                selector_version=member.selector_version,
                selector_digest=member.selector_digest,
                basis_revision_number=1,
                basis_digest="a" * 64,
                proposed_text="Keep this proposal",
                grapheme_count=18,
            )
        )
    session.add(
        ReviewActivity(
            proposal_id=proposal.id,
            translation_key_id=members[0].translation_key_id,
            language=members[0].language,
            kind="proposal_saved",
            proposal_version=1,
            actor_id=actor,
            after_values=[{"translation_value_id": str(v.id), "text": "Old text"} for v in members],
        )
    )
    return proposal.id


@pytest.mark.parametrize("all_deleted", [False, True])
def test_purge_removes_dependent_history_but_keeps_live_proposals(factory, all_deleted):
    WORK.authority(factory)
    product, scope = SEARCH._seed_dataset(factory)
    SEARCH._add_group(
        factory,
        product_id=product,
        scope_id=scope,
        raw_key="retiring",
        language="fr",
        values=({"display_text": "One"}, {"display_text": "Two"}),
    )
    _, survivor, _ = WORK.seed(factory, name="Unchanged", target_revision=False)
    with factory.begin() as session:
        actor = session.scalar(select(User.id))
        members = list(
            session.scalars(select(TranslationValue).where(TranslationValue.scope_id == scope))
        )
        proposal = seed_proposal(session, members, actor)
        untouched = seed_proposal(session, [session.get_one(TranslationValue, survivor)], actor)
        comment = TranslationComment(
            scope_id=scope,
            translation_key_id=members[0].translation_key_id,
            language="fr",
            author_id=actor,
        )
        session.add(comment)
        session.flush()
        version = TranslationCommentVersion(
            comment_id=comment.id,
            translation_key_id=members[0].translation_key_id,
            language="fr",
            version_number=1,
            body="@User comment",
            author_id=actor,
        )
        session.add(version)
        session.flush()
        session.add(
            TranslationCommentMention(
                comment_version_id=version.id,
                mentioned_user_id=actor,
                start_utf16=0,
                end_utf16=5,
                display_text="@User",
            )
        )
        ids = [v.id for v in (members if all_deleted else members[:1])]
        for member in members if all_deleted else members[:1]:
            member.is_deleted = True
            member.deleted_at = datetime.now(UTC)
        key = members[0].translation_key_id
        if all_deleted:
            session.execute(
                text("UPDATE translation_keys SET is_deleted=true, deleted_at=now() WHERE id=:id"),
                {"id": key},
            )
    with factory.begin() as session:
        counts = translation_purge.purge_retired_translations(session, scope_id=scope, batch_size=1)
        assert counts["translation_values"] == len(ids)
    with factory() as session:
        assert session.get_one(TranslationProposal, untouched).state == "approved"
        assert (
            session.scalar(
                text("SELECT count(*) FROM translation_value_revisions WHERE value_id=ANY(:ids)"),
                {"ids": ids},
            )
            == 0
        )
        assert (
            session.scalar(select(ReviewActivity).where(ReviewActivity.proposal_id == proposal))
            is None
        )
        if all_deleted:
            assert session.get(TranslationProposal, proposal) is None
            assert session.get(TranslationComment, comment.id) is None
            assert session.get(TranslationCommentVersion, version.id) is None
            assert session.scalar(text("SELECT count(*) FROM translation_comment_mentions")) == 0
        else:
            pending = session.get_one(TranslationProposal, proposal)
            assert pending.state == "draft" and pending.reconciliation_required
            assert (
                len(pending.values) == 1 and pending.values[0].proposed_text == "Keep this proposal"
            )
            assert session.get(TranslationCommentVersion, version.id) is not None
    with factory.begin() as session:
        assert (
            sum(translation_purge.purge_retired_translations(session, scope_id=scope).values()) == 0
        )
    with factory.begin() as session, pytest.raises(DBAPIError, match="immutable"):
        session.execute(
            text("DELETE FROM translation_value_revisions WHERE value_id=:id"), {"id": survivor}
        )
