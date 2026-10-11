"""Real PostgreSQL conflict and append-only evidence tests for discussions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from tests.api.test_translation_reviews import _review_database, _seed_scalar_basis
from tests.api.test_translations import _create_authority, _settings
from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.principal import Principal
from verboflex.models.review import TranslationCommentVersion
from verboflex.schemas.users import RoleName
from verboflex.services import translation_comments


def _principal(token: str) -> Principal:
    claims = decode_access_token(token, settings=_settings())
    return Principal(
        user_id=claims.user_id,
        email=f"{claims.user_id}@example.com",
        display_name="Concurrent editor",
        roles=(RoleName.TRANSLATOR,),
        must_change_password=False,
        session_id=claims.session_id,
    )


def test_two_sessions_release_together_and_only_first_comment_edit_wins() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Concurrent comment")
        token = _create_authority(factory, role_names=("translator",))
        principal = _principal(token)
        with factory.begin() as session:
            created = translation_comments.create_translation_comment(
                session,
                principal=principal,
                translation_group_id=ids["group"],
                body="basis",
            )
            comment_id = created.id

        barrier = Barrier(2)

        def edit(label: str) -> tuple[str, object]:
            with factory() as session:
                barrier.wait(timeout=3)
                try:
                    projection = translation_comments.edit_translation_comment(
                        session,
                        principal=principal,
                        translation_group_id=ids["group"],
                        comment_id=comment_id,
                        body=f"local {label}",
                        expected_version=1,
                    )
                    session.commit()
                    return "success", projection
                except translation_comments.CommentVersionConflict as error:
                    session.rollback()
                    return "conflict", error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(edit, ("a", "b")))

        assert {kind for kind, _ in results} == {"success", "conflict"}
        winner = next(result for kind, result in results if kind == "success")
        loser = next(result for kind, result in results if kind == "conflict")
        assert winner.current_version == 2
        assert loser.attempted_body in {"local a", "local b"}
        assert loser.attempted_body != winner.body
        assert loser.latest.current_version == 2
        assert loser.latest.body == winner.body

        with factory() as session:
            versions = tuple(
                session.scalars(
                    select(TranslationCommentVersion)
                    .where(TranslationCommentVersion.comment_id == comment_id)
                    .order_by(TranslationCommentVersion.version_number)
                )
            )
        assert [(item.version_number, item.body) for item in versions] == [
            (1, "basis"),
            (2, winner.body),
        ]


def test_comment_version_rows_reject_update_and_delete() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Immutable comment evidence")
        principal = _principal(_create_authority(factory, role_names=("translator",)))
        with factory.begin() as session:
            created = translation_comments.create_translation_comment(
                session,
                principal=principal,
                translation_group_id=ids["group"],
                body="immutable",
            )

        for statement in (
            "UPDATE translation_comment_versions SET body = 'tampered' WHERE comment_id = :id",
            "DELETE FROM translation_comment_versions WHERE comment_id = :id",
        ):
            with factory() as session, pytest.raises(DBAPIError):
                session.execute(text(statement), {"id": created.id})
                session.commit()
