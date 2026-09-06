"""A confirmed layout follows current immutable files through the real worker."""

from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from tests.integration.test_import_jobs import ProviderResourceSpy
from tests.integration.test_preview_jobs import (
    _seed_preview_graph,
    clean_preview_database,  # noqa: F401 -- shared PostgreSQL isolation fixture
    preview_session_factory,  # noqa: F401 -- shared PostgreSQL database fixture
)
from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketAncestry
from verboflex.models.bitbucket_connection import BitbucketConnection
from verboflex.models.import_job import ImportJob
from verboflex.models.translation import (
    LocalizationScope,
    TranslationKey,
    TranslationParseIssue,
    TranslationValue,
    TranslationValueLocator,
)
from verboflex.models.user import User
from verboflex.services import import_jobs, preview_jobs
from verboflex.services.publication import publish_product_candidate
from verboflex.worker import import_tasks
from verboflex.worker.preview_tasks import process_preview


class RefreshSource(ProviderResourceSpy):
    async def compare_repository_ancestry(self, _session, **kwargs):
        return BitbucketAncestry(
            old_commit_hash=kwargs["old_commit_hash"],
            new_commit_hash=kwargs["new_commit_hash"],
            relation="descendant",
            complete=True,
        )

    async def aclose(self):
        pass


def _xml(text, *, extra=""):
    return f'<resources><string name="hello">{text}</string>{extra}</resources>'.encode()


def _published_confirmation(factory, adapter):
    product_id, _, revision_id, mapping_id = _seed_preview_graph(factory)
    with factory() as session:
        job = preview_jobs.create_or_reuse_preview_job(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            expected_candidate_version=4,
            commits={"direct": "a" * 40},
            enqueuer=lambda _: None,
        )
    preview_jobs.execute_preview_job(
        factory,
        job_id=job.id,
        processor=lambda identity: process_preview(identity, factory=factory, adapter=adapter),
    )
    with factory() as session:
        completed = preview_jobs.get_preview_job(session, job_id=job.id)
    assert completed.state == "succeeded"
    assert len(completed.result["layout_candidates"]) == 1
    candidate = completed.result["layout_candidates"][0]
    actor = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=actor,
                email=f"refresh-{actor}@example.com",
                display_name="Reviewer",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
            )
        )
    with factory() as session:
        preview_jobs.confirm_preview_job(
            session,
            job_id=job.id,
            preview_digest=completed.result["digest"],
            layout_candidate_id=UUID(candidate["id"]),
            layout_candidate_version=1,
            base_language="en",
            actor_id=actor,
        )
    with factory() as session:
        publish_product_candidate(
            session,
            product_id=product_id,
            candidate_revision_id=revision_id,
            expected_candidate_version=4,
        )
    return product_id, mapping_id


def _run(factory, product_id, mapping_id):
    with factory() as session:
        job = import_jobs.start_or_refresh_import(
            session,
            product_id=product_id,
            mapping_id=mapping_id,
            enqueuer=lambda _: None,
        )
    import_tasks.run_import_job.run(str(job.id))
    with factory() as session:
        return session.get_one(ImportJob, job.id)


@pytest.mark.parametrize("failure", ["malformed", "stale"])
def test_worker_refresh_tracks_new_locale_and_moved_files_without_changing_identity(
    preview_session_factory, monkeypatch, failure
):
    factory = preview_session_factory
    adapter = RefreshSource(
        files={
            "app/res/values-en/old.xml": _xml("Hello"),
            "app/res/values-it/old.xml": _xml("Ciao"),
        },
        commit_hashes=["a" * 40],
    )
    product_id, mapping_id = _published_confirmation(factory, adapter)
    settings = Settings(
        bitbucket_oauth_client_id="worker-test-client",
        bitbucket_oauth_client_secret=SecretStr("worker-test-secret"),
        bitbucket_token_encryption_keyring=SecretStr(Fernet.generate_key().decode()),
    )
    monkeypatch.setattr(import_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "BitbucketHttpAdapter", lambda **_: adapter)
    initial = _run(factory, product_id, mapping_id)
    assert initial.state == "current"
    with factory() as session:
        original = {
            value.language: (value.id, value.translation_key_id)
            for value in session.scalars(select(TranslationValue))
        }
    assert set(original) == {"en", "it"}

    adapter.commit_hashes = ["b" * 40]
    adapter.files = {
        "app/res/values/moved.xml": _xml(
            "Hello",
            extra=(
                '<plurals name="count"><item quantity="one">One</item>'
                '<item quantity="other">Many</item></plurals>'
                '<string-array name="choices"><item>Yes</item></string-array>'
            ),
        ),
        "app/res/values-it/moved.xml": _xml("Salve"),
        "app/res/values-fr/added.xml": _xml("Bonjour"),
        "other/res/values/ignored.xml": _xml("Outside confirmed layout"),
    }
    refreshed = _run(factory, product_id, mapping_id)
    assert refreshed.state == "current"
    assert refreshed.active_baseline_execution_id != initial.active_baseline_execution_id
    with factory() as session:
        values = list(
            session.scalars(
                select(TranslationValue)
                .join(TranslationKey, TranslationKey.id == TranslationValue.translation_key_id)
                .where(TranslationKey.raw_key == "hello")
            )
        )
        assert {value.language: value.text for value in values} == {
            "en": "Hello",
            "it": "Salve",
            "fr": "Bonjour",
        }
        assert {
            value.language: (value.id, value.translation_key_id)
            for value in values
            if value.language in original
        } == original
        scope = session.scalar(select(LocalizationScope))
        epoch = scope.dataset_version
        assert scope.active_execution_id == refreshed.active_baseline_execution_id
        assert set(session.scalars(select(TranslationKey.raw_key))) == {"hello", "count", "choices"}
        assert set(session.scalars(select(TranslationValueLocator.path))) == {
            "app/res/values/moved.xml",
            "app/res/values-it/moved.xml",
            "app/res/values-fr/added.xml",
        }

    adapter.commit_hashes = ["c" * 40]
    adapter.files["app/res/values-it/moved.xml"] = _xml("Must not activate")
    if failure == "malformed":
        adapter.files["app/res/values-fr/added.xml"] = b"<resources>PRIVATE_RAW_FAILURE"
    else:
        with factory.begin() as session:
            session.get_one(BitbucketConnection, 1).generation += 1
    failed = _run(factory, product_id, mapping_id)
    assert failed.state == "import_failed"
    assert failed.active_baseline_execution_id == refreshed.active_baseline_execution_id
    with factory() as session:
        assert session.get_one(LocalizationScope, scope.id).dataset_version == epoch
        assert session.get_one(TranslationValue, original["it"][0]).text == "Salve"
        issues = list(session.scalars(select(TranslationParseIssue)))
        assert issues
        assert all("PRIVATE_RAW_FAILURE" not in issue.message for issue in issues)
