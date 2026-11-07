"""Language creation through real imports, HTTP, PostgreSQL and the Git outbox."""

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.integration.test_branch_workflow import Remote, run
from tests.integration.test_confirmed_layout_refresh import (
    RefreshSource,
    _published_confirmation,
    _run,
)
from tests.integration.test_preview_jobs import (  # noqa: F401
    clean_preview_database,
    preview_session_factory,
)
from tests.legacy_product_fixtures import mirror_fixture_role
from verboflex.auth.principal import Principal, get_current_principal
from verboflex.db.session import get_db_session
from verboflex.main import app
from verboflex.models.branch_workflow import BranchJob
from verboflex.models.role import Role
from verboflex.models.translation import TranslationValue
from verboflex.models.user import User
from verboflex.schemas.users import RoleName
from verboflex.worker import import_tasks

CASES = {
    "json": ({"locales/en.json": b'{"MENU":{"NAME":"Hello {{name}}"}}'}, "locales/fr.json"),
    "rooted_json": (
        {"catalog.json": b'{"en":{"hello":"Hello %s"},"it":{"hello":"Ciao %s"}}'},
        "catalog.json",
    ),
    "android": (
        {
            "app/res/values/strings.xml": (
                b'<resources><string name="hello">Hello %1$s</string></resources>'
            )
        },
        "app/res/values-fr/strings.xml",
    ),
    "moko": (
        {
            "shared/moko-resources/base/strings.xml": (
                b'<resources><string name="hello">Hello %1$s</string></resources>'
            )
        },
        "shared/moko-resources/fr/strings.xml",
    ),
    "separate_moko": (
        {
            "app/src/main/Screen.kt": (
                b'package demo\nobject Keys {\n    const val HELLO = "hello"\n}\n'
                b"fun Screen() = Res.strings.hello\n"
            ),
            "shared/moko-resources/base/strings.xml": (
                b'<resources><string name="hello">Hello %1$s</string>'
                b'<string name="other">One</string><string name="other">Two</string></resources>'
            ),
        },
        "shared/moko-resources/fr/strings.xml",
    ),
    "ios": (
        {"app/en.lproj/Localizable.strings": b'// keep\n"hello" = "Hello %@";\n'},
        "app/fr.lproj/Localizable.strings",
    ),
    "qt": (
        {
            "messages_en.ts": (
                b'<TS version="2.1" language="en"><context><name>Main</name><message i'
                b'd="hello"><source>Hello %1</source><translation>Hello %1</translatio'
                b"n></message></context></TS>"
            )
        },
        "messages_fr.ts",
    ),
    "xliff": (
        {
            "locales/en.xlf": (
                b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2"><'
                b'file original="app" source-language="en" target-language="en" dataty'
                b'pe="plaintext"><body><trans-unit id="hello"><source>Hello <x id="1"/'
                b'></source><target>Hello <x id="1"/></target></trans-unit></body></fi'
                b"le></xliff>"
            )
        },
        "locales/fr.xlf",
    ),
    "html": (
        {"mail/Welcome-EN.html": b"<html><body><p>Hello {{name}}</p></body></html>"},
        "mail/Welcome-FR.html",
    ),
}


