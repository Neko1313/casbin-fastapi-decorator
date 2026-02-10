from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import AccessSubject, PermissionGuard
from tests.conftest import MockEnforcer, _error_factory


@pytest.fixture
def app(guard: PermissionGuard, mock_enforcer: MockEnforcer) -> FastAPI:
    app = FastAPI()

    @app.get("/auth-only")
    @guard.auth_required()
    async def auth_only_route() -> dict:
        return {"ok": True}

    @app.get("/static-permission")
    @guard.require_permission("resource", "read")
    async def static_permission_route() -> dict:
        return {"ok": True}

    async def get_item(item_id: int = 42) -> dict:
        return {"id": item_id, "name": "test-item"}

    @app.get("/dynamic-permission/{item_id}")
    @guard.require_permission(
        AccessSubject(val=get_item, selector=lambda item: item["name"]),
        "read",
    )
    async def dynamic_permission_route(item: dict = Depends(get_item)) -> dict:
        return {"item": item}

    return app


@pytest.fixture
def deny_app(deny_guard: PermissionGuard) -> FastAPI:
    app = FastAPI()

    @app.get("/denied")
    @deny_guard.require_permission("resource", "read")
    async def denied_route() -> dict:
        return {"ok": True}

    return app


@pytest.fixture
def auth_fail_app() -> FastAPI:
    app = FastAPI()

    async def failing_user_provider() -> None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async def get_enforcer() -> None:
        return None

    guard = PermissionGuard(
        user_provider=failing_user_provider,
        enforcer_provider=get_enforcer,
        error_factory=_error_factory,
    )

    @app.get("/protected")
    @guard.auth_required()
    async def protected() -> dict:
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_auth_required_allows_authenticated_user(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth-only")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_auth_required_rejects_unauthenticated(auth_fail_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=auth_fail_app), base_url="http://test") as client:
        resp = await client.get("/protected")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_static_permission_allowed(app: FastAPI, mock_enforcer: MockEnforcer) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/static-permission")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Verify enforce was called with user + static args
    assert mock_enforcer.last_call is not None
    user, resource, action = mock_enforcer.last_call
    assert user == {"sub": "user-1", "role": "admin"}
    assert resource == "resource"
    assert action == "read"


@pytest.mark.asyncio
async def test_static_permission_denied(deny_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=deny_app), base_url="http://test") as client:
        resp = await client.get("/denied")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dynamic_permission_with_access_subject(app: FastAPI, mock_enforcer: MockEnforcer) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/dynamic-permission/123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["item"]["name"] == "test-item"
    # Verify enforce was called with selector result
    assert mock_enforcer.last_call is not None
    user, item_name, action = mock_enforcer.last_call
    assert user == {"sub": "user-1", "role": "admin"}
    assert item_name == "test-item"
    assert action == "read"
