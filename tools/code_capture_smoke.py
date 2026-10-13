"""Code-only import and screenshot E2E on the owned Phase 7 application stack.

Real HTTP, PostgreSQL, Redis, scheduler, worker and browser. Only the Android
renderer and external repository provider are synthetic boundaries.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from phase7_smoke import ROOT, Harness, write_json

HEAD = "1" * 40


def configure(h):
    # An extra override affects this UUID-named disposable project only.
    command = json.dumps(["python", "/run/code_capture_renderer.py"])
    override = h.runtime / "code-capture.yml"
    renderer = ROOT / "tools/fixtures/code_capture_renderer.py"
    override.write_text(
        f"""services:
  backend:
    environment:
      VERBOFLEX_SCREENSHOT_RUNNER_COMMAND: '{command}'
  worker:
    environment:
      VERBOFLEX_SCREENSHOT_RUNNER_COMMAND: '{command}'
    command: ["celery", "-A", "verboflex.worker.celery_app", "worker", "--loglevel=INFO", "--queues=celery,screenshots", "--concurrency=2"]
    volumes:
      - {renderer}:/run/code_capture_renderer.py:ro
"""
    )
    h.fixture["compose"].extend(["-f", str(override)])
    h.compose(
        "up",
        "-d",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "120",
        "backend",
        "worker",
        timeout=180,
    )
    files = {
        "code-e2e-app": {
            "app/src/main/Screen.kt": b"""package demo
