"""Integration tests — make_casdoor_router endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator_casdoor import make_casdoor_router

ACCESS_TOKEN = "header.payload.access"
REFRESH_TOKEN = "header.payload.refresh"


class _FakeUrlopenResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _patch_sso_logout(monkeypatch, body: bytes | None = None):
    calls = []

    def urlopen(request, timeout):
        calls.append(
            {
                "url": request.full_url,
                "authorization": request.get_header("Authorization"),
                "accept": request.get_header("Accept"),
                "timeout": timeout,
            }
        )
        return _FakeUrlopenResponse(
            body or b'{"status":"ok","msg":"","data":""}'
        )

    monkeypatch.setattr(
        "casbin_fastapi_decorator_casdoor._router.urlrequest.urlopen",
        urlopen,
    )
    return calls


def _make_sdk(tokens: dict | None = None) -> MagicMock:
    sdk = MagicMock()
    sdk.endpoint = "http://casdoor.example"
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
    sdk.parse_jwt_token = MagicMock(
        return_value={"owner": "org", "name": "user1"}
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


@pytest.mark.integration
async def test_logout_calls_casdoor_sso_logout(monkeypatch) -> None:
    sdk = _make_sdk()
    calls = _patch_sso_logout(monkeypatch)
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("access_token", ACCESS_TOKEN)
        resp = await client.post("/logout")
    assert resp.status_code == 200
    assert calls == [
        {
            "url": "http://casdoor.example/api/sso-logout?logoutAll=true",
            "authorization": f"Bearer {ACCESS_TOKEN}",
            "accept": "application/json",
            "timeout": 10,
        }
    ]


@pytest.mark.integration
async def test_logout_without_access_token_does_not_call_casdoor(
    monkeypatch,
) -> None:
    sdk = _make_sdk()

    def urlopen(*args, **kwargs):
        msg = "Casdoor SSO logout should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "casbin_fastapi_decorator_casdoor._router.urlrequest.urlopen",
        urlopen,
    )
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/logout")
    assert resp.status_code == 200


@pytest.mark.integration
async def test_logout_clears_cookies_when_casdoor_sso_logout_fails(
    monkeypatch,
) -> None:
    sdk = _make_sdk()
    _patch_sso_logout(monkeypatch, b'{"status":"error","msg":"token expired"}')
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("access_token", ACCESS_TOKEN)
        client.cookies.set("refresh_token", REFRESH_TOKEN)
        resp = await client.post("/logout")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "token expired"}
    all_headers = resp.headers.multi_items()
    set_cookies = [v for k, v in all_headers if k.lower() == "set-cookie"]
    assert any("access_token" in h for h in set_cookies)
    assert any("refresh_token" in h for h in set_cookies)


@pytest.mark.integration
async def test_me_returns_user_profile() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("access_token", ACCESS_TOKEN)
        resp = await client.get("/me")
    assert resp.status_code == 200
    assert resp.json() == {"owner": "org", "name": "user1"}


@pytest.mark.integration
async def test_me_returns_401_when_no_access_token() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_me_returns_401_on_invalid_token() -> None:
    sdk = _make_sdk()
    sdk.parse_jwt_token.side_effect = pyjwt.PyJWTError("Invalid signature")
    app = _make_app(sdk, cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("access_token", "invalid.token.here")
        resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_me_with_custom_cookie_name() -> None:
    sdk = _make_sdk()
    app = _make_app(
        sdk,
        access_token_cookie="my_access",
        cookie_secure=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("my_access", ACCESS_TOKEN)
        resp = await client.get("/me")
    assert resp.status_code == 200
    assert resp.json() == {"owner": "org", "name": "user1"}


@pytest.mark.integration
async def test_me_with_prefix() -> None:
    sdk = _make_sdk()
    app = _make_app(sdk, prefix="/auth", cookie_secure=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("access_token", ACCESS_TOKEN)
        resp = await client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"owner": "org", "name": "user1"}
