"""Source-bound Phase 6 gate; results contain only stages, counts and digests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES = {"backend", "frontend", "tools", "docker"}
ROOT_CONFIG = {".dockerignore", ".env.example", "AGENTS.md", ".gitignore", "Makefile"}


def run_stage(command, *, cwd, log, timeout=1800, grace=90):
    """Give the owned shell its cleanup trap before forcibly reaping its group."""
    child = subprocess.Popen(
        command, cwd=cwd, stdout=log, stderr=log, start_new_session=True
    )

    def stop():
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

    def interrupted(signum, _frame):
        stop()
        raise SystemExit(128 + signum)

    handlers = {
        sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop()
            return 124
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def included(path: str) -> bool:
    parts = Path(path).parts
    return bool(parts) and (
        parts[0] in TREES
        or path in ROOT_CONFIG
        or (
            len(parts) == 1
            and path.startswith("docker-compose")
            and path.endswith((".yml", ".yaml"))
        )
    )


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if (root / ".git").exists():
        names = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=root,
            )
            .decode()
            .split("\0")
        )
    else:  # Hermetic inventory tests, without requiring a fixture git repository.
        names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    for name in sorted(set(filter(included, names))):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Source inventory is missing or symbolic")
        for part in (
            name.encode(),
            str(path.stat().st_mode & 0o777).encode(),
            path.read_bytes(),
        ):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def validate_evidence(evidence: dict, expected_digest: str) -> None:
    smoke = evidence.get("smoke", {})
    if (
        evidence.get("source_digest") != expected_digest
        or len(expected_digest) != 64
        or evidence.get("stages")
        != dict.fromkeys(("tests", "ruff", "mypy", "smoke"), "pass")
        or type(evidence.get("tests")) is not int
        or evidence["tests"] < 1
        or evidence.get("skipped") != 0
        or smoke.get("formats") != 4
        or smoke.get("approved_groups", 0) < 8
        or smoke.get("prepared_files", 0) < 5
        or smoke.get("resource_mutations") != 0
        or any(
            smoke.get(key) is not True
            for key in (
                "revalidated",
                "localization_unchanged",
                "stale_direct",
                "stale_keys",
                "tampered_file",
                "mixed_markup",
                "duplicate_snapshot",
                "cleanup",
            )
        )
    ):
        raise ValueError("Incomplete or stale Phase 6 evidence")


def main() -> None:
    if sys.argv[1:] == ["--digest"]:
        print(source_digest(ROOT))
        return
    if sys.argv[1:]:
        raise ValueError("Unknown gate option")
    if not os.environ.get("VERBOFLEX_TEST_POSTGRES_ADMIN_URL"):
        raise ValueError("Dedicated PostgreSQL URL required")
    digest = source_digest(ROOT)
    evidence = {"source_digest": digest, "stages": {}}
    source = [
        "backend/src/verboflex/localization/writing",
        "backend/src/verboflex/services/writeback.py",
        "backend/src/verboflex/services/writeback_authority.py",
        "backend/src/verboflex/integrations/bitbucket/client.py",
        "backend/src/verboflex/integrations/bitbucket/urls.py",
        "backend/src/verboflex/services/import_jobs.py",
        "backend/src/verboflex/localization/moko_source.py",
    ]
    tests = [
        "backend/tests/unit/localization/writing",
        "backend/tests/unit/localization/importing",
        "backend/tests/unit/services/test_writeback.py",
        "backend/tests/unit/services/test_writeback_snapshots.py",
        "backend/tests/unit/integrations/bitbucket",
        "backend/tests/integration/test_writeback_authority.py",
        "backend/tests/integration/test_confirmed_layout_refresh.py",
        "backend/tests/integration/test_bitbucket_http_adapter.py",
        "backend/tests/integration/test_import_jobs.py",
        "backend/tests/integration/test_translation_review_concurrency.py",
        "backend/tests/unit/localization/preview/test_moko_xml.py",
        "backend/tests/architecture/test_phase6_boundary.py",
        "backend/tests/architecture/test_provider_boundaries.py",
        "backend/tests/architecture/test_background_boundaries.py",
        "backend/tests/architecture/test_phase3_scope.py",
    ]
    commands = {
        "tests": [sys.executable, "-m", "pytest", *tests, "-q", "--no-header"],
        "ruff": [
            sys.executable,
            "-m",
            "ruff",
            "check",
            *source,
            "tools/phase6_gate.py",
            "tools/phase6_smoke.py",
            "backend/tests/architecture/test_phase6_boundary.py",
        ],
        "mypy": [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            "backend/pyproject.toml",
            *source,
        ],
        "smoke": ["bash", "tools/phase6_smoke.sh"],
    }
    for stage, command in commands.items():
        print(f"phase6 gate {stage}: RUNNING", flush=True)
        with tempfile.TemporaryFile(mode="w+") as log:
            returncode = run_stage(command, cwd=ROOT, log=log)
            log.seek(0)
            output = log.read()
        if returncode:
            # Output may contain source and OAuth data. Export only fixed labels.
            labels = re.findall(
                r"^phase[46] (?:smoke|driver) failed: ([a-zA-Z0-9_-]+)$",
                output,
                re.MULTILINE,
            )
            print(
                f"phase6 gate {stage}: FAIL"
                + (" (" + labels[-1] + ")" if labels else ""),
                flush=True,
            )
            raise SystemExit(1)
        if stage == "tests":
            count = re.search(r"(\d+) passed", output)
            evidence["tests"] = int(count[1]) if count else 0
            evidence["skipped"] = sum(map(int, re.findall(r"(\d+) skipped", output)))
        if stage == "smoke":
            lines = re.findall(r"^phase6 evidence: (.+)$", output, re.MULTILINE)
            if len(lines) != 1:
                raise ValueError("Missing smoke evidence")
            evidence["smoke"] = json.loads(lines[0])
        evidence["stages"][stage] = "pass"
        print(f"phase6 gate {stage}: PASS", flush=True)
    validate_evidence(evidence, source_digest(ROOT))
    destination = ROOT / ".planning/phases/06-format-safe-write-back/06-GATE.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"phase6 gate: PASS tests={evidence['tests']} source_sha256={digest}")


if __name__ == "__main__":
    main()
