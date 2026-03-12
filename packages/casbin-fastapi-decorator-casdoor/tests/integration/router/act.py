"""Integration tests — make_casdoor_router endpoints."""
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
    sdk.get_auth_link = AsyncMock(
        return_value=(
            "http://casdoor.example/login/oauth/authorize"
            "?client_id=test&response_type=code"
        )
    )
    sdk.get_oauth_token = AsyncMock(
        return_value=(
            {"access_token": ACCESS_TOKEN, "refresh_token": REFRESH_TOKEN}
            if tokens is None
            else tokens
        )
    )
    return sdk


def _make_app(
    sdk: MagicMock, **router_kwargs
) -> FastAPI:  # type: ignore[return]
    app = FastAPI()
    router = make_casdoor_router(sdk, **router_kwargs)
    app.include_router(router)
    return app


async def _start_login(client: AsyncClient) -> tuple[str, str]:
    login_resp = await client.get("/login", follow_redirects=False)
    state_cookie = client.cookies.get("casdoor_oauth_state")
    assert state_cookie is not None
    assert login_resp.status_code == 302
    assert "state=" in login_resp.headers["location"]
    return state_cookie, login_resp.headers["location"]


@pytest.mark.integration
async def test_login_sets_state_cookie_and_redirects_to_casdoor() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        state_cookie, location = await _start_login(client)
    assert state_cookie
    assert location.startswith("http://casdoor.example/login/oauth/authorize")


@pytest.mark.integration
async def test_callback_redirects_after_successful_token_exchange() -> None:
    app = _make_app(
        _make_sdk(),
        redirect_after_login="/dashboard",
        cookie_secure=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
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
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
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
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("refresh_token" in h for h in set_cookies)


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
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("my_access" in h for h in set_cookies)
    assert any("my_refresh" in h for h in set_cookies)


@pytest.mark.integration
async def test_callback_returns_422_when_state_missing() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = await client.get("/callback", params={"code": "auth-code"})
    assert resp.status_code == 422


@pytest.mark.integration
async def test_callback_returns_400_when_state_is_invalid() -> None:
    app = _make_app(_make_sdk(), cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": "invalid-state"}
        )
    assert resp.status_code == 400


@pytest.mark.integration
async def test_callback_returns_401_when_access_token_missing() -> None:
    sdk = _make_sdk(tokens={"refresh_token": REFRESH_TOKEN})
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
    assert resp.status_code == 401


@pytest.mark.integration
async def test_callback_returns_401_when_refresh_token_missing() -> None:
    sdk = _make_sdk(tokens={"access_token": ACCESS_TOKEN})
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
    assert resp.status_code == 401


@pytest.mark.integration
async def test_callback_returns_401_when_tokens_dict_empty() -> None:
    sdk = _make_sdk(tokens={})
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        state_cookie, _ = await _start_login(client)
        resp = await client.get(
            "/callback", params={"code": "auth-code", "state": state_cookie}
        )
    assert resp.status_code == 401


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


@pytest.mark.integration
async def test_router_prefix_applied() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, prefix="/auth", cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        login_resp = await client.get("/auth/login")
        state_cookie = client.cookies.get("casdoor_oauth_state")
        assert state_cookie is not None
        resp = await client.get(
            "/auth/callback",
            params={"code": "auth-code", "state": state_cookie},
            follow_redirects=False,
        )
    assert login_resp.status_code == 302
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
