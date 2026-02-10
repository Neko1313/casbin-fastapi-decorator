from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from casbin_fastapi_decorator import PermissionGuard


class MockEnforcer:
    """Mock enforcer that returns a configurable result."""

    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.last_call: tuple[Any, ...] | None = None

    def enforce(self, *args: Any) -> bool:
        self.last_call = args
        return self.allow


@pytest.fixture
def mock_enforcer() -> MockEnforcer:
    return MockEnforcer(allow=True)


@pytest.fixture
def deny_enforcer() -> MockEnforcer:
    return MockEnforcer(allow=False)


def _make_user_provider(user: dict[str, Any]):
    async def get_current_user() -> dict[str, Any]:
        return user

    return get_current_user


def _make_enforcer_provider(enforcer: MockEnforcer):
    async def get_enforcer() -> MockEnforcer:
        return enforcer

    return get_enforcer


def _error_factory(user: Any, *rvals: Any) -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


@pytest.fixture
def test_user() -> dict[str, Any]:
    return {"sub": "user-1", "role": "admin"}


@pytest.fixture
def guard(test_user, mock_enforcer) -> PermissionGuard:
    return PermissionGuard(
        user_provider=_make_user_provider(test_user),
        enforcer_provider=_make_enforcer_provider(mock_enforcer),
        error_factory=_error_factory,
    )


@pytest.fixture
def deny_guard(test_user, deny_enforcer) -> PermissionGuard:
    return PermissionGuard(
        user_provider=_make_user_provider(test_user),
        enforcer_provider=_make_enforcer_provider(deny_enforcer),
        error_factory=_error_factory,
    )
