"""Real preview/import/review authority for immutable write-back preparation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import event, select, text

from tests.integration.test_confirmed_layout_refresh import (
    RefreshSource,
    _published_confirmation,
    _run,
)
from tests.integration.test_preview_jobs import (
    _seed_preview_graph,
    clean_preview_database,  # noqa: F401
    preview_session_factory,  # noqa: F401
)
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.auth.principal import Principal
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketBranch, BitbucketSourceMetadata
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.product import Product
from verboflex.models.product_mapping import ProductMappingRepositorySide, ProductRepositoryMapping
from verboflex.models.repository import Repository
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.role import Role
from verboflex.models.translation import (
    TranslationKey,
    TranslationValue,
    TranslationValueLocator,
    TranslationValueRevision,
)
from verboflex.models.translation_constraint import TranslationConstraint
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services import preview_jobs
from verboflex.services.publication import publish_product_candidate
from verboflex.services.translation_reviews import (
    save_translation_proposal,
    transition_translation_proposal,
)
from verboflex.services.writeback import (
    ProposalSelection,
    WritebackSelection,
    prepare_writeback,
    revalidate_writeback_authority,
)
from verboflex.worker import import_tasks
from verboflex.worker.preview_tasks import process_preview

__all__ = ["clean_preview_database", "preview_session_factory"]


def _published_separate(factory, adapter):
    product_id, _, revision_id, mapping_id = _seed_preview_graph(factory)
    with factory.begin() as session:
        mapping = session.get(ProductRepositoryMapping, mapping_id)
        keys_id = mapping.sides[0].repository_id
        session.get(Repository, keys_id).repository_slug = "keys-repository"
        translations = Repository(
            workspace="preview-team", repository_slug="translations-repository"
        )
        session.add(translations)
        session.flush()
        mapping.topology = "separate"
        mapping.identity_key = (
            f'[["keys","{keys_id}","main"],["translations","{translations.id}","main"]]'
        )
        mapping.sides[0].role = "keys"
        mapping.sides.append(
            ProductMappingRepositorySide(
                role="translations", repository_id=translations.id, source_branch="main"
            )
        )
        actor = User(
            id=uuid4(),
            email=f"{uuid4()}@example.test",
            display_name="Confirmation",
            hashed_password="unused",
            must_change_password=False,
        )
        session.add(actor)
        actor_id = actor.id
    with factory() as session:
        job = preview_jobs.create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"keys": "a" * 40, "translations": "a" * 40},
            enqueuer=lambda _: None,
            actor_id=None,
        )
    preview_jobs.execute_preview_job(
        factory,
        job_id=job.id,
        processor=lambda identity: process_preview(identity, factory=factory, adapter=adapter),
    )
    with factory() as session:
        completed = preview_jobs.get_preview_job(session, job_id=job.id)
        assert completed.state == "succeeded"
        candidate = next(
            item
            for item in completed.result["layout_candidates"]
            if item["repository_side"] == "translations"
        )
        preview_jobs.confirm_preview_job(
            session,
            job_id=job.id,
            preview_digest=completed.result["digest"],
            layout_candidate_id=UUID(candidate["id"]),
            layout_candidate_version=1,
            base_language="en",
            actor_id=actor_id,
        )
    with factory() as session:
        publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=revision_id,
            expected_candidate_version=4,
            actor_id=None,
        )
    return product_id, mapping_id


class SeparateSource(RefreshSource):
    async def list_repository_source_page(self, session, **kwargs):
        page = await super().list_repository_source_page(session, **kwargs)
        if kwargs["repository_slug"] == "keys-repository":
            return replace(
                page, entries=tuple(entry for entry in page.entries if "values-en" in entry.path)
            )
        return page


def seed_writeback_authority(factory, monkeypatch, *, separate=False, members=2):
    """Reusable 06/07 fixture: no fabricated selectors, locators or byte digests."""
    adapter = (SeparateSource if separate else RefreshSource)(
        files={
            f"app/res/values-{language}/strings.xml": (
                (
                    f'<resources><plurals name="hello"><item quantity="one">{one}</item>'
                    f'<item quantity="other">{other}</item></plurals></resources>'
                )
                if members == 2
                else (
                    '<resources><string-array name="hello">'
                    + "".join(f"<item>{one} {index}</item>" for index in range(members))
                    + "</string-array></resources>"
                )
            ).encode()
            for language, one, other in (("en", "Hello", "Hellos"), ("it", "Ciao", "Saluti"))
        },
        commit_hashes=["a" * 40],
    )
    product_id, mapping_id = (_published_separate if separate else _published_confirmation)(
        factory, adapter
    )
    settings = Settings(
        bitbucket_oauth_client_id="worker-test-client",
        bitbucket_oauth_client_secret=SecretStr("worker-test-secret"),
        bitbucket_token_encryption_keyring=SecretStr(Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(import_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "create_repository_read_adapters", lambda _: adapter)
    job = _run(factory, product_id, mapping_id)
    assert job.state == "current"
    actor_id = uuid4()
    principal = Principal(actor_id, f"{actor_id}@example.test", "Writer", (RoleName.ADMIN,), False)
    with factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=principal.email,
                display_name=principal.display_name,
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
                roles=[session.scalars(select(Role).where(Role.name == "admin")).one()],
            )
        )
    with factory.begin() as session:
        values = tuple(
            session.scalars(
                select(TranslationValue)
                .join(TranslationKey, TranslationKey.id == TranslationValue.translation_key_id)
                .where(TranslationValue.language == "it", TranslationKey.product_id == product_id)
                .order_by(TranslationValue.id)
            )
        )
        assert len(values) == members
        revisions = {
            value.id: session.scalars(
                select(TranslationValueRevision)
                .where(TranslationValueRevision.value_id == value.id)
                .order_by(TranslationValueRevision.revision_number.desc())
            ).first()
            for value in values
        }
        saved = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=values[0].id,
            expected_version=0,
            values=[
                {
                    "translation_value_id": value.id,
                    "selector_version": value.selector_version,
                    "selector_digest": value.selector_digest,
                    "basis_revision_number": revisions[value.id].revision_number,
                    "basis_digest": revisions[value.id].revision_digest,
                    "proposed_text": "Ok",
                }
                for value in values
            ],
        )
        approved = transition_translation_proposal(
            session,
            principal=principal,
            translation_group_id=values[0].id,
            target_state="approved",
            expected_version=saved.version,
            reason=None,
        )
        proposal = session.scalars(
            select(TranslationProposal).where(
                TranslationProposal.translation_key_id == values[0].translation_key_id
            )
        ).one()
        return SimpleNamespace(
            actor_id=actor_id,
            product_id=product_id,
            mapping_id=mapping_id,
            proposal_id=proposal.id,
            version=approved.version,
            value_ids=tuple(v.id for v in values),
            key_id=values[0].translation_key_id,
            adapter=adapter,
            execution_id=job.active_baseline_execution_id,
        )


def _capture(factory, seed):
    from verboflex.services.writeback_authority import (
        ProposalSelection,
        WritebackSelection,
        capture_writeback_authority,
    )

    with factory.begin() as session:
        return capture_writeback_authority(
            session,
            selection=WritebackSelection(
                seed.actor_id, (ProposalSelection(seed.proposal_id, seed.version),)
            ),
        )


def test_capture_complete_current_approved_aggregate(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    writes = []

    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    try:
        result = _capture(factory, seed)
        assert result == _capture(factory, seed)
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", observe)
    assert not writes
    assert result.actor_id == seed.actor_id and result.roles == ("admin",)
    assert len(result.proposals[0].members) == 2
    assert result.mappings[0].execution_id == seed.execution_id
    assert len(result.mappings[0].source_references) == 2
    assert len(result.files) == 1 and len(result.files[0].edits) == 2
    assert result.files[0].parser_input.content == b""
    assert "encrypted-access" not in repr(result)
    assert "Ciao" not in repr(result) and "Saluti" not in repr(result)


def test_unchanged_refresh_keeps_basis_and_updates_locator(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    before = _capture(factory, seed)
    seed.adapter.commit_hashes = ["b" * 40]
    job = _run(factory, seed.product_id, seed.mapping_id)
    assert job.state == "current"
    after = _capture(factory, seed)
    assert after.proposals[0].members[0].basis_digest == before.proposals[0].members[0].basis_digest
    assert (
        after.files[0].authority.import_execution_id
        != before.files[0].authority.import_execution_id
    )
    assert after.files[0].authority.commit_hash == "b" * 40


def test_selected_file_uses_exact_confirmed_layout(preview_session_factory, monkeypatch):
    seed = seed_writeback_authority(preview_session_factory, monkeypatch)
    result = _capture(preview_session_factory, seed)
    parser = result.files[0].parser_input
    assert (parser.format, parser.layout_identity, parser.layout_version, parser.base_language) == (
        "android_xml",
        "app/res",
        1,
        "en",
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "deleted",
        "inactive",
        "foreign",
        "version",
        "draft",
        "incomplete",
        "basis",
        "locator",
        "format",
        "constraint",
        "actor",
        "roles",
        "password",
        "connection",
        "confirmation",
    ],
)
def test_foreign_or_deleted_authority_is_rejected(preview_session_factory, monkeypatch, mutation):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        if mutation == "deleted":
            session.get(TranslationKey, seed.key_id).is_deleted = True
            session.get(TranslationKey, seed.key_id).deleted_at = datetime.now(UTC)
        elif mutation == "inactive":
            session.get(Product, seed.product_id).is_active = False
        elif mutation == "foreign":
            seed.proposal_id = uuid4()
        elif mutation == "version":
            seed.version += 1
        elif mutation == "draft":
            session.get(TranslationProposal, seed.proposal_id).state = "draft"
        elif mutation == "incomplete":
            session.delete(
                session.scalars(
                    select(TranslationProposalValue).where(
                        TranslationProposalValue.proposal_id == seed.proposal_id
                    )
                ).first()
            )
        elif mutation == "basis":
            session.scalars(
                select(TranslationProposalValue).where(
                    TranslationProposalValue.proposal_id == seed.proposal_id
                )
            ).first().basis_digest = "f" * 64
        elif mutation == "locator":
            session.execute(text("SET LOCAL session_replication_role = replica"))
            session.get(TranslationValueLocator, seed.value_ids[0]).source_commit_hash = "b" * 40
        elif mutation == "format":
            session.get(TranslationValueLocator, seed.value_ids[0]).format = "json"
        elif mutation == "constraint":
            key = session.get(TranslationKey, seed.key_id)
            session.add(
                TranslationConstraint(
                    scope_id=key.scope_id,
                    translation_key_id=key.id,
                    language="en",
                    max_chars=1,
                    created_by=seed.actor_id,
                    updated_by=seed.actor_id,
                )
            )
        elif mutation == "actor":
            session.get(User, seed.actor_id).is_active = False
        elif mutation == "roles":
            session.get(User, seed.actor_id).roles = []
            mirror_fixture_role(session, session.get(User, seed.actor_id).id)
        elif mutation == "password":
            session.get(User, seed.actor_id).must_change_password = True
        elif mutation == "connection":
            session.get(BitbucketConnection, 1).access_token_ciphertext = None
        elif mutation == "confirmation":
            # Simulate damaged historical evidence only in this disposable DB;
            # ordinary writes are already rejected by immutable-graph triggers.
            session.execute(text("SET LOCAL session_replication_role = replica"))
            session.get(ProductRepositoryMapping, seed.mapping_id).confirmed_preview_digest = (
                "b" * 64
            )
    with pytest.raises(WritebackRejected):
        _capture(factory, seed)


def test_normal_credential_renewal_captures_current_generation(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    before = _capture(factory, seed)
    with factory.begin() as session:
        session.get(BitbucketConnection, 1).generation += 1
        session.get(User, seed.actor_id).token_version += 1
    after = _capture(factory, seed)
    assert after.connection_generation == before.connection_generation + 1
    assert after.actor_token_version == before.actor_token_version + 1
    assert after.mappings == before.mappings


def test_stale_identity_map_cannot_supply_authority(preview_session_factory, monkeypatch):
    from verboflex.services.writeback_authority import (
        ProposalSelection,
        WritebackSelection,
        capture_writeback_authority,
    )

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory() as stale:
        cached = stale.get(TranslationProposal, seed.proposal_id)
        with factory.begin() as concurrent:
            concurrent.get(TranslationProposal, seed.proposal_id).state = "draft"
        assert cached.state == "approved"
        with pytest.raises(WritebackRejected):
            capture_writeback_authority(
                stale,
                selection=WritebackSelection(
                    seed.actor_id, (ProposalSelection(seed.proposal_id, seed.version),)
                ),
            )


def test_selection_is_bounded_and_exact():
    from verboflex.services.writeback_authority import ProposalSelection, WritebackSelection

    item = ProposalSelection(uuid4(), 2)
    for proposals in ((), (item, item), (item,) * 5001):
        with pytest.raises(WritebackRejected):
            WritebackSelection(uuid4(), proposals)
    with pytest.raises(WritebackRejected):
        replace(item, expected_version=True)


def test_separate_mapping_retains_all_sides_but_only_translation_files(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch, separate=True)
    result = _capture(factory, seed)
    assert {side.repository_side for side in result.mappings[0].sides} == {"keys", "translations"}
    assert len(result.mappings[0].source_references) == 3
    assert {file.authority.repository_side for file in result.files} == {"translations"}
    with factory.begin() as session:
        session.execute(text("SET LOCAL session_replication_role = replica"))
        session.get(TranslationValueLocator, seed.value_ids[0]).repository_side = "keys"
    with pytest.raises(WritebackRejected):
        _capture(factory, seed)


def test_aggregate_reference_budget_is_enforced_before_retention(
    preview_session_factory, monkeypatch
):
    from verboflex.services import writeback_authority as authority

    factory = preview_session_factory
    first = seed_writeback_authority(factory, monkeypatch)
    second = seed_writeback_authority(factory, monkeypatch)
    monkeypatch.setattr(authority, "MAX_CANONICAL_FILES", 3)
    with factory.begin() as session, pytest.raises(WritebackRejected) as rejected:
        authority.capture_writeback_authority(
            session,
            selection=authority.WritebackSelection(
                first.actor_id,
                (
                    authority.ProposalSelection(first.proposal_id, first.version),
                    authority.ProposalSelection(second.proposal_id, second.version),
                ),
            ),
        )
    assert rejected.value.reason.value == "limit_exceeded"


def test_proposed_text_constraint_is_independent_of_imported_cache(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        key = session.get(TranslationKey, seed.key_id)
        session.add(
            TranslationConstraint(
                scope_id=key.scope_id,
                translation_key_id=key.id,
                language="en",
                max_chars=2,
                created_by=seed.actor_id,
                updated_by=seed.actor_id,
            )
        )
        before = [
            (value.id, value.effective_max_chars, value.is_over_limit)
            for value in session.scalars(
                select(TranslationValue).where(TranslationValue.id.in_(seed.value_ids))
            )
        ]
    captured = _capture(factory, seed)
    assert captured.proposals[0].effective_maximum == 2
    assert len(captured.proposals[0].constraints) == 1
    with factory() as session:
        assert before == [
            (value.id, value.effective_max_chars, value.is_over_limit)
            for value in session.scalars(
                select(TranslationValue).where(TranslationValue.id.in_(seed.value_ids))
            )
        ]


def test_capture_rejects_budget_before_rich_projection_or_anchor_load(
    preview_session_factory, monkeypatch
):
    from verboflex.services import translation_search, writeback_authority

    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    source_bytes = sum(len(content) for content in seed.adapter.files.values())
    budget = source_bytes + 50
    with factory.begin() as session:
        for pending in session.scalars(
            select(TranslationProposalValue).where(
                TranslationProposalValue.proposal_id == seed.proposal_id
            )
        ):
            pending.proposed_text = "x" * budget
    processed = []
    loaded = []

    def note_load(value, _context):
        loaded.append(value.id)

    original = translation_search.grapheme_count
    monkeypatch.setattr(
        translation_search,
        "grapheme_count",
        lambda value: (processed.append(len(value)), original(value))[1],
    )
    monkeypatch.setattr(writeback_authority, "MAX_CANONICAL_AGGREGATE_BYTES", budget)
    event.listen(TranslationValue, "load", note_load)
    try:
        with pytest.raises(WritebackRejected) as error:
            _capture(factory, seed)
    finally:
        event.remove(TranslationValue, "load", note_load)
    assert error.value.reason.value == "limit_exceeded"
    assert not loaded, "oversize group loaded TranslationValue before its database byte/count gate"
    assert processed == [], (
        "oversize pending text reached rich UI projection before the budget gate"
    )


class PreparedSource:
    """Provider barrier held while an independent session changes DB authority."""

    def __init__(self, seed):
        self.seed = seed
        self.arrived = Event()
        self.release = Event()
        self.pause = False
        self.interrupt = False
        self.heads = {}
        self.sessions = []

    async def resolve_repository_branch(self, session, **kwargs):
        self.sessions.append(session)
        assert not session.in_transaction()
        return BitbucketBranch(
            kwargs["branch"], self.heads.get(kwargs["repository_slug"], "a" * 40)
        )

    async def read_repository_metadata(self, session, **kwargs):
        from uuid import NAMESPACE_URL, uuid5

        self.sessions.append(session)
        assert not session.in_transaction()
        name = f"{kwargs['workspace']}/{kwargs['repository_slug']}"
        return {"type": "repository", "full_name": name, "uuid": str(uuid5(NAMESPACE_URL, name))}

    async def read_repository_source_metadata(self, session, **kwargs):
        self.sessions.append(session)
        assert not session.in_transaction()
        return BitbucketSourceMetadata(
            kwargs["path"], kwargs["commit_hash"], len(self.seed.adapter.files[kwargs["path"]]), ()
        )

    async def read_repository_source_file(self, session, **kwargs):
        self.sessions.append(session)
        assert not session.in_transaction()
        if self.pause:
            self.pause = False
            self.arrived.set()
            assert await asyncio.to_thread(self.release.wait, 15), (
                "DB mutation did not release provider barrier"
            )
        if self.interrupt:
            raise asyncio.CancelledError()
        content = self.seed.adapter.files[kwargs["path"]]
        assert len(content) <= kwargs["max_bytes"]
        return content


def _prepared(factory, seed, reader):
    return asyncio.run(
        prepare_writeback(
            factory,
            selection=WritebackSelection(
                seed.actor_id, (ProposalSelection(seed.proposal_id, seed.version),)
            ),
            adapter=reader,
        )
    )


def _race_prepared(factory, seed, mutate):
    reader = PreparedSource(seed)
    prepared = _prepared(factory, seed, reader)
    reader.pause = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            lambda: asyncio.run(
                revalidate_writeback_authority(factory, prepared=prepared, adapter=reader)
            )
        )
        try:
            assert reader.arrived.wait(15), "revalidation never reached provider barrier"
            mutate(reader)
        finally:
            reader.release.set()
        with pytest.raises(WritebackRejected) as error:
            pending.result(timeout=15)
    assert error.value.reason in {
        WritebackReason.STALE_BASIS,
        WritebackReason.AUTHORITY_UNAVAILABLE,
        WritebackReason.SOURCE_BRANCH_CHANGED,
    }
    return prepared


def test_race_proposal_version_invalidates_prepared(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)

    def mutate(_reader):
        with factory.begin() as session:
            session.execute(text("SET LOCAL lock_timeout='1000ms'"))
            session.get(TranslationProposal, seed.proposal_id).version += 1

    _race_prepared(factory, seed, mutate)


def test_race_import_activation_invalidates_prepared(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)

    def mutate(_reader):
        job = _run(factory, seed.product_id, seed.mapping_id)
        assert job.state == "current"
        assert job.active_baseline_execution_id != seed.execution_id

    _race_prepared(factory, seed, mutate)


def test_race_constraint_change_invalidates_prepared(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)

    def mutate(_reader):
        with factory.begin() as session:
            session.execute(text("SET LOCAL lock_timeout='1000ms'"))
            key = session.get(TranslationKey, seed.key_id)
            session.add(
                TranslationConstraint(
                    scope_id=key.scope_id,
                    translation_key_id=key.id,
                    language="en",
                    max_chars=100,
                    created_by=seed.actor_id,
                    updated_by=seed.actor_id,
                )
            )

    _race_prepared(factory, seed, mutate)


@pytest.mark.parametrize(
    "mutation", ["actor", "token", "roles", "connection", "generation", "deleted", "reconciliation"]
)
def test_race_actor_or_connection_change_invalidates_prepared(
    preview_session_factory, monkeypatch, mutation
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)

    def mutate(_reader):
        with factory.begin() as session:
            session.execute(text("SET LOCAL lock_timeout='1000ms'"))
            if mutation == "actor":
                session.get(User, seed.actor_id).is_active = False
            elif mutation == "token":
                session.get(User, seed.actor_id).token_version += 1
            elif mutation == "roles":
                session.get(User, seed.actor_id).roles = []
                mirror_fixture_role(session, session.get(User, seed.actor_id).id)
            elif mutation == "connection":
                session.get(BitbucketConnection, 1).access_token_ciphertext = None
            elif mutation == "generation":
                session.get(BitbucketConnection, 1).generation += 1
            elif mutation == "deleted":
                key = session.get(TranslationKey, seed.key_id)
                key.is_deleted = True
                key.deleted_at = datetime.now(UTC)
            elif mutation == "reconciliation":
                proposal = session.get(TranslationProposal, seed.proposal_id)
                proposal.state = "draft"
                proposal.reconciliation_required = True

    _race_prepared(factory, seed, mutate)


@pytest.mark.parametrize("side", ["keys-repository", "translations-repository"])
def test_race_separate_source_sides_invalidate_prepared(preview_session_factory, monkeypatch, side):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch, separate=True)
    _race_prepared(factory, seed, lambda reader: reader.heads.update({side: "b" * 40}))


def _observe_mutations():
    writes = []

    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    return writes, observe


def test_preparation_leaves_imports_and_proposals_unchanged(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    before = _capture(factory, seed)
    reader = PreparedSource(seed)
    writes, observe = _observe_mutations()
    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    try:
        prepared = _prepared(factory, seed, reader)
        asyncio.run(revalidate_writeback_authority(factory, prepared=prepared, adapter=reader))
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", observe)
    assert not writes
    assert _capture(factory, seed) == before
    assert len({id(session) for session in reader.sessions}) == len(reader.sessions)
    assert prepared.files[0].original_bytes == seed.adapter.files[prepared.files[0].authority.path]


def test_interrupted_preparation_has_no_durable_effect(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    before = _capture(factory, seed)
    reader = PreparedSource(seed)
    reader.interrupt = True
    writes, observe = _observe_mutations()
    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    try:
        with pytest.raises(asyncio.CancelledError):
            _prepared(factory, seed, reader)
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", observe)
    assert not writes and _capture(factory, seed) == before


@pytest.mark.parametrize("all_noop", [False, True])
def test_complete_noop_members_remain_bound_to_manifest(
    preview_session_factory, monkeypatch, all_noop
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        pending = tuple(
            session.scalars(
                select(TranslationProposalValue)
                .where(TranslationProposalValue.proposal_id == seed.proposal_id)
                .order_by(TranslationProposalValue.translation_value_id)
            )
        )
        for item in pending if all_noop else pending[:1]:
            item.proposed_text = session.get(
                TranslationValue, item.translation_value_id
            ).display_text
    prepared = _prepared(factory, seed, PreparedSource(seed))
    assert len(prepared.authority.proposals[0].members) == 2
    assert len(prepared.files[0].changed_edits) == (0 if all_noop else 1)
    asyncio.run(
        revalidate_writeback_authority(factory, prepared=prepared, adapter=PreparedSource(seed))
    )


class RenewingSource(PreparedSource):
    async def resolve_repository_branch(self, session, **kwargs):
        assert not session.in_transaction()
        # Models the established read-lease service: token lifecycle only,
        # completed before returning any repository data to the caller.
        with session.begin():
            connection = session.get(BitbucketConnection, 1)
            if connection.provider_expires_at <= datetime.now(UTC) + timedelta(seconds=60):
                connection.generation += 1
                connection.provider_expires_at = datetime.now(UTC) + timedelta(hours=1)
        return await super().resolve_repository_branch(session, **kwargs)


def test_expired_credentials_renew_before_definitive_capture(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        connection = session.get(BitbucketConnection, 1)
        before_generation = connection.generation
        connection.provider_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    reader = RenewingSource(seed)
    prepared = _prepared(factory, seed, reader)
    assert prepared.authority.connection_generation == before_generation + 1
    assert _prepared(factory, seed, reader) == prepared


def test_renewal_never_reauthorizes_old_prepared(preview_session_factory, monkeypatch):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    prepared = _prepared(factory, seed, PreparedSource(seed))
    original_generation = prepared.authority.connection_generation
    with factory.begin() as session:
        session.get(BitbucketConnection, 1).provider_expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    with pytest.raises(WritebackRejected) as error:
        asyncio.run(
            revalidate_writeback_authority(factory, prepared=prepared, adapter=RenewingSource(seed))
        )
    assert error.value.reason == WritebackReason.STALE_BASIS
    assert prepared.authority.connection_generation == original_generation


def test_retired_member_is_excluded_after_live_proposal_is_resaved(
    preview_session_factory, monkeypatch
):
    factory = preview_session_factory
    seed = seed_writeback_authority(factory, monkeypatch)
    with factory.begin() as session:
        retired = session.get_one(TranslationValue, seed.value_ids[0])
        retired.is_deleted = True
        retired.deleted_at = datetime.now(UTC)
    # The old proposal still contains the deleted member and must remain blocked.
    with pytest.raises(WritebackRejected):
        _capture(factory, seed)
    principal = Principal(
        seed.actor_id, f"{seed.actor_id}@example.test", "Writer", (RoleName.ADMIN,), False
    )
    with factory.begin() as session:
        live = session.get_one(TranslationValue, seed.value_ids[1])
        revision = session.scalars(
            select(TranslationValueRevision)
            .where(TranslationValueRevision.value_id == live.id)
            .order_by(TranslationValueRevision.revision_number.desc())
        ).first()
        saved = save_translation_proposal(
            session,
            principal=principal,
            translation_group_id=seed.value_ids[0],
            expected_version=seed.version,
            values=[
                {
                    "translation_value_id": live.id,
                    "selector_version": live.selector_version,
                    "selector_digest": live.selector_digest,
                    "basis_revision_number": revision.revision_number,
                    "basis_digest": revision.revision_digest,
                    "proposed_text": "Current only",
                }
            ],
        )
        approved = transition_translation_proposal(
            session,
            principal=principal,
            translation_group_id=seed.value_ids[0],
            expected_version=saved.version,
            target_state="approved",
            reason=None,
        )
        seed.version = approved.version
    result = _capture(factory, seed)
    assert len(result.proposals[0].members) == 1
    assert result.proposals[0].members[0].value_id == seed.value_ids[1]
