"""Worker adapter lifecycle through real durable import discovery."""

import hashlib
from dataclasses import dataclass

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.test_import_jobs import (
    COMMIT_HASH,
    ProviderResourceSpy,
    _seed_published_direct_mapping,
    clean_import_database,
    import_session_factory,
)
from verboflex.core.config import Settings
from verboflex.services.import_jobs import start_import_execution, start_or_refresh_import
from verboflex.worker import import_tasks

__all__ = ["clean_import_database", "import_session_factory"]


@dataclass
class ClosingProvider(ProviderResourceSpy):
    closed: bool = False

    async def aclose(self) -> None:
        self.closed = True


def test_production_worker_discovers_exact_source_and_closes_provider(
    import_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    product_id, _, repository_id, mapping_id = _seed_published_direct_mapping(
        import_session_factory
    )
    with import_session_factory() as session:
        job = start_or_refresh_import(
            session, product_id=product_id, mapping_id=mapping_id, enqueuer=lambda _id: None
        )
    identity = start_import_execution(import_session_factory, import_id=job.id)
    assert identity is not None
    path = "mobile/src/main/res/values/strings.xml"
    content = b'<resources><string name="save">Save</string></resources>'
    provider = ClosingProvider(files={path: content})
    settings = Settings(
        bitbucket_oauth_client_id="worker-test-client",
        bitbucket_oauth_client_secret=SecretStr("worker-test-secret"),
        bitbucket_token_encryption_keyring=SecretStr(Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(import_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(import_tasks, "SessionFactory", import_session_factory)
    monkeypatch.setattr(import_tasks, "BitbucketHttpAdapter", lambda **_kwargs: provider)

    result = import_tasks.production_import_processor(identity)

    assert provider.closed is True
    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.repository_id == repository_id
    assert reference.repository_side == "direct"
    assert reference.path == path
    assert reference.commit_hash == COMMIT_HASH
    assert reference.sha256 == hashlib.sha256(content).hexdigest()
    assert reference.size_bytes == len(content)
    assert result.movement is None
    assert result.canonical_manifest_digest is None
    assert any(f"/src/{COMMIT_HASH}/{path}" in url for _, url in provider.requests)
