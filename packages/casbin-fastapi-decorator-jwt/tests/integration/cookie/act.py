"""Integration tests — Cookie token happy paths."""
from __future__ import annotations

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_jwt import JWTUserProvider

SECRET = "test-secret-key"
ALGORITHM = "HS256"


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


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
async def test_cookie_token_valid(cookie_app: FastAPI) -> None:
    token = _make_token({"sub": "user-2"})
    async with AsyncClient(transport=ASGITransport(app=cookie_app), base_url="http://test") as client:
        resp = await client.get("/me", cookies={"access_token": token})
    assert resp.status_code == 200
    assert resp.json()["sub"] == "user-2"
