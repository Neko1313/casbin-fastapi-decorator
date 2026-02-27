"""Unit tests for CasdoorUserProvider constructor (no HTTP, no token decoding)."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from casbin_fastapi_decorator_casdoor import CasdoorUserProvider


def _make_sdk() -> MagicMock:
    return MagicMock()


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_sdk_stored() -> None:
    sdk = _make_sdk()
    provider = CasdoorUserProvider(sdk=sdk)
    assert provider._sdk is sdk


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_access_cookie_scheme_created() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    assert provider._access_cookie_scheme is not None


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_refresh_cookie_scheme_created() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    assert provider._refresh_cookie_scheme is not None


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_cookie_scheme_names_default() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    assert provider._access_cookie_scheme.model.name == "access_token"
    assert provider._refresh_cookie_scheme.model.name == "refresh_token"


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_cookie_scheme_names_custom() -> None:
    provider = CasdoorUserProvider(
        sdk=_make_sdk(),
        access_token_cookie="my_access",
        refresh_token_cookie="my_refresh",
    )
    assert provider._access_cookie_scheme.model.name == "my_access"
    assert provider._refresh_cookie_scheme.model.name == "my_refresh"


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_custom_unauthorized_error_stored() -> None:
    def my_error() -> Exception:
        return HTTPException(status_code=403)

    provider = CasdoorUserProvider(sdk=_make_sdk(), unauthorized_error=my_error)
    assert provider._unauthorized_error is my_error


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_custom_invalid_token_error_stored() -> None:
    def my_error(reason: str) -> Exception:
        return HTTPException(status_code=400, detail=reason)

    provider = CasdoorUserProvider(sdk=_make_sdk(), invalid_token_error=my_error)
    assert provider._invalid_token_error is my_error


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_provider_is_callable() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    assert callable(provider)


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_signature_has_access_and_refresh_params() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    sig = inspect.signature(provider)
    assert list(sig.parameters) == ["access_token", "refresh_token"]


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_signature_access_token_annotation_is_optional_str() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    param = inspect.signature(provider).parameters["access_token"]
    assert param.annotation == str | None


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_signature_refresh_token_annotation_is_optional_str() -> None:
    provider = CasdoorUserProvider(sdk=_make_sdk())
    param = inspect.signature(provider).parameters["refresh_token"]
    assert param.annotation == str | None


@pytest.mark.unit
@pytest.mark.casdoor_provider
def test_different_cookie_names_create_independent_schemes() -> None:
    p1 = CasdoorUserProvider(sdk=_make_sdk(), access_token_cookie="tok_a")
    p2 = CasdoorUserProvider(sdk=_make_sdk(), access_token_cookie="tok_b")
    assert p1._access_cookie_scheme is not p2._access_cookie_scheme
