#!/usr/bin/env python3
"""Render one frozen Compose capture bundle INSIDE an isolated Android runner.

Production: mirror is read-only, dependencies are prewarmed, network is disabled.
Development workspace mode is explicit and never supplied by the HTTP API.
"""

import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path

from verboflex.localization.code_keys.capture import (
    CaptureBundle,
    preview_source,
    resource_overlay,
)
from verboflex.worker.screenshot_tasks import validate_png


def apply_fixture_patch(workspace: Path, patch: str) -> None:
    """Apply an operator-reviewed patch only inside the disposable checkout."""
    subprocess.run(
        ["git", "apply", "--no-index", patch],
        cwd=workspace,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(workspace.parent)},
        check=True,
        timeout=30,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args],
        timeout=60,
    )


def checkout(repo: Path, commit: str, destination: Path, depth: int = 0) -> None:
    if depth > 3 or not re.fullmatch(r"[a-f0-9]{40,64}", commit):
        raise ValueError("Invalid immutable checkout")
    if (
        git(repo, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
        != commit
    ):
        raise ValueError("Commit unavailable in mirror")
    with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", commit))) as archive:
        archive.extractall(destination, filter="data")
    modules = [
        entry
        for entry in git(repo, "ls-tree", "-rz", commit).split(b"\0")
        if entry.startswith(b"160000 ")
    ]
    if len(modules) > 20:
        raise ValueError("Submodule budget exceeded")
    for entry in modules:
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("Invalid submodule path")
        checkout(
            repo / path, metadata.split()[2].decode(), destination / path, depth + 1
        )


def capture(
    workspace: Path,
    bundle: CaptureBundle,
    output: Path,
    *,
    quiet: bool = False,
    run_build: Callable[[list[str], Path], None] | None = None,
) -> None:
    module = workspace.joinpath(*bundle.capture.module.strip(":").split(":"))
    if not module.resolve().is_relative_to(workspace.resolve()) or not module.is_dir():
        raise ValueError("Capture module unavailable")
    # Only registered main-source fixture functions are callable. Each disposable
    # checkout gets exactly one screenshot test and no old reference images.
    test_sources = module / "src/screenshotTest"
    if test_sources.exists():
        shutil.rmtree(test_sources)
    reference = module / f"src/screenshotTest{bundle.capture.variant}/reference"
    if reference.exists():
        shutil.rmtree(reference)
    generated = module / "build/verboflex-capture"
    generated.mkdir(parents=True, exist_ok=True)
    source = test_sources / "kotlin/verboflex/capture/Capture.kt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(preview_source(bundle))
    locale = "b+" + bundle.language.replace("-", "+")
    for folder in ("values", f"values-{locale}"):
        resources = generated / "res" / folder
        resources.mkdir(parents=True, exist_ok=True)
        (resources / "verboflex.xml").write_bytes(resource_overlay(bundle))
    command = [
        str(workspace / "gradlew"),
        f"{bundle.capture.module}:update{bundle.capture.variant}ScreenshotTest",
        "--rerun",
        "--offline",
        "--no-daemon",
        "--console=plain",
        "--build-cache",
        "-Pverboflex.capture=true",
        "-Pandroid.experimental.enableScreenshotTest=true",
        f"-Pverboflex.captureVariant={bundle.capture.variant[0].lower() + bundle.capture.variant[1:]}",
        f"-Pverboflex.captureRoot={generated}",
    ]
    if run_build is not None:
        run_build(command, workspace)
    else:
        subprocess.run(
            command,
            cwd=workspace,
            check=True,
            timeout=840,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
    images = list(reference.rglob("*.png"))
    if len(images) != 1 or images[0].is_symlink():
        raise ValueError("Expected exactly one newly rendered preview")
    content = images[0].read_bytes()
    validate_png(content)
    output.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--emit-png", action="store_true")
    parser.add_argument("--mirror", type=Path)
    parser.add_argument("--repository-id")
    parser.add_argument("--profile")
    parser.add_argument("--commit")
    parser.add_argument("--fixture-patch", type=Path)
    parser.add_argument("--fixture-patch-sha256")
    parser.add_argument("--development-workspace", type=Path)
    args = parser.parse_args()
    bundle = CaptureBundle.model_validate_json(args.input.read_bytes())
    if args.development_workspace:
        capture(
            args.development_workspace.resolve(),
            bundle,
            args.output.resolve(),
            quiet=args.emit_png,
        )
        if args.emit_png:
            sys.stdout.buffer.write(args.output.read_bytes())
        return
    if (
        args.mirror is None
        or bundle.code_repository_id != args.repository_id
        or bundle.capture.runner_profile != args.profile
        or (args.commit is not None and bundle.code_commit != args.commit)
    ):
        raise ValueError("Runner profile does not own this repository")
    if args.fixture_patch and (
        not args.commit
        or hashlib.sha256(args.fixture_patch.read_bytes()).hexdigest()
        != args.fixture_patch_sha256
    ):
        raise ValueError("Fixture patch is not bound to a reviewed revision")
    with tempfile.TemporaryDirectory(prefix="compose-checkout-") as directory:
        root = Path(directory)
        checkout(args.mirror, bundle.code_commit, root)
        if args.fixture_patch:
            apply_fixture_patch(root, str(args.fixture_patch.resolve()))
        sdk = os.environ.get("ANDROID_HOME")
        if sdk:
            (root / "local.properties").write_text(f"sdk.dir={sdk}\n")
        capture(root, bundle, args.output.resolve(), quiet=args.emit_png)
        if args.emit_png:
            sys.stdout.buffer.write(args.output.read_bytes())


if __name__ == "__main__":
    main()
