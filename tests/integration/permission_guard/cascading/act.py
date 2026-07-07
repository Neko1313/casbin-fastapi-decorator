"""Integration tests — stacking multiple require_permission() decorators."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import AccessSubject, PermissionGuard

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "admin"}


class _RecordingEnforcer:
    def __init__(self, *, deny_for: set[Any] | None = None) -> None:
        self.deny_for = deny_for or set()
        self.calls: list[tuple[Any, ...]] = []

    def enforce(self, *args: Any) -> bool:
        self.calls.append(args)
        return args[-1] not in self.deny_for


def _user():
    async def _get() -> dict[str, Any]:
        return _DEFAULT_USER

    return _get


def _enforcer(e: Any):
    async def _get() -> Any:
        return e

    return _get


def _forbidden(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail=f"Forbidden:{rvals}")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_stacked_require_permission_decorators_both_enforce() -> None:
    enf = _RecordingEnforcer()
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_domain_a() -> str:
        return "domain-a"

    async def get_domain_b() -> str:
        return "domain-b"

    @app.get("/check")
    @guard.require_permission(
        AccessSubject(val=get_domain_a, selector=lambda x: x),
        "read",
    )
    @guard.require_permission(
        AccessSubject(val=get_domain_b, selector=lambda x: x),
        "write",
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "domain-a", "read"),
        (_DEFAULT_USER, "domain-b", "write"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_stacked_decorators_inner_denial_blocks_route_body() -> None:
    enf = _RecordingEnforcer(deny_for={"write"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()
    route_called = False

    async def get_domain_a() -> str:
        return "domain-a"

    async def get_domain_b() -> str:
        return "domain-b"

    @app.get("/check")
    @guard.require_permission(
        AccessSubject(val=get_domain_a, selector=lambda x: x),
        "read",
    )
    @guard.require_permission(
        AccessSubject(val=get_domain_b, selector=lambda x: x),
        "write",
    )
    async def route() -> dict:
        nonlocal route_called
        route_called = True
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 403
    assert route_called is False
    # outer decorator's check ran and passed before the inner one denied
    assert enf.calls == [
        (_DEFAULT_USER, "domain-a", "read"),
        (_DEFAULT_USER, "domain-b", "write"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_three_stacked_decorators_all_enforce_independently() -> None:
    enf = _RecordingEnforcer()
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.post("/migrate")
    @guard.require_permission("locations", "migrate")
    @guard.require_permission("floors", "migrate")
    @guard.require_permission("floor-state", "migrate")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/migrate")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "locations", "migrate"),
        (_DEFAULT_USER, "floors", "migrate"),
        (_DEFAULT_USER, "floor-state", "migrate"),
    ]
