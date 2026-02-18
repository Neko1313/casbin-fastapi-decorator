"""Integration tests — DatabaseEnforcerProvider denial cases against a real PostgreSQL container."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider
from tests.fixtures.entities.policy import PolicyModel

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
def model_path(tmp_path: Path) -> Path:
    path = tmp_path / "model.conf"
    path.write_text(_RBAC_MODEL)
    return path


@pytest.mark.integration
@pytest.mark.db_provider
async def test_denies_access_when_policy_table_empty(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()

    assert enforcer.enforce("admin", "anything", "read") is False
    assert enforcer.enforce("alice", "data", "write") is False


@pytest.mark.integration
@pytest.mark.db_provider
async def test_denies_unlisted_action_even_if_subject_has_other_permissions(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    async with db_session_factory() as session:
        session.add(PolicyModel(sub="alice", obj="docs", act="read"))
        await session.commit()

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "docs", "read") is True
    assert enforcer.enforce("alice", "docs", "write") is False   # not granted
    assert enforcer.enforce("alice", "docs", "delete") is False  # not granted
