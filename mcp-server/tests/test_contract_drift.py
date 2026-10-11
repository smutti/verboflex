"""Catch changed REST signatures when both workspace environments are installed."""

import subprocess
from pathlib import Path

import pytest


def test_generated_contract_matches_backend():
    root = Path(__file__).resolve().parents[2]
    python = root / "backend/.venv/bin/python"
    if not python.exists():
        pytest.skip(
            "Backend development environment not installed; run generate_contract.py --check"
        )
    subprocess.run(
        [str(python), str(root / "mcp-server/generate_contract.py"), "--check"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
