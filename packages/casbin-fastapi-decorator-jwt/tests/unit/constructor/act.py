"""Unit tests for JWTUserProvider constructor (no HTTP, no token decoding)."""
from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from casbin_fastapi_decorator_jwt import JWTUserProvider

SECRET = "at-least-32-bytes-long-secret-key!"


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_secret_key_stored() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert provider._secret_key == SECRET


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_algorithm_defaults_to_hs256() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert provider._algorithm == "HS256"


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_algorithm_stored_when_overridden() -> None:
    provider = JWTUserProvider(secret_key=SECRET, algorithm="HS512")
    assert provider._algorithm == "HS512"


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_user_model_defaults_to_none() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert provider._user_model is None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_user_model_stored_when_provided() -> None:
    class User(BaseModel):
        sub: str

    provider = JWTUserProvider(secret_key=SECRET, user_model=User)
    assert provider._user_model is User


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_custom_unauthorized_error_stored() -> None:
    def my_error() -> Exception:
        return HTTPException(status_code=403)

    provider = JWTUserProvider(secret_key=SECRET, unauthorized_error=my_error)
    assert provider._unauthorized_error is my_error


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_custom_invalid_token_error_stored() -> None:
    def my_error(reason: str) -> Exception:
        return HTTPException(status_code=400, detail=reason)

    provider = JWTUserProvider(secret_key=SECRET, invalid_token_error=my_error)
    assert provider._invalid_token_error is my_error


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_cookie_scheme_none_without_cookie_name() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert provider._cookie_scheme is None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_cookie_scheme_set_with_cookie_name() -> None:
    provider = JWTUserProvider(secret_key=SECRET, cookie_name="access_token")
    assert provider._cookie_scheme is not None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_bearer_scheme_always_created() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert provider._bearer_scheme is not None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_provider_is_callable() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    assert callable(provider)


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_signature_without_cookie_has_only_header_auth() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    sig = inspect.signature(provider)
    assert list(sig.parameters) == ["header_auth"]


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_signature_with_cookie_has_cookie_first_then_header() -> None:
    provider = JWTUserProvider(secret_key=SECRET, cookie_name="access_token")
    sig = inspect.signature(provider)
    assert list(sig.parameters) == ["cookie_token", "header_auth"]


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_signature_cookie_param_annotation_is_optional_str() -> None:
    provider = JWTUserProvider(secret_key=SECRET, cookie_name="access_token")
    param = inspect.signature(provider).parameters["cookie_token"]
    assert param.annotation == str | None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_signature_header_auth_annotation_is_optional_credentials() -> None:
    provider = JWTUserProvider(secret_key=SECRET)
    param = inspect.signature(provider).parameters["header_auth"]
    assert param.annotation == HTTPAuthorizationCredentials | None


@pytest.mark.unit
@pytest.mark.jwt_provider
def test_different_cookie_names_create_independent_schemes() -> None:
    p1 = JWTUserProvider(secret_key=SECRET, cookie_name="token_a")
    p2 = JWTUserProvider(secret_key=SECRET, cookie_name="token_b")
    assert p1._cookie_scheme is not p2._cookie_scheme
