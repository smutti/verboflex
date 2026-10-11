"""Stable discussion ownership survives mutable import and review context."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import inspect, select

from tests.api import test_translation_comments as comments
from verboflex.models.review import TranslationProposal
from verboflex.models.translation import TranslationValue

comment_api_session_factory = comments.comment_api_session_factory


def test_discussion_survives_import_locator_proposal_and_review_changes(
    comment_api_session_factory,
) -> None:
    ids = comments._seed_group(comment_api_session_factory, name="Persistent discussion")
    token = comments.SUPPORT.SUPPORT._create_authority(
        comment_api_session_factory, role_names=("translator",)
    )
    comments.SUPPORT.SUPPORT._configure_dependencies(comment_api_session_factory)
    created = comments._create(ids["group"], token=token, body="survives changes")
    assert created.status_code == 201

    with comment_api_session_factory.begin() as session:
        anchor = session.get_one(TranslationValue, ids["group"])
        values = tuple(
            session.scalars(
                select(TranslationValue).where(
                    TranslationValue.translation_key_id == anchor.translation_key_id,
                    TranslationValue.language == anchor.language,
                )
            )
        )
        for value in values:
            value.review_state = "rejected"
        proposal = session.scalar(
            select(TranslationProposal).where(
                TranslationProposal.translation_key_id == anchor.translation_key_id,
                TranslationProposal.language == anchor.language,
            )
        )
        if proposal is not None:
            proposal.version += 1
            proposal.state = "draft"

    engine = comment_api_session_factory.kw["bind"]
    foreign_targets = {
        foreign_key["referred_table"]
        for foreign_key in inspect(engine).get_foreign_keys("translation_comments")
    }
    assert foreign_targets.isdisjoint(
        {"translation_values", "translation_value_locators", "translation_proposals"}
    )

    listed = asyncio.run(
        comments._request(
            "GET",
            f"{comments.TRANSLATIONS_PATH}/{ids['group']}/comments",
            token=token,
        )
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [created.json()["id"]]
    assert listed.json()["items"][0]["body"] == "survives changes"
    assert UUID(listed.json()["items"][0]["translation_group_id"]) == ids["group"]
