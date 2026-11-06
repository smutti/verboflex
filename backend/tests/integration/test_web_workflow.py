"""Profile preview/import, HTTP review, exact writeback bytes and worker refresh."""

import asyncio
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from tests.integration.test_code_screenshots import _capture_client
from tests.integration.test_confirmed_layout_refresh import (
    RefreshSource,
    _published_confirmation,
    _run,
)
from tests.integration.test_preview_jobs import (  # noqa: F401
    clean_preview_database,
    preview_session_factory,
)
from tests.integration.test_web_screenshots import proposal_body
from tests.integration.test_writeback_authority import PreparedSource
from verboflex.auth.principal import Principal
from verboflex.core.config import Settings
from verboflex.localization.writing.core import WritebackRejected
from verboflex.models.review import TranslationProposal, TranslationProposalValue
from verboflex.models.role import Role
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.services.writeback import ProposalSelection, WritebackSelection, prepare_writeback
from verboflex.worker import import_tasks


def test_web_profile_preview_review_writeback_refresh(preview_session_factory, monkeypatch):  # noqa: F811
    factory = preview_session_factory
    original = b'{\n  "SITE": { "NAME": "Ciao {{ name }}" },\n  "OTHER": "unchanged"\n}\n'
    adapter = RefreshSource(
        files={
            "locales/en.json": b'{"SITE":{"NAME":"Hello {{name}}"},"OTHER":"unchanged"}',
            "locales/it.json": original,
            "locales/template.json": b"not even valid JSON",
        },
        commit_hashes=["a" * 40],
    )
    product, mapping = _published_confirmation(
        factory,
        adapter,
        localization_profile={
            "files": {"en": "locales/en.json", "it": "locales/it.json"},
        },
    )
    settings = Settings(
        bitbucket_oauth_client_id="fixture",
        bitbucket_oauth_client_secret=SecretStr("fixture"),
        bitbucket_token_encryption_keyring=SecretStr(Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(import_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "create_repository_read_adapters", lambda _: adapter)
    imported = _run(factory, product, mapping)
    assert imported.state == "current"
    with factory.begin() as session:
        actor = session.scalars(select(User)).one()
        actor.roles = [session.scalars(select(Role).where(Role.name == "admin")).one()]
        principal = Principal(actor.id, actor.email, actor.display_name, (RoleName.ADMIN,), False)
        target = session.scalar(
            select(TranslationValue.id).where(
                TranslationValue.language == "it",
                TranslationValue.display_text == "Ciao {{ name }}",
            )
        )
    assert target

    async def review():
        async with _capture_client(factory, principal) as client:
            path = f"/api/v1/translations/{target}"
            detail = (await client.get(path)).json()
            invalid = await client.put(
                path + "/proposal", json=proposal_body(detail, "Missing parameter")
            )
            assert invalid.status_code == 422
            saved = await client.put(
                path + "/proposal", json=proposal_body(detail, "Benvenuto {{name}}")
            )
            assert saved.status_code == 200, saved.text
            # Simulate a retained proposal predating enforcement of this contract.
            with factory.begin() as session:
                session.scalars(
                    select(TranslationProposalValue)
                ).one().proposed_text = "Lost parameter"
            refused = await client.post(
                path + "/proposal/state",
                json={
                    "target_state": "approved",
                    "expected_version": saved.json()["version"],
                    "reason": None,
                },
            )
            assert refused.status_code == 409, refused.text
            with factory.begin() as session:
                session.scalars(
                    select(TranslationProposalValue)
                ).one().proposed_text = "Benvenuto {{name}}"
            approved = await client.post(
                path + "/proposal/state",
                json={
                    "target_state": "approved",
                    "expected_version": saved.json()["version"],
                    "reason": None,
                },
            )
            assert approved.status_code == 200, approved.text
            return approved.json()["version"]

    version = asyncio.run(review())
    with factory() as session:
        proposal = session.scalars(select(TranslationProposal)).one()
        selection = WritebackSelection(
            principal.user_id, (ProposalSelection(proposal.id, version),)
        )
    with factory.begin() as session:
        session.scalars(select(TranslationProposalValue)).one().proposed_text = "Lost parameter"
    with pytest.raises(WritebackRejected):
        asyncio.run(
            prepare_writeback(
                factory,
                selection=selection,
                adapter=PreparedSource(SimpleNamespace(adapter=adapter)),
            )
        )
    with factory.begin() as session:
        session.scalars(select(TranslationProposalValue)).one().proposed_text = "Benvenuto {{name}}"
    prepared = asyncio.run(
        prepare_writeback(
            factory, selection=selection, adapter=PreparedSource(SimpleNamespace(adapter=adapter))
        )
    )
    assert len(prepared.files) == 1
    rendered = prepared.files[0]
    assert rendered.authority.path == "locales/it.json"
    assert rendered.content == original.replace(b"Ciao {{ name }}", b"Benvenuto {{name}}")
    adapter.files[rendered.authority.path] = rendered.content
    adapter.commit_hashes = ["b" * 40]
    refreshed = _run(factory, product, mapping)
    assert refreshed.state == "current"
    assert refreshed.active_baseline_execution_id != imported.active_baseline_execution_id
    with factory() as session:
        assert session.get_one(TranslationValue, target).display_text == "Benvenuto {{name}}"
    assert not any(url.endswith("/template.json") for _, url in adapter.requests)
