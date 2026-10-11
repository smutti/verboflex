"""Persistent stable key-language discussion HTTP contracts."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from collections.abc import Iterator
from datetime import UTC, datetime
from types import ModuleType
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from verboflex.auth.access_tokens import decode_access_token
from verboflex.auth.passwords import hash_password
from verboflex.main import app
from verboflex.models.auth_session import AuthSession
from verboflex.models.review import (
    Notification,
    TranslationComment,
    TranslationCommentMention,
    TranslationCommentVersion,
)
from verboflex.models.user import User


def _support() -> ModuleType:
    module = importlib.import_module("tests.api.test_translation_reviews")
    return module


SUPPORT = _support()
TRANSLATIONS_PATH = SUPPORT.TRANSLATIONS_PATH


def _require_comment_contract() -> None:
    required = {
        "verboflex.schemas.comments": (
            "CreateTranslationCommentRequest",
            "TranslationCommentResponse",
            "TranslationCommentPageResponse",
            "CommentAnchorWindowResponse",
        ),
        "verboflex.services.translation_comments": (
            "create_translation_comment",
            "list_translation_comments",
            "get_translation_comment_anchor",
            "edit_translation_comment",
            "delete_translation_comment",
            "list_comment_versions",
        ),
    }
    for module_name, symbols in required.items():
        assert importlib.util.find_spec(module_name) is not None, f"missing {module_name}"
        module = importlib.import_module(module_name)
        assert not (set(symbols) - set(dir(module)))
    paths = app.openapi()["paths"]
    assert (
        paths["/api/v1/translations/{translation_group_id}/comments"]["post"]["operationId"]
        == "createTranslationComment"
    )
    assert (
        paths["/api/v1/translations/{translation_group_id}/comments"]["get"]["operationId"]
        == "listTranslationComments"
    )
    assert (
        paths["/api/v1/translations/{translation_group_id}/comments/anchor"]["get"]["operationId"]
        == "getTranslationCommentAnchor"
    )
    item_path = paths["/api/v1/translations/{translation_group_id}/comments/{comment_id}"]
    assert item_path["put"]["operationId"] == "updateTranslationComment"
    assert item_path["delete"]["operationId"] == "deleteTranslationComment"
    assert (
        paths["/api/v1/translations/{translation_group_id}/comments/{comment_id}/versions"]["get"][
            "operationId"
        ]
        == "listTranslationCommentVersions"
    )


@pytest.fixture(scope="module")
def comment_api_session_factory() -> Iterator[sessionmaker[Session]]:
    with SUPPORT._review_database() as factory:
        yield factory


@pytest.fixture(autouse=True)
def clean_comment_api_database(
    comment_api_session_factory: sessionmaker[Session],
) -> Iterator[None]:
    app.dependency_overrides.clear()
    with comment_api_session_factory.begin() as session:
        session.execute(text("TRUNCATE products, repositories CASCADE"))
        session.execute(delete(AuthSession))
        session.execute(delete(User))
    yield
    app.dependency_overrides.clear()


async def _request(
    method: str,
    path: str,
    *,
    token: str,
    json: object | None = None,
    params: dict[str, object] | None = None,
):
    import httpx

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            json=json,
            params=params,
        )


def _seed_group(factory: sessionmaker[Session], *, name: str) -> dict[str, object]:
    return SUPPORT._seed_scalar_basis(factory, name=name)


def _create(
    group_id: object,
    *,
    token: str,
    body: str,
):
    return asyncio.run(
        _request(
            "POST",
            f"{TRANSLATIONS_PATH}/{group_id}/comments",
            token=token,
            json={"body": body},
        )
    )


def _update(
    group_id: object,
    comment_id: object,
    *,
    token: str,
    body: str,
    expected_version: int,
):
    return asyncio.run(
        _request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{group_id}/comments/{comment_id}",
            token=token,
            json={"body": body, "expected_version": expected_version},
        )
    )


def _versions(
    group_id: object,
    comment_id: object,
    *,
    token: str,
    cursor: str | None = None,
):
    return asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{group_id}/comments/{comment_id}/versions",
            token=token,
            params={"cursor": cursor} if cursor else None,
        )
    )


def test_comment_contract_is_closed_bounded_and_registered() -> None:
    _require_comment_contract()
    schemas = importlib.import_module("verboflex.schemas.comments")
    request = schemas.CreateTranslationCommentRequest.model_validate(
        {"body": "  first\nمرحبا 日本語 😀 <script>  "}
    )
    assert request.body == "  first\nمرحبا 日本語 😀 <script>  "
    for invalid in ("", " \n\t", "x" * 65_537):
        with pytest.raises(ValueError):
            schemas.CreateTranslationCommentRequest.model_validate({"body": invalid})
    with pytest.raises(ValueError):
        schemas.CreateTranslationCommentRequest.model_validate(
            {"body": "valid", "recipient_id": str(uuid4())}
        )

    schemas = app.openapi()["components"]["schemas"]
    mention = schemas["MentionInput"]["properties"]
    assert set(mention) == {"user_id", "start_utf16", "end_utf16", "display_text"}
    candidate = schemas["MentionUserResponse"]["properties"]
    assert set(candidate) == {"id", "display_name", "email"}


def test_mention_search_is_active_minimal_deterministic_and_author_only(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    tokens = {
        role: SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=(role,))
        for role in ("admin", "product_manager_reviewer", "translator", "viewer")
    }
    with comment_api_session_factory.begin() as session:
        for index in range(10):
            session.add(
                User(
                    email=f"candidate-{index:02d}@example.com",
                    display_name=f"Candidate {index:02d}",
                    hashed_password=hash_password(f"candidate password {index}!"),
                    is_active=index != 3,
                    must_change_password=False,
                )
            )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)

    for role in ("admin", "product_manager_reviewer", "translator"):
        response = asyncio.run(
            _request("GET", "/api/v1/users/mentions", token=tokens[role], params={"q": "candidate"})
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 8
        assert [item["email"] for item in payload] == sorted(item["email"] for item in payload)
        assert all(set(item) == {"id", "display_name", "email"} for item in payload)
        assert "candidate-03@example.com" not in {item["email"] for item in payload}

    denied = asyncio.run(
        _request(
            "GET",
            "/api/v1/users/mentions",
            token=tokens["viewer"],
            params={"q": "candidate"},
        )
    )
    assert denied.status_code == 403


def test_structured_mentions_persist_but_plain_at_text_has_no_identity(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_group(comment_api_session_factory, name="Structured mentions")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    candidate_id = uuid4()
    with comment_api_session_factory.begin() as session:
        session.add(
            User(
                id=candidate_id,
                email="alice@example.com",
                display_name="Alice 😀",
                hashed_password=hash_password("candidate password phrase!"),
                is_active=True,
                must_change_password=False,
            )
        )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    body = "Hi 😀 @Alice 😀 and unselected @Nobody"
    prefix = "Hi 😀 "
    visible = "@Alice 😀"
    start = len(prefix.encode("utf-16-le")) // 2
    created = asyncio.run(
        _request(
            "POST",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=author,
            json={
                "body": body,
                "mentions": [
                    {
                        "user_id": str(candidate_id),
                        "start_utf16": start,
                        "end_utf16": start + len(visible.encode("utf-16-le")) // 2,
                        "display_text": visible,
                    }
                ],
            },
        )
    )
    assert created.status_code == 201
    assert created.json()["mentions"] == [
        {
            "user_id": str(candidate_id),
            "start_utf16": start,
            "end_utf16": start + len(visible.encode("utf-16-le")) // 2,
            "display_text": visible,
        }
    ]

    plain = _create(ids["group"], token=author, body="unselected @Alice text")
    assert plain.status_code == 201
    assert plain.json()["mentions"] == []
    with comment_api_session_factory() as session:
        persisted = tuple(session.scalars(select(TranslationCommentMention)))
    assert len(persisted) == 1
    assert persisted[0].mentioned_user_id == candidate_id


def test_invalid_mentions_reject_the_whole_comment_mutation(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_group(comment_api_session_factory, name="Atomic mention rejection")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    before: tuple[int, int, int]
    with comment_api_session_factory() as session:
        before = (
            session.scalar(select(func.count()).select_from(TranslationComment)) or 0,
            session.scalar(select(func.count()).select_from(TranslationCommentVersion)) or 0,
            session.scalar(select(func.count()).select_from(TranslationCommentMention)) or 0,
        )

    rejected = asyncio.run(
        _request(
            "POST",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=author,
            json={
                "body": "😀 @Unknown",
                "mentions": [
                    {
                        "user_id": str(uuid4()),
                        "start_utf16": 1,
                        "end_utf16": 10,
                        "display_text": "@Unknown",
                    }
                ],
            },
        )
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "Invalid comment input"}
    with comment_api_session_factory() as session:
        after = (
            session.scalar(select(func.count()).select_from(TranslationComment)) or 0,
            session.scalar(select(func.count()).select_from(TranslationCommentVersion)) or 0,
            session.scalar(select(func.count()).select_from(TranslationCommentMention)) or 0,
        )
    assert after == before


def test_create_and_edit_notify_only_new_distinct_non_author_mentions(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_group(comment_api_session_factory, name="Mention notifications")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    author_id = decode_access_token(
        author,
        settings=SUPPORT.SUPPORT._settings(),
    ).user_id
    recipients = ((uuid4(), "Alice"), (uuid4(), "Bob"))
    with comment_api_session_factory.begin() as session:
        for user_id, display_name in recipients:
            session.add(
                User(
                    id=user_id,
                    email=f"{display_name.lower()}@example.com",
                    display_name=display_name,
                    hashed_password=hash_password(f"{display_name} candidate password!"),
                    is_active=True,
                    must_change_password=False,
                )
            )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)

    body = "@Alice and again @Alice"
    first = "@Alice"
    second_start = len("@Alice and again ")
    created = asyncio.run(
        _request(
            "POST",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=author,
            json={
                "body": body,
                "mentions": [
                    {
                        "user_id": str(recipients[0][0]),
                        "start_utf16": 0,
                        "end_utf16": len(first),
                        "display_text": first,
                    },
                    {
                        "user_id": str(recipients[0][0]),
                        "start_utf16": second_start,
                        "end_utf16": second_start + len(first),
                        "display_text": first,
                    },
                ],
            },
        )
    )
    assert created.status_code == 201
    comment_id = UUID(created.json()["id"])
    with comment_api_session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.originating_comment_id == comment_id)
            )
            == 1
        )

    edited_body = "@Alice and @Bob"
    edited = asyncio.run(
        _request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments/{comment_id}",
            token=author,
            json={
                "body": edited_body,
                "expected_version": 1,
                "mentions": [
                    {
                        "user_id": str(recipients[0][0]),
                        "start_utf16": 0,
                        "end_utf16": 6,
                        "display_text": "@Alice",
                    },
                    {
                        "user_id": str(recipients[1][0]),
                        "start_utf16": 11,
                        "end_utf16": 15,
                        "display_text": "@Bob",
                    },
                ],
            },
        )
    )
    assert edited.status_code == 200
    with comment_api_session_factory() as session:
        rows = tuple(
            session.scalars(
                select(Notification)
                .where(Notification.originating_comment_id == comment_id)
                .order_by(Notification.recipient_user_id)
            )
        )
    assert {row.recipient_user_id for row in rows} == {user_id for user_id, _ in recipients}
    assert {row.actor_user_id for row in rows} == {author_id}

    removed = _update(
        ids["group"],
        comment_id,
        token=author,
        body="No selected mentions",
        expected_version=2,
    )
    assert removed.status_code == 200
    readded = asyncio.run(
        _request(
            "PUT",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments/{comment_id}",
            token=author,
            json={
                "body": "@Alice returns",
                "expected_version": 3,
                "mentions": [
                    {
                        "user_id": str(recipients[0][0]),
                        "start_utf16": 0,
                        "end_utf16": 6,
                        "display_text": "@Alice",
                    }
                ],
            },
        )
    )
    assert readded.status_code == 200
    with comment_api_session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.originating_comment_id == comment_id)
            )
            == 2
        )


def test_self_only_mentions_create_zero_notifications(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_group(comment_api_session_factory, name="Self mention")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    author_id = decode_access_token(
        author,
        settings=SUPPORT.SUPPORT._settings(),
    ).user_id
    with comment_api_session_factory() as session:
        author_display_name = session.get_one(User, author_id).display_name
    visible = f"@{author_display_name}"
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    created = asyncio.run(
        _request(
            "POST",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=author,
            json={
                "body": visible,
                "mentions": [
                    {
                        "user_id": str(author_id),
                        "start_utf16": 0,
                        "end_utf16": len(visible.encode("utf-16-le")) // 2,
                        "display_text": visible,
                    }
                ],
            },
        )
    )
    assert created.status_code == 201
    with comment_api_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Notification)) == 0


def test_create_roles_viewer_denial_and_signed_prepend_pages(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    _require_comment_contract()
    ids = _seed_group(comment_api_session_factory, name="Discussion paging")
    tokens = {
        role: SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=(role,))
        for role in ("admin", "product_manager_reviewer", "translator", "viewer")
    }
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    bodies = [
        "  first\nمرحبا 日本語 😀 <script>  ",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
    ]
    created: list[dict[str, object]] = []
    author_roles = ("admin", "product_manager_reviewer", "translator")
    for index, body in enumerate(bodies):
        response = _create(ids["group"], token=tokens[author_roles[index % 3]], body=body)
        assert response.status_code == 201
        item = response.json()
        assert item["body"] == body
        assert item["status"] == "available"
        assert item["current_version"] == 1
        assert item["created_at"] == item["updated_at"]
        created.append(item)

    with comment_api_session_factory() as session:
        before = session.scalar(select(func.count()).select_from(TranslationComment))
    denied = _create(ids["group"], token=tokens["viewer"], body="not allowed")
    assert denied.status_code == 403
    with comment_api_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TranslationComment)) == before

    latest = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=tokens["viewer"],
        )
    )
    assert latest.status_code == 200
    page = latest.json()
    assert [item["id"] for item in page["items"]] == [item["id"] for item in created[-5:]]
    assert page["older_cursor"]
    older = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=tokens["viewer"],
            params={"cursor": page["older_cursor"]},
        )
    )
    assert older.status_code == 200
    assert [item["id"] for item in older.json()["items"]] == [created[0]["id"]]
    assert older.json()["older_cursor"] is None
    tampered = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=tokens["viewer"],
            params={"cursor": f"{page['older_cursor']}x"},
        )
    )
    assert tampered.status_code == 422
    assert tampered.json() == {"detail": "Invalid comment cursor"}

    equal_timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    with comment_api_session_factory.begin() as session:
        for comment in session.scalars(select(TranslationComment)):
            comment.created_at = equal_timestamp
    first_equal = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=tokens["viewer"],
        )
    ).json()
    second_equal = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=tokens["viewer"],
            params={"cursor": first_equal["older_cursor"]},
        )
    ).json()
    equal_ids = [item["id"] for item in second_equal["items"] + first_equal["items"]]
    assert equal_ids == sorted(item["id"] for item in created)


def test_anchor_is_target_centered_bounded_and_scope_private(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    _require_comment_contract()
    first = _seed_group(comment_api_session_factory, name="Anchor one")
    second = _seed_group(comment_api_session_factory, name="Anchor two")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    viewer = SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=("viewer",))
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    comments = [
        _create(first["group"], token=author, body=f"comment {index}").json() for index in range(13)
    ]
    foreign = _create(second["group"], token=author, body="foreign").json()

    response = asyncio.run(
        _request(
            "GET",
            f"{TRANSLATIONS_PATH}/{first['group']}/comments/anchor",
            token=viewer,
            params={"comment": comments[6]["id"]},
        )
    )
    assert response.status_code == 200
    window = response.json()
    assert window["target_id"] == comments[6]["id"]
    assert len(window["items"]) == 11
    assert [item["id"] for item in window["items"]] == [item["id"] for item in comments[1:12]]

    unavailable_bodies = []
    for comment_id in (uuid4(), UUID(foreign["id"])):
        unavailable = asyncio.run(
            _request(
                "GET",
                f"{TRANSLATIONS_PATH}/{first['group']}/comments/anchor",
                token=viewer,
                params={"comment": str(comment_id)},
            )
        )
        assert unavailable.status_code == 404
        unavailable_bodies.append(unavailable.json())
    assert unavailable_bodies == [
        {"detail": "Comment unavailable"},
        {"detail": "Comment unavailable"},
    ]


def test_comment_versions_are_created_in_the_same_transaction(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    _require_comment_contract()
    ids = _seed_group(comment_api_session_factory, name="Atomic create")
    token = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    response = _create(ids["group"], token=token, body="atomic")
    assert response.status_code == 201
    with comment_api_session_factory() as session:
        comment = session.get_one(TranslationComment, UUID(response.json()["id"]))
        versions = tuple(
            session.scalars(
                select(TranslationCommentVersion).where(
                    TranslationCommentVersion.comment_id == comment.id
                )
            )
        )
    assert len(versions) == 1
    assert versions[0].version_number == comment.current_version == 1
    assert versions[0].body == "atomic"


def test_author_edits_with_exact_version_and_all_roles_read_live_history(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    _require_comment_contract()
    ids = _seed_group(comment_api_session_factory, name="Versioned lifecycle")
    tokens = {
        role: SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=(role,))
        for role in ("admin", "product_manager_reviewer", "translator", "viewer")
    }
    other_translator = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    created = _create(ids["group"], token=tokens["translator"], body="first body").json()

    updated = _update(
        ids["group"],
        created["id"],
        token=tokens["translator"],
        body="  edited\n日本語 😀  ",
        expected_version=1,
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "  edited\n日本語 😀  "
    assert updated.json()["current_version"] == 2
    assert updated.json()["edited"] is True

    for token in tokens.values():
        history = _versions(ids["group"], created["id"], token=token)
        assert history.status_code == 200
        assert [item["version"] for item in history.json()["items"]] == [1, 2]
        assert [item["body"] for item in history.json()["items"]] == [
            "first body",
            "  edited\n日本語 😀  ",
        ]
        assert history.json()["next_cursor"] is None

    for role in ("admin", "product_manager_reviewer", "viewer"):
        denied = _update(
            ids["group"],
            created["id"],
            token=tokens[role],
            body=f"not the author: {role}",
            expected_version=2,
        )
        assert denied.status_code == 403
        assert denied.json() == {"detail": "Comment action denied"}
    denied_translator = _update(
        ids["group"],
        created["id"],
        token=other_translator,
        body="not the author: translator",
        expected_version=2,
    )
    assert denied_translator.status_code == 403
    assert denied_translator.json() == {"detail": "Comment action denied"}

    conflict = _update(
        ids["group"],
        created["id"],
        token=tokens["translator"],
        body="losing local body",
        expected_version=1,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Comment version conflict"
    assert conflict.json()["attempted_body"] == "losing local body"
    assert conflict.json()["attempted_version"] == 1
    assert conflict.json()["latest"]["body"] == "  edited\n日本語 😀  "
    assert conflict.json()["latest"]["current_version"] == 2

    with comment_api_session_factory() as session:
        persisted = session.get_one(TranslationComment, UUID(created["id"]))
        versions = tuple(
            session.scalars(
                select(TranslationCommentVersion)
                .where(TranslationCommentVersion.comment_id == persisted.id)
                .order_by(TranslationCommentVersion.version_number)
            )
        )
    assert persisted.current_version == 2
    assert [version.body for version in versions] == [
        "first body",
        "  edited\n日本語 😀  ",
    ]


def test_admin_delete_retains_tombstone_and_hides_prior_text_from_non_admins(
    comment_api_session_factory: sessionmaker[Session],
) -> None:
    ids = _seed_group(comment_api_session_factory, name="Deletion privacy")
    author = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    reviewer = SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("product_manager_reviewer",)
    )
    viewer = SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=("viewer",))
    admin = SUPPORT.SUPPORT._create_authority(comment_api_session_factory, role_names=("admin",))
    SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    secret = "sensitive deleted body 日本語"
    created = _create(ids["group"], token=author, body=secret).json()
    edited = _update(
        ids["group"],
        created["id"],
        token=author,
        body=f"{secret} edited",
        expected_version=1,
    )
    assert edited.status_code == 200

    for token in (author, reviewer, viewer):
        denied = asyncio.run(
            _request(
                "DELETE",
                f"{TRANSLATIONS_PATH}/{ids['group']}/comments/{created['id']}",
                token=token,
            )
        )
        assert denied.status_code == 403

    deleted = asyncio.run(
        _request(
            "DELETE",
            f"{TRANSLATIONS_PATH}/{ids['group']}/comments/{created['id']}",
            token=admin,
        )
    )
    assert deleted.status_code == 200
    tombstone = deleted.json()
    assert tombstone["id"] == created["id"]
    assert tombstone["status"] == "removed"
    assert tombstone["body"] is None
    assert tombstone["deleted_at"] is not None
    assert tombstone["deleted_by"] is not None

    for token in (author, reviewer, viewer):
        page = asyncio.run(
            _request(
                "GET",
                f"{TRANSLATIONS_PATH}/{ids['group']}/comments",
                token=token,
            )
        )
        anchor = asyncio.run(
            _request(
                "GET",
                f"{TRANSLATIONS_PATH}/{ids['group']}/comments/anchor",
                token=token,
                params={"comment": created["id"]},
            )
        )
        history = _versions(ids["group"], created["id"], token=token)
        for response in (page, anchor, history):
            assert response.status_code == 200
            assert secret not in response.text
        assert page.json()["items"][0]["status"] == "removed"
        assert page.json()["items"][0]["body"] is None
        assert anchor.json()["items"][0]["body"] is None
        assert len(history.json()["items"]) == 1
        removed_version = history.json()["items"][0]
        assert removed_version["version"] == 3
        assert removed_version["status"] == "removed"
        assert removed_version["body"] is None
        assert removed_version["actor"]["id"] == tombstone["deleted_by"]
        assert removed_version["actor"]["display_name"]
        assert removed_version["created_at"] == tombstone["updated_at"]

    admin_history = _versions(ids["group"], created["id"], token=admin)
    assert admin_history.status_code == 200
    assert [item["version"] for item in admin_history.json()["items"]] == [1, 2, 3]
    assert [item["body"] for item in admin_history.json()["items"][:2]] == [
        secret,
        f"{secret} edited",
    ]
    assert admin_history.json()["items"][2]["status"] == "removed"
    assert admin_history.json()["items"][2]["body"] is None

    with comment_api_session_factory() as session:
        assert session.get(TranslationComment, UUID(created["id"])) is not None
        evidence = session.scalar(
            select(TranslationCommentVersion).where(
                TranslationCommentVersion.comment_id == UUID(created["id"]),
                TranslationCommentVersion.version_number == 1,
            )
        )
        assert evidence is not None
        with pytest.raises(DBAPIError):
            session.execute(
                text("UPDATE translation_comment_versions SET body = 'tampered' WHERE id = :id"),
                {"id": evidence.id},
            )
            session.commit()
