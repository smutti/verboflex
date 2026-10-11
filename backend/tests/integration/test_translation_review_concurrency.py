"""Real PostgreSQL first-save-wins evidence for complete proposal aggregates."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from tests.api.test_translation_reviews import _review_database, _seed_scalar_basis
from verboflex.auth.principal import Principal
from verboflex.models.review import ReviewActivity, TranslationProposal, TranslationProposalValue
from verboflex.schemas.users import RoleName
from verboflex.services import translation_reviews


def test_two_independent_sessions_release_together_and_only_first_save_wins() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Concurrent aggregate")
        barrier = Barrier(2)

        def save(label: str) -> tuple[str, object]:
            principal = Principal(
                user_id=ids["actor_a"] if label == "a" else ids["actor_b"],
                email=f"{label}@example.com",
                display_name=label,
                roles=(RoleName.TRANSLATOR,),
                must_change_password=False,
            )
            basis = ids["basis"]
            assert isinstance(basis, list)
            values = [
                {
                    "translation_value_id": item["translation_value_id"],
                    "selector_version": item["selector_version"],
                    "selector_digest": item["selector_digest"],
                    "basis_revision_number": item["basis_revision_number"],
                    "basis_digest": item["basis_digest"],
                    "proposed_text": f"{label}:{index}",
                }
                for index, item in enumerate(basis)
            ]
            with factory() as session:
                barrier.wait(timeout=3)
                try:
                    projection = translation_reviews.save_translation_proposal(
                        session,
                        principal=principal,
                        translation_group_id=ids["group"],
                        values=values,
                        expected_version=0,
                    )
                    session.commit()
                    return "success", projection
                except translation_reviews.ProposalVersionConflict as error:
                    session.rollback()
                    return "conflict", error.comparison

        # Actor rows are real FK authorities and sessions are independent.
        from tests.api.test_translation_constraints import _create_authority
        from verboflex.models.user import User

        _create_authority(factory, role_names=("translator",))
        _create_authority(factory, role_names=("translator",))
        with factory() as session:
            actors = tuple(
                session.scalars(select(User.id).order_by(User.created_at.desc()).limit(2))
            )
        ids["actor_a"], ids["actor_b"] = actors

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(save, ("a", "b")))

        assert {result[0] for result in results} == {"success", "conflict"}
        success = next(result[1] for result in results if result[0] == "success")
        conflict = next(result[1] for result in results if result[0] == "conflict")
        assert success.version == 1
        assert conflict.latest is not None
        assert conflict.latest.version == 1
        assert {item.text for item in conflict.latest.pending} == {
            item.text for item in success.pending
        }
        with factory() as session:
            assert len(tuple(session.scalars(select(TranslationProposal)))) == 1
            assert len(tuple(session.scalars(select(TranslationProposalValue)))) == 2
            assert len(tuple(session.scalars(select(ReviewActivity)))) == 1


def test_two_independent_review_transitions_leave_one_winner_and_one_fresh_conflict() -> None:
    with _review_database() as factory:
        ids = _seed_scalar_basis(factory, name="Concurrent transition")

        from tests.api.test_translation_constraints import _create_authority
        from verboflex.models.user import User

        _create_authority(factory, role_names=("product_manager_reviewer",))
        _create_authority(factory, role_names=("product_manager_reviewer",))
        with factory() as session:
            actors = tuple(
                session.scalars(select(User.id).order_by(User.created_at.desc()).limit(2))
            )
        save_principal = Principal(
            user_id=actors[0],
            email="reviewer-a@example.com",
            display_name="reviewer-a",
            roles=(RoleName.PRODUCT_MANAGER_REVIEWER,),
            must_change_password=False,
        )
        basis = ids["basis"]
        assert isinstance(basis, list)
        with factory.begin() as session:
            saved = translation_reviews.save_translation_proposal(
                session,
                principal=save_principal,
                translation_group_id=ids["group"],
                values=[
                    {
                        "translation_value_id": item["translation_value_id"],
                        "selector_version": item["selector_version"],
                        "selector_digest": item["selector_digest"],
                        "basis_revision_number": item["basis_revision_number"],
                        "basis_digest": item["basis_digest"],
                        "proposed_text": f"pending:{index}",
                    }
                    for index, item in enumerate(basis)
                ],
                expected_version=0,
            )
        assert saved.version == 1
        barrier = Barrier(2)

        def transition(index_and_state: tuple[int, str]) -> tuple[str, object]:
            index, target_state = index_and_state
            principal = Principal(
                user_id=actors[index],
                email=f"reviewer-{index}@example.com",
                display_name=f"reviewer-{index}",
                roles=(RoleName.PRODUCT_MANAGER_REVIEWER,),
                must_change_password=False,
            )
            with factory() as session:
                barrier.wait(timeout=3)
                try:
                    result = translation_reviews.transition_translation_proposal(
                        session,
                        principal=principal,
                        translation_group_id=ids["group"],
                        target_state=target_state,
                        expected_version=1,
                        reason=None,
                    )
                    session.commit()
                    return "success", result
                except translation_reviews.ProposalVersionConflict as error:
                    session.rollback()
                    return "conflict", error.comparison

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(transition, ((0, "approved"), (1, "rejected"))))

        assert {result[0] for result in results} == {"success", "conflict"}
        winner = next(result[1] for result in results if result[0] == "success")
        loser = next(result[1] for result in results if result[0] == "conflict")
        assert winner.version == 2
        assert winner.state in {"approved", "rejected"}
        assert loser.latest is not None
        assert loser.latest.version == winner.version
        assert loser.latest.state == winner.state
        with factory() as session:
            proposal = session.scalar(select(TranslationProposal))
            assert proposal is not None
            assert (proposal.version, proposal.state) == (2, winner.state)
            activities = tuple(
                session.scalars(
                    select(ReviewActivity).order_by(ReviewActivity.created_at, ReviewActivity.id)
                )
            )
            assert [activity.kind for activity in activities] == [
                "proposal_saved",
                "state_changed",
            ]
