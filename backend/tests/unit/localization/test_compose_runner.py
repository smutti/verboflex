"""Real Git snapshot checkout and fail-closed archive extraction, using local fixtures."""

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "compose_capture_runner", ROOT / "tools/compose_capture.py"
)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

adapter_spec = importlib.util.spec_from_file_location(
    "capture_container", ROOT / "tools/compose_capture_container.py"
)
assert adapter_spec and adapter_spec.loader
adapter = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(adapter)


def git(path, *args):
    return (
        subprocess.check_output(
            [
                "git",
                "-C",
                str(path),
                "-c",
                "user.name=Synthetic",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            stderr=subprocess.PIPE,
        )
        .decode()
        .strip()
    )


def repository(path):
    path.mkdir()
    git(path, "init", "--quiet")
    return path


def commit(path, name, content):
    (path / name).write_text(content)
    git(path, "add", name)
    git(path, "commit", "--quiet", "-m", "Synthetic fixture")
    return git(path, "rev-parse", "HEAD")


def test_capture_checkout_is_bound_to_commit_and_not_working_tree(tmp_path):
    repo = repository(tmp_path / "repo")
    original = commit(repo, "Screen.kt", "original fixture")
    commit(repo, "Screen.kt", "new committed fixture")
    (repo / "Screen.kt").write_text("uncommitted fixture")
    target = tmp_path / "snapshot"
    target.mkdir()
    runner.checkout(repo, original, target)
    assert (target / "Screen.kt").read_text() == "original fixture"
    assert not (target / ".git").exists()
    assert (repo / "Screen.kt").read_text() == "uncommitted fixture"
    for invalid in ("HEAD", "../escape", "a" * 39):
        with pytest.raises(ValueError, match="immutable checkout"):
            runner.checkout(repo, invalid, target)


def test_capture_checkout_rejects_archive_symlink_escape(tmp_path):
    repo = repository(tmp_path / "repo")
    (repo / "escape").symlink_to("/etc/passwd")
    git(repo, "add", "escape")
    git(repo, "commit", "--quiet", "-m", "Synthetic unsafe symlink")
    target = tmp_path / "snapshot"
    target.mkdir()
    with pytest.raises(tarfile.AbsoluteLinkError):
        runner.checkout(repo, git(repo, "rev-parse", "HEAD"), target)
    assert not (target / "escape").exists()


def test_container_exchange_is_private_on_host_and_readable_with_restrictive_umask(
    tmp_path, monkeypatch
):
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    payload = tmp_path / "input.json"
    payload.write_text(
        json.dumps({"capture": {"runner_profile": "synthetic"}, "code_repository_id": "fixture"})
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "synthetic": {
                    "repository_id": "fixture",
                    "mirror": str(mirror),
                    "image": "synthetic@sha256:" + "a" * 64,
                }
            }
        )
    )
    output = tmp_path / "output.png"
    monkeypatch.setattr(
        sys,
        "argv",
        ["capture", "--input", str(payload), "--output", str(output), "--profiles", str(profiles)],
    )

    def capture(command, timeout):
        assert "--log-driver=none" in command
        mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
        assert all(value.endswith(",readonly") for value in mounts)
        mount = next(value for value in mounts if "target=/input.json" in value)
        source = Path(mount.split("source=", 1)[1].split(",")[0])
        assert stat.S_IMODE(source.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(source.stat().st_mode) == 0o644
        assert "--emit-png" in command
        assert command[command.index("--output") + 1].startswith("/tmp/")
        return b"synthetic output"

    monkeypatch.setattr(adapter, "capture_output", capture, raising=False)
    monkeypatch.setattr(
        adapter.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0)
    )
    previous = os.umask(0o077)
    try:
        adapter.main()
    finally:
        os.umask(previous)
    assert output.read_bytes() == b"synthetic output"


def test_container_stdout_is_bounded_and_timed():
    assert (
        adapter.capture_output([sys.executable, "-c", "print('synthetic', end='')"], 5)
        == b"synthetic"
    )
    with pytest.raises(ValueError, match="output"):
        adapter.capture_output(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x' * (8 * 1024 * 1024 + 1))",
            ],
            5,
        )
    with pytest.raises(subprocess.TimeoutExpired):
        adapter.capture_output([sys.executable, "-c", "import time; time.sleep(5)"], 0.1)


@pytest.mark.parametrize("image", ["runner:latest", "runner@sha256:wrong", "sha256:" + "a" * 63])
def test_container_rejects_mutable_or_malformed_image(image, tmp_path):
    payload = json.dumps(
        {"capture": {"runner_profile": "demo"}, "code_repository_id": "demo"}
    ).encode()
    with pytest.raises(ValueError, match="digest"):
        adapter.render(payload, {"demo": {"repository_id": "demo", "image": image}})


def test_container_binds_reviewed_patch_and_revision_before_docker(tmp_path, monkeypatch):
    patch = tmp_path / "fixture.patch"
    patch.write_text("reviewed synthetic fixture")
    payload = json.dumps(
        {
            "capture": {"runner_profile": "demo"},
            "code_repository_id": "demo",
            "code_commit": "a" * 40,
        }
    ).encode()
    profile = {
        "repository_id": "demo",
        "commit": "a" * 40,
        "mirror": str(tmp_path),
        "image": "sha256:" + "b" * 64,
        "patch": str(patch),
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
    }

    def capture(command, timeout):
        assert command[command.index("--commit") + 1] == "a" * 40
        assert command[command.index("--fixture-patch-sha256") + 1] == profile["patch_sha256"]
        assert f"type=bind,source={patch},target=/fixture.patch,readonly" in command
        return b"synthetic"

    monkeypatch.setattr(adapter, "capture_output", capture)
    monkeypatch.setattr(adapter.subprocess, "run", lambda *args, **kwargs: None)
    assert adapter.render(payload, {"demo": profile}, exchange_root=tmp_path) == b"synthetic"
    with pytest.raises(ValueError, match="revision"):
        adapter.render(payload, {"demo": {**profile, "commit": "c" * 40}})
    patch.write_text("unreviewed change")
    with pytest.raises(ValueError, match="patch"):
        adapter.render(payload, {"demo": profile})
