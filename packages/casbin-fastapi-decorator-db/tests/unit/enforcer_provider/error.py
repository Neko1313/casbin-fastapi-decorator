"""Unit tests — DatabaseEnforcerProvider denial cases (mocked session, no real DB)."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider

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


@pytest.fixture
def model_path(tmp_path):
    path = tmp_path / "model.conf"
    path.write_text(_RBAC_MODEL)
    return path


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


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_denies_all_when_no_policies(mock_select: MagicMock, model_path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()

    assert enforcer.enforce("admin", "anything", "read") is False
    assert enforcer.enforce("alice", "data", "write") is False
