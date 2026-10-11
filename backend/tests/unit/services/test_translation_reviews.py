"""Pure aggregate proposal validation contracts."""

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verboflex.services import translation_reviews


def _item(index: int) -> dict[str, object]:
    return {
        "translation_value_id": uuid4(),
        "selector_version": 1,
        "selector_digest": f"{index:064x}",
        "basis_revision_number": 1,
        "basis_digest": f"{index + 100:064x}",
        "proposed_text": "" if index == 0 else "A😀 e\u0301 — مرحبا — 中文",
    }


@given(st.permutations(tuple(range(6))))
def test_aggregate_input_canonicalizes_order_without_changing_exact_text(
    order: list[int],
) -> None:
    values = [_item(index) for index in order]

    canonical = translation_reviews.validate_proposal_values(values)

    assert [item.selector_digest for item in canonical] == sorted(
        item["selector_digest"] for item in values
    )
    assert {item.proposed_text for item in canonical} == {"", "A😀 e\u0301 — مرحبا — 中文"}


@pytest.mark.parametrize("duplicate_field", ["translation_value_id", "selector_digest"])
def test_aggregate_input_rejects_duplicate_member_identity(duplicate_field: str) -> None:
    values = [_item(1), _item(2)]
    values[1][duplicate_field] = values[0][duplicate_field]

    with pytest.raises(translation_reviews.TranslationProposalInputInvalid):
        translation_reviews.validate_proposal_values(values)


@pytest.mark.parametrize("invalid", [None, {}, [], "values"])
def test_aggregate_input_rejects_absent_or_non_sequence_values(invalid: object) -> None:
    with pytest.raises(translation_reviews.TranslationProposalInputInvalid):
        translation_reviews.validate_proposal_values(invalid)


@pytest.mark.parametrize(
    ("target_state", "reason"),
    [
        ("draft", None),
        ("approved", None),
        ("rejected", None),
        ("rejected", ""),
        ("rejected", "  Motivo esatto 日本語\nseconda riga  "),
    ],
)
def test_review_transition_input_preserves_the_closed_state_and_exact_reason(
    target_state: str,
    reason: str | None,
) -> None:
    transition = translation_reviews.validate_review_transition(
        target_state=target_state,
        expected_version=7,
        reason=reason,
    )

    assert transition.target_state == target_state
    assert transition.expected_version == 7
    assert transition.reason == reason


@pytest.mark.parametrize(
    ("target_state", "expected_version", "reason"),
    [
        ("published", 1, None),
        ("APPROVED", 1, None),
        ("approved", True, None),
        ("approved", 1.0, None),
        ("approved", -1, None),
        ("approved", 1, "not a rejection reason"),
        ("rejected", 1, "x" * 4097),
        ("rejected", 1, 42),
    ],
)
def test_review_transition_input_rejects_open_or_inexact_values(
    target_state: object,
    expected_version: object,
    reason: object,
) -> None:
    with pytest.raises(translation_reviews.TranslationProposalInputInvalid):
        translation_reviews.validate_review_transition(
            target_state=target_state,
            expected_version=expected_version,
            reason=reason,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("translation_value_id", "not-a-uuid"),
        ("selector_version", 2),
        ("selector_version", True),
        ("selector_digest", "not-a-digest"),
        ("basis_revision_number", 0),
        ("basis_digest", None),
        ("proposed_text", "x" * (translation_reviews.MAX_TEXT_LENGTH + 1)),
    ],
)
def test_aggregate_member_rejects_every_invalid_closed_field(field: str, value: object) -> None:
    item = _item(1)
    item[field] = value
    with pytest.raises(translation_reviews.TranslationProposalInputInvalid):
        translation_reviews.validate_proposal_values([item])


def test_aggregate_member_rejects_missing_mapping_and_object_attributes() -> None:
    item = _item(1)
    item.pop("proposed_text")
    with pytest.raises(translation_reviews.TranslationProposalInputInvalid, match="required"):
        translation_reviews.validate_proposal_values([item])

    with pytest.raises(translation_reviews.TranslationProposalInputInvalid, match="required"):
        translation_reviews.validate_proposal_values([object()])
