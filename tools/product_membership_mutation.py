#!/usr/bin/env python3
"""Run the installed mutmut on delegation policy in an owned source copy."""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--properties-only", action="store_true")
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verboflex-team-mutation-") as directory:
        target = Path(directory)
        for folder in ("src", "tests", "alembic"):
            shutil.copytree(
                ROOT / "backend" / folder,
                target / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        shutil.copy2(ROOT / "backend/alembic.ini", target)
        config = (ROOT / "backend/pyproject.toml").read_text()
        config, count = re.subn(
            r"only_mutate = \[.*?\]",
            'only_mutate = ["src/verboflex/auth/product_access.py"]',
            config,
            flags=re.DOTALL,
        )
        assert count == 1
        config, count = re.subn(
            r"pytest_add_cli_args_test_selection = \[.*?\]",
            'pytest_add_cli_args_test_selection = ["tests/auth/test_product_access.py"]',
            config,
            flags=re.DOTALL,
        )
        assert count == 1
        if args.properties_only:
            config = config.replace(
                'pytest_add_cli_args_test_selection = ["tests/auth/test_product_access.py"]',
                'pytest_add_cli_args_test_selection = ["tests/auth/test_product_access.py", "-k", "property"]',
            )
        (target / "pyproject.toml").write_text(config)
        environment = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("VERBOFLEX_", "BITBUCKET_", "PYTHONPATH"))
        }
        environment["PATH"] = (
            str(ROOT / "backend/.venv/bin") + os.pathsep + environment["PATH"]
        )
        environment["PYTHONPATH"] = str(target / "src") + os.pathsep + str(target)
        binary = str(ROOT / "backend/.venv/bin/mutmut")
        with (args.artifacts / "run.log").open("w") as log:
            result = subprocess.run(
                [binary, "run", "*may_manage_member*", "--max-children", "2"],
                cwd=target,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
                check=False,
            )
        if result.returncode:
            raise SystemExit(result.returncode)
        with (args.artifacts / "results.txt").open("w") as log:
            subprocess.run(
                [binary, "results", "--all", "true"],
                cwd=target,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        lines = (args.artifacts / "results.txt").read_text().splitlines()
        selected = [line for line in lines if "x_may_manage_member__mutmut_" in line]
        if not selected or any(not line.endswith(": killed") for line in selected):
            raise SystemExit(
                "Delegation policy has surviving, missing or untested mutants"
            )
        print(f"{len(selected)} delegation mutants killed: {args.artifacts.resolve()}")


if __name__ == "__main__":
    main()
