"""Integration tests — auth_required() authenticates without invoking the enforcer."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import PermissionGuard

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "admin"}


class _SyncEnforcer:
    def __init__(self) -> None:
        self.last_call: tuple[Any, ...] | None = None

    def enforce(self, *args: Any) -> bool:
        self.last_call = args
        return True


def _forbidden(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_auth_required_does_not_call_enforcer() -> None:
    enf = _SyncEnforcer()

    async def user_provider() -> dict[str, Any]:
        return _DEFAULT_USER

    async def enforcer_provider() -> Any:
        return enf

    guard = PermissionGuard(
        user_provider=user_provider,
        enforcer_provider=enforcer_provider,
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/me")
    @guard.auth_required()
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 200
    assert enf.last_call is None
