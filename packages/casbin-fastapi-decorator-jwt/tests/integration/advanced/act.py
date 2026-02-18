"""Integration tests — advanced happy paths (token source priority, full payload, custom errors)."""
from __future__ import annotations

from typing import Any

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

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


@pytest.mark.integration
@pytest.mark.jwt_provider
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


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_custom_unauthorized_error_used() -> None:
    def my_unauth() -> Exception:
        return HTTPException(status_code=403, detail="Custom unauthorized")

    provider = JWTUserProvider(secret_key=SECRET, unauthorized_error=my_unauth)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Custom unauthorized"


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_default_unauthorized_detail() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    app = _app(provider)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"
