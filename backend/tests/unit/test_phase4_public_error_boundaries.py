"""Persisted authority and public error translation remain closed and content-free."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from verboflex.api.v1.routes import translation_constraints as constraint_routes
from verboflex.api.v1.routes import translations as routes
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.schemas.translations import TranslationSearchQuery
from verboflex.services import import_jobs as imports
from verboflex.services import preview_jobs as previews


@pytest.mark.parametrize("languages", [None, [], "en", ["en", 42], ["EN"]])
def test_persisted_candidate_languages_cannot_assume_valid_json_shape(languages):
    with pytest.raises(previews.PreviewBaseLanguageRequired, match="^base_language_required$"):
        previews._candidate_languages({"languages": languages})
    assert previews._candidate_languages({"languages": ["en", "it"]}) == ("en", "it")
    assert previews._candidate_languages({"languages": ["default", "en"]}) == ("en",)


def test_candidate_base_language_must_be_an_exact_detected_member():
    candidate = {"languages": ["en", "it"]}
    assert previews._candidate_has_base_language(candidate, "it") is True
    assert previews._candidate_has_base_language(candidate, "fr") is False
    assert previews._candidate_has_base_language(candidate, "EN") is False


def test_nullable_active_confirmation_digest_is_never_projected_as_authority():
    with pytest.raises(
        previews.PreviewJobConflict, match="^active revalidation confirmation conflict$"
    ):
        previews._active_confirmation_record(
            SimpleNamespace(preview_digest=None), base_language="en"
        )


def test_selected_layout_without_base_language_never_authorizes_import():
    mapping = SimpleNamespace(
        selected_layout_candidate_id=uuid4(), selected_layout_version=1, base_language=None
    )
    assert previews._selected_layout_matches([], mapping) is False


def test_constraint_invalid_input_translates_to_fixed_public_error():
    with pytest.raises(HTTPException) as raised:
        constraint_routes._raise_constraint_error(
            constraint_routes.ConstraintInputInvalid("secret repository content")
        )
    assert raised.value.status_code == 422
    assert raised.value.detail == "Invalid translation constraint input"


@pytest.mark.anyio
async def test_search_without_signing_key_does_not_call_repository_service(monkeypatch):
    search = Mock()
    monkeypatch.setattr(routes, "search_translations", search)
    with pytest.raises(HTTPException) as raised:
        await routes.search_translation_collection(
            SimpleNamespace(user_id=uuid4()),
            Mock(),
            SimpleNamespace(jwt_secret_key=None),
            TranslationSearchQuery(),
        )
    assert raised.value.status_code == 503
    assert raised.value.detail == "Translation search unavailable"
    search.assert_not_called()


@pytest.mark.anyio
async def test_search_service_input_rejection_never_discloses_provider_content(monkeypatch):
    search = Mock(side_effect=routes.TranslationSearchInputError("secret provider text"))
    monkeypatch.setattr(routes, "search_translations", search)
    principal = SimpleNamespace(user_id=uuid4())
    with pytest.raises(HTTPException) as raised:
        await routes.search_translation_collection(
            principal,
            Mock(),
            SimpleNamespace(jwt_secret_key=SecretStr("test-signing-key")),
            TranslationSearchQuery(),
        )
    assert raised.value.status_code == 422 and raised.value.detail == "Invalid translation cursor"
    assert search.call_args.kwargs["principal_id"] == principal.user_id


def test_noncanonical_terminalization_preserves_unexpected_failure_for_worker(monkeypatch):
    failure = RuntimeError("database unavailable")
    monkeypatch.setattr(imports, "_finish_import_execution_transaction", Mock(side_effect=failure))
    with pytest.raises(RuntimeError) as raised:
        imports.finish_import_execution(Mock(), identity=SimpleNamespace(), references=())
    assert raised.value is failure


def test_late_canonical_failure_cannot_rewrite_a_missing_execution():
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    factory = Mock()
    factory.begin.return_value.__enter__ = Mock(return_value=session)
    factory.begin.return_value.__exit__ = Mock(return_value=False)
    identity = SimpleNamespace(
        import_id=uuid4(), execution_id=uuid4(), sequence=1, connection_generation=9
    )
    assert (
        imports._terminalize_failed_canonical_activation(
            factory, identity=identity, failure_category="bounded_failure"
        )
        is False
    )
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_rewrite_identity_cannot_assume_a_persisted_repository_still_exists():
    session = Mock()
    session.get.return_value = None
    mapping = SimpleNamespace(
        topology="direct",
        sides=[
            SimpleNamespace(
                role="direct", repository_id=uuid4(), source_branch="main", localization_root=None
            )
        ],
    )
    with pytest.raises(imports.ImportRewriteStale, match="^import rewrite proposal stale$"):
        imports._persisted_execution_identity(
            session, mapping=mapping, job=SimpleNamespace(), execution=SimpleNamespace()
        )
    session.flush.assert_not_called()


@pytest.mark.parametrize("failure", ["missing-scope", "rejected-manifest"])
def test_rewrite_confirmation_rejects_lost_canonical_authority_without_adopting_it(
    monkeypatch, failure
):
    proposed_id = uuid4()
    proposal = SimpleNamespace(proposed_execution_id=proposed_id, digest="a" * 64, status="pending")
    execution = SimpleNamespace(id=proposed_id)
    mapping = SimpleNamespace(base_language="en", identity_key="mapping")
    job = SimpleNamespace(active_baseline_execution_id=uuid4())
    old_baseline = job.active_baseline_execution_id
    monkeypatch.setattr(
        imports,
        "_current_rewrite_authority",
        Mock(return_value=(None, mapping, job, proposal, execution, ())),
    )
    monkeypatch.setattr(
        imports, "_persisted_execution_identity", Mock(return_value=SimpleNamespace())
    )
    reject = Mock(side_effect=imports.TranslationImportRejected("private staged text"))
    monkeypatch.setattr(imports, "staged_manifest_digest", reject)
    session = Mock()
    session.begin.return_value.__enter__ = Mock()
    session.begin.return_value.__exit__ = Mock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = (
        None if failure == "missing-scope" else SimpleNamespace()
    )
    with pytest.raises(imports.ImportRewriteStale, match="^import rewrite proposal stale$"):
        imports.confirm_rewrite_baseline(
            session,
            product_id=uuid4(),
            mapping_id=uuid4(),
            import_id=uuid4(),
            proposal_id=uuid4(),
            proposed_execution_id=proposed_id,
            proposal_digest="a" * 64,
            actor_id=uuid4(),
        )
    assert proposal.status == "pending" and job.active_baseline_execution_id == old_baseline
    session.flush.assert_not_called()
    assert reject.call_count == (0 if failure == "missing-scope" else 1)


def test_confirmed_layout_path_rejects_mismatched_template_grammar():
    candidate = SimpleNamespace(format="json", layout_identity="qt-ts:translations/{locale}.ts")
    assert imports._path_belongs_to_confirmed_layout(candidate, "translations/en.ts") is False
    candidate.layout_identity = "json:flat-per-locale:translations/{locale}.json"
    assert imports._path_belongs_to_confirmed_layout(candidate, "translations/en.json") is True
    assert imports._path_belongs_to_confirmed_layout(candidate, "elsewhere/en.json") is False


@pytest.mark.anyio
async def test_worker_rejects_execution_lost_between_parse_and_staging(monkeypatch):
    identity = SimpleNamespace(
        execution_id=uuid4(),
        import_id=uuid4(),
        sequence=1,
        repository_sides=(
            SimpleNamespace(
                role="direct",
                repository_id=uuid4(),
                workspace="workspace",
                repository_slug="app",
                source_branch="main",
                localization_root=None,
            ),
        ),
    )
    content = b'{"en":{"key":"Hello"},"it":{"key":"Ciao"}}'
    discovered = SimpleNamespace(
        commit_hash="a" * 40, files=(SimpleNamespace(path="locales.json", content=content),)
    )
    monkeypatch.setattr(
        imports, "discover_repository_sources_for_record", AsyncMock(return_value=discovered)
    )
    monkeypatch.setattr(imports, "_canonical_import_enabled", Mock(return_value=True))
    monkeypatch.setattr(
        imports,
        "_confirmed_parser_inputs",
        Mock(
            return_value=(
                CanonicalParserInput(
                    format="json",
                    repository_side="direct",
                    path="locales.json",
                    content=content,
                    layout_identity="json:locale-rooted:locales.json",
                    layout_version=1,
                    base_language="en",
                ),
            )
        ),
    )
    stage = Mock(return_value=None)
    monkeypatch.setattr(imports, "stage_translation_parse", stage)
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=Mock())
    factory.return_value.__exit__ = Mock(return_value=False)
    diagnostic_session = Mock()
    diagnostic_session.scalar.return_value = None
    factory.begin.return_value.__enter__ = Mock(return_value=diagnostic_session)
    factory.begin.return_value.__exit__ = Mock(return_value=False)
    with pytest.raises(ValueError, match="^canonical import execution is stale$"):
        await imports._process_import(identity, factory=factory, adapter=Mock())
    parsed = stage.call_args.kwargs["result"]
    assert not parsed.issues and {value.display_text for value in parsed.values} == {
        "Hello",
        "Ciao",
    }
    assert stage.call_args.kwargs["identity"] is identity


@pytest.mark.anyio
async def test_worker_stages_unique_values_when_duplicate_keys_are_quarantined(monkeypatch):
    identity = SimpleNamespace(
        execution_id=uuid4(),
        import_id=uuid4(),
        sequence=1,
        repository_sides=(
            SimpleNamespace(
                role="direct",
                repository_id=uuid4(),
                workspace="workspace",
                repository_slug="app",
                source_branch="main",
                localization_root=None,
            ),
        ),
    )
    content = b'{"en":{"dup":"One","safe":"Safe","dup":"Two"}}'
    discovered = SimpleNamespace(
        commit_hash="a" * 40,
        files=(SimpleNamespace(path="locales.json", content=content),),
    )
    parser_input = CanonicalParserInput(
        format="json",
        repository_side="direct",
        path="locales.json",
        content=content,
        layout_identity="json:locale-rooted:locales.json",
        layout_version=1,
        base_language="en",
    )
    monkeypatch.setattr(
        imports, "discover_repository_sources_for_record", AsyncMock(return_value=discovered)
    )
    monkeypatch.setattr(imports, "_canonical_import_enabled", Mock(return_value=True))
    monkeypatch.setattr(
        imports, "_confirmed_parser_inputs", Mock(return_value=(parser_input,))
    )
    stage = Mock(return_value=SimpleNamespace(digest="manifest"))
    monkeypatch.setattr(imports, "stage_translation_parse", stage)
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=Mock())
    factory.return_value.__exit__ = Mock(return_value=False)
    diagnostic_session = Mock()
    diagnostic_session.scalar.return_value = None
    factory.begin.return_value.__enter__ = Mock(return_value=diagnostic_session)
    factory.begin.return_value.__exit__ = Mock(return_value=False)

    processed = await imports._process_import(identity, factory=factory, adapter=Mock())

    parsed = stage.call_args.kwargs["result"]
    assert parsed.issues == ()
    assert [(value.logical_key, value.display_text) for value in parsed.values] == [
        ("safe", "Safe")
    ]
    assert processed.canonical_manifest_digest == "manifest"
