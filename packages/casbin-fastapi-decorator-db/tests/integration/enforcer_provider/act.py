"""Integration tests — DatabaseEnforcerProvider against a real PostgreSQL container."""
from __future__ import annotations

import asyncio
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

_WATCHDOG_SETTLE = 0.5  # seconds to wait for watchdog to detect file changes


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
    async with db_session_factory() as session:
        session.add_all([
            PolicyModel(sub="alice", obj="docs", act="read"),
            PolicyModel(sub="bob", obj="docs", act="write"),
            PolicyModel(sub="carol", obj="reports", act="read"),
        ])
        await session.commit()

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "docs", "read") is True
    assert enforcer.enforce("bob", "docs", "write") is True
    assert enforcer.enforce("carol", "reports", "read") is True
    assert enforcer.enforce("alice", "docs", "write") is False
    assert enforcer.enforce("dave", "docs", "read") is False


@pytest.mark.integration
@pytest.mark.db_provider
async def test_default_policies_merged_with_db_policies(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    async with db_session_factory() as session:
        session.add(PolicyModel(sub="bob", obj="data2", act="write"))
        await session.commit()

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
        default_policies=[("alice", "data1", "read")],
    )
    enforcer = await provider()

    assert enforcer.enforce("alice", "data1", "read") is True    # default
    assert enforcer.enforce("bob", "data2", "write") is True     # from DB
    assert enforcer.enforce("alice", "data2", "write") is False


@pytest.mark.integration
@pytest.mark.db_provider
async def test_empty_table_returns_working_enforcer(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
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
async def test_second_call_returns_cached_enforcer(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    """Enforcer is cached — both calls return the same object."""
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
    )
    e1 = await provider()
    e2 = await provider()

    assert e1 is e2


@pytest.mark.integration
@pytest.mark.db_provider
async def test_db_change_detected_after_poll(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    """Inserting a new policy row is picked up after poll_interval elapses."""
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
        poll_interval=0.1,
    )

    async with provider:
        enforcer_before = await provider()
        assert enforcer_before.enforce("alice", "docs", "read") is False

        # Insert a new policy row while the provider is running
        async with db_session_factory() as session:
            session.add(PolicyModel(sub="alice", obj="docs", act="read"))
            await session.commit()

        # Wait for at least one poll cycle to complete
        await asyncio.sleep(0.4)

        enforcer_after = await provider()
        assert enforcer_after.enforce("alice", "docs", "read") is True
        assert enforcer_before is not enforcer_after


@pytest.mark.integration
@pytest.mark.db_provider
async def test_model_conf_change_picked_up_by_watchdog(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    """Overwriting model.conf causes the enforcer to reload on next call."""
    async with db_session_factory() as session:
        session.add(PolicyModel(sub="alice", obj="docs", act="read"))
        await session.commit()

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
        poll_interval=3600.0,  # disable polling — only watchdog should trigger
    )

    async with provider:
        e1 = await provider()
        assert e1.enforce("alice", "docs", "read") is True

        # Overwrite model.conf with an always-deny matcher (sub must be "nobody")
        deny_model = _RBAC_MODEL.replace(
            "m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act",
            'm = r.sub == "nobody"',
        )
        await asyncio.to_thread(model_path.write_text, deny_model)
        await asyncio.sleep(_WATCHDOG_SETTLE)

        # Next call must reload with the new model
        e2 = await provider()
        assert e1 is not e2
        assert e2.enforce("alice", "docs", "read") is False


@pytest.mark.integration
@pytest.mark.db_provider
async def test_poll_task_cancelled_on_aexit(
    db_session_factory: async_sessionmaker[AsyncSession],
    model_path: Path,
) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=db_session_factory,
        policy_model=PolicyModel,
        policy_mapper=_mapper,
        poll_interval=3600.0,
    )

    async with provider:
        assert provider._poll_task is not None
        assert not provider._poll_task.done()

    assert provider._poll_task is None
    assert provider._observer is None
