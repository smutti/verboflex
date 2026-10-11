"""Native login is deliberately separate from model-callable MCP tools."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys
from pathlib import Path

import httpx
from filelock import Timeout

from verboflex_mcp.api import ApiClient
from verboflex_mcp.server import serve
from verboflex_mcp.session import ConnectorError, SessionStore, http_client


def main() -> None:
    parser = argparse.ArgumentParser(description="VerboFlex MCP connector")
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path(os.environ.get("VERBOFLEX_MCP_SESSION_FILE", "~/.verboflex/mcp-session.json")),
        help="Private session file (default: ~/.verboflex/mcp-session.json)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    login = commands.add_parser("login", help="Sign in interactively; never stores your password")
    login.add_argument("--api-url", required=True, help="API root, including /api/v1")
    login.add_argument("--username", help="VerboFlex email; prompted when omitted")
    commands.add_parser("logout", help="Revoke this connector session")
    commands.add_parser("status", help="Check the signed-in user without printing credentials")
    run = commands.add_parser("serve", help="Run the MCP server on stdin/stdout")
    run.add_argument("--read-only", action="store_true", help="Expose and allow only read tools")
    args = parser.parse_args()
    # stdout belongs exclusively to the MCP protocol while serving.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    store = SessionStore(args.session_file)
    try:
        with http_client() as client:
            if args.command == "login":
                username = args.username or input("VerboFlex email: ")
                password = getpass.getpass("VerboFlex password: ")
                store.login(client, args.api_url, username, password)
                print("Signed in. Codex and Claude can use this session.")
            elif args.command == "logout":
                store.logout(client)
                print("Session revoked.")
            elif args.command == "status":
                response = ApiClient(store, client).call(
                    {"path": "/users/me", "method": "GET", "bindings": {}},
                    {},
                )
                if response["status_code"] != 200:
                    raise ConnectorError("Session unavailable. Run verboflex-mcp login again.")
                user = response["data"]
                print(f"Signed in as {user['display_name']} ({user['email']})")
            else:
                asyncio.run(serve(ApiClient(store, client), read_only=args.read_only))
    except ConnectorError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    except (httpx.HTTPError, Timeout, OSError):
        print("VerboFlex unavailable or session storage inaccessible.", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
