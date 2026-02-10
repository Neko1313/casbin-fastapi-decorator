from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from casbin_fastapi_decorator_db import DatabaseEnforcerProvider

if TYPE_CHECKING:
    from pathlib import Path

# Minimal RBAC model for testing
RBAC_MODEL = """\
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


@pytest.fixture
def model_path(tmp_path: Path) -> Path:
    path = tmp_path / "model.conf"
    path.write_text(RBAC_MODEL)
    return path


class PolicyRow:
    """A simple class mimicking an SQLAlchemy model row."""

    def __init__(self, sub: str, obj: str, act: str) -> None:
        self.sub = sub
        self.obj = obj
        self.act = act


def _make_mock_session(rows: list[Any]) -> MagicMock:
    """Create a mock async session factory that returns given rows."""
    scalars_mock = MagicMock()
    scalars_mock.__iter__ = MagicMock(return_value=iter(rows))

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    return session_factory


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_enforcer_with_db_policies(mock_select: MagicMock, model_path: Path) -> None:
    rows = [
        PolicyRow("alice", "data1", "read"),
        PolicyRow("bob", "data2", "write"),
    ]

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_mock_session(rows),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )

    enforcer = await provider()

    assert enforcer.enforce("alice", "data1", "read") is True
    assert enforcer.enforce("alice", "data2", "write") is False
    assert enforcer.enforce("bob", "data2", "write") is True
    mock_select.assert_called_once_with(PolicyRow)


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_enforcer_with_default_policies(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_mock_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
        default_policies=[("admin", "data1", "read")],
    )

    enforcer = await provider()
    assert enforcer.enforce("admin", "data1", "read") is True
    assert enforcer.enforce("admin", "data1", "write") is False


@pytest.mark.asyncio
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_enforcer_empty_policies(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_mock_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )

    enforcer = await provider()
    # With no policies, everything should be denied
    assert enforcer.enforce("alice", "data1", "read") is False
