"""Integration tests — AccessSubject resolution, ordering, and selector application."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import AccessSubject, PermissionGuard

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


def _forbidden(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_multiple_access_subjects_resolved_in_order() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_resource() -> dict:
        return {"type": "article"}

    async def get_action() -> str:
        return "read"

    @app.get("/check")
    @guard.require_permission(
        AccessSubject(val=get_resource, selector=lambda r: r["type"]),
        AccessSubject(val=get_action, selector=lambda a: a),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "article", "read")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_access_subject_before_static_arg() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_obj() -> dict:
        return {"name": "target-resource"}

    @app.get("/check")
    @guard.require_permission(
        AccessSubject(val=get_obj, selector=lambda o: o["name"]),
        "write",
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "target-resource", "write")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_static_arg_before_access_subject() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_action() -> str:
        return "delete"

    @app.get("/check")
    @guard.require_permission(
        "documents",
        AccessSubject(val=get_action, selector=lambda a: a),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "documents", "delete")


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_selector_applied_before_enforce() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_item(item_id: int = 1) -> dict:
        return {"id": item_id, "owner": "alice"}

    @app.get("/items/{item_id}")
    @guard.require_permission(
        AccessSubject(val=get_item, selector=lambda item: item["owner"]),
        "read",
    )
    async def route(item_id: int) -> dict:
        return {"item_id": item_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/items/5")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "alice", "read")
