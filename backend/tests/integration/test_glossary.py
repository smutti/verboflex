from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.integration.test_preview_jobs import clean_preview_database, preview_session_factory
from tests.integration.test_writeback_authority import seed_writeback_authority
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.models.glossary import GlossaryEntry
from verboflex.schemas.glossary import GlossaryInput, GlossaryMatchQuery
from verboflex.services import glossary
from verboflex.services.translation_authoring import AuthoringError

__all__ = ["clean_preview_database", "preview_session_factory"]


def test_versioned_terms_match_and_are_physically_deleted(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    entry = uuid4()
    data = GlossaryInput(
        source_language="en", target_language="it", source_term="app", target_term="applicazione"
    )
    common = dict(product_id=seed.product_id, actor_id=seed.actor_id)
    with factory.begin() as session:
        first = glossary.save(session, **common, entry_id=entry, data=data)
        assert first.version == 1
        assert glossary.save(session, **common, entry_id=entry, data=data).version == 1
        found = glossary.matches(
            session,
            **common,
            query=GlossaryMatchQuery(
                source_language="en", target_language="it", source_text="Open the APP"
            ),
        )
        assert found.items[0].id == entry
        assert not glossary.matches(
            session,
            **common,
            query=GlossaryMatchQuery(
                source_language="en", target_language="it", source_text="happy"
            ),
        ).items
    with factory.begin() as session, pytest.raises(AuthoringError, match="already exists"):
        glossary.save(session, **common, entry_id=uuid4(), data=data)
    with factory.begin() as session, pytest.raises(AuthoringError, match="changed"):
        glossary.save(
            session,
            **common,
            entry_id=entry,
            data=data.model_copy(update={"target_term": "programma"}),
        )
    with factory.begin() as session:
        assert (
            glossary.save(
                session,
                **common,
                entry_id=entry,
                data=data.model_copy(update={"expected_version": 1, "forbidden": True}),
            ).version
            == 2
        )
    with factory.begin() as session, pytest.raises(AuthoringError, match="changed"):
        glossary.delete(session, **common, entry_id=entry, expected_version=1)
    with factory.begin() as session:
        glossary.delete(session, **common, entry_id=entry, expected_version=2)
        assert session.scalar(select(GlossaryEntry).where(GlossaryEntry.id == entry)) is None
        assert not glossary.list_entries(session, **common).items


@pytest.mark.parametrize(
    "text,term,sensitive,expected",
    [
        ("happy", "app", False, False),
        ("App", "app", True, False),
        ("APP", "app", False, True),
        ("Straße", "STRASSE", False, True),
        ("请打开应用程序", "应用", False, True),
        ("a+b", "a+b", False, True),
    ],
)
def test_word_boundaries(text, term, sensitive, expected):
    assert glossary.contains_term(text, term, case_sensitive=sensitive) is expected


@pytest.mark.parametrize("role", ["viewer", "translator"])
def test_only_reviewers_can_manage_terms(preview_session_factory, monkeypatch, role):
    from verboflex.models.role import Role
    from verboflex.models.user import User

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        session.get(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == role))
        ]
        mirror_fixture_role(session, session.get(User, seed.actor_id).id)
    with factory.begin() as session:
        assert (
            glossary.list_entries(session, product_id=seed.product_id, actor_id=seed.actor_id).items
            == []
        )
    with factory.begin() as session, pytest.raises(AuthoringError) as error:
        glossary.save(
            session,
            product_id=seed.product_id,
            actor_id=seed.actor_id,
            entry_id=uuid4(),
            data=GlossaryInput(
                source_language="en", target_language="it", source_term="hello", target_term="ciao"
            ),
        )
    assert error.value.status == 403
