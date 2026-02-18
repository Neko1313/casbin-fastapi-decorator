"""Integration tests — Cookie token missing error case."""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_jwt import JWTUserProvider

SECRET = "test-secret-key"
ALGORITHM = "HS256"


@pytest.fixture
def cookie_app() -> FastAPI:
    provider = JWTUserProvider(secret_key=SECRET, algorithm=ALGORITHM, cookie_name="access_token")
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: dict = Depends(provider)) -> dict:
        return user

    return app


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_cookie_token_missing(cookie_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=cookie_app), base_url="http://test") as client:
        resp = await client.get("/me")
    assert resp.status_code == 401
