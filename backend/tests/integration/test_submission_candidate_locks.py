"""Real PostgreSQL lock ordering for overlapping candidate pages.

Only capture's source-proof work is replaced: it acquires the actual scope row
lock and rejects the candidate. No fake writable proof is returned. The minimum
relational fixture isolates page locking from preview/import/provider behavior.
"""

# ruff: noqa: F811

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import UUID, uuid4

from sqlalchemy import event, select

from tests.integration.test_preview_jobs import (
    _seed_preview_graph,
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.product import Product, ProductRevision
from verboflex.models.product_mapping import ProductRepositoryMapping
from verboflex.models.review import TranslationProposal
from verboflex.models.role import Role
from verboflex.models.translation import LocalizationScope, TranslationKey
from verboflex.models.user import User
from verboflex.services import submission_reviews


def _candidate_rows(factory):
    product_id, _, revision_id, mapping_id = _seed_preview_graph(factory)
    actor_id = uuid4()
    proposal_ids = tuple(UUID(int=n) for n in (101, 102, 103))
    with factory.begin() as session:
        first = session.get(ProductRepositoryMapping, mapping_id)
        second = ProductRepositoryMapping(
            id=uuid4(),
            revision_id=revision_id,
            topology="direct",
            identity_key="candidate-lock-second-mapping",
        )
        session.add(second)
        actor = User(
            id=actor_id,
            email=f"{actor_id}@example.test",
            display_name="Candidate reader",
            hashed_password="unused",
            is_active=True,
            must_change_password=False,
            roles=[session.scalar(select(Role).where(Role.name == "admin"))],
        )
        session.add(actor)
        session.flush()
        scopes = []
        for index, mapping in enumerate((first, second), 1):
            scope = LocalizationScope(
                id=UUID(int=index),
                product_id=product_id,
                current_revision_id=revision_id,
                current_mapping_id=mapping.id,
                mapping_identity_key=mapping.identity_key,
            )
            session.add(scope)
            scopes.append(scope)
        session.flush()
        for index, scope in enumerate((scopes[0], scopes[1], scopes[0])):
            key = TranslationKey(
                id=uuid4(),
                scope_id=scope.id,
                product_id=product_id,
                repository_id=first.sides[0].repository_id,
                configured_branch="main",
                raw_key=f"candidate-{index}",
            )
            session.add(key)
            session.flush()
            session.add(
                TranslationProposal(
                    id=proposal_ids[index],
                    scope_id=scope.id,
                    translation_key_id=key.id,
                    language="it",
                    version=1,
                    state="approved",
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        revision = session.get(ProductRevision, revision_id)
        revision.is_published = True
        revision.published_at = datetime.now(UTC)
        product = session.get(Product, product_id)
        product.candidate_revision_id = None
        product.active_revision_id = revision_id
    return product_id, actor_id, proposal_ids


def test_overlapping_candidate_pages_do_not_reverse_scope_locks(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    product_id, actor_id, (a1, b1, a2) = _candidate_rows(factory)
    first_locked = Event()
    second_locked = Event()
    first_needs_second = Event()

    def capture(session, *, selection, **_):
        proposal_id = selection.proposals[0].proposal_id
        page = session.info["candidate_page"]
        if page == "first" and proposal_id == b1:
            first_needs_second.set()
        if page == "second" and proposal_id == a2:
            assert first_needs_second.wait(3)
        scope_id = session.scalar(
            select(TranslationProposal.scope_id).where(TranslationProposal.id == proposal_id)
        )
        session.execute(
            select(LocalizationScope.id)
            .where(LocalizationScope.id == scope_id)
            .with_for_update()
        ).one()
        if page == "first" and proposal_id == a1:
            first_locked.set()
            # With sorted page-wide locks the second request waits outside
            # capture; let the first finish. Without them both acquire A/B.
            second_locked.wait(0.75)
        if page == "second" and proposal_id == b1:
            second_locked.set()
        raise WritebackRejected(WritebackReason.STALE_BASIS)

    monkeypatch.setattr(submission_reviews, "capture_writeback_authority", capture)

    def page(label, after):
        if label == "second":
            assert first_locked.wait(3)
        with factory() as session:
            session.info["candidate_page"] = label

            def bounded(_session, _transaction, connection):
                connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
                connection.exec_driver_sql("SET LOCAL statement_timeout = '7s'")

            event.listen(session, "after_begin", bounded)
            return submission_reviews.list_change_set_candidates(
                session, product_id=product_id, actor_id=actor_id, after=after
            )

    errors = []
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (pool.submit(page, "first", None), pool.submit(page, "second", a1))
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except Exception as error:
                errors.append(
                    (
                        type(error).__name__,
                        getattr(getattr(error, "orig", None), "sqlstate", None),
                    )
                )
    assert errors == [], f"Candidate requests must not deadlock or time out: {errors}"
    assert [len(result.items) for result in results] == [3, 2]
