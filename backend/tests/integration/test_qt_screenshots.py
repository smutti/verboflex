"""Synthetic Qt imports, exact context selection, saved drafts and capture permissions."""

import asyncio
import hashlib
import json
from uuid import uuid4

import pytest
from sqlalchemy import select

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
from verboflex.localization.qt_capture import QtManifest
from verboflex.main import app
from verboflex.models.product_member import ProductMember
from verboflex.models.screenshot import ScreenshotJob
from verboflex.models.translation import TranslationValue
from verboflex.schemas.users import RoleName
from verboflex.services.import_jobs import ImportSourceReferenceRecord, finish_import_execution
from verboflex.services.qt_imports import collect_qt_context
from verboflex.services.translation_imports import stage_translation_parse
from verboflex.worker import screenshot_tasks


@pytest.fixture
def qt_data(activation_session_factory, monkeypatch):  # noqa: F811
    factory = activation_session_factory
    identity, repository_id = _seed_running_direct_import(factory, base_language="en-US")
    manifest = QtManifest(
        runner_profile="synthetic",
        width=800,
        height=480,
        qt_version="5.15.8",
        platform="offscreen",
        sources={"screen.ui": "a" * 64},
        scenarios=[{"id": "home", "label": "Home", "context": "Main", "source": "Hello"}],
    )
    inputs = tuple(
        CanonicalParserInput(
            format="qt_ts",
            repository_side="direct",
            path=f"i18n/app_{lang}.ts",
            content=(
                f'<TS version="2.1" language="{lang}" sourcelanguage="en_US">'
                "<context><name>Main</name><message><source>Hello</source>"
                f"<translation>{text}</translation></message>"
                "<message><source>Hello</source><comment>other meaning</comment>"
                "<translation>Other meaning</translation></message></context>"
                "<context><name>Other</name><message><source>Hello</source>"
                "<translation>Other screen</translation></message></context></TS>"
            ).encode(),
            layout_identity="qt-ts:i18n/app_{locale}.ts",
            layout_version=1,
            base_language="en-US",
        )
        for lang, text in (("en_US", "Hello"), ("it_IT", "Ciao"))
    )

    class Adapter:
        async def read_repository_source_file(self, session, **kwargs):
            assert not session.in_transaction()
            assert kwargs["commit_hash"] == "a" * 40
            assert kwargs["path"] == ".verboflex/qt-screenshots.json"
            return manifest.model_dump_json().encode()

    data = asyncio.run(
        collect_qt_context(
            factory,
            identity=identity,
            adapter=Adapter(),
            parser_inputs=inputs,
            commits={"direct": "a" * 40},
        )
    )
    refs = tuple(
        ImportSourceReferenceRecord(
            position=i,
            repository_side="direct",
            repository_id=repository_id,
            source_branch="main",
            commit_hash="a" * 40,
            path=item.path,
            size_bytes=len(item.content),
            sha256=hashlib.sha256(item.content).hexdigest(),
        )
        for i, item in enumerate(inputs)
    )
    result = parse_canonical_mapping(inputs)
    assert not result.issues
    staged = stage_translation_parse(
        factory, identity=identity, references=refs, result=result, qt_context=data
    )
    assert staged and finish_import_execution(
        factory, identity=identity, references=refs, canonical_manifest_digest=staged.digest
    )
    actor = shared_reader(factory)
    with factory.begin() as session:
        session.get_one(
            ProductMember, (identity.product_id, actor)
        ).role = "product_manager_reviewer"
        values = {
            tuple(sorted(json.loads(v.selector_bytes)["fields"].items())): v.id
            for v in session.scalars(
                select(TranslationValue).where(TranslationValue.language == "it-IT")
            )
        }
    principal = Principal(
        actor, "synthetic@example.test", "Reviewer", (RoleName.PRODUCT_MANAGER_REVIEWER,), False
    )
    monkeypatch.setattr(screenshot_tasks.app, "send_task", lambda *args, **kwargs: None)
    app.dependency_overrides[get_settings] = lambda: Settings(
        qt_screenshot_runner_command=["runner"]
    )
    try:
        yield factory, identity, principal, values
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_qt_exact_context_saved_proposal_and_revocation(qt_data, monkeypatch):
    factory, identity, principal, values = qt_data
    group = min(values.values())
    target = values[(("context", "Main"), ("identity_kind", "source"))]
    other = values[(("context", "Other"), ("identity_kind", "source"))]
    base = f"/api/v1/translations/{group}"

    async def exercise():
        async with _capture_client(factory, principal) as client:
            app.dependency_overrides[get_settings] = lambda: Settings(
                qt_screenshot_runner_command=["runner"]
            )
            response = await client.get(base + "/code-context")
            assert response.status_code == 200, response.text
            context = response.json()
            assert context["engine"] == "qt" and len(context["qt_targets"]) == 1
            assert context["qt_targets"][0]["value_id"] == str(target)
            body = {"engine": "qt", "scenario_id": "home", "target_value_id": str(other)}
            bad = await client.put(base + f"/screenshots/{uuid4()}", json=body)
            assert bad.status_code == 409
            body["target_value_id"] = str(target)
            invalid = await client.put(
                base + f"/screenshots/{uuid4()}", json={**body, "viewport": "mobile"}
            )
            assert invalid.status_code == 422
            detail = (await client.get(base)).json()
            saved = await client.put(
                base + "/proposal",
                json={
                    "expected_version": 0,
                    "values": [
                        {
                            "translation_value_id": v["id"],
                            "selector_version": v["selector_version"],
                            "selector_digest": v["selector_digest"],
                            "basis_revision_number": v["history"][0]["revision_number"],
                            "basis_digest": v["history"][0]["revision_digest"],
                            "proposed_text": "Bozza salvata"
                            if v["id"] == str(target)
                            else v["display_text"],
                        }
                        for v in detail["values"]
                    ],
                },
            )
            assert saved.status_code == 200, saved.text
            body["proposal_version"] = saved.json()["version"]
            job_id = uuid4()
            response = await client.put(base + f"/screenshots/{job_id}", json=body)
            assert response.status_code == 202, response.text
            with factory() as session:
                row = session.get_one(ScreenshotJob, job_id)
                assert row.inputs["target_text"] == "Bozza salvata"
                assert row.inputs["language"] == "it-IT"
                assert row.inputs["scenario"]["context"] == "Main"
            stale = await client.put(
                base + f"/screenshots/{uuid4()}", json={**body, "proposal_version": 99}
            )
            assert stale.status_code == 409
            with factory.begin() as session:
                session.get_one(
                    ProductMember, (identity.product_id, principal.user_id)
                ).active = False
            monkeypatch.setattr(
                screenshot_tasks,
                "render_qt",
                lambda _: pytest.fail("Revoked access must not render"),
            )
            screenshot_tasks.execute_capture(job_id, factory)
            with factory() as session:
                assert (
                    session.get_one(ScreenshotJob, job_id).error_code == "source_or_access_changed"
                )
            denied = await client.get(base + f"/screenshots/{job_id}/image")
            assert denied.status_code == 404

    asyncio.run(exercise())
