"""Synthetic shared dependency seed and isolated writable renderer state."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "tools/compose_capture_cache.py"
spec = importlib.util.spec_from_file_location("capture_cache", SCRIPT)
assert spec and spec.loader
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


def seed_cache(root):
    for name, content in {
        "caches/modules-2/files-2.1/demo.jar": b"synthetic dependency",
        "caches/modules-2/metadata-2.107/module.bin": b"synthetic metadata",
        "caches/8.13/transforms/demo/result.bin": b"synthetic transform",
        "caches/build-cache-1/demo": b"synthetic compiled output",
        "wrapper/dists/demo/gradle/bin/gradle": b"synthetic wrapper",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def test_shared_dependencies_are_not_copied_and_writable_caches_are_isolated(tmp_path):
    seed = seed_cache(tmp_path / "seed")
    before = {
        path.relative_to(seed): path.read_bytes() for path in seed.rglob("*") if path.is_file()
    }
    destinations = [tmp_path / "first", tmp_path / "second"]
    for destination in destinations:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--seed", str(seed), "--destination", str(destination)],
            capture_output=True,
            check=True,
        )
        assert result.stdout == b""  # The renderer's stdout is reserved for PNG bytes.
        assert not (destination / "caches/modules-2").exists()
        for name, content in before.items():
            if name.parts[1] != "modules-2":
                assert (destination / name).read_bytes() == content
    relative = Path("caches/8.13/transforms/demo/result.bin")
    (destinations[0] / relative).write_bytes(b"private update")
    local = destinations[0] / "caches/modules-2"
    local.mkdir()
    (local / "local.lock").write_bytes(b"private lock")
    assert not (destinations[1] / "caches/modules-2").exists()
    assert (destinations[1] / relative).read_bytes() == before[relative]
    assert before == {
        path.relative_to(seed): path.read_bytes() for path in seed.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize("location", ["same", "inside", "parent", "symlink"])
def test_writable_cache_cannot_overlap_shared_seed(tmp_path, location):
    seed = seed_cache(tmp_path / "seed")
    destination = {"same": seed, "inside": seed / "nested", "parent": tmp_path}.get(location)
    if location == "symlink":
        destination = tmp_path / "alias"
        destination.symlink_to(seed, target_is_directory=True)
    with pytest.raises(ValueError, match="separate"):
        cache.prepare_cache(seed, destination)


def test_missing_dependency_seed_fails_before_writing(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    destination = tmp_path / "private"
    with pytest.raises(ValueError, match="missing"):
        cache.prepare_cache(seed, destination)
    assert not destination.exists()
