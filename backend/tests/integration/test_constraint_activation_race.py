"""Constraint mutations serialize with activation before taking subordinate locks."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text

from tests.integration.test_import_jobs import _create_admin
from tests.integration.test_translation_import_activation import (
    _json_result,
    _seed_running_direct_import,
    _stage_direct_manifest,
    _start_refresh_execution,
)
from tests.integration.test_translation_import_activation import (
    activation_session_factory as activation_session_factory,
)
from tests.integration.test_translation_import_activation import (
    clean_activation_database as clean_activation_database,
)
from verboflex.models.import_job import ImportJob
from verboflex.models.product import Product
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.services import import_jobs, translation_constraints
from verboflex.services.translation_search import get_translation_group


def _active_dataset(factory):
    identity, repository = _seed_running_direct_import(factory)
    manifest, references = _stage_direct_manifest(
        factory, identity=identity, repository_id=repository, result=_json_result()
    )
    assert import_jobs.finish_import_execution(
        factory, identity=identity, references=references, canonical_manifest_digest=manifest.digest
    )
    _create_admin(factory)
    with factory() as session:
        actor = session.scalar(select(User.id).order_by(User.id).limit(1))
        group = session.scalar(select(TranslationValue.id).where(TranslationValue.language == "it"))
    return identity, repository, actor, group


@pytest.mark.parametrize("action", ["put", "delete"])
@pytest.mark.parametrize("cross_product", [False, True])
def test_constraint_and_activation_complete_without_lock_inversion(
    activation_session_factory, action, cross_product
):
    factory = activation_session_factory
    identity, repository, actor, group = _active_dataset(factory)
    version = 0
    if action == "delete":
        with factory.begin() as session:
            version = translation_constraints.put_translation_constraint(
                session,
                translation_group_id=group,
                language="it",
                max_chars=8,
                expected_version=0,
                actor_id=actor,
            ).version
    if cross_product:
        refresh, repository = _seed_running_direct_import(factory)
    else:
        refresh = _start_refresh_execution(factory, identity)
    manifest, references = _stage_direct_manifest(
        factory,
        identity=refresh,
        repository_id=repository,
        result=_json_result(translated="Ciao nuovo"),
    )
    engine = factory.kw["bind"]
    worker_ready = Event()
    worker_mapping_locked = Event()
    worker_pid = []
    future = None
    blocked_before_mapping = False

    def capture_worker(connection, _cursor, _statement, _parameters, _context, _many):
        if current_thread().name.startswith("constraint-activation") and not worker_pid:
            worker_pid.append(connection.connection.driver_connection.info.backend_pid)
            worker_ready.set()

    def activate():
        result = import_jobs.finish_import_execution(
            factory,
            identity=refresh,
            references=references,
            canonical_manifest_digest=manifest.digest,
        )
        with factory() as verification:
            job = verification.get_one(ImportJob, refresh.import_id)
            assert job.state == "current", (job.state, job.error_category)
        return result

    event.listen(engine, "before_cursor_execute", capture_worker)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="constraint-activation") as executor:

        def interleave(_connection, _cursor, statement, _parameters, _context, _many):
            nonlocal future, blocked_before_mapping
            if current_thread().name.startswith("constraint-activation"):
                if "FROM product_repository_mappings" in statement and "FOR UPDATE" in statement:
                    worker_mapping_locked.set()
                return
            if (
                future is not None
                or "FROM localization_scopes" not in statement
                or "FOR UPDATE" not in statement
            ):
                return
            # The constraint owns scope now. Without Product-first serialization,
            # activation can own mapping and wait for this scope: a real cycle.
            future = executor.submit(activate)
            assert worker_ready.wait(3)
            deadline = time.monotonic() + 3
            with engine.connect() as observer:
                while not future.done():
                    if observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": worker_pid[0]}
                    ):
                        blocked_before_mapping = not worker_mapping_locked.is_set()
                        assert cross_product or blocked_before_mapping, (
                            "activation acquired mapping before waiting on the constraint: "
                            "lock inversion"
                        )
                        break
                    assert time.monotonic() < deadline, "worker did not reach real database barrier"
                    time.sleep(0.01)

        event.listen(engine, "after_cursor_execute", interleave)
        try:
            with factory.begin() as session:
                assert not get_translation_group(session, group_id=group).is_deleted
                if action == "put":
                    translation_constraints.put_translation_constraint(
                        session,
                        translation_group_id=group,
                        language="it",
                        max_chars=8,
                        expected_version=version,
                        actor_id=actor,
                    )
                else:
                    translation_constraints.delete_translation_constraint(
                        session,
                        translation_group_id=group,
                        language="it",
                        expected_version=version,
                        actor_id=None,
                    )
            assert future is not None and future.result(timeout=5)
            assert blocked_before_mapping is (not cross_product)
            with factory() as session:
                detail = get_translation_group(session, group_id=group)
                assert detail.explicit_maximum == (8 if action == "put" else None)
                assert detail.values[0].display_text == ("Ciao" if cross_product else "Ciao nuovo")
                assert detail.values[0].constraint.maximum == (8 if action == "put" else None)
        finally:
            event.remove(engine, "before_cursor_execute", capture_worker)
            event.remove(engine, "after_cursor_execute", interleave)


@pytest.mark.parametrize("change", ["inactive", "unpublished"])
def test_constraint_revalidates_product_after_preloaded_authority_becomes_inactive(
    activation_session_factory,
    change,
):
    factory = activation_session_factory
    identity, _repository, actor, group = _active_dataset(factory)
    with factory() as session:
        assert not get_translation_group(session, group_id=group).is_deleted
        session.get_one(TranslationValue, group)
        with factory.begin() as concurrent:
            product = concurrent.get_one(Product, identity.product_id)
            if change == "inactive":
                product.is_active = False
            else:
                product.active_revision_id = None
        with pytest.raises(translation_constraints.ConstraintAuthorityUnavailable):
            translation_constraints.put_translation_constraint(
                session,
                translation_group_id=group,
                language="it",
                max_chars=8,
                expected_version=0,
                actor_id=actor,
            )
        session.rollback()


def test_worker_recomputation_does_not_assume_a_missing_scope_exists(activation_session_factory):
    with (
        activation_session_factory.begin() as session,
        pytest.raises(translation_constraints.ConstraintAuthorityUnavailable, match="scope"),
    ):
        translation_constraints.recompute_translation_constraints(
            session, scope_id=uuid4(), base_language="en"
        )
