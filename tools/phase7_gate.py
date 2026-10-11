"""Source-bound Phase 7 certification using the existing owned command lifecycle."""

from __future__ import annotations

import ast
import hashlib
import http.client
import json
import math
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import yaml
from phase4_gate import terminate
from phase6_gate import ROOT, included, run_stage, source_digest

STAGES = (
    "backend",
    "harness",
    "shell",
    "ruff",
    "mypy",
    "api",
    "frontend",
    "typecheck",
    "lint",
    "build",
    "e2e",
    "native-cleanup",
    "mutants",
    "smoke",
)
PHASE = ROOT / ".planning/phases/07-change-sets-and-pull-requests"
MANIFEST = "tools/phase7_source_manifest.txt"
BASE = "04addbc"
FAULTS = (
    "lost_enqueue_same_id",
    "duplicate_delivery_no_effect",
    "killed_worker_readonly_recovery",
    "missing_branch_no_resend",
    "delayed_original_effect_adopted",
    "same_path_distinct_targets",
    "uuid_only_submission_queue",
    "partial_success_preserved",
    "lost_pr_reply_one_effect",
    "drift_drift_refused",
    "known_pre_pr_finalize_new_version",
    "source_drift_refused",
    "readonly_and_blocked_built_ui",
    "foreign_branch_never_reset",
    "four_pr_states_without_source_branch",
    "long_rtl_multiline_built_browser",
    "different_target_head_same_selected_bytes",
    "renewed_credentials_same_frozen_commit",
    "exact_bytes",
    "immutable_receipts",
)
DEPENDENCIES = {
    "backend/pyproject.toml",
    "backend/uv.lock",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/playwright.config.ts",
    "docker-compose.yml",
    "tools/phase3_smoke.sh",
    "tools/phase4_gate.py",
    "tools/phase6_gate.py",
    "tools/phase6_smoke.py",
    "tools/phase6_smoke_browser.mjs",
    "tools/verify_phase5_mutants.py",
}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, label="Incomplete or stale Phase 7 evidence"):
    if not condition:
        raise ValueError(label)


def owned_paths(root=ROOT):
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", BASE, "--"], cwd=root)
        .decode()
        .splitlines()
    )
    untracked = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=root
        )
        .decode()
        .splitlines()
    )
    return set(filter(included, changed + untracked))


def validate_inventory(root, manifest, owned):
    paths = manifest.get("files", [])
    require(manifest.get("version") == 1 and manifest.get("base") == BASE)
    require(
        paths == sorted(set(paths))
        and set(paths) == set(owned) | DEPENDENCIES | {MANIFEST},
        "Omitted source inventory",
    )
    for name in paths:
        path = root / name
        require(
            included(name)
            and not Path(name).is_absolute()
            and ".." not in Path(name).parts
        )
        require(path.is_file() and not path.is_symlink(), "Missing source inventory")
    edges = json.loads(
        (root / "backend/tests/fixtures/submissions/edge_matrix.json").read_text()
    )["edges"]
    require(len(edges) == 15 and len({e["id"] for e in edges}) == 15)
    for edge in edges:
        require(
            edge["smoke"]["status"] == "requires_current_gate" and edge["test_nodes"]
        )
        for selector in edge["test_nodes"]:
            path, name = selector.split("::", 1)
            require(path in paths, "Omitted behavioral selector")
            text = (root / path).read_text()
            if path.endswith(".py"):
                require(
                    any(
                        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and n.name == name
                        for n in ast.parse(text).body
                    )
                )
            else:
                require(f"it({json.dumps(name)}," in text)


def load_manifest():
    manifest = json.loads((ROOT / MANIFEST).read_text())
    validate_inventory(ROOT, manifest, owned_paths())
    return manifest


