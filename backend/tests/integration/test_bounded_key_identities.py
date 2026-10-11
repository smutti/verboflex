"""Generated identities preserve bytes and fail closed on digest collisions."""

import hashlib

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.integration.test_translation_import_activation import (
    BACKEND_ROOT,
    _json_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
)
from tests.integration.test_translation_import_activation import (
    activation_session_factory as activation_session_factory,
)
from tests.integration.test_translation_import_activation import (
    clean_activation_database as clean_activation_database,
)
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.translation import (
    LocalizationScope,
    StagedTranslationValue,
    TranslationKey,
    TranslationValue,
)
from verboflex.services import import_jobs


def test_bounded_identity_migration_roundtrip_preserves_existing_key_and_digest(
    activation_session_factory,
):
    factory = activation_session_factory
    identity, repository_id = _seed_running_direct_import(factory)
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository_id, result=_json_result()
    )
    assert import_jobs.finish_import_execution(
        factory, identity=identity, references=references, canonical_manifest_digest=manifest.digest
    )
    with factory() as session:
        key = session.scalar(select(TranslationKey))
        original = (key.id, key.raw_key, key.raw_key_digest)
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", factory.kw["bind"].url.render_as_string(hide_password=False)
    )
    command.downgrade(config, "0019_unicode_search_indexes")
    command.upgrade(config, "0020_bounded_key_identities")
    with factory() as session:
        key = session.scalar(select(TranslationKey))
        assert (key.id, key.raw_key, key.raw_key_digest) == original
        assert key.raw_key_digest == hashlib.sha256(key.raw_key.encode("utf8")).digest()
    # Keep the historical 0019/0020 assertion, then restore the shared module
    # fixture to current metadata before subsequent tests use newly added fields.
    command.upgrade(config, "head")


@pytest.mark.parametrize("table", ["translation_keys", "staged_translation_values"])
@pytest.mark.parametrize("raw_key", ["", "é👩🏽‍💻", r"\x6162", r"\001\n\\", "x" * 1048576])
def test_generated_digest_matches_exact_utf8_bytes(activation_session_factory, raw_key, table):
    with activation_session_factory.begin() as session:
        expression = session.scalar(
            text(
                "SELECT pg_get_expr(adbin, adrelid) FROM pg_attrdef "
                "JOIN pg_attribute ON attrelid=adrelid AND attnum=adnum "
                "WHERE adrelid=CAST(:table AS regclass) AND attname='raw_key_digest'"
            ),
            {"table": table},
        )
        # Exercise the actual applied generated expression; never a test copy.
        session.execute(
            text(
                "CREATE TEMP TABLE digest_probe (raw_key text, digest bytea "
                f"GENERATED ALWAYS AS ({expression}) STORED) ON COMMIT DROP"
            )
        )
        actual = session.scalar(
            text("INSERT INTO digest_probe(raw_key) VALUES (:key) RETURNING digest"),
            {"key": raw_key},
        )
        assert actual == hashlib.sha256(raw_key.encode("utf8")).digest()


def test_staged_hash_collision_rejects_distinct_exact_key_without_partial_changes(
    activation_session_factory,
):
    factory = activation_session_factory
    identity, repository_id = _seed_running_direct_import(factory)
    _stage_direct_manifest(
        factory, identity=identity, repository_id=repository_id, result=_json_result()
    )
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.execute(
            text(
                "ALTER TABLE staged_translation_values ALTER COLUMN raw_key_digest "
                "SET EXPRESSION AS (decode(repeat('00',32),'hex'))"
            )
        )
        row = session.scalars(select(StagedTranslationValue)).first()
        payload = {
            column.name: getattr(row, column.name)
            for column in StagedTranslationValue.__table__.columns
            if column.name != "raw_key_digest"
        }
        payload.update(position=99, raw_key="different-exact-provider-key")
        session.add(StagedTranslationValue(**payload))
        session.flush()
    with factory() as session:
        rows = tuple(session.scalars(select(StagedTranslationValue)))
        assert len(rows) == 2 and {row.raw_key for row in rows} == {"welcome"}
        assert all(row.raw_key_digest == hashlib.sha256(b"welcome").digest() for row in rows)
        assert tuple(session.scalars(select(TranslationKey))) == ()


def test_forced_digest_collision_rolls_back_activation_with_bounded_failure(
    activation_session_factory,
):
    factory = activation_session_factory
    identity, repository_id = _seed_running_direct_import(factory)
    # Two different exact keys share neither logical identity nor source text.
    from verboflex.localization.importing.core import CanonicalParseResult, canonical_value_order

    result = CanonicalParseResult(
        values=tuple(
            sorted(
                (*_json_result(raw_key="first").values, *_json_result(raw_key="second").values),
                key=canonical_value_order,
            )
        )
    )
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository_id, result=result
    )
    with factory.begin() as session:
        original = session.scalar(
            text(
                "SELECT pg_get_expr(adbin, adrelid) FROM pg_attrdef "
                "JOIN pg_attribute ON attrelid=adrelid AND attnum=adnum "
                "WHERE adrelid='translation_keys'::regclass AND attname='raw_key_digest'"
            )
        )
        # An adversarial collision is injected only in this isolated fixture DB.
        session.execute(
            text(
                "ALTER TABLE translation_keys ALTER COLUMN raw_key_digest "
                "SET EXPRESSION AS (decode(repeat('00',32),'hex'))"
            )
        )
    try:
        assert (
            import_jobs.finish_import_execution(
                factory,
                identity=identity,
                references=references,
                canonical_manifest_digest=manifest.digest,
            )
            is True
        )
        with factory() as session:
            assert tuple(session.scalars(select(TranslationKey))) == ()
            assert tuple(session.scalars(select(TranslationValue))) == ()
            scope = session.scalar(select(LocalizationScope))
            assert scope.active_execution_id is None and scope.dataset_version == 0
            job = session.get_one(ImportJob, identity.import_id)
            execution = session.get_one(ImportExecution, identity.execution_id)
            assert job.state == "import_failed" and execution.state == "failed"
            assert job.error_category == "bounded_failure"
            assert "first" not in job.error_message and "second" not in job.error_message
            assert "constraint" not in job.error_message.lower()
    finally:
        with factory.begin() as session:
            session.execute(
                text(
                    "ALTER TABLE translation_keys ALTER COLUMN raw_key_digest "
                    f"SET EXPRESSION AS ({original})"
                )
            )
