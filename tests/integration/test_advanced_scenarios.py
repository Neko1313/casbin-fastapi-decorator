"""
Integration tests for PermissionGuard — advanced scenarios not covered by
tests/test_integration.py:
  - async enforcer (enforce() returns a coroutine)
  - multiple AccessSubject args
  - mixed static + AccessSubject args
  - error_factory receives (user, *rvals)
  - route return value is preserved
  - custom error status code
  - auth_required() does not invoke the enforcer
  - AccessSubject selector is applied before enforce()
"""
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import AccessSubject, PermissionGuard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_USER: dict[str, Any] = {"sub": "alice", "role": "admin"}


class _SyncEnforcer:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.last_call: tuple[Any, ...] | None = None

    def enforce(self, *args: Any) -> bool:
        self.last_call = args
        return self.allow


class _AsyncEnforcer:
    """Enforcer whose .enforce() returns a coroutine."""

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


# ---------------------------------------------------------------------------
# Async enforcer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_enforcer_allows_request() -> None:
    enf = _AsyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

    app = FastAPI()

    @app.get("/resource")
    @guard.require_permission("articles", "read")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/resource")

    assert resp.status_code == 200
    assert enf.last_call == (_DEFAULT_USER, "articles", "read")


@pytest.mark.asyncio
async def test_async_enforcer_denies_request() -> None:
    enf = _AsyncEnforcer(allow=False)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

    app = FastAPI()

    @app.get("/resource")
    @guard.require_permission("articles", "write")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/resource")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Multiple AccessSubject args
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_access_subjects_resolved_in_order() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

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


# ---------------------------------------------------------------------------
# Mixed static + AccessSubject
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_access_subject_before_static_arg() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

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


@pytest.mark.asyncio
async def test_static_arg_before_access_subject() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

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


# ---------------------------------------------------------------------------
# error_factory contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_factory_receives_user_and_rvals() -> None:
    captured: list[Any] = []

    def capturing_error(user: Any, *rvals: Any) -> HTTPException:
        captured.extend([user, *rvals])
        return HTTPException(status_code=403, detail="Forbidden")

    enf = _SyncEnforcer(allow=False)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=capturing_error)

    app = FastAPI()

    @app.get("/check")
    @guard.require_permission("articles", "delete")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/check")

    assert resp.status_code == 403
    assert captured == [_DEFAULT_USER, "articles", "delete"]


@pytest.mark.asyncio
async def test_custom_error_status_code() -> None:
    def not_found_error(user: Any, *rvals: Any) -> HTTPException:
        return HTTPException(status_code=404, detail="Not found")

    enf = _SyncEnforcer(allow=False)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=not_found_error)

    app = FastAPI()

    @app.get("/secret")
    @guard.require_permission("secret", "access")
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/secret")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Route return value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_return_value_passed_through() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

    app = FastAPI()

    @app.get("/data")
    @guard.require_permission("data", "read")
    async def route() -> dict:
        return {"payload": "secret", "count": 42}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/data")

    assert resp.status_code == 200
    assert resp.json() == {"payload": "secret", "count": 42}


# ---------------------------------------------------------------------------
# AccessSubject selector
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_selector_applied_before_enforce() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

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
    # enforce receives selector result, NOT the raw dict
    assert enf.last_call == (_DEFAULT_USER, "alice", "read")


# ---------------------------------------------------------------------------
# auth_required() does not call enforcer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_required_does_not_call_enforcer() -> None:
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(user_provider=_user(), enforcer_provider=_enforcer(enf), error_factory=_forbidden)

    app = FastAPI()

    @app.get("/me")
    @guard.auth_required()
    async def route() -> dict:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/me")

    assert resp.status_code == 200
    assert enf.last_call is None  # enforcer never called


# ---------------------------------------------------------------------------
# User value propagation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enforce_called_with_correct_user() -> None:
    custom_user = {"sub": "bob", "role": "viewer"}
    enf = _SyncEnforcer(allow=True)
    guard = PermissionGuard(
        user_provider=_user(custom_user),
        enforcer_provider=_enforcer(enf),
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
