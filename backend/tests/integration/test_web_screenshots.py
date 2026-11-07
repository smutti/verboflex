"""Synthetic direct-import, exact selector, saved proposal and web capture authority."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from tests.integration.test_code_screenshots import _capture_client
from tests.integration.test_translation_import_activation import (
    _seed_running_direct_import,
    activation_session_factory,  # noqa: F401
    clean_activation_database,  # noqa: F401
)
from tests.legacy_product_fixtures import shared_reader
from verboflex.auth.principal import Principal
from verboflex.core.config import Settings, get_settings
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_mapping
from verboflex.localization.preview.registry import detect_preview_layouts
from verboflex.localization.web.config import JsonCatalogProfile
from verboflex.main import app
from verboflex.models.product_member import ProductMember
from verboflex.models.screenshot import ScreenshotJob
from verboflex.models.translation import TranslationKey, TranslationValue
from verboflex.schemas.users import RoleName
from verboflex.services.import_jobs import ImportSourceReferenceRecord, finish_import_execution
from verboflex.services.repositories import RepositoryRecord
from verboflex.services.repository_discovery import RepositorySourceFile
from verboflex.services.translation_imports import stage_translation_parse
from verboflex.services.web_imports import collect_web_context
from verboflex.worker import screenshot_tasks

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tools/fixtures/angular-web"


@pytest.fixture
def web_data(activation_session_factory, monkeypatch, tmp_path):  # noqa: F811
    app.dependency_overrides.clear()
    factory = activation_session_factory
    with factory.begin() as session:
        session.execute(delete(ScreenshotJob))
    commit = os.environ.get("VERBOFLEX_TEST_WEB_COMMIT", "a" * 40)
    profile = JsonCatalogProfile(
        files={"en": "en.json", "it": "it.json"},
        web_capture={
            "manifest_path": "capture.json",
            "source_roots": ["src"],
            "runner_profile": "angular-synthetic",
        },
    )
    identity, repository_id = _seed_running_direct_import(
        factory,
        localization_profile=profile.model_dump(mode="json"),
        localization_root="src/assets/i18n",
    )
    monkeypatch.setenv(
        "VERBOFLEX_WEB_EXTRACTOR_COMMAND",
        json.dumps(
            ["node", "--max-old-space-size=256", str(ROOT / "tools/web-runtime/extract.mjs")]
        ),
    )
    get_settings.cache_clear()
    files = {
        path.relative_to(FIXTURE).as_posix(): path.read_bytes()
        for path in (FIXTURE / "src").rglob("*")
        if path.is_file()
    }
    files["capture.json"] = (FIXTURE / "capture.json").read_bytes()
    catalogs = tuple(
        RepositorySourceFile(
            path=f"src/assets/i18n/{locale}.json", content=files[f"src/assets/i18n/{locale}.json"]
        )
        for locale in ("en", "it")
    )

    class Adapter:
        async def list_repository_source_page(self, session, **kwargs):
            assert kwargs["commit_hash"] == commit
            return SimpleNamespace(
                entries=[
                    SimpleNamespace(path=p, kind="file", size=len(c))
                    for p, c in files.items()
                    if p.startswith(kwargs["directory_path"] + "/")
                ],
                next_url=None,
            )

        async def read_repository_source_file(self, session, **kwargs):
            assert kwargs["commit_hash"] == commit
            return files[kwargs["path"]]

        async def resolve_repository_branch(self, *args, **kwargs):
            raise AssertionError("Web source collection must not resolve the branch again")

    with factory() as session:
        context, _ = asyncio.run(
            collect_web_context(
                session,
                profile=profile,
                repository=RepositoryRecord(
                    id=repository_id,
                    workspace="synthetic",
                    repository_slug="web",
                    descriptive_name=None,
                ),
                branch="main",
                commit=commit,
                adapter=Adapter(),
                root="src/assets/i18n",
                catalogs=catalogs,
                base_language="en",
            )
        )
    layout = detect_preview_layouts(catalogs, repository_side="direct").candidates[0]
    parsed = parse_canonical_mapping(
        tuple(
            CanonicalParserInput(
                format="json",
                repository_side="direct",
                path=f.path,
                content=f.content,
                layout_identity=layout.layout_identity,
                layout_version=1,
                base_language="en",
            )
            for f in catalogs
        )
    )
    assert not parsed.issues
    refs = tuple(
        ImportSourceReferenceRecord(
            position=i,
            repository_side="direct",
            repository_id=repository_id,
            source_branch="main",
            commit_hash=commit,
            path=f.path,
            size_bytes=len(f.content),
            sha256=hashlib.sha256(f.content).hexdigest(),
        )
        for i, f in enumerate(catalogs)
    )
    manifest = stage_translation_parse(
        factory, identity=identity, references=refs, result=parsed, web_context=context
    )
    assert manifest and finish_import_execution(
        factory, identity=identity, references=refs, canonical_manifest_digest=manifest.digest
    )
    actor = shared_reader(factory)
    with factory.begin() as session:
        session.get_one(
            ProductMember, (identity.product_id, actor)
        ).role = "product_manager_reviewer"
    principal = Principal(
        actor,
        "synthetic@example.test",
        "Synthetic reviewer",
        (RoleName.PRODUCT_MANAGER_REVIEWER,),
        False,
    )
    with factory() as session:
        values = {
            (
                key,
                value.language,
                tuple(json.loads(value.selector_bytes)["fields"]["parents"]),
            ): value.id
            for key, value in session.execute(
                select(TranslationKey.raw_key, TranslationValue).join(
                    TranslationValue, TranslationValue.translation_key_id == TranslationKey.id
                )
            )
        }
    if not os.environ.get("VERBOFLEX_TEST_WEB_IMAGE"):
        monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kwargs: None)
    try:
        yield factory, identity, principal, values, context
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def proposal_body(detail, replacement):
    return {
        "expected_version": detail["pending_change"]["version"] if detail["pending_change"] else 0,
        "values": [
            {
                "translation_value_id": v["id"],
                "selector_version": v["selector_version"],
                "selector_digest": v["selector_digest"],
                "basis_revision_number": v["history"][0]["revision_number"],
                "basis_digest": v["history"][0]["revision_digest"],
                "proposed_text": replacement
                if v["selector_fields"][0]["value"] != ["OTHER"]
                else v["display_text"],
            }
            for v in detail["values"]
        ],
    }


def test_web_exact_value_and_invalid_message_permissions(web_data, monkeypatch):
    factory, identity, principal, values, context = web_data
    assert context["sources"] and "capture.json" in {s["path"] for s in context["sources"]}
    group = min(
        value for (key, language, _), value in values.items() if key == "NAME" and language == "it"
    )
    validation = values[("MAX_LENGTH", "it", ("VALIDATE",))]

    async def exercise():
        async with _capture_client(factory, principal) as client:
            from verboflex.main import app

            app.dependency_overrides[get_settings] = lambda: Settings(
                web_screenshot_runner_command=["runner"]
            )
            response = await client.get(f"/api/v1/translations/{group}/code-context")
            assert response.status_code == 200, response.text
            source = response.json()
            assert source["engine"] == "web" and len(source["web_targets"]) == 1
            assert source["web_targets"][0]["json_path"] == ["SITE", "NAME"]
            bad = await client.put(
                f"/api/v1/translations/{group}/screenshots/{uuid4()}",
                json={
                    "engine": "web",
                    "scenario_id": "sites.list",
                    "target_value_id": str(values[("NAME", "it", ("OTHER",))]),
                },
            )
            assert bad.status_code == 409
            detail = (await client.get(f"/api/v1/translations/{validation}")).json()
            body = proposal_body(detail, "Removed parameter")
            invalid = await client.put(f"/api/v1/translations/{validation}/proposal", json=body)
            assert invalid.status_code == 422, invalid.text
            body = proposal_body(detail, "Massimo {{value.requiredLength}} caratteri")
            valid = await client.put(f"/api/v1/translations/{validation}/proposal", json=body)
            assert valid.status_code == 200, valid.text
            with factory.begin() as session:
                session.get_one(
                    ProductMember, (identity.product_id, principal.user_id)
                ).active = False
            denied = await client.put(
                f"/api/v1/translations/{validation}/screenshots/{uuid4()}",
                json={
                    "engine": "web",
                    "scenario_id": "tenant.create.validation",
                    "target_value_id": str(validation),
                    "proposal_version": valid.json()["version"],
                },
            )
            assert denied.status_code == 404

    asyncio.run(exercise())


@pytest.mark.skipif(
    not os.environ.get("VERBOFLEX_TEST_WEB_IMAGE"),
    reason="Run tools/web_capture_smoke.py for isolated Angular builds",
)
def test_real_celery_angular_twelve_captures(web_data, tmp_path):
    """Real queue, offline Docker build, Chromium, saved text and authenticated PNGs."""
    import subprocess
    import sys
    import time

    from verboflex.main import app

    factory, identity, principal, values, context = web_data
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "angular-synthetic": {
                    "repository_id": context["repository_id"],
                    "commit": context["commit"],
                    "mirror": os.environ["VERBOFLEX_TEST_WEB_MIRROR"],
                    "image": os.environ["VERBOFLEX_TEST_WEB_IMAGE"],
                }
            }
        )
    )
    command = [
        sys.executable,
        str(ROOT / "tools/web_capture_container.py"),
        "--profiles",
        str(profiles),
    ]
    environment = {k: v for k, v in os.environ.items() if not k.startswith("VERBOFLEX_")}
    environment.update(
        VERBOFLEX_DATABASE_URL=factory.kw["bind"].url.render_as_string(hide_password=False),
        VERBOFLEX_REDIS_URL=os.environ["VERBOFLEX_REDIS_URL"],
        VERBOFLEX_WEB_SCREENSHOT_RUNNER_COMMAND=json.dumps(command),
    )
    output = Path(os.environ["VERBOFLEX_TEST_WEB_EVIDENCE"])
    output.mkdir(parents=True, exist_ok=True)
    worker_log = (output / "celery.log").open("wb")
    worker = subprocess.Popen(
        [
            str(ROOT / "backend/.venv/bin/celery"),
            "-A",
            "verboflex.worker.celery_app",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--queues=screenshots",
            "--loglevel=WARNING",
        ],
        cwd=ROOT / "backend",
        env=environment,
        stdout=worker_log,
        stderr=subprocess.STDOUT,
    )
    receipts = []

    async def exercise():
        async with _capture_client(factory, principal) as client:
            app.dependency_overrides[get_settings] = lambda: Settings(
                web_screenshot_runner_command=command
            )
            for language in ("en", "it"):
                for scenario, key, parents in [
                    ("sites.list", "NAME", ("SITE",)),
                    ("tenant.create.open", "CREATE", ("TENANT",)),
                    ("tenant.create.validation", "MAX_LENGTH", ("VALIDATE",)),
                ]:
                    target = values[(key, language, parents)]
                    group = min(
                        value
                        for (k, lang, _), value in values.items()
                        if k == key and lang == language
                    )
                    base = f"/api/v1/translations/{group}"
                    detail = (await client.get(base)).json()
                    replacement = f"Saved {language}: " + (
                        "{{value.requiredLength}} characters" if key == "MAX_LENGTH" else scenario
                    )
                    saved = await client.put(
                        base + "/proposal", json=proposal_body(detail, replacement)
                    )
                    assert saved.status_code == 200, saved.text
                    version = saved.json()["version"]
                    for viewport in ("desktop", "mobile"):
                        path = base + f"/screenshots/{uuid4()}"
                        response = await client.put(
                            path,
                            json={
                                "engine": "web",
                                "scenario_id": scenario,
                                "target_value_id": str(target),
                                "viewport": viewport,
                                "proposal_version": version,
                            },
                        )
                        assert response.status_code == 202, response.text
                        deadline = time.monotonic() + 180
                        while True:
                            job = (await client.get(path)).json()
                            if job["state"] not in {"queued", "rendering"}:
                                break
                            assert time.monotonic() < deadline, "Web worker timeout"
                            await asyncio.sleep(0.3)
                        assert job["state"] == "succeeded", job
                        assert job["receipt"]["text"] == replacement.replace(
                            "{{value.requiredLength}}", "97"
                        )
                        assert job["receipt"]["commit"] == context["commit"]
                        image = await client.get(path + "/image")
                        assert (
                            image.status_code == 200
                            and image.headers["cache-control"] == "private, no-store"
                        )
                        assert hashlib.sha256(image.content).hexdigest() == job["image_digest"]
                        (output / f"{scenario}-{language}-{viewport}.png").write_bytes(
                            image.content
                        )
                        receipts.append(job)
            (output / "receipt.json").write_text(json.dumps(receipts, indent=2))
            assert len(receipts) == 12
            assert len({job["receipt"]["render_id"] for job in receipts}) == 12

    try:
        asyncio.run(exercise())
    finally:
        worker.terminate()
        worker.wait(timeout=20)
        worker_log.close()
