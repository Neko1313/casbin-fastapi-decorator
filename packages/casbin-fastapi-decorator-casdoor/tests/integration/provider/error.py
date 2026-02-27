"""Integration tests — CasdoorUserProvider error cases."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_casdoor import CasdoorUserProvider

ACCESS_TOKEN = "header.payload.signature_access"
REFRESH_TOKEN = "header.payload.signature_refresh"


def _make_app(sdk: MagicMock) -> FastAPI:
    provider = CasdoorUserProvider(sdk=sdk)
    app = FastAPI()

    @app.get("/me")
    async def get_me(token: str = Depends(provider)) -> dict:
        return {"token": token}

    return app


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_missing_both_cookies_returns_401() -> None:
    sdk = MagicMock()
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_missing_access_token_returns_401() -> None:
    sdk = MagicMock()
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/me", cookies={"refresh_token": REFRESH_TOKEN})
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_missing_refresh_token_returns_401() -> None:
    sdk = MagicMock()
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/me", cookies={"access_token": ACCESS_TOKEN})
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_invalid_token_returns_401() -> None:
    sdk = MagicMock()
    sdk.parse_jwt_token.side_effect = ValueError("bad token")
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/me",
            cookies={
                "access_token": "bad-token",
                "refresh_token": REFRESH_TOKEN,
            },
        )
    assert resp.status_code == 401
