"""The approved parser dependency adds one exact license identity, not a waiver."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "name,version,license_name,allowed",
    [
        ("regex", "2026.9.3", "Apache-2.0 AND CNRI-Python", True),
        ("regex", "2026.9.4", "Apache-2.0 AND CNRI-Python", False),
        ("other", "2026.9.3", "Apache-2.0 AND CNRI-Python", False),
        ("regex", "2026.9.3", "CNRI-Python", False),
        ("regex", "2026.9.3", "UNKNOWN", False),
    ],
)
def test_approved_regex_license_is_bound_to_exact_release(
    tmp_path, name, version, license_name, allowed
):
    inventory = tmp_path / "licenses.json"
    inventory.write_text(
        json.dumps(
            [
                {
                    "Name": name,
                    "Version": version,
                    "License": license_name,
                    "URL": "https://github.com/mrabarnett/mrab-regex",
                }
            ]
        )
    )
    result = subprocess.run(
        ["bash", "tools/phase4_parser_checkpoint.sh", "--license-policy", str(inventory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == (0 if allowed else 1)
    assert ("license-policy: PASS" in result.stdout) is allowed
    if not allowed:
        assert result.stderr.strip() == "license-policy: FAIL"
