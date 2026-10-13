#!/usr/bin/env python3
"""Trusted worker adapter for an authenticated, local macOS capture service."""

import argparse
import urllib.request
from pathlib import Path

MAX_INPUT = 4 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024


def request_capture(url: str, token: str, payload: bytes, timeout: int) -> bytes:
    if len(payload) > MAX_INPUT:
        raise ValueError("Capture input exceeds limit")
    request = urllib.request.Request(
        url + "/capture",
        data=payload,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    # No proxies or redirects: never forward the runner credential elsewhere.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        if response.headers.get_content_type() != "image/png":
            raise ValueError("Unexpected capture response")
        content = response.read(MAX_OUTPUT + 1)
    if len(content) > MAX_OUTPUT:
        raise ValueError("Capture output exceeds limit")
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    args.output.write_bytes(
        request_capture(
            args.url,
            args.token_file.read_text().strip(),
            args.input.read_bytes(),
            args.timeout,
        )
    )


if __name__ == "__main__":
    main()
