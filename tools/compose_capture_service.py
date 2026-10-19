#!/usr/bin/env python3
"""Private Linux relay. Only this trusted service holds the Docker socket.

Its exchange directory must have the same absolute path on the Docker host.
Repository builds receive only read-only source/input/fixture mounts, no network,
no credentials and no writable host filesystem.
"""

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path

from compose_capture_container import render
from compose_capture_macos import handler
from verboflex.worker.screenshot_tasks import validate_png


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--exchange-root", type=Path, required=True)
    args = parser.parse_args()
    args.exchange_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = args.token_file.read_text().strip()
    if len(token) < 32:
        raise ValueError("A strong relay credential is required")

    def capture(payload, profiles):
        content = render(payload, profiles, exchange_root=args.exchange_root)
        validate_png(content)
        return content

    ThreadingHTTPServer(
        ("0.0.0.0", 8766),
        handler(token, json.loads(args.profiles.read_bytes()), render_fn=capture),
    ).serve_forever()


if __name__ == "__main__":
    main()
