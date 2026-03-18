"""Unit tests — DatabaseEnforcerProvider caching behaviour (mocked session, no real DB)."""
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import casbin
import pytest

from casbin_fastapi_decorator_db._provider import (
    DatabaseEnforcerProvider,
    _ModelFileHandler,
)

if TYPE_CHECKING:
    from pathlib import Path

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
async def test_returns_casbin_enforcer(mock_select: MagicMock, model_path: Path) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    enforcer = await provider()
    assert isinstance(enforcer, casbin.Enforcer)


@pytest.mark.unit
@pytest.mark.db_provider
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


@pytest.mark.unit
@pytest.mark.db_provider
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
    assert enforcer.enforce("alice", "docs", "write") is False


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_custom_mapper_field_names(mock_select: MagicMock, acl_model_path: Path) -> None:
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


@pytest.mark.unit
@pytest.mark.db_provider
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
    assert enforcer.enforce("alice", "data2", "write") is False


@pytest.mark.unit
@pytest.mark.db_provider
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


@pytest.mark.unit
@pytest.mark.db_provider
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


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_returns_same_cached_enforcer_on_subsequent_calls(
    mock_select: MagicMock, model_path: Path
) -> None:
    """After the first call the enforcer is cached — same object returned."""
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    e1 = await provider()
    e2 = await provider()

    assert e1 is e2


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_db_queried_only_once_without_dirty(
    mock_select: MagicMock, model_path: Path
) -> None:
    """Session factory is called once; subsequent calls hit the cache."""
    session_factory = _make_session([])
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=session_factory,
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    await provider()
    await provider()
    await provider()

    session_factory.return_value.__aenter__.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_mark_dirty_triggers_reload_on_next_call(
    mock_select: MagicMock, model_path: Path
) -> None:
    session_factory = _make_session([])
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=session_factory,
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    e1 = await provider()
    provider._mark_dirty()
    e2 = await provider()

    assert e1 is not e2
    assert session_factory.return_value.__aenter__.await_count == 2


@pytest.mark.unit
@pytest.mark.db_provider
def test_compute_hash_order_independent() -> None:
    """Same policies in different order must produce the same hash."""
    policies_a = [("alice", "data", "read"), ("bob", "data", "write")]
    policies_b = [("bob", "data", "write"), ("alice", "data", "read")]

    assert DatabaseEnforcerProvider._compute_hash(policies_a) == \
           DatabaseEnforcerProvider._compute_hash(policies_b)


@pytest.mark.unit
@pytest.mark.db_provider
def test_compute_hash_differs_for_different_policies() -> None:
    policies_a = [("alice", "data", "read")]
    policies_b = [("alice", "data", "write")]

    assert DatabaseEnforcerProvider._compute_hash(policies_a) != \
           DatabaseEnforcerProvider._compute_hash(policies_b)


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_needs_reload_false_after_first_call(
    mock_select: MagicMock, model_path: Path
) -> None:
    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=_make_session([]),
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
    )
    assert provider._needs_reload is True
    await provider()
    assert provider._needs_reload is False


@pytest.mark.unit
@pytest.mark.db_provider
def test_model_file_handler_on_created(model_path: Path) -> None:
    callback = MagicMock()
    handler = _ModelFileHandler(str(model_path), callback)
    event = MagicMock()
    event.is_directory = False
    event.src_path = str(model_path)

    handler.on_created(event)
    callback.assert_called_once()


@pytest.mark.unit
@pytest.mark.db_provider
def test_model_file_handler_on_moved(model_path: Path) -> None:
    callback = MagicMock()
    handler = _ModelFileHandler(str(model_path), callback)
    event = MagicMock()
    event.is_directory = False
    event.dest_path = str(model_path)

    handler.on_moved(event)
    callback.assert_called_once()


@pytest.mark.unit
@pytest.mark.db_provider
def test_model_file_handler_on_deleted(model_path: Path) -> None:
    callback = MagicMock()
    handler = _ModelFileHandler(str(model_path), callback)
    event = MagicMock()
    event.is_directory = False
    event.src_path = str(model_path)

    handler.on_deleted(event)
    callback.assert_called_once()


@pytest.mark.unit
@pytest.mark.db_provider
@patch("casbin_fastapi_decorator_db._provider.select", return_value=MagicMock())
async def test_poll_loop_handles_exception(mock_select: MagicMock, model_path: Path) -> None:
    """_poll_loop should not crash on DB errors."""
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB down"))

    provider = DatabaseEnforcerProvider(
        model_path=model_path,
        session_factory=session_factory,
        policy_model=PolicyRow,
        policy_mapper=lambda p: (p.sub, p.obj, p.act),
        poll_interval=0.01,
    )
    # We don't start the actual loop but call it once manually or mock sleep
    with (
        patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]),
        contextlib.suppress(asyncio.CancelledError),
    ):
        await provider._poll_loop()

    # If it reached here without crashing the provider, it works.
    # The first call to _fetch_policies inside _poll_loop failed,
    # and the loop continued (until our CancelledError).
