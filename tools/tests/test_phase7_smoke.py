"""Executable contract for the owned full-stack smoke entry."""

import base64
import copy
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_control_publication_flushes_complete_private_document_before_replace(
    tmp_path, monkeypatch
):
    module = driver()
    target = tmp_path / "provider-control.json"
    target.write_text('{"old":true}')
    flushed = []
    original_fsync = os.fsync

    def fsync(fd):
        assert json.loads(target.read_text()) == {"old": True}
        assert json.loads(os.pread(fd, 4096, 0)) == {"write_faults": {}}
        assert os.fstat(fd).st_mode & 0o777 == 0o600
        flushed.append(True)
        original_fsync(fd)

    monkeypatch.setattr(module.os, "fsync", fsync)
    module.write_json(target, {"write_faults": {}})
    assert flushed == [True]
    assert json.loads(target.read_text()) == {"write_faults": {}}
    assert target.stat().st_mode & 0o777 == 0o600


def driver():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        spec = importlib.util.spec_from_file_location(
            "phase7_driver_test", ROOT / "tools/phase7_smoke.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def happy_fixture():
    module = driver()
    graph, facts = {"repositories": {}}, {"groups": []}
    paths = {
        "android_xml": "res/values-it/strings.xml",
        "qt_ts": "translations/app_it.ts",
        "json": "locales/it.json",
        "ios_strings": "it.lproj/Localizable.strings",
        "separate": "res/values-it/strings.xml",
    }
    for name, path in paths.items():
        identity, repo_id = str(uuid4()), str(uuid4())
        branch, commit = (
            "verboflex/change-set-" + identity,
            str(len(facts["groups"]) + 3) * 40,
        )
        before = module.p6.fixture_files(name)[path]
        after = module.p6.expected_bytes(before)
        b64 = lambda value: base64.b64encode(value).decode()
        slug = "phase6-" + name
        graph["repositories"][slug] = {
            "uuid": repo_id,
            "commits": {
                module.p6.HEAD: {"files": {path: b64(before)}},
                commit: {"parents": [module.p6.HEAD], "files": {path: b64(after)}},
            },
            "pull_requests": {
                "1": {
                    "source": {
                        "branch": {"name": branch},
                        "commit": {"hash": commit},
                        "repository": {"uuid": repo_id},
                    },
                    "destination": {
                        "branch": {"name": "main"},
                        "commit": {"hash": module.p6.HEAD},
                        "repository": {"uuid": repo_id},
                    },
                }
            },
            "counters": {
                op: {"attempts": 1, "effects": 1}
                for op in ("branch", "commit", "pull_request")
            },
        }
        facts["groups"].append(
            {
                "id": identity,
                "slug": slug,
                "branch": branch,
                "provider_uuid": repo_id,
                "status": "succeeded",
                "target": "main",
                "target_head": module.p6.HEAD,
                "commit": commit,
                "pr_id": 1,
                "original_digest": "a" * 64,
                "expected_original_digest": "a" * 64,
                "files": [
                    {
                        "path": path,
                        "before": b64(before),
                        "after": b64(after),
                        "attributes": ["binary"]
                        if before.startswith(b"\xff\xfe")
                        else [],
                    }
                ],
                "items": [0, 1] if name in ("android_xml", "qt_ts", "json") else [0],
                "events": [{"outcome": "verified", "step": "pull_request"}],
            }
        )
    return module, graph, facts


def test_independent_oracle_accepts_only_exact_five_group_effects_and_bytes():
    module, graph, facts = happy_fixture()
    assert module.validate_graph(graph, facts, happy_only=True)["effects"] == {
        "branch": 5,
        "commit": 5,
        "pull_request": 5,
    }


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "repost_refused",
        "bytes",
        "unselected_file",
        "wrong_selected_path",
        "attributes",
        "target_commit",
        "parent",
        "repository",
        "proof",
        "receipt",
        "extra_group",
    ],
)
def test_independent_oracle_rejects_plausible_success_with_wrong_provider_facts(damage):
    module, graph, facts = happy_fixture()
    group = facts["groups"][0]
    repo = graph["repositories"][group["slug"]]
    if damage == "duplicate":
        repo["counters"]["pull_request"]["effects"] += 1
    elif damage == "repost_refused":
        repo["counters"]["pull_request"]["attempts"] += 1
    elif damage == "bytes":
        repo["commits"][group["commit"]]["files"][group["files"][0]["path"]] = "YmFk"
    elif damage == "unselected_file":
        repo["commits"][group["commit"]]["files"]["unrelated.txt"] = "YmFk"
    elif damage == "wrong_selected_path":
        original_path = group["files"][0]["path"]
        wrong_path = "unselected/strings.xml"
        group["files"][0]["path"] = wrong_path
        for commit in repo["commits"].values():
            commit["files"][wrong_path] = commit["files"].pop(original_path)
    elif damage == "attributes":
        group["files"][0]["attributes"] = ["binary"]
    elif damage == "target_commit":
        repo["pull_requests"]["1"]["destination"]["commit"]["hash"] = "f" * 40
    elif damage == "parent":
        repo["commits"][group["commit"]]["parents"] = ["f" * 40]
    elif damage == "repository":
        repo["uuid"] = str(uuid4())
    elif damage == "proof":
        group["original_digest"] = "f" * 64
    elif damage == "receipt":
        group["events"] = []
    else:
        facts["groups"].append(copy.deepcopy(group))
    with pytest.raises(AssertionError):
        module.validate_graph(graph, facts, happy_only=True)


