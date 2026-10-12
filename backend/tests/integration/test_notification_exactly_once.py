"""Transactional and concurrent exactly-once mention notification evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from sqlalchemy import func, select

from tests.api.test_translation_reviews import _review_database, _seed_scalar_basis
from tests.api.test_translations import _create_authority
from tests.integration.test_translation_comment_concurrency import _principal
from verboflex.auth.passwords import hash_password
from verboflex.models.review import (
    Notification,
    TranslationComment,
    TranslationCommentMention,
    TranslationCommentVersion,
)
from verboflex.models.role import Role
from verboflex.models.user import User
from verboflex.services import translation_comments


def _recipient(factory, *, display_name: str = "Recipient") -> UUID:
    user_id = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                display_name=display_name,
                hashed_password=hash_password("recipient password phrase!"),
                is_active=True,
                must_change_password=False,
                roles=list(session.scalars(select(Role).where(Role.name == "viewer"))),
            )
        )
    return user_id


def test_notification_helper_returns_only_the_recipient_it_inserted() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Inserted recipients")
        principal = _principal(_create_authority(factory, role_names=("translator",)))
        recipient_id = _recipient(factory)
        with factory.begin() as session:
            created = translation_comments.create_translation_comment(
                session,
                principal=principal,
                translation_group_id=ids["group"],
                body="plain",
            )
        with factory.begin() as session:
            first = translation_comments.insert_mention_notifications(
                session,
                comment_id=created.id,
                actor_id=principal.user_id,
                recipient_ids=(recipient_id, recipient_id, principal.user_id),
            )
        with factory.begin() as session:
            repeated = translation_comments.insert_mention_notifications(
                session,
                comment_id=created.id,
                actor_id=principal.user_id,
                recipient_ids=(recipient_id,),
            )

        assert first == (recipient_id,)
        assert repeated == ()


def test_two_independent_sessions_insert_one_durable_notification() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Concurrent notification")
        principal = _principal(_create_authority(factory, role_names=("translator",)))
        recipient_id = _recipient(factory)
        with factory.begin() as session:
            created = translation_comments.create_translation_comment(
                session,
                principal=principal,
                translation_group_id=ids["group"],
                body="plain",
            )
        ready = Barrier(2)

        def insert_once() -> tuple[UUID, ...]:
            with factory() as session:
                ready.wait(timeout=3)
                inserted = translation_comments.insert_mention_notifications(
                    session,
                    comment_id=created.id,
                    actor_id=principal.user_id,
                    recipient_ids=(recipient_id,),
                )
                session.commit()
                return inserted

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(lambda _index: insert_once(), range(2)))

        assert sorted(len(result) for result in results) == [0, 1]
        with factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Notification)
                    .where(
                        Notification.originating_comment_id == created.id,
                        Notification.recipient_user_id == recipient_id,
                    )
                )
                == 1
            )


def test_forced_rollback_leaves_no_comment_version_mention_or_notification() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Rollback notification")
        principal = _principal(_create_authority(factory, role_names=("translator",)))
        recipient_id = _recipient(factory, display_name="Rollback recipient")
        session = factory()
        try:
            result = translation_comments.create_translation_comment(
                session,
                principal=principal,
                translation_group_id=ids["group"],
                body="@Rollback recipient",
                mentions=(
                    translation_comments.MentionInput(
                        user_id=recipient_id,
                        start_utf16=0,
                        end_utf16=19,
                        display_text="@Rollback recipient",
                    ),
                ),
            )
            assert result.new_notification_recipient_ids == (recipient_id,)
            session.rollback()
        finally:
            session.close()

        with factory() as session:
            assert session.scalar(select(func.count()).select_from(TranslationComment)) == 0
            assert session.scalar(select(func.count()).select_from(TranslationCommentVersion)) == 0
            assert session.scalar(select(func.count()).select_from(TranslationCommentMention)) == 0
            assert session.scalar(select(func.count()).select_from(Notification)) == 0
