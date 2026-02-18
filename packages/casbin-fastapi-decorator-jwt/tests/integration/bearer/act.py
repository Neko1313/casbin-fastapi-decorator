"""Integration tests — Bearer token happy paths."""
from __future__ import annotations

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from casbin_fastapi_decorator_jwt import JWTUserProvider

SECRET = "test-secret-key"
ALGORITHM = "HS256"


def _make_token(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


@pytest.fixture
def bearer_app() -> FastAPI:
    provider = JWTUserProvider(secret_key=SECRET, algorithm=ALGORITHM)
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: dict = Depends(provider)) -> dict:
        return user

    return app


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_bearer_token_valid(bearer_app: FastAPI) -> None:
    token = _make_token({"sub": "user-1", "role": "admin"})
    async with AsyncClient(transport=ASGITransport(app=bearer_app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sub"] == "user-1"
    assert data["role"] == "admin"


@pytest.mark.integration
@pytest.mark.jwt_provider
async def test_user_model_validation() -> None:
    class UserPayload(BaseModel):
        sub: str
        role: str

    provider = JWTUserProvider(
        secret_key=SECRET,
        algorithm=ALGORITHM,
        user_model=UserPayload,
    )
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: UserPayload = Depends(provider)) -> dict:
        return {"sub": user.sub, "role": user.role}

    token = _make_token({"sub": "user-3", "role": "editor"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"sub": "user-3", "role": "editor"}
