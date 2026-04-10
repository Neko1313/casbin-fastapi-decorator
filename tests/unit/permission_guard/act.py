"""Unit tests for PermissionGuard factory (no HTTP, no DI resolution)."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from casbin_fastapi_decorator import AccessSubject, PermissionGuard


async def _user_provider() -> dict[str, str]:
    return {"sub": "alice"}


async def _enforcer_provider() -> Any:
    return None


def _error_factory(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


@pytest.fixture
def guard() -> PermissionGuard:
    return PermissionGuard(
        user_provider=_user_provider,
        enforcer_provider=_enforcer_provider,
        error_factory=_error_factory,
    )


@pytest.mark.unit
@pytest.mark.permission_guard
def test_guard_stores_user_provider(guard: PermissionGuard) -> None:
    assert guard._user_provider is _user_provider


@pytest.mark.unit
@pytest.mark.permission_guard
def test_guard_stores_enforcer_provider(guard: PermissionGuard) -> None:
    assert guard._enforcer_provider is _enforcer_provider


@pytest.mark.unit
@pytest.mark.permission_guard
def test_guard_stores_error_factory(guard: PermissionGuard) -> None:
    assert guard._error_factory is _error_factory


@pytest.mark.unit
@pytest.mark.permission_guard
def test_auth_required_returns_callable(guard: PermissionGuard) -> None:
    assert callable(guard.auth_required())


@pytest.mark.unit
@pytest.mark.permission_guard
def test_auth_required_can_decorate_async_function(guard: PermissionGuard) -> None:
    decorator = guard.auth_required()

    async def route() -> dict:
        return {"ok": True}

    decorated = decorator(route)
    assert callable(decorated)


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_static_args_returns_callable(guard: PermissionGuard) -> None:
    assert callable(guard.require_permission("resource", "read"))


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_no_args_returns_callable(guard: PermissionGuard) -> None:
    assert callable(guard.require_permission())


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_single_access_subject_returns_callable(
    guard: PermissionGuard,
) -> None:
    async def dep() -> str:
        return "value"

    decorator = guard.require_permission(
        AccessSubject(val=dep, selector=lambda x: x),
    )
    assert callable(decorator)


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_mixed_args_returns_callable(guard: PermissionGuard) -> None:
    async def dep() -> dict:
        return {"name": "foo"}

    decorator = guard.require_permission(
        AccessSubject(val=dep, selector=lambda d: d["name"]),
        "write",
    )
    assert callable(decorator)


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_can_decorate_async_function(guard: PermissionGuard) -> None:
    decorator = guard.require_permission("resource", "read")

    async def route() -> dict:
        return {"ok": True}

    decorated = decorator(route)
    assert callable(decorated)


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_uses_guard_error_factory_by_default(
    guard: PermissionGuard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def build_stub(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return lambda func: func

    monkeypatch.setattr(
        "casbin_fastapi_decorator._guard.build_permission_decorator",
        build_stub,
    )

    guard.require_permission("resource", "read")

    assert captured["error_factory"] is _error_factory


@pytest.mark.unit
@pytest.mark.permission_guard
def test_require_permission_accepts_route_error_factory(
    guard: PermissionGuard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def route_error_factory(user: Any, *rvals: Any) -> HTTPException:
        return HTTPException(status_code=404, detail="Not found")

    def build_stub(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return lambda func: func

    monkeypatch.setattr(
        "casbin_fastapi_decorator._guard.build_permission_decorator",
        build_stub,
    )

    guard.require_permission(
        "resource",
        "read",
        error_factory=route_error_factory,
    )

    assert captured["error_factory"] is route_error_factory


@pytest.mark.unit
@pytest.mark.permission_guard
def test_multiple_guards_are_independent() -> None:
    async def user_a() -> dict:
        return {"sub": "alice"}

    async def user_b() -> dict:
        return {"sub": "bob"}

    async def enforcer_stub() -> Any:
        return None

    def err(user: Any, *rv: Any) -> HTTPException:
        return HTTPException(403)

    g1 = PermissionGuard(user_provider=user_a, enforcer_provider=enforcer_stub, error_factory=err)
    g2 = PermissionGuard(user_provider=user_b, enforcer_provider=enforcer_stub, error_factory=err)

    assert g1._user_provider is user_a
    assert g2._user_provider is user_b
    assert g1._user_provider is not g2._user_provider
