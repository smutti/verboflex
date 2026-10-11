"""Real local OAuth discovery/browser consent/MCP/refresh/revocation. No translation writes.

Run with backend/.venv/bin/python tools/mcp_oauth_smoke.py.
Needs running localhost:8080 deployment, frontend Playwright and .env.docker-access.json.
OAuth tokens remain in memory and are revoked; screenshots contain no credentials.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
import httpx2
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientMetadata
from pydantic import AnyUrl

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = "http://localhost:8080/mcp"


class MemoryStorage:
    tokens = None
    client = None

    async def get_tokens(self):
        return self.tokens

    async def set_tokens(self, tokens):
        self.tokens = tokens

    async def get_client_info(self):
        return self.client

    async def set_client_info(self, client):
        self.client = client


async def main():
    storage = MemoryStorage()
    output = Path(tempfile.mkdtemp(prefix="verboflex-oauth-smoke-"))
    name = "OAuth SDK smoke " + uuid4().hex[:8]
    code = None

    async def browser(mode, target):
        proc = await asyncio.create_subprocess_exec(
            "node",
            str(ROOT / "tools/mcp_oauth_browser_smoke.mjs"),
            mode,
            target,
            str(ROOT / ".env.docker-access.json"),
            str(output),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode:
            (output / "browser-error.txt").write_bytes(stderr)
            print(f"Browser diagnostics: {output}")
            raise RuntimeError(
                "Browser smoke failed; no credentials or callback data printed"
            )
        return json.loads(stdout)

    async def redirect(url):
        nonlocal code
        code = await browser("consent", url)

    async def callback():
        return AuthorizationCodeResult(**code)

    auth = OAuthClientProvider(
        RESOURCE,
        OAuthClientMetadata(
            client_name=name,
            redirect_uris=[AnyUrl("http://127.0.0.1:19342/callback")],
            token_endpoint_auth_method="none",
            scope="verboflex:read verboflex:write",
        ),
        storage,
        redirect_handler=redirect,
        callback_handler=callback,
    )
    try:
        async with (
            httpx2.AsyncClient(auth=auth, follow_redirects=True, timeout=45) as http,
            streamable_http_client(RESOURCE, http_client=http) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            assert all(tool.annotations.read_only_hint for tool in listed.tools)
            result = await session.call_tool("list_projects_and_languages", {})
            assert (
                not result.is_error and result.structured_content["status_code"] == 200
            )
            print(
                f"SDK OAuth + browser login + read-only MCP: {len(listed.tools)} tools; real projects read"
            )
        async with httpx.AsyncClient() as client:
            refreshed = await client.post(
                "http://localhost:8080/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": storage.client.client_id,
                    "refresh_token": storage.tokens.refresh_token,
                    "resource": RESOURCE,
                },
            )
            assert refreshed.status_code == 200
            storage.tokens = type(storage.tokens).model_validate(refreshed.json())
            await browser("revoke", name)
            denied = await client.post(
                RESOURCE,
                headers={"Authorization": "Bearer " + storage.tokens.access_token},
            )
            assert denied.status_code == 401
            print(
                "Refresh rotated; browser revocation immediately rejected access (401)."
            )
        print(f"Screenshots: {output}")
    finally:
        if storage.tokens and storage.client:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:8080/oauth/revoke",
                    data={
                        "client_id": storage.client.client_id,
                        "token": storage.tokens.refresh_token,
                    },
                )


if __name__ == "__main__":
    asyncio.run(main())