@pytest.fixture
def language_api(preview_session_factory, monkeypatch, request):  # noqa: F811
    factory = preview_session_factory
    case = getattr(request, "param", "json")
    if case == "angular":
        import json

        from verboflex.core.config import get_settings

        root = Path(__file__).resolve().parents[3]
        fixture = root / "tools/fixtures/angular-web"
        files = {
            p.relative_to(fixture).as_posix(): p.read_bytes()
            for p in (fixture / "src").rglob("*")
            if p.is_file()
        }
        files["capture.json"] = (fixture / "capture.json").read_bytes()
        target = "src/assets/i18n/fr.json"
        monkeypatch.setenv(
            "VERBOFLEX_WEB_EXTRACTOR_COMMAND",
            json.dumps(
                ["node", "--max-old-space-size=256", str(root / "tools/web-runtime/extract.mjs")]
            ),
        )
        get_settings.cache_clear()
    else:
        files, target = CASES[case]
    profile = {"files": {"en": "locales/en.json"}} if case == "json" else None
    if case == "angular":
        profile = {
            "files": {"en": "en.json", "it": "it.json"},
            "web_capture": {
                "manifest_path": "capture.json",
                "source_roots": ["src"],
                "catalog_url_prefix": "/",
                "runner_profile": "angular-synthetic",
            },
        }
        # Catalog URLs must be relative to the real capture loader, not the repo root.
        profile["web_capture"]["catalog_url_prefix"] = "/assets/i18n/"

    class Source(RefreshSource):
        async def list_repository_source_page(self, session, **kwargs):
            from verboflex.integrations.bitbucket.client import (
                BitbucketSourceEntry,
                BitbucketSourcePage,
            )

            if kwargs["directory_path"] is None:
                return await super().list_repository_source_page(session, **kwargs)
            return BitbucketSourcePage(
                entries=tuple(
                    BitbucketSourceEntry(path=path, kind="file", size=len(content))
                    for path, content in self.files.items()
                    if path.startswith(kwargs["directory_path"] + "/")
                ),
                next_url=None,
            )

    adapter = Source(files=dict(files), commit_hashes=["a" * 40])
    product_id, mapping_id = _published_confirmation(
        factory,
        adapter,
        localization_profile=profile,
        localization_root="src/assets/i18n" if case == "angular" else None,
        code_source=case == "separate_moko",
    )
    monkeypatch.setattr(import_tasks, "SessionFactory", factory)
    monkeypatch.setattr(import_tasks, "create_repository_read_adapters", lambda _: adapter)
    assert _run(factory, product_id, mapping_id).state == "current"
    actor_id = uuid4()
    with factory.begin() as session:
        session.add(
            User(
                id=actor_id,
                email=f"{actor_id}@example.test",
                display_name="Language reviewer",
                hashed_password="unused",
                is_active=True,
                must_change_password=False,
                roles=[session.scalar(select(Role).where(Role.name == "admin"))],
            )
        )
    principal = Principal(
        actor_id, f"{actor_id}@example.test", "Language reviewer", (RoleName.ADMIN,), False
    )
    seed = SimpleNamespace(
        product_id=product_id,
        mapping_id=mapping_id,
        actor_id=actor_id,
        adapter=adapter,
        target=target,
    )

    def db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            result = client.put(
                f"/api/v1/products/{product_id}/branch-workflow",
                json={
                    "mapping_id": str(mapping_id),
                    "work_branch": "main",
                    "target_branch": "release",
                },
            )
            assert result.status_code == 200, result.text
            seed.workflow_id = result.json()["workflow_id"]
            seed.endpoint = f"/api/v1/products/{product_id}/languages"
            yield client, seed, factory
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("language_api", list(CASES), indirect=True)
def test_create_commit_refresh_and_duplicate_rejection_for_every_format(language_api):
    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202, response.text
    job_id = UUID(response.json()["id"])
    with factory() as session:
        job = session.get_one(BranchJob, job_id)
        assert job.state == "queued" and job.intent is None
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    assert run(factory, remote, job_id) == ("committed", None)
    assert seed.target in remote.versions[remote.head]
    assert remote.prs == []
    assert len(remote.commits) == 1
    assert run(factory, remote, job_id) == ("committed", None)
    assert len(remote.commits) == 1
    for path, content in seed.adapter.files.items():
        if path != seed.target:
            assert remote.versions[remote.head][path] == content
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    with factory() as session:
        values = session.scalars(
            select(TranslationValue).where(TranslationValue.language == "fr")
        ).all()
        assert values and all(not v.is_deleted for v in values)
        assert all("Hello" in value.display_text for value in values)
    duplicate = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert duplicate.status_code == 409
    # A second language extends the first verified registration instead of replacing it.
    second = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "de"})
    assert second.status_code == 202, second.text
    assert run(factory, remote, UUID(second.json()["id"])) == ("committed", None)
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    with factory() as session:
        assert {v.language for v in session.scalars(select(TranslationValue))} >= {"en", "fr", "de"}


@pytest.mark.parametrize("role", ["translator", "viewer"])
def test_creation_denies_non_reviewers(language_api, role):
    client, seed, factory = language_api
    with factory.begin() as session:
        session.get_one(User, seed.actor_id).roles = [
            session.scalar(select(Role).where(Role.name == role))
        ]
        mirror_fixture_role(session, seed.actor_id)
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 403
    with factory() as session:
        assert session.scalar(select(BranchJob.id)) is None


