"""A failed checkpoint command cannot echo or retain provider/secret output."""

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_failed_checkpoint_command_emits_digest_only_and_removes_raw_output(tmp_path):
    source = (ROOT / "tools/phase4_parser_checkpoint.sh").read_text()
    functions = []
    for name in ("record_command", "sha256_file"):
        body = source.split(f"{name}() {{\n", 1)[1].split("\n}\n", 1)[0]
        functions.append(f"{name}() {{\n{body}\n}}")
    canary = "SECRET-CANARY OAuth-private-key <resources>provider-private-text</resources>"
    shell = (
        "\n".join(functions)
        + "\n"
        + (
            "now_ms() { printf '0\\n'; }\n"
            'HOST_RUNTIME_DIR="$1"\n'
            "record_command canary 'Safe checkpoint identity' 'fixture failure' "
            'bash -c \'printf "%s\\n" "$1"; exit 9\' bash "$2"\n'
        )
    )
    result = subprocess.run(
        ["bash", "-c", shell, "probe", str(tmp_path), canary],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 9
    assert canary not in result.stdout + result.stderr
    digest = hashlib.sha256((canary + "\n").encode()).hexdigest()
    assert result.stdout == ""
    assert result.stderr == (
        "phase4-parser-checkpoint error: Safe checkpoint identity failed "
        f"(return_code=9, output_sha256={digest})\n"
    )
    assert not (tmp_path / "canary.log").exists()
