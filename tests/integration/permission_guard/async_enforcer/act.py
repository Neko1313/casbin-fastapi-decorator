"""Integration tests — async enforcer allows requests."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import PermissionGuard

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "admin"}


class _AsyncEnforcer:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.last_call: tuple[Any, ...] | None = None

    async def enforce(self, *args: Any) -> bool:
        self.last_call = args
        return self.allow


def _user(user: dict[str, Any] = _DEFAULT_USER):
    async def _get() -> dict[str, Any]:
        return user

    return _get


def _enforcer(e: Any):
    async def _get() -> Any:
        return e

    return _get


def _forbidden(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_async_enforcer_allows_request() -> None:
    enf = _AsyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/resource")
    @guard.require_permission("articles", "read")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/resource")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "articles", "read")
