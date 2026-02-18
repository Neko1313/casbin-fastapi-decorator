"""
Additional integration tests for JWTUserProvider.__call__:
  - cookie takes priority over bearer when both present
  - custom unauthorized_error factory
  - custom invalid_token_error factory
  - expired token → 401
  - wrong secret → 401
  - algorithm mismatch → 401
  - full payload dict returned without user_model
  - default error messages
  - user_model validation failure (direct call)
"""
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


# ---------------------------------------------------------------------------
# Token source priority
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cookie_takes_priority_over_bearer() -> None:
    provider = JWTUserProvider(secret_key=SECRET, cookie_name="access_token")
    app = _app(provider)

    cookie_tok = _token({"sub": "from-cookie"})
    bearer_tok = _token({"sub": "from-bearer"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/me",
            cookies={"access_token": cookie_tok},
            headers={"Authorization": f"Bearer {bearer_tok}"},
        )
    assert resp.status_code == 200
    assert resp.json()["sub"] == "from-cookie"


# ---------------------------------------------------------------------------
# Custom error factories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_unauthorized_error_used() -> None:
    def my_unauth() -> Exception:
        return HTTPException(status_code=403, detail="Custom unauthorized")

    provider = JWTUserProvider(secret_key=SECRET, unauthorized_error=my_unauth)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Custom unauthorized"


@pytest.mark.asyncio
async def test_custom_invalid_token_error_used() -> None:
    def my_invalid(reason: str) -> Exception:
        return HTTPException(status_code=400, detail=f"Bad token: {reason}")

    provider = JWTUserProvider(secret_key=SECRET, invalid_token_error=my_invalid)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": "Bearer bad-token"})

    assert resp.status_code == 400
    assert "Bad token:" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Token validation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_token_returns_401() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    expired = _token({"sub": "alice", "exp": int(time.time()) - 10})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {expired}"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_returns_401() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    tok = _token({"sub": "alice"}, secret="completely-different-secret-key-!")  # noqa: S106

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {tok}"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_algorithm_mismatch_returns_401() -> None:
    # Provider expects HS256 but token is HS512
    provider = JWTUserProvider(secret_key=SECRET, algorithm="HS256")
    app = _app(provider)

    tok = _token({"sub": "alice"}, algorithm="HS512")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {tok}"})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Payload handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_payload_returned_as_dict() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    tok = _token({"sub": "alice", "role": "admin", "level": 5})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {tok}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["sub"] == "alice"
    assert data["role"] == "admin"
    assert data["level"] == 5


@pytest.mark.asyncio
async def test_user_model_validation_failure_raises_pydantic_error() -> None:
    """model_validate() raises ValidationError when payload is missing required fields."""

    class StrictUser(BaseModel):
        sub: str
        role: str  # required

    provider = JWTUserProvider(secret_key=SECRET, user_model=StrictUser)

    # Call directly (bypass HTTP), missing "role"
    tok = _token({"sub": "alice"})
    mock_auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)

    with pytest.raises(ValidationError):
        await provider(header_auth=mock_auth)


# ---------------------------------------------------------------------------
# Default error messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_default_unauthorized_detail() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_default_invalid_token_detail_prefix() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": "Bearer bad"})

    assert resp.status_code == 401
    assert resp.json()["detail"].startswith("Invalid token:")
