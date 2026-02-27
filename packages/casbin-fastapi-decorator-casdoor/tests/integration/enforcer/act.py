"""Integration tests — CasdoorEnforcer and CasdoorEnforcerProvider happy paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from casbin_fastapi_decorator_casdoor import (
    CasdoorEnforcer,
    CasdoorEnforcerProvider,
    CasdoorEnforceTarget,
)

ACCESS_TOKEN = "header.payload.signature"
PARSED_USER = {"owner": "my_org", "name": "alice"}


def _make_sdk(enforce_result: bool = True) -> MagicMock:
    sdk = MagicMock()
    sdk.parse_jwt_token.return_value = PARSED_USER
    sdk.enforce = AsyncMock(return_value=enforce_result)
    return sdk


def _static_target(enforcer_name: str = "enforcer_0") -> CasdoorEnforceTarget:
    return CasdoorEnforceTarget(enforce_id=f"my_org/{enforcer_name}")


def _dynamic_target(enforcer_name: str = "enforcer_0") -> CasdoorEnforceTarget:
    return CasdoorEnforceTarget(
        enforce_id=lambda parsed: f"{parsed['owner']}/{enforcer_name}",
    )


# ---------------------------------------------------------------------------
# CasdoorEnforcer — basic behaviour
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_enforcer_calls_sdk_enforce() -> None:
    sdk = _make_sdk(enforce_result=True)
    enforcer = CasdoorEnforcer(sdk=sdk, target=_static_target())

    result = await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    assert result is True
    sdk.enforce.assert_called_once()


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_enforcer_returns_false_when_denied() -> None:
    sdk = _make_sdk(enforce_result=False)
    enforcer = CasdoorEnforcer(sdk=sdk, target=_static_target())

    result = await enforcer.enforce(ACCESS_TOKEN, "resource", "read")
    assert result is False


# ---------------------------------------------------------------------------
# Static target
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_static_target_builds_correct_user_path() -> None:
    sdk = _make_sdk()
    enforcer = CasdoorEnforcer(sdk=sdk, target=_static_target())
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["casbin_request"][0] == "my_org/alice"


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_static_target_passes_enforce_id() -> None:
    sdk = _make_sdk()
    enforcer = CasdoorEnforcer(sdk=sdk, target=_static_target("my_enforcer"))
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["enforce_id"] == "my_org/my_enforcer"


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_static_target_passes_rvals() -> None:
    sdk = _make_sdk()
    enforcer = CasdoorEnforcer(sdk=sdk, target=_static_target())
    await enforcer.enforce(ACCESS_TOKEN, "resource", "write")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["casbin_request"] == ["my_org/alice", "resource", "write"]


# ---------------------------------------------------------------------------
# Dynamic target (callable enforce_id)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_dynamic_target_resolves_enforce_id_from_jwt() -> None:
    sdk = _make_sdk()
    enforcer = CasdoorEnforcer(sdk=sdk, target=_dynamic_target("my_enforcer"))
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["enforce_id"] == "my_org/my_enforcer"


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_dynamic_target_uses_owner_from_parsed_jwt() -> None:
    sdk = MagicMock()
    sdk.parse_jwt_token.return_value = {"owner": "other_org", "name": "bob"}
    sdk.enforce = AsyncMock(return_value=True)

    enforcer = CasdoorEnforcer(sdk=sdk, target=_dynamic_target("enforcer_0"))
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["enforce_id"] == "other_org/enforcer_0"
    assert call_kwargs["casbin_request"][0] == "other_org/bob"


# ---------------------------------------------------------------------------
# Permission target
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_permission_target_passes_permission_id() -> None:
    sdk = _make_sdk()
    target = CasdoorEnforceTarget(permission_id="my_org/can_read")
    enforcer = CasdoorEnforcer(sdk=sdk, target=target)
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["permission_id"] == "my_org/can_read"
    assert call_kwargs["enforce_id"] == ""


# ---------------------------------------------------------------------------
# Custom user_factory
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_custom_user_factory_is_used() -> None:
    sdk = _make_sdk()
    enforcer = CasdoorEnforcer(
        sdk=sdk,
        target=_static_target(),
        user_factory=lambda parsed: parsed["name"],
    )
    await enforcer.enforce(ACCESS_TOKEN, "resource", "read")

    call_kwargs = sdk.enforce.call_args.kwargs
    assert call_kwargs["casbin_request"][0] == "alice"


# ---------------------------------------------------------------------------
# CasdoorEnforcerProvider
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_enforcer_provider_returns_enforcer() -> None:
    sdk = _make_sdk()
    provider = CasdoorEnforcerProvider(sdk=sdk, target=_static_target())
    enforcer = await provider()
    assert isinstance(enforcer, CasdoorEnforcer)


@pytest.mark.integration
@pytest.mark.casdoor_enforcer
async def test_enforcer_provider_returns_same_instance() -> None:
    """Enforcer is shared — no per-request construction cost."""
    sdk = _make_sdk()
    provider = CasdoorEnforcerProvider(sdk=sdk, target=_static_target())
    e1 = await provider()
    e2 = await provider()
    assert e1 is e2
