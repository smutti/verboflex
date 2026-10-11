"""Public repository linking remains admin-only and provider-scoped."""

import asyncio

import httpx
from sqlalchemy import select

from tests.api.test_admin_discovery import (
    _authority,
    _configure,
    clean_discovery_database,
    discovery_session_factory,
)
from verboflex.api.v1.routes.admin_github import get_github_adapter
from verboflex.integrations.github.client import GitHubHttpAdapter
from verboflex.main import app
from verboflex.models.repository import Repository

__all__ = ["clean_discovery_database", "discovery_session_factory"]


def test_link_requires_admin_and_is_idempotent_across_providers(discovery_session_factory):
    factory = discovery_session_factory
    calls = []

    def metadata(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "private": False,
                "full_name": "acme/mobile",
                "default_branch": "main",
                "stargazers_count": 800,
                "language": "Kotlin",
            },
        )

    adapter = GitHubHttpAdapter(transport=httpx.MockTransport(metadata))
    _configure(factory, None)
    app.dependency_overrides[get_github_adapter] = lambda: adapter
    admin = _authority(factory, role="admin", email="admin@example.test")
    viewer = _authority(factory, role="viewer", email="viewer@example.test")
    with factory.begin() as session:
        session.add(Repository(workspace="acme", repository_slug="mobile"))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {"owner": "Acme", "repository": "Mobile"}
            for token, expected in ((None, 401), (viewer, 403)):
                response = await client.post(
                    "/api/v1/admin/github/repositories",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                )
                assert response.status_code == expected
            assert not calls
            records = []
            for _ in range(2):
                response = await client.post(
                    "/api/v1/admin/github/repositories",
                    json=payload,
                    headers={"Authorization": f"Bearer {admin}"},
                )
                assert response.status_code == 200, response.text
                records.append(response.json())
            assert records[0]["id"] == records[1]["id"]
            assert records[0]["provider"] == "github"
            assert records[0]["stars"] == 800
            assert records[0]["import_only"] is True
        await adapter.aclose()

    asyncio.run(run())
    with factory() as session:
        assert set(session.scalars(select(Repository.provider))) == {"github", "bitbucket"}
