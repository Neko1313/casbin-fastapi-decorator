"""Unit tests — CachedFileEnforcerProvider caching behaviour (mocked I/O)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import casbin
import pytest
from casbin_fastapi_decorator_file import CachedFileEnforcerProvider

if TYPE_CHECKING:
    from pathlib import Path

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
    path.write_text(_ACL_MODEL)
    return path


@pytest.fixture
def policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy.csv"
    path.write_text("p, alice, data, read\n")
    return path


@pytest.mark.unit
@pytest.mark.file_provider
async def test_returns_casbin_enforcer(model_path: Path, policy_path: Path) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    enforcer = await provider()
    assert isinstance(enforcer, casbin.Enforcer)


@pytest.mark.unit
@pytest.mark.file_provider
async def test_returns_same_instance_on_second_call(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    e1 = await provider()
    e2 = await provider()
    assert e1 is e2


@pytest.mark.unit
@pytest.mark.file_provider
async def test_mark_dirty_triggers_reload_on_next_call(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    e1 = await provider()
    provider._mark_dirty()
    e2 = await provider()
    assert e1 is not e2


@pytest.mark.unit
@pytest.mark.file_provider
async def test_build_enforcer_called_once_without_dirty(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    with patch.object(provider, "_build_enforcer", wraps=provider._build_enforcer) as mock:
        await provider()
        await provider()
        await provider()
    mock.assert_called_once()


@pytest.mark.unit
@pytest.mark.file_provider
async def test_build_enforcer_called_again_after_dirty(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    with patch.object(provider, "_build_enforcer", wraps=provider._build_enforcer) as mock:
        await provider()
        provider._mark_dirty()
        await provider()
    assert mock.call_count == 2


@pytest.mark.unit
@pytest.mark.file_provider
async def test_enforcer_loaded_eagerly_on_aenter(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    with patch.object(provider, "_build_enforcer", wraps=provider._build_enforcer) as mock:
        async with provider:
            pass
    mock.assert_called_once()


@pytest.mark.unit
@pytest.mark.file_provider
async def test_observer_stopped_on_aexit(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    async with provider:
        assert provider._observer is not None

    assert provider._observer is None


@pytest.mark.unit
@pytest.mark.file_provider
async def test_enforces_loaded_policy(model_path: Path, policy_path: Path) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    enforcer = await provider()
    assert enforcer.enforce("alice", "data", "read") is True
    assert enforcer.enforce("alice", "data", "write") is False
    assert enforcer.enforce("bob", "data", "read") is False


@pytest.mark.unit
@pytest.mark.file_provider
async def test_needs_reload_false_after_first_call(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    assert provider._needs_reload is True
    await provider()
    assert provider._needs_reload is False


@pytest.mark.unit
@pytest.mark.file_provider
async def test_needs_reload_true_after_mark_dirty(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    await provider()
    provider._mark_dirty()
    assert provider._needs_reload is True
