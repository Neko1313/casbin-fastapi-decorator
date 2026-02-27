"""Unit tests for CasdoorIntegration facade."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from casbin_fastapi_decorator import PermissionGuard
from fastapi import APIRouter, HTTPException

from casbin_fastapi_decorator_casdoor import (
    CasdoorEnforcerProvider,
    CasdoorEnforceTarget,
    CasdoorIntegration,
    CasdoorUserProvider,
)

_CERT = """\
-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQDU+pQ4pHgSpDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjAwMTAxMDAwMDAwWhcNMjEwMTAxMDAwMDAwWjAUMRIwEAYD
VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC7
o4qne60TB3wolKGWBUjQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
-----END CERTIFICATE-----
"""

_TARGET = CasdoorEnforceTarget(enforce_id="my_org/my_enforcer")


def _make_integration(**overrides) -> CasdoorIntegration:  # type: ignore[return]
    defaults = {
        "endpoint": "http://localhost:8000",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "certificate": _CERT,
        "org_name": "test-org",
        "application_name": "test-app",
        "target": _TARGET,
    }
    defaults.update(overrides)
    with patch("casbin_fastapi_decorator_casdoor._integration.AsyncCasdoorSDK"):
        return CasdoorIntegration(**defaults)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sdk_property_returns_sdk_instance() -> None:
    integration = _make_integration()
    assert integration.sdk is not None


@pytest.mark.unit
def test_user_provider_property_returns_user_provider() -> None:
    integration = _make_integration()
    assert isinstance(integration.user_provider, CasdoorUserProvider)


@pytest.mark.unit
def test_enforcer_provider_property_returns_enforcer_provider() -> None:
    integration = _make_integration()
    assert isinstance(integration.enforcer_provider, CasdoorEnforcerProvider)


@pytest.mark.unit
def test_router_property_returns_api_router() -> None:
    integration = _make_integration()
    assert isinstance(integration.router, APIRouter)


@pytest.mark.unit
def test_router_has_callback_and_logout_routes() -> None:
    integration = _make_integration()
    paths = {route.path for route in integration.router.routes}  # type: ignore[attr-defined]
    assert "/callback" in paths
    assert "/logout" in paths


# ---------------------------------------------------------------------------
# create_guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_guard_returns_permission_guard() -> None:
    integration = _make_integration()
    guard = integration.create_guard()
    assert isinstance(guard, PermissionGuard)


@pytest.mark.unit
def test_create_guard_with_custom_error_factory() -> None:
    integration = _make_integration()
    guard = integration.create_guard(
        error_factory=lambda _user, *_rv: HTTPException(404)
    )
    assert isinstance(guard, PermissionGuard)


@pytest.mark.unit
def test_create_guard_called_multiple_times_returns_different_instances() -> None:
    integration = _make_integration()
    g1 = integration.create_guard()
    g2 = integration.create_guard()
    assert g1 is not g2


# ---------------------------------------------------------------------------
# Router prefix
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_router_prefix_applied_to_routes() -> None:
    integration = _make_integration(router_prefix="/auth")
    assert integration.router.prefix == "/auth"
    # Route paths may include the prefix depending on FastAPI version;
    # verify both callback and logout routes exist under the prefix.
    paths = {route.path for route in integration.router.routes}  # type: ignore[attr-defined]
    assert any("callback" in p for p in paths)
    assert any("logout" in p for p in paths)
