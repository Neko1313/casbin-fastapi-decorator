"""Integration tests — error_factory contract, custom status codes, return value pass-through."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import PermissionGuard

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "admin"}


class _SyncEnforcer:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.last_call: tuple[Any, ...] | None = None

    def enforce(self, *args: Any) -> bool:
        self.last_call = args
        return self.allow


def _user():
    async def _get() -> dict[str, Any]:
        return _DEFAULT_USER

    return _get


def _enforcer(e: Any):
    async def _get() -> Any:
        return e

    return _get


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_error_factory_receives_user_and_rvals() -> None:
    captured: list[Any] = []

    def capturing_error(user: Any, *rvals: Any) -> HTTPException:
        captured.extend([user, *rvals])
        return HTTPException(status_code=403, detail="Forbidden")

    enf = _SyncEnforcer(allow=False)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=capturing_error,
    )
    app = FastAPI()

    @app.get("/check")
    @guard.require_permission("articles", "delete")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 403
    assert captured == [_DEFAULT_USER, "articles", "delete"]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_custom_error_status_code() -> None:
    def not_found_error(user: Any, *rvals: Any) -> HTTPException:
        return HTTPException(status_code=404, detail="Not found")

    enf = _SyncEnforcer(allow=False)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=not_found_error,
    )
    app = FastAPI()

    @app.get("/secret")
    @guard.require_permission("secret", "access")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/secret")

    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_route_return_value_passed_through() -> None:
    def _forbidden(user: Any, *rvals: Any) -> HTTPException:
        return HTTPException(status_code=403, detail="Forbidden")

    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/data")
    @guard.require_permission("data", "read")
    async def route() -> dict:
        return {"payload": "secret", "count": 42}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/data")

    assert resp.status_code == 200
    assert resp.json() == {"payload": "secret", "count": 42}


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_enforce_called_with_correct_user() -> None:
    def _forbidden(user: Any, *rvals: Any) -> HTTPException:
        return HTTPException(status_code=403, detail="Forbidden")

    custom_user = {"sub": "bob", "role": "viewer"}
    enf = _SyncEnforcer(allow=True)

    async def custom_user_provider() -> dict[str, Any]:
        return custom_user

    async def enforcer_provider() -> Any:
        return enf

    guard = PermissionGuard(
        user_provider=custom_user_provider,
        enforcer_provider=enforcer_provider,
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/resource")
    @guard.require_permission("reports", "read")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/resource")

    assert resp.status_code == 200
    user_arg, *_ = enf.last_call  # type: ignore[misc]
    assert user_arg == custom_user