def test_full_smoke_dry_run_describes_owned_fault_oracle():
    result = subprocess.run(
        ["bash", str(ROOT / "tools/phase7_smoke.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    for term in ("TLS", "UUID", "exact", "Redis", "worker", "200%", "320", "cleanup"):
        assert term in result.stdout
    assert "access_token" not in result.stdout


def test_unknown_smoke_option_is_rejected():
    result = subprocess.run(
        ["bash", str(ROOT / "tools/phase7_smoke.sh"), "--unknown"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2


@pytest.mark.parametrize("failure", ["none", "down", "leftover"])
def test_reused_cleanup_is_owned_and_cannot_report_success_with_leftovers(
    tmp_path, failure
):
    runtime = tmp_path / "owned-runtime"
    runtime.mkdir()
    (runtime / "owner.env").write_text("private fixture")
    unrelated = tmp_path / "shared-stack-marker"
    unrelated.write_text("retain")
    calls = tmp_path / "calls"
    library = (
        (ROOT / "tools/phase3_smoke.sh").read_text().split('case "${1:-}:${2:-}" in')[0]
    )
    script = tmp_path / "cleanup.sh"
    script.write_text(
        library
        + f"""\n
SMOKE_PROJECT=verboflex_phase03_14_owned_fixture
SMOKE_RUNTIME_DIR={shlex.quote(str(runtime))}
SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner.env"
SMOKE_IMAGE_TAG=phase7-owned-fixture
compose() {{
  printf '%s\\n' "compose $*" >> {shlex.quote(str(calls))}
  [ {failure} != down ]
}}
docker() {{
  printf '%s\\n' "docker $*" >> {shlex.quote(str(calls))}
  if [ {failure} = leftover ] && [ "$1" = ps ]; then printf 'owned-container\\n'; fi
  return 0
}}
cleanup
"""
    )
    result = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=10, check=False
    )
    assert (result.returncode == 0) == (failure == "none")
    assert not runtime.exists() and unrelated.read_text() == "retain"
    recorded = calls.read_text()
    assert "compose down --volumes --remove-orphans --timeout 10" in recorded
    assert (
        recorded.count(
            "label=com.docker.compose.project=verboflex_phase03_14_owned_fixture"
        )
        == 3
    )
    assert "image rm verboflex-backend:phase7-owned-fixture" in recorded
    assert "image rm verboflex-frontend:phase7-owned-fixture" in recorded
    assert "prune" not in recorded and "shared-stack" not in recorded
