"""Synthetic Angular AST, exact runtime addresses and legacy request compatibility."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from verboflex.localization.web.context import catalog_addresses, set_catalog_value
from verboflex.localization.web.contracts import WebManifest
from verboflex.schemas.screenshots import ScreenshotRequest

ROOT = Path(__file__).resolve().parents[4]


def test_same_leaf_names_keep_distinct_exact_addresses():
    catalog = {"A": {"NAME": "A"}, "B": {"NAME": "B"}, "literal.dot": "C"}
    addresses = catalog_addresses(catalog)
    assert addresses["A.NAME"] == ("A", "NAME")
    assert addresses["literal.dot"] == ("literal.dot",)
    set_catalog_value(catalog, addresses["B.NAME"], "Changed")
    assert catalog == {"A": {"NAME": "A"}, "B": {"NAME": "Changed"}, "literal.dot": "C"}
    with pytest.raises(ValueError, match="Ambiguous"):
        catalog_addresses({"a.b": "literal", "a": {"b": "nested"}})


def test_legacy_compose_requests_keep_the_exact_v1_shape():
    data = {"preview_function": "demo.Preview", "theme": "light", "proposal_version": None}
    assert ScreenshotRequest.model_validate(data).as_payload() == data
    with pytest.raises(ValidationError):
        ScreenshotRequest(engine="web", scenario_id="sites.list")
    with pytest.raises(ValidationError):
        ScreenshotRequest(
            engine="web", scenario_id="sites.list", target_value_id=uuid4(), theme="dark"
        )


@pytest.mark.parametrize(
    "change",
    [
        {"route": "//evil.test"},
        {"route": "https://evil.test"},
        {"actions": [{"action": "evaluate", "selector": "body"}]},
        {"responses": [{"path": "https://evil.test", "body": {}}]},
    ],
)
def test_manifest_cannot_supply_commands_or_external_destinations(change):
    scenario = {
        "id": "sites.list",
        "label": "Sites",
        "route": "#/sites",
        "ready": "body",
        "targets": [{"key": "SITE.NAME", "selector": "h1"}],
        **change,
    }
    with pytest.raises(ValidationError):
        WebManifest.model_validate({"version": 1, "scenarios": [scenario]})


def test_angular_parser_uses_ast_and_reports_dynamic_references(tmp_path):
    source = """import { TranslateService } from '@ngx-translate/core';
    import { inject as di } from '@angular/core';
    class Example {
      constructor(private translate: TranslateService) {}
      show(dynamic: string) { this.translate.instant('SITE.NAME'); this.translate.get(dynamic); }
      shadow(translate: Other) { translate.get('SHADOW.IGNORED'); }
    }
    class Unrelated { translate: Other; show(){this.translate.get('UNRELATED.IGNORED');} }
    class Injected {
      service = di(TranslateService);
      show(){this.service.instant('INJECTED.KEY');}
    }
    // translate.instant('COMMENT.IGNORED')
    const ordinary = "'FAKE.KEY' | translate";
    other.get('NOT.TRANSLATE');
    _('MARKED.KEY');
    """
    request, output = tmp_path / "input.json", tmp_path / "output.json"
    request.write_text(
        json.dumps(
            {
                "files": {
                    "src/app/test.ts": source,
                    "src/app/test.html": (
                        "<!-- 'IGNORE' | translate --><h1>{{ 'TENANT.CREATE' | translate }}</h1>"
                    ),
                },
                "marker": "_",
            }
        )
    )
    subprocess.run(
        ["node", str(ROOT / "tools/web-runtime/extract.mjs"), str(request), str(output)],
        check=True,
        timeout=20,
    )
    data = json.loads(output.read_text())["occurrences"]
    assert {item["key"] for item in data} == {
        "SITE.NAME",
        "TENANT.CREATE",
        "MARKED.KEY",
        "INJECTED.KEY",
        None,
    }
    request.write_text(json.dumps({"files": {"bad.ts": "function { broken"}, "marker": "_"}))
    assert (
        subprocess.run(
            ["node", str(ROOT / "tools/web-runtime/extract.mjs"), str(request), str(output)],
            capture_output=True,
            timeout=20,
        ).returncode
        != 0
    )


def test_context_blocks_cross_locale_literal_dot_path_mismatch(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    from verboflex.localization.web.config import JsonCatalogProfile
    from verboflex.services import web_imports
    from verboflex.services.repositories import RepositoryRecord
    from verboflex.services.repository_discovery import RepositorySourceFile

    profile = JsonCatalogProfile(
        files={"en": "en.json", "it": "it.json"},
        web_capture={"manifest_path": "capture.json", "runner_profile": "synthetic"},
    )
    manifest = {
        "version": 1,
        "scenarios": [
            {
                "id": "sites.list",
                "label": "Sites",
                "route": "#/sites",
                "ready": "h1",
                "targets": [{"key": "SITE.NAME", "selector": "h1"}],
            }
        ],
    }

    class Adapter:
        async def read_repository_source_file(self, *args, **kwargs):
            assert kwargs["commit_hash"] == "a" * 40
            return json.dumps(manifest).encode()

    async def discover(*args, **kwargs):
        assert kwargs["commit_hash"] == "a" * 40
        return SimpleNamespace(files=())

    monkeypatch.setattr(web_imports, "discover_repository_sources_for_record", discover)
    monkeypatch.setattr(web_imports, "extract_usages", lambda *_: {"occurrences": []})
    context, _ = asyncio.run(
        web_imports.collect_web_context(
            object(),
            profile=profile,
            repository=RepositoryRecord(
                id=uuid4(), workspace="synthetic", repository_slug="web", descriptive_name=None
            ),
            branch="main",
            commit="a" * 40,
            adapter=Adapter(),
            root=None,
            base_language="en",
            catalogs=(
                RepositorySourceFile(path="en.json", content=b'{"SITE.NAME":"Name"}'),
                RepositorySourceFile(path="it.json", content=b'{"SITE":{"NAME":"Nome"}}'),
            ),
        )
    )
    assert context["capture_blocked"] is True
    assert any("incompatible literal-dot" in item for item in context["diagnostics"])
    assert context["catalogs"]["it"] == {"SITE": {"NAME": "Nome"}}
