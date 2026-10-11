"""Launched by tools/mcp_workflow_smoke.py against an isolated real API/database."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def run(directory: Path) -> None:
    fixture = json.loads((directory / "fixture.json").read_text())
    group = {"translation_group_id": fixture["group"]}

    def connect(role: str, *, read_only: bool = False) -> Client:
        return Client(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "verboflex_mcp.cli",
                    "--session-file",
                    str(directory / f"{role}.json"),
                    "serve",
                    *(["--read-only"] if read_only else []),
                ],
            )
        )

    checks = []

    async def call(client, name, args, expected=200):
        response = await client.call_tool(name, args)
        content = response.structured_content
        assert content["status_code"] == expected, (name, content)
        assert response.is_error == (expected >= 400)
        checks.append(f"{name}: {expected}")
        return content["data"]

    async with (
        connect("admin") as admin,
        connect("translator") as translator,
        connect("viewer") as viewer,
    ):
        assert len((await admin.list_tools()).tools) == 70
        await call(admin, "whoami", {})
        await call(viewer, "get_translation", group)
        saved = await call(translator, "save_translation", {**group, "payload": fixture["payload"]})
        assert saved["version"] == 1 and saved["state"] == "draft"
        # A stale version must not replace the first saved draft.
        stale = await call(
            translator, "save_translation", {**group, "payload": fixture["payload"]}, 409
        )
        assert stale["latest"]["version"] == 1
        await call(viewer, "save_translation", {**group, "payload": fixture["payload"]}, 403)
        await call(
            translator,
            "review_translation",
            {**group, "payload": {"target_state": "approved", "expected_version": 1}},
            403,
        )
        limit = await call(
            admin,
            "set_translation_limit",
            {**group, "language": "it", "payload": {"max_chars": 4, "expected_version": 0}},
        )
        # Length rules remain authoritative for agents as for the browser.
        await call(
            admin,
            "review_translation",
            {**group, "payload": {"target_state": "approved", "expected_version": 1}},
            409,
        )
        payload = fixture["payload"]
        payload["expected_version"] = 1
        for value in payload["values"]:
            value["proposed_text"] = "Ciao"
        saved = await call(translator, "save_translation", {**group, "payload": payload})
        assert saved["version"] == 2
        approved = await call(
            admin,
            "review_translation",
            {**group, "payload": {"target_state": "approved", "expected_version": 2}},
        )
        assert approved["state"] == "approved"
        await call(
            admin,
            "remove_translation_limit",
            {**group, "language": "it", "payload": {"expected_version": limit["version"]}},
        )
        detail = await call(viewer, "get_translation", group)
        assert detail["pending_change"]["state"] == "approved"
        history = await call(admin, "list_translation_activity", group)
        assert len(history["items"]) >= 3
    async with connect("admin", read_only=True) as readonly:
        assert "save_translation" not in {t.name for t in (await readonly.list_tools()).tools}
        assert (
            await readonly.call_tool("save_translation", {**group, "payload": payload})
        ).is_error
        checks.append("read-only mode: write rejected")
    print(
        json.dumps(
            {"transport": "stdio -> HTTP -> FastAPI -> PostgreSQL", "checks": checks}, indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1])))
