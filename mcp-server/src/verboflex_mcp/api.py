"""Bounded, non-retrying REST adapter. The API owns roles and optimistic concurrency."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from verboflex_mcp.session import ConnectorError, SessionStore

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ApiClient:
    def __init__(self, store: SessionStore, client: httpx.Client) -> None:
        self.store = store
        self.client = client

    def call(self, operation: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        authority = self.store.authority(self.client)
        path = operation["path"]
        query: list[tuple[str, str]] = []
        for key, location in operation["bindings"].items():
            value = arguments.get(key)
            if value is None:
                continue
            if location == "path":
                path = path.replace("{" + key + "}", quote(str(value), safe=""))
            else:
                values = value if isinstance(value, list) else [value]
                query.extend(
                    (key, str(item).lower() if isinstance(item, bool) else str(item))
                    for item in values
                )
        # No API-supplied paths, redirects, retries, or automatic page traversal.
        with self.client.stream(
            operation["method"],
            authority.api_url + path,
            params=httpx.QueryParams(tuple(query)),
            json=arguments.get("payload"),
            headers={"Authorization": f"Bearer {authority.access_token}"},
        ) as response:
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ConnectorError(
                        "Response too large. Narrow the project/language filters. "
                        "If this was a write, inspect its current state before retrying."
                    )
            if response.status_code == 204:
                data: Any = None
            elif response.status_code >= 500 or 300 <= response.status_code < 400:
                data = {"detail": "VerboFlex unavailable. Check its status before retrying writes."}
            else:
                import json

                try:
                    data = json.loads(content)
                except ValueError as error:
                    raise ConnectorError(
                        "Invalid API response; check VerboFlex before retrying."
                    ) from error
            return {"status_code": response.status_code, "data": data}