def commands_for(manifest):
    files = manifest["files"]
    tests = sorted(
        p for p in files if p.startswith("backend/tests/") and p.endswith(".py")
    )
    tests += [
        "backend/tests/unit/localization/writing",
        "backend/tests/unit/services/test_writeback_snapshots.py",
        "backend/tests/integration/test_confirmed_layout_refresh.py",
    ]
    source = sorted(
        p for p in files if p.startswith("backend/src/") and p.endswith(".py")
    )
    python_files = [p for p in files if p.endswith(".py") and p not in DEPENDENCIES]
    return {
        "backend": [
            sys.executable,
            "-m",
            "pytest",
            *tests,
            "-q",
            "--junitxml={report}",
        ],
        "harness": [
            sys.executable,
            "-m",
            "pytest",
            "tools/tests/test_phase7_smoke.py",
            "tools/tests/test_phase7_mock_provider.py",
            "-q",
        ],
        "shell": ["bash", "tools/tests/test_phase7_smoke.sh"],
        "ruff": [
            sys.executable,
            "-m",
            "ruff",
            "check",
            *python_files,
        ],
        "mypy": [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            "backend/pyproject.toml",
            *source,
        ],
        "api": ["npm", "--prefix", "frontend", "run", "api:check"],
        "frontend": [
            "npm",
            "--prefix",
            "frontend",
            "test",
            "--",
            "--run",
            "src/features/change-sets",
            "src/features/translations/TranslationDetailPage.test.tsx",
        ],
        **{
            stage: ["npm", "--prefix", "frontend", "run", stage]
            for stage in ("typecheck", "lint", "build")
        },
        "e2e": [
            "npm",
            "--prefix",
            "frontend",
            "run",
            "e2e",
            "--",
            "change-sets.spec.ts",
        ],
        "native-cleanup": [
            "node",
            "--test",
            "--test-reporter=tap",
            "tools/phase7_zoom_extension/native_zoom.test.mjs",
        ],
        "mutants": [sys.executable, "tools/verify_phase7_mutants.py"],
        "smoke": ["bash", "tools/phase7_smoke.sh"],
    }


def validate_evidence(evidence, digest, commands):
    try:
        require(
            bool(HEX.fullmatch(digest))
            and evidence["source_digest"] == evidence["source_digest_after"] == digest
        )
        require(set(evidence["stages"]) == set(commands) == set(STAGES))
        for stage, command in commands.items():
            row = evidence["stages"][stage]
            duration = row["duration_seconds"]
            require(
                row["status"] == "pass"
                and type(row["exit_code"]) is int
                and row["exit_code"] == 0
            )
            require(
                row["command"] == command
                and row["source_digest"] == digest
                and bool(HEX.fullmatch(row["output_sha256"]))
            )
            require(
                type(duration) in (int, float)
                and math.isfinite(duration)
                and duration > 0
            )
            start, finish = (
                datetime.fromisoformat(row[key])
                for key in ("started_at", "finished_at")
            )
            require(
                start.tzinfo is not None
                and finish.tzinfo is not None
                and finish > start
            )
        for stage in ("backend", "harness", "frontend", "e2e", "native-cleanup"):
            counts = evidence["tests"][stage]
            require(
                type(counts["passed"]) is int
                and counts["passed"] > 0
                and counts["skipped"] == 0
            )
        require(evidence["migration_round_trip"] is True)
        mutants = evidence["mutants"]
        require(
            mutants["status"] == "pass"
            and mutants["killed"] == 7
            and mutants["survived"] == 0
            and mutants["source_restored"] is True
        )
        smoke = evidence["smoke"]
        require(smoke["cleanup"] is True)
        for name, groups, effects in (
            ("happy", 5, {"branch": 5, "commit": 5, "pull_request": 5}),
            ("faults", 17, {"branch": 15, "commit": 14, "pull_request": 14}),
        ):
            row = smoke[name]
            require(row["groups"] == groups and row["effects"] == effects)
            require(row["exact_bytes"] is True and row["immutable_receipts"] is True)
        require(smoke["happy"]["localization_unchanged"] is True)
        require(all(smoke["faults"][key] is True for key in FAULTS))
        browser = evidence["browser"]
        require(
            browser["backstops"] == 60
            and all(
                browser[key] is True for key in ("native_zoom", "geometry", "keyboard")
            )
        )
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("Incomplete or stale Phase 7 evidence") from error


def validate_reviews(records, digest):
    require(
        set(records) == {"review", "security", "verification"},
        "Missing independent verdict",
    )
    for key, status, field in (
        ("review", "clean", "unresolved_high"),
        ("security", "verified", "threats_open"),
        ("verification", "passed", "behavior_unverified"),
    ):
        record = records[key]
        require(isinstance(record, dict), "Missing independent verdict")
        require(
            record.get("source_digest") == digest
            and record.get("status") == status
            and record.get(field) == 0,
            "Stale or unresolved independent verdict",
        )


