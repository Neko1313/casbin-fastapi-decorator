"""
Functional tests for DatabaseEnforcerProvider.__call__:
  - returns casbin.Enforcer
  - select() called with policy_model
  - policy_mapper applied to every row
  - default + DB policies combined
  - session context manager exercised
  - multiple calls create independent enforcers
  - custom mapper shape
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import casbin
import pytest

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Shared RBAC model fixture
# ---------------------------------------------------------------------------

_RBAC_MODEL = """\
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
"""

_ACL_MODEL = """\
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
"""


@pytest.fixture
def model_path(tmp_path: Path) -> Path:
    path = tmp_path / "model.conf"
    path.write_text(_RBAC_MODEL)
    return path


@pytest.fixture
def acl_model_path(tmp_path: Path) -> Path:
    path = tmp_path / "acl.conf"
    path.write_text(_ACL_MODEL)
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class PolicyRow:
    def __init__(self, sub: str, obj: str, act: str) -> None:
        self.sub = sub
        self.obj = obj
        self.act = act


def _make_session(rows: list[Any]) -> MagicMock:
    scalars_mock = MagicMock()
    scalars_mock.__iter__ = MagicMock(return_value=iter(rows))

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)

    return factory


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_returns_casbin_enforcer(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()
    assert isinstance(enforcer, casbin.Enforcer)


# ---------------------------------------------------------------------------
# select() call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_select_called_with_policy_model(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    await provider()
    mock_select.assert_called_once_with(PolicyRow)


# ---------------------------------------------------------------------------
# Policy mapper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_mapper_applied_to_every_row(mock_select: MagicMock, model_path: Path) -> None:
    rows = [
        PolicyRow("alice", "docs", "read"),
        PolicyRow("bob", "docs", "write"),
        PolicyRow("carol", "reports", "read"),
    ]
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session(rows),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "docs", "read") is True
    assert enforcer.enforce("bob", "docs", "write") is True
    assert enforcer.enforce("carol", "reports", "read") is True
    assert enforcer.enforce("alice", "docs", "write") is False  # not granted


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_custom_mapper_field_names(mock_select: MagicMock, acl_model_path: Path) -> None:
    """Mapper can use any attribute names from the ORM row."""

    class PermRow:
        def __init__(self, user: str, resource: str, action: str) -> None:
            self.user = user
            self.resource = resource
            self.action = action

    rows = [PermRow("dave", "invoices", "approve")]
    provider = DatabaseEnforcerProvider(
        model_path=acl_model_path,
        session_factory=_make_session(rows),
        policy_model=PermRow,
        policy_mapper=lambda p: (p.user, p.resource, p.action),
    )
    enforcer = await provider()

    assert enforcer.enforce("dave", "invoices", "approve") is True
    assert enforcer.enforce("dave", "invoices", "read") is False


# ---------------------------------------------------------------------------
# Default + DB policies combined
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_default_and_db_policies_both_enforced(mock_select: MagicMock, model_path: Path) -> None:
    rows = [PolicyRow("bob", "data2", "write")]
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session(rows),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
        default_policies=[("alice", "data1", "read")],
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "data1", "read") is True   # default
    assert enforcer.enforce("bob", "data2", "write") is True    # from DB
    assert enforcer.enforce("alice", "data2", "write") is False  # not granted


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_only_default_policies_when_db_empty(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
        default_policies=[("admin", "data1", "read")],
    )
    enforcer = await provider()

    assert enforcer.enforce("admin", "data1", "read") is True
    assert enforcer.enforce("admin", "data1", "write") is False


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_denies_all_when_no_policies(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()

    assert enforcer.enforce("admin", "anything", "read") is False
    assert enforcer.enforce("alice", "data", "write") is False


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_session_context_manager_entered_and_exited(
    mock_select: MagicMock, model_path: Path
) -> None:
    session_factory = _make_session([])
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=session_factory,
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    await provider()

    session_factory.return_value.__aenter__.assert_awaited_once()
    session_factory.return_value.__aexit__.assert_awaited_once()


# ---------------------------------------------------------------------------
# Multiple calls → independent enforcers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_each_call_returns_new_enforcer(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    e1 = await provider()
    e2 = await provider()

    assert e1 is not e2
