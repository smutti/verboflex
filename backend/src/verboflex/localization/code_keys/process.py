"""Crash and time isolation for the native syntax parser, used only by workers."""

import base64
import json
import subprocess
import sys

from verboflex.localization.code_keys.catalog import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    CodeKeyCatalog,
    CodeSourceConfig,
    extract_catalog,
)


def extract_catalog_isolated(files: dict[str, bytes], config: CodeSourceConfig) -> CodeKeyCatalog:
    if (
        len(files) > MAX_FILES
        or sum(map(len, files.values())) > MAX_TOTAL_BYTES
        or any(len(data) > MAX_FILE_BYTES for data in files.values())
    ):
        raise ValueError("Code source budget exceeded")
    payload = json.dumps(
        {
            "files": {name: base64.b64encode(data).decode("ascii") for name, data in files.items()},
            "config": config.model_dump(mode="json"),
        }
    ).encode()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "verboflex.localization.code_keys.process"],
            input=payload,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Code extraction timed out") from error
    if completed.returncode != 0 or len(completed.stdout) > 64 * 1024 * 1024:
        raise ValueError("Code extraction failed; no catalog was activated")
    return CodeKeyCatalog.model_validate_json(completed.stdout)


if __name__ == "__main__":
    request = json.loads(sys.stdin.buffer.read(30 * 1024 * 1024))
    result = extract_catalog(
        {name: base64.b64decode(data, validate=True) for name, data in request["files"].items()},
        CodeSourceConfig.model_validate(request["config"]),
    )
    sys.stdout.write(result.model_dump_json())