def test_pending_requests_and_revocation_before_send(language_api):
    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202
    assert (
        client.post(
            seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"}
        ).status_code
        == 409
    )
    with factory.begin() as session:
        session.get_one(User, seed.actor_id).is_active = False
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    assert run(factory, remote, UUID(response.json()["id"])) == ("blocked", "authority_changed")
    assert remote.commits == []


def test_uncertain_send_reconciles_without_duplicate_commit(language_api):
    from verboflex.services.branch_workflow import retry_job

    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202
    job_id = UUID(response.json()["id"])
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    remote.uncertain = True
    assert run(factory, remote, job_id) == ("blocked", "timeout")
    assert client.delete(seed.endpoint + "/" + str(job_id)).status_code == 409
    with factory.begin() as session:
        retry_job(session, product_id=seed.product_id, actor_id=seed.actor_id, job_id=job_id)
    assert run(factory, remote, job_id) == ("committed", None)
    assert len(remote.commits) == 1


def test_registered_catalogs_require_verified_commit_same_project_and_unchanged_profile(
    language_api,
):
    from tests.integration.test_preview_jobs import _seed_preview_graph
    from verboflex.models.product_mapping import ProductRepositoryMapping
    from verboflex.services.project_languages import registered_catalog_profile

    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202
    with factory() as session:
        mapping = session.get_one(ProductRepositoryMapping, seed.mapping_id)
        assert registered_catalog_profile(session, mapping).files == {"en": "locales/en.json"}
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    assert run(factory, remote, UUID(response.json()["id"])) == ("committed", None)
    _, _, foreign_revision, _ = _seed_preview_graph(factory)
    with factory() as session:
        mapping = session.get_one(ProductRepositoryMapping, seed.mapping_id)
        assert registered_catalog_profile(session, mapping).files == {
            "en": "locales/en.json",
            "fr": "locales/fr.json",
        }
        assert mapping.localization_profile["files"] == {"en": "locales/en.json"}
        original = {
            "revision_id": mapping.revision_id,
            "identity_key": mapping.identity_key,
            "localization_profile": mapping.localization_profile,
        }
        for changed in (
            {"revision_id": foreign_revision},
            {"identity_key": "another-mapping"},
            {
                "localization_profile": {
                    **mapping.localization_profile,
                    "rich_text_paths": [["MENU", "NAME"]],
                }
            },
        ):
            other = SimpleNamespace(**{**original, **changed})
            assert registered_catalog_profile(session, other).files == {"en": "locales/en.json"}


def test_stale_import_blocks_without_commit_and_can_be_discarded(language_api):
    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202
    job_id = UUID(response.json()["id"])
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    remote.head = "b" * 40
    remote.versions[remote.head] = dict(seed.adapter.files)
    assert run(factory, remote, job_id) == ("blocked", "import_changed")
    assert remote.commits == []
    assert client.delete(seed.endpoint + "/" + str(job_id)).status_code == 200
    assert (
        client.post(
            seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"}
        ).status_code
        == 202
    )


