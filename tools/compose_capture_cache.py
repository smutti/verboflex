#!/usr/bin/env python3
"""Prepare private writable caches without copying shared Gradle dependencies."""

import argparse
import subprocess
from pathlib import Path


def prepare_cache(seed: Path, destination: Path) -> None:
    """The image owns the seed; only per-render state is copied into tmpfs."""
    seed = seed.resolve(strict=True)
    destination = destination.resolve()
    if destination.is_relative_to(seed) or seed.is_relative_to(destination):
        raise ValueError("Writable cache must be separate from its immutable seed")
    if not (seed / "caches/modules-2").is_dir():
        raise ValueError("Prepared read-only dependency cache is missing")
    destination.mkdir(parents=True, exist_ok=True)
    for source in seed.iterdir():
        if source.name == "caches":
            target = destination / "caches"
            target.mkdir(exist_ok=True)
            sources = [entry for entry in source.iterdir() if entry.name != "modules-2"]
        else:
            target = destination
            sources = [source]
        if sources:
            # Keep the same native copy semantics as the original entrypoint for
            # compiler/transform caches and the wrapper distribution.
            subprocess.run(["cp", "-a", *map(str, sources), str(target)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    prepare_cache(args.seed, args.destination)


if __name__ == "__main__":
    main()
