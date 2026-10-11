"""Focused proofs for Phase 5 fail-closed service branches."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from verboflex.auth.principal import Principal
from verboflex.auth.translation_access import TranslationGroupAccessUnavailable
from verboflex.schemas.users import RoleName
from verboflex.services import (
    notifications,
    translation_comments,
    translation_reviews,
    translation_search,
)
from verboflex.services.signed_cursor import CursorPosition, SignedCursorCodec
from verboflex.services.translation_comments import TranslationCommentInputInvalid
from verboflex.services.translation_reviews import TranslationProposalUnavailable


class Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value

    def one_or_none(self) -> object:
        return self.value

    def mappings(self) -> Result:
        return self

    def all(self) -> object:
        return self.value


class ScriptSession:
    def __init__(
        self,
        *,
        execute: tuple[object, ...] = (),
        scalar: tuple[object, ...] = (),
        scalars: tuple[object, ...] = (),
        get: tuple[object, ...] = (),
    ) -> None:
        self.execute_values = iter(execute)
        self.scalar_values = iter(scalar)
        self.scalars_values = iter(scalars)
        self.get_values = iter(get)

    def execute(self, *_args: object, **_kwargs: object) -> Result:
        return Result(next(self.execute_values))

    def scalar(self, *_args: object, **_kwargs: object) -> object:
        return next(self.scalar_values)

    def scalars(self, *_args: object, **_kwargs: object) -> object:
        return next(self.scalars_values)

    def get(self, *_args: object, **_kwargs: object) -> object:
        return next(self.get_values)


def _principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        email="phase5-service@example.com",
        display_name="Phase Five Service",
        roles=(RoleName.ADMIN,),
        must_change_password=False,
    )


def _discussion() -> object:
    return SimpleNamespace(
        translation_group_id=uuid4(),
        translation_key_id=uuid4(),
        scope_id=uuid4(),
        language="it",
    )


def test_notification_projection_rejects_missing_or_foreign_durable_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal()
    foreign = SimpleNamespace(recipient_user_id=uuid4())
    with pytest.raises(notifications.NotificationUnavailable):
        notifications._project(object(), principal=principal, notification=foreign)

    owned = SimpleNamespace(
        recipient_user_id=principal.user_id,
        originating_comment_id=uuid4(),
        actor_user_id=uuid4(),
    )
    with pytest.raises(notifications.NotificationUnavailable):
        notifications._project(
            ScriptSession(get=(None, None)), principal=principal, notification=owned
        )

    comment = SimpleNamespace(translation_key_id=uuid4(), language="it")
    actor = SimpleNamespace(id=owned.actor_user_id, display_name="Actor")
    with pytest.raises(notifications.NotificationUnavailable):
        notifications._project(
            ScriptSession(get=(comment, actor), scalar=(None,)),
            principal=principal,
            notification=owned,
        )

    monkeypatch.setattr(
        notifications,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TranslationGroupAccessUnavailable("unavailable")
        ),
    )
    with pytest.raises(notifications.NotificationUnavailable):
        notifications._project(
            ScriptSession(get=(comment, actor), scalar=(uuid4(),)),
            principal=principal,
            notification=owned,
        )

    monkeypatch.setattr(
        notifications,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: SimpleNamespace(
            product_id=uuid4(),
            group=SimpleNamespace(raw_key="", product_name="Product", id=uuid4()),
        ),
    )
    with pytest.raises(notifications.NotificationUnavailable):
        notifications._project(
            ScriptSession(get=(comment, actor), scalar=(uuid4(),)),
            principal=principal,
            notification=owned,
        )


def test_notification_visible_list_skips_stale_items(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        notifications,
        "_project",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            notifications.NotificationUnavailable("unavailable")
        ),
    )
    items = notifications._visible_items(
        ScriptSession(scalars=((stale,),)),
        principal=_principal(),
        view="all",
        product_id=None,
        position=None,
    )
    assert items == ()


@pytest.mark.parametrize("body", [None, "", "   ", "x" * 65_537])
def test_comment_body_validation_rejects_absent_blank_and_oversized(body: object) -> None:
    with pytest.raises(TranslationCommentInputInvalid):
        translation_comments._require_body(body)


@pytest.mark.parametrize("version", [None, True, 0, 9_007_199_254_740_992])
def test_comment_version_validation_rejects_inexact_bounds(version: object) -> None:
    with pytest.raises(TranslationCommentInputInvalid):
        translation_comments._require_version(version)


def test_comment_helpers_reject_inconsistent_durable_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = SimpleNamespace(
        product_id=uuid4(),
        group=SimpleNamespace(id=uuid4(), language="it"),
    )
    monkeypatch.setattr(
        translation_comments,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: access,
    )
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments._discussion(
            ScriptSession(get=(None,)),
            principal=_principal(),
            translation_group_id=access.group.id,
            mode=translation_comments.TranslationGroupAccessMode.READ,
        )
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments._load_user(ScriptSession(get=(None,)), uuid4())
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments._load_scoped_comment(
            ScriptSession(scalar=(None,)),
            discussion=_discussion(),
            comment_id=uuid4(),
        )

    discussion = _discussion()
    comment = SimpleNamespace(
        id=uuid4(),
        author_id=uuid4(),
        deleted_at=None,
        current_version=1,
    )
    author = SimpleNamespace(id=comment.author_id, display_name="Author")
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments._project(
            ScriptSession(get=(author,), scalar=(None,)),
            discussion=discussion,
            comment=comment,
        )


def test_comment_mutations_reject_already_removed_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discussion = _discussion()
    removed = SimpleNamespace(deleted_at=datetime.now(UTC))
    monkeypatch.setattr(translation_comments, "_discussion", lambda *_args, **_kwargs: discussion)
    monkeypatch.setattr(
        translation_comments, "_load_scoped_comment", lambda *_args, **_kwargs: removed
    )
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments.edit_translation_comment(
            object(),
            principal=_principal(),
            translation_group_id=discussion.translation_group_id,
            comment_id=uuid4(),
            body="edit",
            expected_version=1,
            mentions=(),
        )
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments.delete_translation_comment(
            object(),
            principal=_principal(),
            translation_group_id=discussion.translation_group_id,
            comment_id=uuid4(),
        )


def test_removed_comment_history_rejects_cursor_and_missing_deleter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discussion = _discussion()
    removed = SimpleNamespace(
        id=uuid4(), deleted_at=datetime.now(UTC), deleted_by=None, current_version=2
    )
    monkeypatch.setattr(translation_comments, "_discussion", lambda *_args, **_kwargs: discussion)
    monkeypatch.setattr(
        translation_comments, "_load_scoped_comment", lambda *_args, **_kwargs: removed
    )
    principal = Principal(
        user_id=uuid4(),
        email="viewer@example.com",
        display_name="Viewer",
        roles=(RoleName.VIEWER,),
        must_change_password=False,
    )
    with pytest.raises(translation_comments.InvalidTranslationCommentCursor):
        translation_comments.list_comment_versions(
            object(),
            principal=principal,
            translation_group_id=discussion.translation_group_id,
            comment_id=removed.id,
            cursor="cursor",
            cursor_secret="secret",
        )
    with pytest.raises(translation_comments.TranslationCommentUnavailable):
        translation_comments.list_comment_versions(
            object(),
            principal=principal,
            translation_group_id=discussion.translation_group_id,
            comment_id=removed.id,
            cursor=None,
            cursor_secret="secret",
        )


def test_comment_history_rejects_bad_cursor_and_emits_next_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discussion = _discussion()
    live = SimpleNamespace(id=uuid4(), deleted_at=None)
    monkeypatch.setattr(translation_comments, "_discussion", lambda *_args, **_kwargs: discussion)
    monkeypatch.setattr(
        translation_comments, "_load_scoped_comment", lambda *_args, **_kwargs: live
    )
    with pytest.raises(translation_comments.InvalidTranslationCommentCursor):
        translation_comments.list_comment_versions(
            object(),
            principal=_principal(),
            translation_group_id=discussion.translation_group_id,
            comment_id=live.id,
            cursor="bad",
            cursor_secret="secret",
        )

    now = datetime.now(UTC)
    rows = tuple(
        SimpleNamespace(id=UUID(int=index + 1), created_at=now)
        for index in range(translation_comments.COMMENT_HISTORY_PAGE_SIZE + 1)
    )
    monkeypatch.setattr(
        translation_comments, "_version_projection", lambda *_args, **_kwargs: "projected"
    )
    page = translation_comments.list_comment_versions(
        ScriptSession(scalars=(rows,)),
        principal=_principal(),
        translation_group_id=discussion.translation_group_id,
        comment_id=live.id,
        cursor=None,
        cursor_secret="secret",
    )
    assert len(page.items) == translation_comments.COMMENT_HISTORY_PAGE_SIZE
    assert page.next_cursor is not None


def test_comment_history_accepts_exact_bound_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    discussion = _discussion()
    live = SimpleNamespace(id=uuid4(), deleted_at=None)
    principal = _principal()
    monkeypatch.setattr(translation_comments, "_discussion", lambda *_args, **_kwargs: discussion)
    monkeypatch.setattr(
        translation_comments, "_load_scoped_comment", lambda *_args, **_kwargs: live
    )
    binding = translation_comments._history_binding(
        principal=principal,
        discussion=discussion,
        comment_id=live.id,
    )
    cursor = SignedCursorCodec("secret").encode(
        binding=binding,
        position=CursorPosition(created_at=datetime.now(UTC), id=uuid4()),
    )
    page = translation_comments.list_comment_versions(
        ScriptSession(scalars=((),)),
        principal=principal,
        translation_group_id=discussion.translation_group_id,
        comment_id=live.id,
        cursor=cursor,
        cursor_secret="secret",
    )
    assert page.items == ()


def _valid_group_parts() -> tuple[object, object, object, object, object]:
    product_id = uuid4()
    revision_id = uuid4()
    scope_id = uuid4()
    key_id = uuid4()
    product = SimpleNamespace(
        id=product_id,
        is_active=True,
        deleted_at=None,
        active_revision_id=revision_id,
    )
    identity = SimpleNamespace(scope_id=scope_id, translation_key_id=key_id)
    scope = SimpleNamespace(
        id=scope_id,
        product_id=product_id,
        current_revision_id=revision_id,
        active_execution_id=uuid4(),
    )
    key = SimpleNamespace(id=key_id)
    anchor = SimpleNamespace(language="it")
    return product, identity, scope, key, anchor


@pytest.mark.parametrize("failure_stage", [0, 1, 2, 4, 5])
def test_review_group_lock_rejects_each_missing_identity_stage(failure_stage: int) -> None:
    group_id = uuid4()
    product, identity, scope, key, anchor = _valid_group_parts()
    stages = [product, identity, scope, key, anchor]
    if failure_stage < 5:
        stages[failure_stage] = None
    leading = None if failure_stage == 5 else group_id
    with pytest.raises(TranslationProposalUnavailable):
        translation_reviews._lock_group(
            ScriptSession(execute=tuple(stages), scalar=(leading,)),
            translation_group_id=group_id,
            product_id=product.id,
        )


def test_review_value_and_revision_locks_reject_empty_authority() -> None:
    with pytest.raises(TranslationProposalUnavailable):
        translation_reviews._lock_current_values(
            ScriptSession(scalars=((),)),
            scope_id=uuid4(),
            key_id=uuid4(),
            language="it",
        )
    with pytest.raises(TranslationProposalUnavailable):
        translation_reviews._lock_latest_revisions(
            ScriptSession(scalars=((),)), value_ids=(uuid4(),)
        )


def test_review_save_rejects_missing_constraint_and_absent_proposal_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal()
    product_id = uuid4()
    group_id = uuid4()
    value_id = uuid4()
    scope = SimpleNamespace(id=uuid4())
    key = SimpleNamespace(id=uuid4(), raw_key="key")
    anchor = SimpleNamespace(language="it")
    value = SimpleNamespace(id=value_id)
    proposal_value = {
        "translation_value_id": value_id,
        "selector_version": 1,
        "selector_digest": "a" * 64,
        "basis_revision_number": 1,
        "basis_digest": "b" * 64,
        "proposed_text": "text",
    }
    monkeypatch.setattr(
        translation_reviews,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: SimpleNamespace(product_id=product_id),
    )
    monkeypatch.setattr(
        translation_reviews, "_lock_group", lambda *_args, **_kwargs: (scope, key, anchor)
    )
    monkeypatch.setattr(
        translation_reviews, "_lock_current_values", lambda *_args, **_kwargs: (value,)
    )
    monkeypatch.setattr(
        translation_reviews, "recompute_translation_constraints", lambda *_args, **_kwargs: ()
    )
    with pytest.raises(TranslationProposalUnavailable, match="constraint authority"):
        translation_reviews.save_translation_proposal(
            object(),
            principal=principal,
            translation_group_id=group_id,
            values=[proposal_value],
            expected_version=0,
        )

    monkeypatch.setattr(
        translation_reviews,
        "recompute_translation_constraints",
        lambda *_args, **_kwargs: (SimpleNamespace(value_id=value_id),),
    )
    monkeypatch.setattr(
        translation_reviews,
        "_lock_latest_revisions",
        lambda *_args, **_kwargs: {value_id: SimpleNamespace()},
    )
    with pytest.raises(translation_reviews.ProposalVersionConflict):
        translation_reviews.save_translation_proposal(
            ScriptSession(execute=(None,)),
            principal=principal,
            translation_group_id=group_id,
            values=[proposal_value],
            expected_version=1,
        )


def test_review_activity_rejects_invalid_anchor_and_stale_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal()
    group_id = uuid4()
    product_id = uuid4()
    access = SimpleNamespace(
        product_id=product_id,
        group=SimpleNamespace(id=group_id, language="it"),
    )
    monkeypatch.setattr(
        translation_reviews,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: access,
    )
    with pytest.raises(TranslationProposalUnavailable):
        translation_reviews.list_review_activity(
            ScriptSession(get=(None,)),
            principal=principal,
            translation_group_id=group_id,
            cursor=None,
            cursor_secret="secret",
        )

    key_id = uuid4()
    anchor = SimpleNamespace(
        id=group_id,
        language="it",
        translation_key_id=key_id,
        key=SimpleNamespace(product_id=product_id),
    )
    binding = translation_reviews._activity_binding(
        principal=principal,
        translation_group_id=group_id,
        translation_key_id=key_id,
        language="it",
    )
    cursor = SignedCursorCodec("secret").encode(
        binding=binding,
        position=CursorPosition(created_at=datetime.now(UTC), id=uuid4()),
    )
    with pytest.raises(translation_reviews.InvalidReviewActivityCursor):
        translation_reviews.list_review_activity(
            ScriptSession(get=(anchor,), scalar=(None,)),
            principal=principal,
            translation_group_id=group_id,
            cursor=cursor,
            cursor_secret="secret",
        )
    with pytest.raises(translation_reviews.InvalidReviewActivityCursor):
        translation_reviews.list_review_activity(
            ScriptSession(get=(anchor,), scalar=(uuid4(), None)),
            principal=principal,
            translation_group_id=group_id,
            cursor=cursor,
            cursor_secret="secret",
        )


def test_review_transition_rejects_already_current_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_id = uuid4()
    product_id = uuid4()
    value_id = uuid4()
    scope = SimpleNamespace(id=uuid4())
    key = SimpleNamespace(id=uuid4(), raw_key="key")
    anchor = SimpleNamespace(language="it")
    value = SimpleNamespace(id=value_id)
    proposal = SimpleNamespace(id=uuid4(), version=1, state="approved", values=())
    monkeypatch.setattr(
        translation_reviews,
        "resolve_translation_group_access",
        lambda *_args, **_kwargs: SimpleNamespace(product_id=product_id),
    )
    monkeypatch.setattr(
        translation_reviews, "_lock_group", lambda *_args, **_kwargs: (scope, key, anchor)
    )
    monkeypatch.setattr(
        translation_reviews, "_lock_current_values", lambda *_args, **_kwargs: (value,)
    )
    monkeypatch.setattr(
        translation_reviews, "recompute_translation_constraints", lambda *_args, **_kwargs: ()
    )
    monkeypatch.setattr(
        translation_reviews,
        "_lock_latest_revisions",
        lambda *_args, **_kwargs: {value_id: SimpleNamespace()},
    )
    monkeypatch.setattr(
        translation_reviews, "_project_proposal", lambda *_args, **_kwargs: object()
    )
    with pytest.raises(translation_reviews.TranslationProposalInputInvalid, match="current"):
        translation_reviews.transition_translation_proposal(
            ScriptSession(execute=(proposal, None)),
            principal=_principal(),
            translation_group_id=group_id,
            target_state="approved",
            expected_version=1,
            reason=None,
        )


def test_pending_detail_rejects_oversized_persisted_aggregate() -> None:
    rows = tuple(
        {"translation_value_id": uuid4()}
        for _ in range(translation_search.MAX_GROUP_VALUE_COUNT + 1)
    )
    with pytest.raises(translation_search.TranslationSearchInputError):
        translation_search._pending_detail(
            ScriptSession(execute=(rows,)),
            group_id=uuid4(),
            current_value_count=1,
            group_is_deleted=False,
        )