object Keys {
 const val TITLE = "title"
 const val MISSING = "missing_key"
}
fun Screen() { translate(Keys.TITLE) }
@Preview @Composable fun ScreenPreview() { Screen() }
""",
            "app/src/main/JavaKeys.java": b'package demo; class JavaKeys { static final String LABEL = "java_label"; }',
        },
        "code-e2e-translations": {
            "res/values/strings.xml": b'<resources><string name="title">Base title</string><string name="java_label">Java base</string><string name="orphan">Unrelated</string></resources>',
            "res/values-it/strings.xml": b'<resources><string name="title">Synthetic imported title</string><string name="java_label">Java label</string></resources>',
        },
    }
    controls = json.loads(h.control_path.read_text())
    repositories = controls.get("repositories", {})
    repositories.update(
        {
            slug: {
                "files": {p: base64.b64encode(b).decode() for p, b in entries.items()}
            }
            for slug, entries in files.items()
        }
    )
    h.control(repositories=repositories)


def setup(h):
    product = h.api(
        "/admin/products",
        "POST",
        {"name": "Code capture E2E", "description": "Synthetic fixture"},
        expected=201,
    )
    pid = product["id"]
    revision = product["candidate_revision"]
    sides = []
    for role, slug in (
        ("keys", "code-e2e-app"),
        ("translations", "code-e2e-translations"),
    ):
        repo = h.api(
            "/admin/repositories",
            "POST",
            {"workspace": "verboflex-smoke", "repository_slug": slug},
            expected=201,
        )
        sides.append(
            {"role": role, "repository_id": repo["id"], "source_branch": "main"}
        )
    mapping = h.api(
        f"/admin/products/{pid}/candidate/mappings",
        "POST",
        {
            "topology": "separate",
            "expected_candidate_version": revision["version"],
            "allowed_target_branches": ["main"],
            "default_target_branch": "main",
            "sides": sides,
            "code_source": {
                "resource_roots": [],
                "declaration_symbols": ["demo.Keys.*", "demo.JavaKeys.*"],
                "localization_calls": ["translate"],
                "compose": {
                    "runner_profile": "synthetic-e2e",
                    "preview_functions": ["demo.ScreenPreview"],
                },
            },
        },
        expected=201,
    )
    preview = h.api(
        f"/admin/products/{pid}/candidate/mappings/{mapping['id']}/preview-jobs",
        "POST",
        {
            "expected_candidate_version": mapping["candidate_version"],
            "commits": [{"role": side["role"], "commit_hash": HEAD} for side in sides],
        },
        expected=202,
    )
    preview = h.wait(
        lambda: h.api(f"/admin/preview-jobs/{preview['id']}"),
        lambda p: p["state"] not in {"queued", "running"},
    )
    assert preview["state"] == "succeeded", "code_preview_failed"
    candidates = preview["result"]["layout_candidates"]
    assert len(candidates) == 1 and candidates[0]["repository_side"] == "translations"
    h.api(
        f"/admin/preview-jobs/{preview['id']}/confirmation",
        "POST",
        {
            "preview_digest": preview["result"]["digest"],
            "layout_candidate_id": candidates[0]["id"],
            "layout_candidate_version": 1,
            "base_language": "en",
        },
    )
    h.api(
        f"/admin/products/{pid}/publish",
        "POST",
        {
            "candidate_revision_id": revision["id"],
            "expected_candidate_version": mapping["candidate_version"],
        },
    )
    job = h.api(
        f"/admin/products/{pid}/published/mappings/{mapping['id']}/imports", "POST"
    )
    job = h.wait(
        lambda: h.api(f"/admin/products/{pid}/imports/{job['id']}"),
        lambda j: j["state"] not in {"queued", "running"},
    )
    assert job["state"] == "current", "code_import_failed"
    sources = h.api(f"/products/{pid}/code-sources")["items"]
    assert (
        len(sources) == 1
        and sources[0]["key_count"] == 3
        and sources[0]["missing_count"] == 1
    )
    catalog = h.api(f"/localization-scopes/{sources[0]['scope_id']}/code-keys")
    assert catalog["orphan_count"] == 1
    assert [k["key"] for k in catalog["items"] if k["missing_translation"]] == [
        "missing_key"
    ]
    groups = h.api(f"/translations?product_id={pid}&language=it&page_size=50")["items"]
    details = [h.api(f"/translations/{item['id']}") for item in groups]
    assert {item["raw_key"] for item in details} == {"title", "java_label"}
    group = next(item for item in details if item["raw_key"] == "title")
    context = h.api(f"/translations/{group['id']}/code-context")
    assert context["configured"] and context["code_commit"] == HEAD
    assert context["previews"][0]["keys"] == ["title"]
    assert h.api(f"/translations/{group['id']}/screenshots")["items"] == []
    h.fixture["code_capture"] = {
        "product": pid,
        "group": group["id"],
        "scope": sources[0]["scope_id"],
    }
    write_json(h.path, h.fixture)


def verify(h):
    fixture = json.loads(h.path.read_text())
    proof = fixture["code_capture"]
    gid, job_id = proof["group"], proof["job"]
    job = h.api(f"/translations/{gid}/screenshots/{job_id}")
    assert job["state"] == "succeeded" and job["request"]["proposal_version"] == 1
    again = h.api(
        f"/translations/{gid}/screenshots/{job_id}", "PUT", job["request"], expected=202
    )
    assert again["id"] == job_id and again["created_at"] == job["created_at"]
    assert len(h.api(f"/translations/{gid}/screenshots")["items"]) == 1
    image = h.client.get(f"/translations/{gid}/screenshots/{job_id}/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, no-store"
    assert b"SyntheticTitle\0Saved on demand" in image.content
    denied = h.client.get(
        f"/translations/{gid}/screenshots/{job_id}/image", headers={"Authorization": ""}
    )
    assert denied.status_code == 401
    outsider = Harness(h.path)
    outsider.fixture["users"]["admin"] = outsider.fixture["users"]["viewer"]
    outsider.login()
    assert (
        outsider.client.get(f"/products/{proof['product']}/code-sources").status_code
        == 404
    )
    assert (
        outsider.client.get(
            f"/translations/{gid}/screenshots/{job_id}/image"
        ).status_code
        == 404
    )
    outsider.client.close()
    invalid = h.api(
        f"/translations/{gid}/screenshots/{uuid4()}",
        "PUT",
        {"preview_function": "demo.Unknown"},
        expected=409,
    )
    assert "detail" in invalid
    # Capture requests and imports must not mutate either provider repository.
    for slug in ("code-e2e-app", "code-e2e-translations"):
        assert all(
            c["effects"] == 0
            for c in h.graph()["repositories"][slug]["counters"].values()
        )
    evidence = Path(fixture["evidence_dir"])
    evidence.mkdir(parents=True, exist_ok=True)
    write_json(
        evidence / "code-capture-e2e.json",
        {
            "http_configuration": True,
            "code_only_kotlin_java": True,
            "separate_translation_join": True,
            "missing_key_catalog": True,
            "lazy_capture": True,
            "saved_proposal_snapshot": True,
            "real_celery_dispatch": True,
            "idempotency": True,
            "authenticated_png": True,
            "nonmember_denied": True,
            "browser_image_reconnect": True,
            "provider_mutations": 0,
            "android_renderer": "synthetic boundary; no Android rendering claimed",
            "browser": proof["browser"],
        },
    )


def main():
    h = Harness(Path(sys.argv[1]))
    stage = "configure"
    try:
        configure(h)
        stage = "setup"
        setup(h)
        stage = "browser"
        result = subprocess.run(
            ["node", str(ROOT / "tools/code_capture_smoke_browser.mjs"), str(h.path)],
            capture_output=True,
            timeout=150,
            check=False,
        )
        if result.returncode:
            # Only a fixed diagnostic label, never browser traces containing tokens.
            raise AssertionError("code_capture_browser_failed")
        stage = "verify"
        verify(h)
    except Exception as error:
        import re
        import traceback

        evidence = Path(h.fixture["evidence_dir"])
        evidence.mkdir(parents=True, exist_ok=True)
        label = str(error)
        write_json(
            evidence / "code-capture-failure.json",
            {
                "stage": stage,
                "error": label
                if re.fullmatch(r"[a-z_0-9]{1,100}", label)
                else type(error).__name__,
                "lines": [f.lineno for f in traceback.extract_tb(error.__traceback__)],
            },
        )
        raise
    print(
        "code capture E2E: PASS (HTTP, import, catalog, proposal, Celery, browser, PNG, reconnect)"
    )


if __name__ == "__main__":
    main()
