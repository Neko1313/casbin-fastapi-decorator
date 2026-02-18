"""Integration tests — DatabaseEnforcerProvider against a real PostgreSQL container."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider
from tests.fixtures.entities.policy import PolicyModel

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    pass

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


def _mapper(p: PolicyModel) -> tuple[str, str, str]:
    return (p.sub, p.obj, p.act)


@pytest.mark.integration
@pytest.mark.db_provider
async def test_enforcer_loads_policies_from_real_db(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    # ── Seed data ──────────────────────────────────────────────────────
    async with db_session_factory() as session:
        session.add_all([
            PolicyModel(sub="alice", obj="docs", act="read"),
            PolicyModel(sub="bob", obj="docs", act="write"),
            PolicyModel(sub="carol", obj="reports", act="read"),
        ])
        await session.commit()

    # ── Act ────────────────────────────────────────────────────────────
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
    )
    enforcer = await provider()

    # ── Assert ─────────────────────────────────────────────────────────
    assert enforcer.enforce("alice", "docs", "read") is True
    assert enforcer.enforce("bob", "docs", "write") is True
    assert enforcer.enforce("carol", "reports", "read") is True
    assert enforcer.enforce("alice", "docs", "write") is False   # not granted
    assert enforcer.enforce("dave", "docs", "read") is False     # unknown user


@pytest.mark.integration
@pytest.mark.db_provider
async def test_default_policies_merged_with_db_policies(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    # ── Seed data ──────────────────────────────────────────────────────
    async with db_session_factory() as session:
        session.add(PolicyModel(sub="bob", obj="data2", act="write"))
        await session.commit()

    # ── Act ────────────────────────────────────────────────────────────
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
        default_policies=[("alice", "data1", "read")],
    )
    enforcer = await provider()

    # ── Assert ─────────────────────────────────────────────────────────
    assert enforcer.enforce("alice", "data1", "read") is True    # default
    assert enforcer.enforce("bob", "data2", "write") is True     # from DB
    assert enforcer.enforce("alice", "data2", "write") is False  # not granted


@pytest.mark.integration
@pytest.mark.db_provider
async def test_empty_table_returns_working_enforcer(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    """Provider works correctly even when the policy table has no rows."""
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "docs", "read") is False


@pytest.mark.integration
@pytest.mark.db_provider
async def test_each_provider_call_sees_latest_db_state(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    """Each __call__ re-queries the DB, so new rows are picked up."""
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
    )

    # First call — table empty
    enforcer1 = await provider()
    assert enforcer1.enforce("alice", "docs", "read") is False

    # Add a policy row
    async with db_session_factory() as session:
        session.add(PolicyModel(sub="alice", obj="docs", act="read"))
        await session.commit()

    # Second call — should see the new row
    enforcer2 = await provider()
    assert enforcer2.enforce("alice", "docs", "read") is True

    # Enforcers are independent objects
    assert enforcer1 is not enforcer2