@pytest.mark.parametrize("language_api", ["angular"], indirect=True)
@pytest.mark.skipif(
    not os.environ.get("VERBOFLEX_TEST_WEB_IMAGE"),
    reason="Run tools/web_capture_smoke.py for isolated Angular builds",
)
def test_created_language_renders_three_real_angular_scenarios(language_api, tmp_path):
    import hashlib
    import json
    import subprocess
    import sys
    import time

    from tests.integration.test_web_screenshots import proposal_body
    from verboflex.core.config import Settings, get_settings
    from verboflex.models.import_job import ImportExecution
    from verboflex.models.translation import LocalizationScope, TranslationKey

    client, seed, factory = language_api
    response = client.post(seed.endpoint, json={"workflow_id": seed.workflow_id, "language": "fr"})
    assert response.status_code == 202, response.text
    remote = Remote(seed, factory, work_branch="main", target_branch="release")
    assert run(factory, remote, UUID(response.json()["id"])) == ("committed", None)
    seed.adapter.files = dict(remote.versions[remote.head])
    seed.adapter.commit_hashes = [remote.head]
    assert _run(factory, seed.product_id, seed.mapping_id).state == "current"
    with factory() as session:
        scope = session.scalar(
            select(LocalizationScope).where(LocalizationScope.product_id == seed.product_id)
        )
        context = session.get_one(ImportExecution, scope.active_execution_id).web_context
        values = list(
            session.execute(
                select(TranslationValue, TranslationKey)
                .join(TranslationKey, TranslationKey.id == TranslationValue.translation_key_id)
                .where(TranslationValue.language == "fr")
            )
        )
        targets = {
            (key.raw_key, tuple(json.loads(value.selector_bytes)["fields"]["parents"])): value.id
            for value, key in values
        }
        groups = {
            key.raw_key: min(v.id for v, k in values if k.raw_key == key.raw_key)
            for _, key in values
        }
    assert context["catalog_urls"]["fr"] == "/assets/i18n/fr.json"
    root = Path(__file__).resolve().parents[3]
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "angular-synthetic": {
                    "repository_id": context["repository_id"],
                    "commit": os.environ["VERBOFLEX_TEST_WEB_COMMIT"],
                    "catalog_overlays": True,
                    "source_digest": context["source_digest"],
                    "mirror": os.environ["VERBOFLEX_TEST_WEB_MIRROR"],
                    "image": os.environ["VERBOFLEX_TEST_WEB_IMAGE"],
                }
            }
        )
    )
    command = [
        sys.executable,
        str(root / "tools/web_capture_container.py"),
        "--profiles",
        str(profiles),
    ]
    app.dependency_overrides[get_settings] = lambda: Settings(web_screenshot_runner_command=command)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("VERBOFLEX_")}
    environment.update(
        VERBOFLEX_DATABASE_URL=factory.kw["bind"].url.render_as_string(hide_password=False),
        VERBOFLEX_REDIS_URL=os.environ["VERBOFLEX_REDIS_URL"],
        VERBOFLEX_WEB_SCREENSHOT_RUNNER_COMMAND=json.dumps(command),
    )
    output = Path(os.environ["VERBOFLEX_TEST_WEB_EVIDENCE"])
    receipts = []
    with (output / "new-language-celery.log").open("wb") as log:
        worker = subprocess.Popen(
            [
                str(root / "backend/.venv/bin/celery"),
                "-A",
                "verboflex.worker.celery_app",
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--queues=screenshots",
                "--loglevel=WARNING",
            ],
            cwd=root / "backend",
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for scenario, key, parent, replacement in [
                ("sites.list", "NAME", "SITE", "Nom du site"),
                ("tenant.create.open", "CREATE", "TENANT", "Créer un locataire"),
                (
                    "tenant.create.validation",
                    "MAX_LENGTH",
                    "VALIDATE",
                    "Maximum {{value.requiredLength}} caractères",
                ),
            ]:
                target = targets[(key, (parent,))]
                base = f"/api/v1/translations/{groups[key]}"
                detail = client.get(base).json()
                saved = client.put(base + "/proposal", json=proposal_body(detail, replacement))
                assert saved.status_code == 200, saved.text
                for viewport in ("desktop", "mobile"):
                    path = base + f"/screenshots/{uuid4()}"
                    result = client.put(
                        path,
                        json={
                            "engine": "web",
                            "scenario_id": scenario,
                            "target_value_id": str(target),
                            "viewport": viewport,
                            "proposal_version": saved.json()["version"],
                        },
                    )
                    assert result.status_code == 202, result.text
                    deadline = time.monotonic() + 180
                    while True:
                        job = client.get(path).json()
                        if job["state"] not in ("queued", "rendering"):
                            break
                        assert time.monotonic() < deadline, "Web worker timeout"
                        time.sleep(0.3)
                    assert job["state"] == "succeeded", job
                    receipt = job["receipt"]
                    assert receipt["language"] == "fr"
                    assert receipt["commit"] == remote.head
                    assert receipt["application_commit"] == os.environ["VERBOFLEX_TEST_WEB_COMMIT"]
                    assert receipt["text"] == replacement.replace("{{value.requiredLength}}", "97")
                    image = client.get(path + "/image")
                    assert image.status_code == 200
                    assert hashlib.sha256(image.content).hexdigest() == job["image_digest"]
                    (output / f"new-language-{scenario}-{viewport}.png").write_bytes(image.content)
                    receipts.append(job)
            assert len(receipts) == len({job["receipt"]["render_id"] for job in receipts}) == 6
            (output / "new-language-receipts.json").write_text(json.dumps(receipts, indent=2))
        finally:
            worker.terminate()
            worker.wait(timeout=20)
            app.dependency_overrides.pop(get_settings, None)
