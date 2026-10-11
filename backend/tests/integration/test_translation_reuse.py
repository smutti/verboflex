"""Suggestions resolve live versions and never reuse deleted/stale proposal content."""

from uuid import uuid4

import pytest

from tests.integration.test_preview_jobs import clean_preview_database, preview_session_factory
from tests.integration.test_writeback_authority import seed_writeback_authority
from verboflex.models.review import TranslationProposal
from verboflex.schemas.reuse import ReuseQuery, ReuseResolve
from verboflex.services.translation_authoring import AuthoringError
from verboflex.services.translation_reuse import resolve, suggest

__all__ = ["clean_preview_database", "preview_session_factory"]


def query(**changes):
    return ReuseQuery(
        source_text="Hello",
        source_language="en",
        target_language="it",
        format="android_xml",
        selector_kind="android_quantity",
        selector_form="one",
        **changes,
    )


def test_exact_approved_suggestion_and_stale_application(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        page = suggest(session, product_id=seed.product_id, actor_id=seed.actor_id, query=query())
        assert len(page.items) == 1
        item = page.items[0]
        assert item.match_percent == 100 and item.target_text == "Ok"
        assert item.origin == "approved_draft"
        payload = ReuseResolve(
            query=query(),
            source_value_id=item.source_value_id,
            target_value_id=item.target_value_id,
            expected_digest=item.digest,
        )
        assert (
            resolve(session, product_id=seed.product_id, actor_id=seed.actor_id, data=payload)
            == item
        )
    with factory.begin() as session:
        proposal = session.get(TranslationProposal, seed.proposal_id)
        proposal.state = "draft"
        proposal.version += 1
    with factory.begin() as session, pytest.raises(AuthoringError, match="changed"):
        resolve(session, product_id=seed.product_id, actor_id=seed.actor_id, data=payload)
    with factory.begin() as session:
        fresh = suggest(session, product_id=seed.product_id, actor_id=seed.actor_id, query=query())
        assert fresh.items[0].target_text == "Ciao"
        assert fresh.items[0].origin == "repository"


def test_fuzzy_is_not_exact_and_obeys_form_and_project(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        q = query().model_copy(update={"source_text": "Hello!"})
        page = suggest(session, product_id=seed.product_id, actor_id=seed.actor_id, query=q)
        assert page.items and all(i.match_percent < 100 for i in page.items)
        assert (
            suggest(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                query=q.model_copy(update={"fuzzy": False}),
            ).items
            == []
        )
        assert (
            suggest(
                session,
                product_id=seed.product_id,
                actor_id=seed.actor_id,
                query=query().model_copy(update={"selector_form": "two"}),
            ).items
            == []
        )
    with factory.begin() as session, pytest.raises(AuthoringError):
        suggest(session, product_id=uuid4(), actor_id=seed.actor_id, query=query())


def test_refresh_physically_removes_suggestion_and_invalidates_resolve(
    preview_session_factory, monkeypatch
):
    from sqlalchemy import select

    from tests.integration.test_confirmed_layout_refresh import _run
    from verboflex.models.translation import TranslationValue

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        item = suggest(
            session, product_id=seed.product_id, actor_id=seed.actor_id, query=query()
        ).items[0]
    payload = ReuseResolve(
        query=query(),
        source_value_id=item.source_value_id,
        target_value_id=item.target_value_id,
        expected_digest=item.digest,
    )
    seed.adapter.files = {
        path: content.replace(b'name="hello"', b'name="replacement"')
        .replace(b"Hello", b"Goodbye")
        .replace(b"Ciao", b"Addio")
        for path, content in seed.adapter.files.items()
    }
    seed.adapter.commit_hashes = ["b" * 40]
    _run(factory, seed.product_id, seed.mapping_id)
    with factory.begin() as session:
        assert (
            session.scalar(
                select(TranslationValue.id).where(TranslationValue.id == item.target_value_id)
            )
            is None
        )
        assert not suggest(
            session, product_id=seed.product_id, actor_id=seed.actor_id, query=query()
        ).items
    with factory.begin() as session, pytest.raises(AuthoringError, match="changed"):
        resolve(session, product_id=seed.product_id, actor_id=seed.actor_id, data=payload)
