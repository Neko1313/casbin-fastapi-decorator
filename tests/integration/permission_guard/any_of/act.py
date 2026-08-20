"""Integration tests — AnyOf() OR semantics across permission clauses."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import AccessSubject, AnyOf, PermissionGuard

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "employee"}


class _RecordingEnforcer:
    def __init__(self, *, allow_for: set[Any]) -> None:
        self.allow_for = allow_for
        self.calls: list[tuple[Any, ...]] = []

    def enforce(self, *args: Any) -> bool:
        self.calls.append(args)
        return args[1] in self.allow_for


class _AsyncRecordingEnforcer:
    def __init__(self, *, allow_for: set[Any]) -> None:
        self.allow_for = allow_for
        self.calls: list[tuple[Any, ...]] = []

    async def enforce(self, *args: Any) -> bool:
        self.calls.append(args)
        return args[1] in self.allow_for


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
async def test_any_of_allows_when_first_clause_passes() -> None:
    enf = _RecordingEnforcer(allow_for={"gallery-employee"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/gallery")
    @guard.require_permission(
        AnyOf(
            ("gallery-employee", "read"),
            ("gallery-criminal", "read"),
        ),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery")

    assert resp.status_code == 200
    # second clause is skipped once the first one passes
    assert enf.calls == [(_DEFAULT_USER, "gallery-employee", "read")]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_any_of_allows_when_second_clause_passes() -> None:
    enf = _RecordingEnforcer(allow_for={"gallery-criminal"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/gallery")
    @guard.require_permission(
        AnyOf(
            ("gallery-employee", "read"),
            ("gallery-criminal", "read"),
        ),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "gallery-employee", "read"),
        (_DEFAULT_USER, "gallery-criminal", "read"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_any_of_denies_when_every_clause_fails() -> None:
    enf = _RecordingEnforcer(allow_for=set())
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()
    route_called = False

    @app.get("/gallery")
    @guard.require_permission(
        AnyOf(
            ("gallery-employee", "read"),
            ("gallery-criminal", "read"),
        ),
    )
    async def route() -> dict:
        nonlocal route_called
        route_called = True
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery")

    assert resp.status_code == 403
    assert route_called is False
    assert enf.calls == [
        (_DEFAULT_USER, "gallery-employee", "read"),
        (_DEFAULT_USER, "gallery-criminal", "read"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_any_of_resolves_access_subject_per_clause() -> None:
    enf = _RecordingEnforcer(allow_for={"gallery-criminal"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    async def get_obj() -> dict:
        return {"domain": "gallery"}

    @app.get("/gallery")
    @guard.require_permission(
        AnyOf(
            (
                "gallery-employee",
                AccessSubject(val=get_obj, selector=lambda o: o["domain"]),
                "read",
            ),
            (
                "gallery-criminal",
                AccessSubject(val=get_obj, selector=lambda o: o["domain"]),
                "read",
            ),
        ),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "gallery-employee", "gallery", "read"),
        (_DEFAULT_USER, "gallery-criminal", "gallery", "read"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_any_of_supports_async_enforcer() -> None:
    enf = _AsyncRecordingEnforcer(allow_for={"gallery-criminal"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/gallery")
    @guard.require_permission(
        AnyOf(
            ("gallery-employee", "read"),
            ("gallery-criminal", "read"),
        ),
    )
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "gallery-employee", "read"),
        (_DEFAULT_USER, "gallery-criminal", "read"),
    ]


@pytest.mark.integration
@pytest.mark.permission_guard
async def test_any_of_combined_with_stacked_decorator_for_and() -> None:
    """AND across independent checks = stack require_permission()."""
    enf = _RecordingEnforcer(allow_for={"gallery-employee", "vip-badge"})
    guard = PermissionGuard(
        user_provider=_user(),
        enforcer_provider=_enforcer(enf),
        error_factory=_forbidden,
    )
    app = FastAPI()

    @app.get("/gallery/vip")
    @guard.require_permission("gallery-employee", "read")
    @guard.require_permission("vip-badge", "read")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/gallery/vip")

    assert resp.status_code == 200
    assert enf.calls == [
        (_DEFAULT_USER, "gallery-employee", "read"),
        (_DEFAULT_USER, "vip-badge", "read"),
    ]