def browser_evidence():
    directory = PHASE / "evidence"
    happy = json.loads((directory / "phase7-browser-verify.json").read_text())
    presentation = json.loads(
        (directory / "phase7-browser-presentation.json").read_text()
    )
    expected = {
        (name, surface, variant)
        for name in (
            "android_xml",
            "qt_ts",
            "json",
            "ios_strings",
            "separate",
            "presentation",
        )
        for surface in (
            "product-navigation",
            "pending-selection",
            "submission-review",
            "submission-history",
            "submission-detail",
        )
        for variant in ("zoom200", "width320")
    }
    rows = happy["surfaces"] + presentation["surfaces"]
    require(
        len(rows) == 60
        and {(r["name"], r["surface"], r["variant"]) for r in rows} == expected
    )
    hashes = {}
    for row in rows:
        zoom = row["variant"] == "zoom200"
        require(
            row["native_zoom"] == (2 if zoom else 1)
            and row["scrollWidth"] <= row["width"]
        )
        require(
            row["width"] == (720 if zoom else 320) and row["dpr"] == (2 if zoom else 1)
        )
        if row["surface"] == "submission-review":
            require(
                row["target_control_count"]
                == (1 if row["name"] == "presentation" else 0)
                and row["target_controls_fit"] is True
            )
        filename = row["screenshot"]
        require(filename == f"{row['name']}-{row['surface']}-{row['variant']}.png")
        path = directory / filename
        require(not path.is_symlink() and path.is_file())
        data = path.read_bytes()
        require(data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 1000)
        require(
            int.from_bytes(data[16:20], "big") == row["pixel_width"]
            and int.from_bytes(data[20:24], "big") == row["pixel_height"]
        )
        hashes[filename] = hashlib.sha256(data).hexdigest()
    require(
        len(happy["submissions"]) == 5
        and sum(s["accepted_response_loss"] for s in happy["submissions"]) == 1
    )
    require(
        happy["keyboard"]
        and all(
            happy["keyboard"][0].get(k) is True
            for k in (
                "dirty_editor",
                "keep_editing_focus",
                "discard_navigation",
                "overlay_unmounted",
                "route_focus_preserved",
            )
        )
    )
    return {
        "backstops": 60,
        "native_zoom": True,
        "geometry": True,
        "keyboard": True,
        "screenshots": hashes,
    }


def statistics(output, *, node=False):
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    passed = re.findall(r"# pass (\d+)" if node else r"(\d+) passed", output)
    skipped = re.findall(
        r"# skipped (\d+)" if node else r"(\d+) (?:skipped|xfailed|xpassed)", output
    )
    require(
        len(passed) >= 1 and int(passed[-1]) > 0 and sum(map(int, skipped)) == 0,
        "Missing unskipped test evidence",
    )
    return {"passed": int(passed[-1]), "skipped": 0}


def extract(output, prefix):
    lines = re.findall(r"^" + re.escape(prefix) + r"(.+)$", output, re.MULTILINE)
    require(len(lines) == 1, "Missing structured command evidence")
    return json.loads(lines[0])


def validate_backend_report(report):
    cases = ElementTree.parse(report).findall(".//testcase")
    matching = [
        c
        for c in cases
        if c.get("name")
        == "test_migration_down_up_preserves_existing_imports_and_proposals"
    ]
    require(
        len(matching) == 2
        and {c.get("classname") for c in matching}
        == {
            "tests.integration.test_submission_schema",
            "tests.integration.test_submission_review_jobs",
        },
        "Missing migration round trip",
    )
    require(
        all(
            not any(c.find(tag) is not None for tag in ("failure", "error", "skipped"))
            for c in cases
        ),
        "Skipped or failed backend test",
    )


