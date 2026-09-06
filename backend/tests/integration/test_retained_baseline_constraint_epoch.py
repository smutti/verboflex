"""Retained dataset constraint epochs preserve immutable activation authority."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.integration.test_translation_import_activation import (
    BACKEND_ROOT,
    _json_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
    _start_refresh_execution,
    _value_for,
)
from tests.integration.test_translation_import_activation import (
    activation_session_factory as activation_session_factory,
)
from tests.integration.test_translation_import_activation import (
    clean_activation_database as clean_activation_database,
)
from verboflex.integrations.bitbucket.client import BitbucketFileDelta
from verboflex.models.import_job import ImportExecution, ImportJob
from verboflex.models.translation import LocalizationScope, TranslationValue
from verboflex.models.user import User
from verboflex.services import import_jobs, translation_constraints, translation_search


def _active_baseline(factory):
    identity, repository_id = _seed_running_direct_import(factory)
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository_id, result=_json_result()
    )
    assert import_jobs.finish_import_execution(
        factory,
        identity=identity,
        references=references,
        canonical_manifest_digest=manifest.digest,
    )
    actor_id = uuid4()
    with factory.begin() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == identity.product_id)
        )
        target = _value_for(session, scope_id=scope.id, raw_key="welcome", language="it")
        session.add(
            User(
                id=actor_id,
                email=f"retained-{actor_id}@example.com",
                display_name="Retained baseline reviewer",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
            )
        )
        return identity, repository_id, scope.id, target.id, actor_id


def _staged_refresh(factory, identity, repository_id, state="running"):
    if state == "queued":
        with factory() as session:
            import_jobs.start_or_refresh_import(
                session,
                product_id=identity.product_id,
                mapping_id=identity.mapping_id,
                enqueuer=lambda _import_id: None,
            )
        with factory() as session:
            job = session.get_one(ImportJob, identity.import_id)
            return replace(
                identity, execution_id=job.current_execution_id, sequence=identity.sequence + 1
            )
    successor = _start_refresh_execution(factory, identity)
    manifest, references = _stage_direct_manifest(
        factory,
        identity=successor,
        repository_id=repository_id,
        result=_json_result(translated="Nuovo"),
        commit_hash="b" * 40,
    )
    if state == "failed":
        assert import_jobs.finish_import_execution(factory, identity=successor, references=None)
    elif state == "reconciliation":
        sides = (
            import_jobs.SourceMovementSideComparison(
                repository_side="direct",
                repository_id=repository_id,
                active_commit_hash="a" * 40,
                proposed_commit_hash="b" * 40,
                relation="diverged",
            ),
        )
        movement = import_jobs.SourceMovementClassification(
            movement="review-required",
            sides=sides,
            rewrite_candidate=import_jobs.SourceRewriteCandidate(
                sides=sides,
                files=(
                    BitbucketFileDelta(
                        repository_side="direct", ordinal=0, change="modified", path="locales.json"
                    ),
                ),
                complete=True,
            ),
        )
        assert import_jobs.finish_import_execution(
            factory,
            identity=successor,
            references=references,
            movement=movement,
            canonical_manifest_digest=manifest.digest,
        )
    return successor


@pytest.mark.parametrize("state", ["queued", "running", "failed", "reconciliation"])
@pytest.mark.parametrize("action", ["put", "delete", "noop"])
def test_retained_baseline_constraint_mutations_preserve_activation(
    activation_session_factory, state, action
):
    factory = activation_session_factory
    baseline, repository_id, scope_id, group_id, actor_id = _active_baseline(factory)
    common = {"translation_group_id": group_id, "language": "it"}
    expected_version = 0
    if action != "put":
        with factory.begin() as session:
            created = translation_constraints.put_translation_constraint(
                session, **common, max_chars=8, expected_version=0, actor_id=actor_id
            )
            expected_version = created.version
    successor = _staged_refresh(factory, baseline, repository_id, state)
    with factory() as session:
        original = session.get_one(LocalizationScope, scope_id)
        epoch = original.dataset_version
        created_at = original.created_at
        detail = translation_search.get_translation_group(session, group_id=group_id)
        assert detail.values[0].translated_text == "Ciao"
    with factory.begin() as session:
        if action == "delete":
            result = translation_constraints.delete_translation_constraint(
                session, **common, expected_version=expected_version
            )
        else:
            result = translation_constraints.put_translation_constraint(
                session, **common, max_chars=8, expected_version=expected_version, actor_id=actor_id
            )
        assert result.explicit_maximum == (None if action == "delete" else 8)
        if action == "noop":
            assert result.version == expected_version
    with factory() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        assert scope.dataset_version == epoch + (action != "noop")
        assert scope.created_at == created_at
        assert scope.active_execution_id == baseline.execution_id
        assert scope.active_import_job_id == baseline.import_id
        assert scope.current_mapping_id == baseline.mapping_id
        assert scope.current_revision_id == baseline.revision_id
        job = session.get_one(ImportJob, baseline.import_id)
        assert job.active_baseline_execution_id == baseline.execution_id
        assert job.current_execution_id == successor.execution_id
        assert job.state == {"failed": "import_failed", "reconciliation": "current"}.get(
            state, state
        )
        assert session.get_one(ImportExecution, baseline.execution_id).state == "succeeded"
        value = session.get_one(TranslationValue, group_id)
        assert value.translated_text == "Ciao"
        assert value.effective_max_chars == (None if action == "delete" else 8)
        assert not value.is_over_limit


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "product_id",
        "mapping_identity_key",
        "current_revision_id",
        "current_mapping_id",
        "active_import_job_id",
        "active_execution_id",
        "created_at",
    ],
)
def test_retained_epoch_does_not_authorize_scope_or_activation_changes(
    activation_session_factory, field
):
    factory = activation_session_factory
    baseline, repository_id, scope_id, _, _ = _active_baseline(factory)
    successor = _staged_refresh(factory, baseline, repository_id)
    with (
        pytest.raises(IntegrityError, match="localization scope activation authority violation"),
        factory.begin() as session,
    ):
        scope = session.get_one(LocalizationScope, scope_id)
        replacement = uuid4()
        if field == "mapping_identity_key":
            replacement = scope.mapping_identity_key.replace("main", "foreign-branch")
        elif field == "created_at":
            replacement = scope.created_at + timedelta(seconds=1)
        elif field == "active_execution_id":
            replacement = successor.execution_id
        setattr(scope, field, replacement)
        scope.dataset_version += 1
    with factory() as session:
        scope = session.get_one(LocalizationScope, scope_id)
        assert scope.active_execution_id == baseline.execution_id and scope.dataset_version == 1


@pytest.mark.parametrize("delta", [-1, 0, 2])
def test_retained_epoch_requires_exact_increment(activation_session_factory, delta):
    factory = activation_session_factory
    baseline, repository_id, scope_id, _, _ = _active_baseline(factory)
    _staged_refresh(factory, baseline, repository_id)
    with (
        pytest.raises(IntegrityError, match="localization scope activation authority violation"),
        factory.begin() as session,
    ):
        session.execute(
            text(
                "UPDATE localization_scopes SET dataset_version = dataset_version + :delta "
                "WHERE id = :scope_id"
            ),
            {"delta": delta, "scope_id": scope_id},
        )


def test_retained_epoch_requires_authentic_job_baseline(activation_session_factory):
    factory = activation_session_factory
    baseline, repository_id, scope_id, _, _ = _active_baseline(factory)
    successor = _staged_refresh(factory, baseline, repository_id)
    with factory.begin() as session:
        session.get_one(
            ImportJob, baseline.import_id
        ).active_baseline_execution_id = successor.execution_id
    with (
        pytest.raises(IntegrityError, match="localization scope activation authority violation"),
        factory.begin() as session,
    ):
        session.get_one(LocalizationScope, scope_id).dataset_version += 1


def test_retained_epoch_rejects_current_execution_older_than_baseline(activation_session_factory):
    factory = activation_session_factory
    baseline, repository_id, scope_id, _, _ = _active_baseline(factory)
    successor = _start_refresh_execution(factory, baseline)
    manifest, references = _stage_direct_manifest(
        factory,
        identity=successor,
        repository_id=repository_id,
        result=_json_result(translated="Nuovo"),
        commit_hash="b" * 40,
    )
    assert import_jobs.finish_import_execution(
        factory,
        identity=successor,
        references=references,
        canonical_manifest_digest=manifest.digest,
    )
    with factory.begin() as session:
        session.get_one(ImportJob, baseline.import_id).current_execution_id = baseline.execution_id
    with (
        pytest.raises(IntegrityError, match="localization scope activation authority violation"),
        factory.begin() as session,
    ):
        session.get_one(LocalizationScope, scope_id).dataset_version += 1


def test_retained_epoch_migration_roundtrip_preserves_data_and_restores_prior_guard(
    activation_session_factory,
):
    factory = activation_session_factory
    baseline, repository_id, scope_id, group_id, actor_id = _active_baseline(factory)
    _staged_refresh(factory, baseline, repository_id)
    engine = factory.kw["bind"]
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    inspector = inspect(engine)
    expected_columns = inspector.get_columns("localization_scopes")
    expected_foreign_keys = inspector.get_foreign_keys("localization_scopes")
    with factory() as session:
        upgraded_function = session.scalar(
            text(
                "SELECT pg_get_functiondef("
                "'verboflex_guard_localization_scope_activation()'::regprocedure)"
            )
        )
    common = {"translation_group_id": group_id, "language": "it"}
    try:
        command.downgrade(config, "0020_bounded_key_identities")
        with (
            pytest.raises(
                IntegrityError, match="localization scope activation authority violation"
            ),
            factory.begin() as session,
        ):
            translation_constraints.put_translation_constraint(
                session, **common, max_chars=8, expected_version=0, actor_id=actor_id
            )
        with factory() as session:
            assert session.get_one(LocalizationScope, scope_id).dataset_version == 1
            assert session.get_one(TranslationValue, group_id).effective_max_chars is None
        command.upgrade(config, "head")
        with factory.begin() as session:
            result = translation_constraints.put_translation_constraint(
                session, **common, max_chars=8, expected_version=0, actor_id=actor_id
            )
        command.downgrade(config, "0020_bounded_key_identities")
        with (
            pytest.raises(
                IntegrityError, match="localization scope activation authority violation"
            ),
            factory.begin() as session,
        ):
            translation_constraints.delete_translation_constraint(
                session, **common, expected_version=result.version
            )
        command.upgrade(config, "head")
        with factory.begin() as session:
            translation_constraints.delete_translation_constraint(
                session, **common, expected_version=result.version
            )
        with factory() as session:
            scope = session.get_one(LocalizationScope, scope_id)
            assert scope.dataset_version == 3 and scope.active_execution_id == baseline.execution_id
            assert session.get_one(TranslationValue, group_id).translated_text == "Ciao"
            assert (
                session.scalar(
                    text(
                        "SELECT pg_get_functiondef("
                        "'verboflex_guard_localization_scope_activation()'::regprocedure)"
                    )
                )
                == upgraded_function
            )
        inspector = inspect(engine)
        assert [column["name"] for column in inspector.get_columns("localization_scopes")] == [
            column["name"] for column in expected_columns
        ]
        assert inspector.get_foreign_keys("localization_scopes") == expected_foreign_keys
    finally:
        command.upgrade(config, "head")
