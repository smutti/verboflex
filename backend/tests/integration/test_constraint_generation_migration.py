"""Constraint generations retain live authority and fence off all old integer tokens."""

from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from tests.integration.test_translation_constraints import (
    BACKEND_ROOT,
    _explicit_constraint,
    _seed_constraint_dataset,
)
from tests.integration.test_translation_constraints import (
    constraint_session_factory as constraint_session_factory,
)
from verboflex.models.translation import TranslationKey
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.services import translation_constraints as service


def test_generation_migration_roundtrip_backfills_live_and_deleted_rule_owners(
    constraint_session_factory,
):
    factory = constraint_session_factory
    ids = _seed_constraint_dataset(factory)
    with factory.begin() as session:
        rule = _explicit_constraint(ids=ids, key="base_key", language="en", maximum=8)
        rule.version = 7
        session.add(rule)
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", factory.kw["bind"].url.render_as_string(hide_password=False)
    )
    command.downgrade(config, "0017_translation_search_indexes")
    command.upgrade(config, "0018_constraint_generation")
    command.upgrade(config, "head")
    with factory() as session:
        assert session.get_one(TranslationKey, ids["base_key"]).constraint_generation == 2147483647
        assert (
            session.get_one(TranslationKey, ids["target_key"]).constraint_generation == 2147483647
        )
        rule = session.scalar(
            select(TranslationConstraint).where(
                TranslationConstraint.translation_key_id == ids["base_key"]
            )
        )
        assert rule.version == 7 and rule.max_chars == 8
    # Schema roundtrip preserves low live versions and their original meaning.
    command.downgrade(config, "0017_translation_search_indexes")
    command.upgrade(config, "0018_constraint_generation")
    command.upgrade(config, "head")
    with factory.begin() as session:
        live = service.put_translation_constraint(
            session,
            translation_group_id=ids["base_value"],
            language="en",
            max_chars=9,
            expected_version=7,
            actor_id=ids["actor"],
        )
        recreated = service.put_translation_constraint(
            session,
            translation_group_id=ids["target_value"],
            language="it",
            max_chars=4,
            expected_version=0,
            actor_id=ids["actor"],
        )
        assert live.version == recreated.version == 2147483648
        assert recreated.version < 2**53
    with factory() as session:
        assert session.scalar(text("SELECT count(*) FROM translation_constraints")) == 2
