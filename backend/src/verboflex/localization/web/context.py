"""Bounded Angular extraction and exact JSON runtime addresses for pinned imports."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from verboflex.core.config import get_settings
from verboflex.localization.web.contracts import WebUsageIndex


def extract_usages(files: dict[str, bytes], marker: str) -> dict[str, object]:
    if len(files) > 5000 or sum(map(len, files.values())) > 20 * 1024 * 1024:
        raise ValueError("Web source budget exceeded")
    command = get_settings().web_extractor_command
    if not command:
        raise ValueError("Angular extraction is not configured")
    with tempfile.TemporaryDirectory(prefix="web-extract-") as directory:
        request, response = Path(directory) / "input.json", Path(directory) / "output.json"
        request.write_text(
            json.dumps(
                {"files": {p: c.decode("utf-8-sig") for p, c in files.items()}, "marker": marker}
            )
        )
        subprocess.run(
            [*command, str(request), str(response)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={k: os.environ[k] for k in ("PATH", "TMPDIR") if k in os.environ},
            timeout=45,
            check=True,
        )
        if response.is_symlink() or response.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Web extraction output exceeds its limit")
        return WebUsageIndex.model_validate_json(response.read_bytes()).model_dump(mode="json")


def catalog_addresses(catalog: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    addresses: dict[str, tuple[str, ...]] = {}

    def walk(value: Any, path: tuple[str, ...]) -> None:
        if len(path) > 12 or len(addresses) > 50000:
            raise ValueError("Catalog exceeds web capture limits")
        if isinstance(value, str):
            address = ".".join(path)
            if address in addresses:
                raise ValueError("Ambiguous literal-dot and nested runtime keys")
            addresses[address] = path
        elif isinstance(value, dict):
            for key, child in value.items():
                walk(child, (*path, key))
        else:
            raise ValueError("Web catalogs require string leaves")

    walk(catalog, ())
    return addresses


def set_catalog_value(catalog: dict[str, Any], path: tuple[str, ...], value: str) -> None:
    current = catalog
    for part in path[:-1]:
        current = current[part]
        if not isinstance(current, dict):
            raise ValueError("Catalog selector unavailable")
    if not path or not isinstance(current.get(path[-1]), str):
        raise ValueError("Catalog value unavailable")
    current[path[-1]] = value
