from __future__ import annotations

import jwt
import pytest
from casbin_fastapi_decorator_jwt import JWTUserProvider
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

SECRET = "test-secret-key"
ALGORITHM = "HS256"


def _make_token(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


@pytest.fixture
def bearer_provider() -> JWTUserProvider:
    return JWTUserProvider(secret_key=SECRET, algorithm=ALGORITHM)


@pytest.fixture
def cookie_provider() -> JWTUserProvider:
    return JWTUserProvider(secret_key=SECRET, algorithm=ALGORITHM, cookie_name="access_token")


@pytest.fixture
def bearer_app(bearer_provider: JWTUserProvider) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: dict = Depends(bearer_provider)) -> dict:
        return user

    return app


@pytest.fixture
def cookie_app(cookie_provider: JWTUserProvider) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def get_me(user: dict = Depends(cookie_provider)) -> dict:
        return user

    return app


@pytest.mark.asyncio
async def test_bearer_token_valid(bearer_app: FastAPI) -> None:
    token = _make_token({"sub": "user-1", "role": "admin"})
    async with AsyncClient(transport=ASGITransport(app=bearer_app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sub"] == "user-1"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_bearer_token_missing(bearer_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=bearer_app), base_url="http://test") as client:
        resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bearer_token_invalid(bearer_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=bearer_app), base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cookie_token_valid(cookie_app: FastAPI) -> None:
    token = _make_token({"sub": "user-2"})
    async with AsyncClient(transport=ASGITransport(app=cookie_app), base_url="http://test") as client:
        resp = await client.get("/me", cookies={"access_token": token})
    assert resp.status_code == 200
    assert resp.json()["sub"] == "user-2"


@pytest.mark.asyncio
async def test_cookie_token_missing(cookie_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=cookie_app), base_url="http://test") as client:
        resp = await client.get("/me")
    assert resp.status_code == 401


class UserPayload(BaseModel):
    sub: str
    role: str


@pytest.mark.asyncio
async def test_user_model_validation() -> None:
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
