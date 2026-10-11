"""Structured mention validation at the browser UTF-16 boundary."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st


@dataclass(slots=True)
class _User:
    id: UUID
    display_name: str
    is_active: bool = True


class _Session:
    def __init__(self, *users: _User) -> None:
        self.users = {user.id: user for user in users}

    def get(self, _model: object, user_id: UUID) -> _User | None:
        return self.users.get(user_id)


def _contracts():
    schemas = importlib.import_module("verboflex.schemas.comments")
    service = importlib.import_module("verboflex.services.translation_comments")
    return schemas.MentionInput, service


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("", id="empty"),
        pytest.param("plain ", id="bmp"),
        pytest.param("😀 ", id="astral"),
        pytest.param("e\u0301 ", id="combining"),
        pytest.param("👩\u200d👩\u200d👧\u200d👦 ", id="zwj"),
        pytest.param("line one\r\n", id="crlf"),
        pytest.param("日本語 ", id="cjk"),
        pytest.param("עברית ", id="rtl"),
    ],
)
def test_validates_browser_utf16_half_open_ranges(prefix: str) -> None:
    MentionInput, service = _contracts()
    user = _User(id=uuid4(), display_name="Alice 😀")
    visible = f"@{user.display_name}"
    body = f"{prefix}{visible} suffix"
    start = _utf16_length(prefix)
    end = start + _utf16_length(visible)

    validated = service.validate_utf16_mentions(
        _Session(user),
        body=body,
        mentions=(
            MentionInput(
                user_id=user.id,
                start_utf16=start,
                end_utf16=end,
                display_text=visible,
            ),
        ),
    )

    assert len(validated) == 1
    assert validated[0].user_id == user.id
    assert validated[0].start_utf16 == start
    assert validated[0].end_utf16 == end
    assert validated[0].display_text == visible


@given(
    st.lists(
        st.sampled_from(("A", "é", "e\u0301", "😀", "👩\u200d💻", "日本", "ש", "\r\n")),
        max_size=40,
    )
)
def test_property_prefixes_do_not_shift_selected_identity(prefix_parts: list[str]) -> None:
    MentionInput, service = _contracts()
    user = _User(id=uuid4(), display_name="Renée 日本")
    prefix = "".join(prefix_parts)
    visible = f"@{user.display_name}"
    body = prefix + visible
    start = _utf16_length(prefix)

    result = service.validate_utf16_mentions(
        _Session(user),
        body=body,
        mentions=(
            MentionInput(
                user_id=user.id,
                start_utf16=start,
                end_utf16=start + _utf16_length(visible),
                display_text=visible,
            ),
        ),
    )

    assert result[0].display_text == visible


@pytest.mark.parametrize(
    ("body", "start", "end", "display"),
    [
        pytest.param("@Alice", -1, 6, "@Alice", id="negative"),
        pytest.param("@Alice", 6, 1, "@Alice", id="reversed"),
        pytest.param("@Alice", 0, 99, "@Alice", id="out-of-bounds"),
        pytest.param("😀@Alice", 1, 8, "@Alice", id="split-surrogate-start"),
        pytest.param("@Alice😀", 0, 7, "@Alice", id="split-surrogate-end"),
        pytest.param("@Alice", 0, 6, "@Mallory", id="submitted-text-mismatch"),
        pytest.param("@Mallory", 0, 8, "@Mallory", id="active-user-name-mismatch"),
    ],
)
def test_rejects_malformed_or_forged_ranges(
    body: str,
    start: int,
    end: int,
    display: str,
) -> None:
    MentionInput, service = _contracts()
    user = _User(id=uuid4(), display_name="Alice")

    with pytest.raises(service.TranslationCommentInputInvalid):
        service.validate_utf16_mentions(
            _Session(user),
            body=body,
            mentions=(
                MentionInput(
                    user_id=user.id,
                    start_utf16=start,
                    end_utf16=end,
                    display_text=display,
                ),
            ),
        )


def test_rejects_overlap_duplicate_range_unknown_and_inactive_users() -> None:
    MentionInput, service = _contracts()
    alice = _User(id=uuid4(), display_name="Alice")
    inactive = _User(id=uuid4(), display_name="Inactive", is_active=False)
    valid = MentionInput(
        user_id=alice.id,
        start_utf16=0,
        end_utf16=6,
        display_text="@Alice",
    )

    adversaries = (
        ("@Alice", (valid, valid)),
        (
            "@Alice Bob",
            (
                valid,
                MentionInput(
                    user_id=uuid4(),
                    start_utf16=3,
                    end_utf16=10,
                    display_text="ice Bob",
                ),
            ),
        ),
        (
            "@Missing",
            (
                MentionInput(
                    user_id=uuid4(),
                    start_utf16=0,
                    end_utf16=8,
                    display_text="@Missing",
                ),
            ),
        ),
        (
            "@Inactive",
            (
                MentionInput(
                    user_id=inactive.id,
                    start_utf16=0,
                    end_utf16=9,
                    display_text="@Inactive",
                ),
            ),
        ),
    )

    for body, mentions in adversaries:
        with pytest.raises(service.TranslationCommentInputInvalid):
            service.validate_utf16_mentions(
                _Session(alice, inactive),
                body=body,
                mentions=mentions,
            )


def test_empty_mentions_and_unselected_at_text_remain_plain_content() -> None:
    _, service = _contracts()

    assert service.validate_utf16_mentions(_Session(), body="Plain @Alice text", mentions=()) == ()
