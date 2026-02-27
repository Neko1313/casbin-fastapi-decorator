"""Integration tests — CasdoorUserProvider happy paths."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_casdoor import CasdoorUserProvider

ACCESS_TOKEN = "header.payload.signature_access"
REFRESH_TOKEN = "header.payload.signature_refresh"


def _make_sdk(parse_raises: Exception | None = None) -> MagicMock:
    sdk = MagicMock()
    if parse_raises:
        sdk.parse_jwt_token.side_effect = parse_raises
    else:
        sdk.parse_jwt_token.return_value = {"owner": "org", "name": "user1"}
    return sdk


@pytest.fixture
def cookie_app() -> FastAPI:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    app = FastAPI()

    @app.get("/me")
    async def get_me(token: str = Depends(provider)) -> dict:
        return {"token": token}

    return app


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_valid_cookies_returns_access_token(cookie_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=cookie_app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/me",
            cookies={
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["token"] == ACCESS_TOKEN


@pytest.mark.integration
@pytest.mark.casdoor_provider
async def test_custom_cookie_names() -> None:
    sdk = _make_sdk()
    provider = CasdoorUserProvider(
        sdk=sdk,
        access_token_cookie="my_access",
        refresh_token_cookie="my_refresh",
    )
    app = FastAPI()

    @app.get("/me")
    async def get_me(token: str = Depends(provider)) -> dict:
        return {"token": token}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/me",
            cookies={"my_access": ACCESS_TOKEN, "my_refresh": REFRESH_TOKEN},
        )
    assert resp.status_code == 200
    assert resp.json()["token"] == ACCESS_TOKEN