@contextmanager
def browser_runtime(runtime):
    """Serve this run's built SPA on an owned loopback port, with bounded cleanup."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    names = ("PLAYWRIGHT_BASE_URL", "PLAYWRIGHT_OUTPUT_DIR")
    previous = {name: os.environ.get(name) for name in names}
    process = None

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    handlers = {
        sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with (Path(runtime) / "preview.log").open("wb") as stream:
            process = subprocess.Popen(
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    "preview",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        deadline = time.monotonic() + 30
        while True:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                connection.request("GET", "/products/phase7/change-sets")
                require(
                    connection.getresponse().status == 200, "Built SPA not available"
                )
                break
            except OSError:
                require(
                    process.poll() is None and time.monotonic() < deadline,
                    "Built SPA readiness timeout",
                )
                time.sleep(0.25)
            finally:
                connection.close()
        os.environ.update(
            PLAYWRIGHT_BASE_URL=f"http://127.0.0.1:{port}",
            PLAYWRIGHT_OUTPUT_DIR=str(Path(runtime) / "playwright"),
        )
        yield
    finally:
        if process is not None:
            terminate(process)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def run():
    require(
        bool(os.environ.get("VERBOFLEX_TEST_POSTGRES_ADMIN_URL")),
        "Dedicated PostgreSQL URL required",
    )
    manifest = load_manifest()
    commands = commands_for(manifest)
    digest = source_digest(ROOT)
    evidence = {"source_digest": digest, "stages": {}, "tests": {}}
    for stage, command in commands.items():
        print(f"phase7 gate {stage}: RUNNING", flush=True)
        started = datetime.now(UTC).isoformat()
        monotonic = time.monotonic()
        with (
            tempfile.TemporaryDirectory(prefix="verboflex-phase7-gate-") as runtime,
            tempfile.TemporaryFile(mode="w+") as log,
            browser_runtime(runtime) if stage == "e2e" else nullcontext(),
        ):
            report = Path(runtime) / "tests.xml"
            actual = [
                str(report)
                if arg == "{report}"
                else arg.replace("{report}", str(report))
                for arg in command
            ]
            result = run_stage(actual, cwd=ROOT, log=log, timeout=2400)
            log.seek(0)
            output = log.read()
            if result:
                print(f"phase7 gate {stage}: FAIL exit={result}", flush=True)
                raise SystemExit(1)
            if stage == "backend":
                validate_backend_report(report)
                evidence["migration_round_trip"] = True
            if stage in {"backend", "harness", "frontend", "e2e", "native-cleanup"}:
                evidence["tests"][stage] = statistics(
                    output, node=stage == "native-cleanup"
                )
            if stage == "mutants":
                evidence["mutants"] = extract(output, "phase7 mutants evidence: ")
            if stage == "smoke":
                evidence["smoke"] = extract(output, "phase7 evidence: ")
        require(source_digest(ROOT) == digest, "Source changed during gate")
        evidence["stages"][stage] = {
            "command": command,
            "exit_code": result,
            "status": "pass",
            "source_digest": digest,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(time.monotonic() - monotonic, 3),
            "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        }
        print(f"phase7 gate {stage}: PASS", flush=True)
    evidence["source_digest_after"] = source_digest(ROOT)
    evidence["browser"] = browser_evidence()
    validate_evidence(evidence, digest, commands)
    (PHASE / "07-GATE.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"phase7 gate: PASS source_sha256={digest}", flush=True)


def verify():
    commands = commands_for(load_manifest())
    digest = source_digest(ROOT)
    evidence = json.loads((PHASE / "07-GATE.json").read_text())
    validate_evidence(evidence, digest, commands)
    require(evidence["browser"] == browser_evidence(), "Browser artifact drift")
    records = {}
    for key, name in (
        ("review", "REVIEW"),
        ("security", "SECURITY"),
        ("verification", "VERIFICATION"),
    ):
        text = (PHASE / f"07-{name}.md").read_text()
        require(text.startswith("---\n"), "Missing verdict frontmatter")
        records[key] = yaml.safe_load(text.split("---", 2)[1])
    validate_reviews(records, digest)
    print(f"phase7 certification: PASS source_sha256={digest}")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--digest"]:
            print(source_digest(ROOT))
        elif sys.argv[1:] == ["verify", "--same-digest"]:
            verify()
        elif sys.argv[1:] in ([], ["run"]):
            run()
        else:
            raise ValueError("Unknown gate option")
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        print(
            "phase7 certification: FAIL (missing, invalid or stale evidence)",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
