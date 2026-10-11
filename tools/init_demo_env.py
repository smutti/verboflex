#!/usr/bin/env python3
"""Create a private environment for a separate, GitHub-import-only demo."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="DNS hostname, without scheme or path")
    parser.add_argument("--output", type=Path, default=Path(".env.demo"))
    args = parser.parse_args()
    if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", args.host):
        parser.error("use a lowercase DNS hostname, without scheme, path or port")
    if not args.output.name.startswith(".env."):
        parser.error("use a private .env.* filename")
    values = {
        "VERBOFLEX_DEMO_HOST": args.host,
        "VERBOFLEX_IMAGE_TAG": "demo",
        "VERBOFLEX_POSTGRES_DB": "verboflex_demo",
        "VERBOFLEX_POSTGRES_PASSWORD": secrets.token_hex(32),
        "VERBOFLEX_JWT_SECRET_KEY": secrets.token_hex(48),
        "VERBOFLEX_CORS_ORIGINS": json.dumps([f"https://{args.host}"], separators=(",", ":")),
        "VERBOFLEX_MCP_PUBLIC_URL": "",
        # Required by the base Compose contract, but never connected to a provider.
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID": "demo-disconnected-" + secrets.token_hex(16),
        "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET": secrets.token_hex(32),
        "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "VERBOFLEX_BACKEND_PORT": "8008",
        "VERBOFLEX_FRONTEND_PORT": "8088",
        "VITE_API_BASE_URL": "/",
    }
    # Never overwrite deployment credentials, even if a previous run was interrupted.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("# Private demo deployment; do not commit or publish.\n")
        for name, value in values.items():
            output.write(f"{name}='{value}'\n")
    print(f"Created {args.output} with owner-only permissions. No provider connected.")


if __name__ == "__main__":
    main()
