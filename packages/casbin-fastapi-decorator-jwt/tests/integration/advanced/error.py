"""Integration tests — advanced error cases (expired, wrong secret, algorithm mismatch, validation failure)."""
from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ValidationError

from casbin_fastapi_decorator_jwt import JWTUserProvider

SECRET = "at-least-32-bytes-long-secret-key!"
ALGORITHM = "HS256"


def _token(payload: dict, secret: str = SECRET, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _app(provider: JWTUserProvider) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: Any = Depends(provider)) -> Any:
        return user

    return app


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_expired_token_returns_401() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    expired = _token({"sub": "alice", "exp": int(time.time()) - 10})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {expired}"})

    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_wrong_secret_returns_401() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    tok = _token({"sub": "alice"}, secret="completely-different-secret-key-!")  # noqa: S106
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {tok}"})

    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_algorithm_mismatch_returns_401() -> None:
    provider = JWTUserProvider(secret_key=SECRET, algorithm="HS256")
    app = _app(provider)

    tok = _token({"sub": "alice"}, algorithm="HS512")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {tok}"})

    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_custom_invalid_token_error_used() -> None:
    def my_invalid(reason: str) -> Exception:
        return HTTPException(status_code=400, detail=f"Bad token: {reason}")

    provider = JWTUserProvider(secret_key=SECRET, invalid_token_error=my_invalid)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": "Bearer bad-token"})

    assert resp.status_code == 400
    assert "Bad token:" in resp.json()["detail"]


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_default_invalid_token_detail_prefix() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": "Bearer bad"})

    assert resp.status_code == 401
    assert resp.json()["detail"].startswith("Invalid token:")


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_user_model_validation_failure_raises_pydantic_error() -> None:
    class StrictUser(BaseModel):
        sub: str
        role: str  # required

    provider = JWTUserProvider(secret_key=SECRET, user_model=StrictUser)

    tok = _token({"sub": "alice"})  # missing "role"
    mock_auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)

    with pytest.raises(ValidationError):
        await provider(header_auth=mock_auth)
