"""Integration tests — make_casdoor_router endpoints (callback + logout)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_casdoor import make_casdoor_router

ACCESS_TOKEN = "header.payload.access"
REFRESH_TOKEN = "header.payload.refresh"


def _make_sdk(tokens: dict | None = None) -> MagicMock:
    sdk = MagicMock()
    sdk.get_oauth_token = AsyncMock(
        return_value=(
            {"access_token": ACCESS_TOKEN, "refresh_token": REFRESH_TOKEN}
            if tokens is None
            else tokens
        )
    )
    return sdk


def _make_app(sdk: MagicMock, **router_kwargs) -> FastAPI:  # type: ignore[return]
    app = FastAPI()
    router = make_casdoor_router(sdk, **router_kwargs)
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# GET /callback — happy path
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_callback_redirects_after_successful_token_exchange() -> None:
    app = _make_app(_make_sdk(), redirect_after_login="/dashboard")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 302
    assert resp.headers["location"] == "/dashboard"


@pytest.mark.integration
async def test_callback_sets_access_token_cookie() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    cookie_header = resp.headers.get("set-cookie", "")
    assert "access_token" in cookie_header


@pytest.mark.integration
async def test_callback_sets_refresh_token_cookie() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    # RedirectResponse may set multiple Set-Cookie headers; check raw headers
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("refresh_token" in h for h in set_cookies)


@pytest.mark.integration
async def test_callback_accepts_state_param_without_error() -> None:
    """state is accepted but not validated — must not cause 422."""
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": "some-nonce"}
        )
    assert resp.status_code == 302


@pytest.mark.integration
async def test_callback_custom_cookie_names() -> None:
    sdk = _make_sdk()
    app = _make_app(
        sdk,
        access_token_cookie="my_access",
        refresh_token_cookie="my_refresh",
        cookie_secure=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("my_access" in h for h in set_cookies)
    assert any("my_refresh" in h for h in set_cookies)


# ---------------------------------------------------------------------------
# GET /callback — error cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_callback_returns_401_when_access_token_missing() -> None:
    sdk = _make_sdk(tokens={"refresh_token": REFRESH_TOKEN})
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_callback_returns_401_when_refresh_token_missing() -> None:
    sdk = _make_sdk(tokens={"access_token": ACCESS_TOKEN})
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_callback_returns_401_when_tokens_dict_empty() -> None:
    sdk = _make_sdk(tokens={})
    app = _make_app(sdk)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_logout_returns_200() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/logout")
    assert resp.status_code == 200


@pytest.mark.integration
async def test_logout_sends_delete_cookie_for_access_token() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/logout")
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("access_token" in h for h in set_cookies)


@pytest.mark.integration
async def test_logout_sends_delete_cookie_for_refresh_token() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/logout")
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("refresh_token" in h for h in set_cookies)


@pytest.mark.integration
async def test_logout_with_custom_cookie_names() -> None:
    sdk = _make_sdk()
    app = _make_app(
        sdk,
        access_token_cookie="my_access",
        refresh_token_cookie="my_refresh",
        cookie_secure=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/logout")
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("my_access" in h for h in set_cookies)
    assert any("my_refresh" in h for h in set_cookies)


# ---------------------------------------------------------------------------
# Router prefix
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_router_prefix_applied() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, prefix="/auth", cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/auth/callback", params={"code": "auth-code"})
    assert resp.status_code == 302


@pytest.mark.integration
async def test_callback_without_prefix_returns_404_when_prefix_set() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, prefix="/auth", cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 404
