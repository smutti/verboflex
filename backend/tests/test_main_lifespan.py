"""Application shutdown never leaves closed provider pools available to later scopes."""

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from verboflex import main


@pytest.mark.parametrize("failure", [False, True])
def test_shutdown_clears_provider_pools_even_after_application_failure(monkeypatch, failure):
    adapters = SimpleNamespace(bitbucket=object(), aclose=AsyncMock())
    monkeypatch.setattr(main, "create_repository_read_adapters", lambda _: adapters)
    app = FastAPI()

    async def run():
        async with main._application_lifespan(app):
            assert app.state.repository_read_adapters is adapters
            assert app.state.bitbucket_http_adapter is adapters.bitbucket
            if failure:
                raise RuntimeError("test shutdown")

    with pytest.raises(RuntimeError, match="test shutdown") if failure else nullcontext():
        asyncio.run(run())
    adapters.aclose.assert_awaited_once()
    assert app.state.repository_read_adapters is None
    assert app.state.bitbucket_http_adapter is None
