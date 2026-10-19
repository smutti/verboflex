"""Verify the host/container channel with a cached synthetic Python image, not Android."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from compose_capture_container import capture_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", required=True, help="Cached digest-pinned Python image"
    )
    args = parser.parse_args()
    if "@sha256:" not in args.image:
        parser.error("Image must be pinned by digest")
    name = "verboflex-transport-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="verboflex-transport-") as directory:
        source = Path(directory) / "input.json"
        source.write_text(json.dumps({"synthetic": True}))
        source.chmod(0o644)
        code = """import json, os, sys
from pathlib import Path
assert os.getuid() == 65532
assert json.loads(Path('/input.json').read_text()) == {'synthetic': True}
try:
    Path('/input.json').write_text('forbidden')
except OSError:
    pass
else:
    raise AssertionError('writable host mount')
sys.stdout.buffer.write(b'synthetic transport')
"""
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--network=none",
            "--read-only",
            "--log-driver=none",
            "--user=65532:65532",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=64m",
            "--pids-limit=32",
            "--mount",
            f"type=bind,source={source},target=/input.json,readonly",
            args.image,
            "python",
            "-c",
            code,
        ]
        try:
            assert capture_output(command, 30) == b"synthetic transport"
        finally:
            subprocess.run(
                ["docker", "rm", "--force", name],
                check=False,
                timeout=15,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    print("Compose transport: PASS (unprivileged UID, read-only input, bounded stdout)")


if __name__ == "__main__":
    main()
