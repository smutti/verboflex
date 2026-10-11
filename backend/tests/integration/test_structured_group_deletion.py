"""Real Android refresh purges removed variants while keeping live siblings editable."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tests.integration.test_translation_import_activation import (
    _reference,
    _seed_running_direct_import,
    _start_refresh_execution,
)
from tests.integration.test_translation_import_activation import (
    activation_session_factory as activation_session_factory,
)
from tests.integration.test_translation_import_activation import (
    clean_activation_database as clean_activation_database,
)
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.services import import_jobs, translation_imports
from verboflex.services.translation_constraints import (
    ConstraintAuthorityUnavailable,
    put_translation_constraint,
)
from verboflex.services.translation_search import (
    TranslationGroupUnavailable,
    TranslationSearchFilters,
    get_translation_group,
    search_translations,
)


def test_refresh_removing_one_variant_keeps_stable_group_and_live_constraint_authority(
    activation_session_factory,
    monkeypatch,
):
    factory = activation_session_factory
    identity, repository_id = _seed_running_direct_import(factory)

    def activate(current, target_items):
        documents = {
            "app/res/values/strings.xml": (
                '<item quantity="one">One</item><item quantity="other">Many</item>'
            ),
            "app/res/values-it/strings.xml": target_items,
        }
        inputs = tuple(
            CanonicalParserInput(
                format="android_xml",
                repository_side="direct",
                path=path,
                content=(
                    f'<resources><plurals name="count">{items}</plurals></resources>'
                    if items
                    else "<resources/>"
                ).encode(),
                layout_identity="app/res",
                layout_version=1,
                base_language="en",
            )
            for path, items in documents.items()
        )
        parsed = parse_canonical_mapping(inputs)
        assert not parsed.issues
        refs = tuple(
            replace(_reference(repository_id, path=path, commit_hash="a" * 40), position=i)
            for i, path in enumerate(documents)
        )
        manifest = translation_imports.stage_translation_parse(
            factory, identity=current, references=refs, result=parsed
        )
        assert manifest is not None
        assert import_jobs.finish_import_execution(
            factory, identity=current, references=refs, canonical_manifest_digest=manifest.digest
        )

    ids = iter(UUID(int=value) for value in range(100, 130))
    with monkeypatch.context() as patch:
        patch.setattr(translation_imports, "uuid4", lambda: next(ids))
        activate(
            identity,
            '<item quantity="one">Uno molto lungo</item><item quantity="other">Altri</item>',
        )
    actor = uuid4()
    with factory.begin() as session:
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .where(TranslationValue.language == "it")
                .order_by(TranslationValue.id)
            )
        )
        old_group_id = values[0].id
        assert values[0].display_text == "Uno molto lungo"
        values[0].review_state = "approved"
        session.add(
            User(
                id=actor,
                email=f"group-{actor}@example.com",
                display_name="Reviewer",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
            )
        )
    successor = _start_refresh_execution(factory, identity)
    activate(successor, '<item quantity="other">Altri</item>')

    def search(**filters):
        with factory() as session:
            return search_translations(
                session,
                principal_id=actor,
                filters=TranslationSearchFilters(language="it", **filters),
                cursor=None,
                cursor_secret="test-secret",
            ).items

    active = search()
    assert len(active) == 1 and active[0].id != old_group_id and not active[0].is_deleted
    current_group_id = active[0].id
    assert search(deleted="deleted") == ()
    assert search(query="Uno") == ()
    assert search(state="approved") == ()
    with factory.begin() as session:
        assert session.get(TranslationValue, old_group_id) is None
        with pytest.raises(TranslationGroupUnavailable):
            get_translation_group(session, group_id=old_group_id)
        detail = get_translation_group(session, group_id=current_group_id)
        assert not detail.is_deleted and len(detail.values) == 1
        changed = put_translation_constraint(
            session,
            translation_group_id=current_group_id,
            language="it",
            max_chars=10,
            expected_version=0,
            actor_id=actor,
        )
        assert changed.explicit_maximum == 10
    assert search(violation="over_limit") == ()
    assert search(violation="over_limit", deleted="all") == ()
    assert len(search(violation="within_limit")) == 1
    with factory.begin() as session:
        changed = put_translation_constraint(
            session,
            translation_group_id=current_group_id,
            language="it",
            max_chars=3,
            expected_version=changed.version,
            actor_id=actor,
        )
        assert any(value.language == "it" and value.is_over_limit for value in changed.values)
    assert len(search(violation="over_limit")) == 1
    final = _start_refresh_execution(factory, successor)
    activate(final, "")
    assert search() == ()
    deleted = search(deleted="deleted")
    assert deleted == ()
    with factory.begin() as session:
        assert session.get(TranslationValue, current_group_id) is None
        with pytest.raises(TranslationGroupUnavailable):
            get_translation_group(session, group_id=current_group_id)
        with pytest.raises(ConstraintAuthorityUnavailable):
            put_translation_constraint(
                session,
                translation_group_id=old_group_id,
                language="it",
                max_chars=9,
                expected_version=changed.version,
                actor_id=actor,
            )
