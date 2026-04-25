from __future__ import annotations

import asyncio
import json
from hmac import compare_digest
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, Literal, Protocol
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import jwt
from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.responses import RedirectResponse, Response
from fastapi.security import APIKeyCookie
from starlette.status import (
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_502_BAD_GATEWAY,
)

if TYPE_CHECKING:
    from casdoor import AsyncCasdoorSDK


class CasdoorStateManager(Protocol):
    """Protocol for OAuth ``state`` issuance and verification."""

    async def issue(self, response: Response) -> str:
        """Issue and persist state for a login attempt."""

    async def verify(
        self,
        request: Request,
        response: Response,
        state: str,
    ) -> bool:
        """Validate the callback ``state`` and clear one-time storage."""


class CookieStateManager:
    """Cookie-backed default implementation for OAuth ``state``."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        cookie_name: str = "casdoor_oauth_state",
        cookie_secure: bool = True,
        cookie_httponly: bool = True,
        cookie_samesite: Literal["lax", "strict", "none"] = "lax",
        cookie_domain: str | None = None,
        cookie_path: str = "/",
        cookie_max_age: int = 300,
    ) -> None:
        self._cookie_name = cookie_name
        self._cookie_kwargs = {
            "secure": cookie_secure,
            "httponly": cookie_httponly,
            "samesite": cookie_samesite,
            "domain": cookie_domain,
            "path": cookie_path,
        }
        self._cookie_max_age = cookie_max_age

    async def issue(self, response: Response) -> str:
        state = token_urlsafe(32)
        response.set_cookie(
            key=self._cookie_name,
            value=state,
            max_age=self._cookie_max_age,
            **self._cookie_kwargs,
        )
        return state

    async def verify(
        self,
        request: Request,
        response: Response,
        state: str,
    ) -> bool:
        expected_state = request.cookies.get(self._cookie_name)
        response.delete_cookie(key=self._cookie_name, **self._cookie_kwargs)
        return bool(expected_state) and compare_digest(expected_state, state)


async def _build_auth_url(
    sdk: AsyncCasdoorSDK,
    *,
    redirect_uri: str,
    state: str,
) -> str:
    auth_url = await sdk.get_auth_link(redirect_uri=redirect_uri)
    parsed = urlparse(auth_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_params["state"] = state
    return urlunparse(parsed._replace(query=urlencode(query_params)))


def _read_casdoor_error(response_body: bytes) -> str:
    try:
        payload = json.loads(response_body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "Casdoor SSO logout request failed"
    if not isinstance(payload, dict):
        return "Casdoor SSO logout request failed"
    msg = payload.get("msg")
    return msg if isinstance(msg, str) and msg else "Casdoor SSO logout failed"


def _request_sso_logout(
    *,
    endpoint: str,
    access_token: str,
    logout_all: bool,
) -> dict[str, Any]:
    logout_url = urljoin(f"{endpoint.rstrip('/')}/", "api/sso-logout")
    query = urlencode({"logoutAll": "true" if logout_all else "false"})
    request = urlrequest.Request(  # noqa: S310
        url=f"{logout_url}?{query}",
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(  # noqa: S310  # nosec B310
            request,
            timeout=10,
        ) as response:
            body = response.read()
    except HTTPError as e:
        return {"status": "error", "msg": _read_casdoor_error(e.read())}
    if not body:
        return {}
    payload = json.loads(body.decode())
    if not isinstance(payload, dict):
        msg = "Casdoor SSO logout returned an invalid response"
        raise ValueError(msg)
    return payload


async def _logout_from_casdoor(
    sdk: AsyncCasdoorSDK,
    access_token: str,
    *,
    logout_all: bool = True,
) -> str | None:
    try:
        payload = await asyncio.to_thread(
            _request_sso_logout,
            endpoint=sdk.endpoint,
            access_token=access_token,
            logout_all=logout_all,
        )
    except (
        TimeoutError,
        URLError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return "Casdoor SSO logout request failed"

    if payload.get("status") == "ok":
        return None

    msg = payload.get("msg")
    return msg if isinstance(msg, str) and msg else "Casdoor SSO logout failed"


def make_casdoor_router(  # noqa: PLR0913
    sdk: AsyncCasdoorSDK,
    *,
    state_manager: CasdoorStateManager | None = None,
    access_token_cookie: str = "access_token",
    refresh_token_cookie: str = "refresh_token",
    redirect_after_login: str = "/",
    cookie_secure: bool = True,
    cookie_httponly: bool = True,
    cookie_samesite: Literal["lax", "strict", "none"] = "lax",
    cookie_domain: str | None = None,
    cookie_path: str = "/",
    cookie_max_age: int | None = None,
    prefix: str = "",
) -> APIRouter:
    """
    Create an :class:`APIRouter` with Casdoor OAuth2 endpoints.

    Routes:

    - ``GET {prefix}/login`` — Start OAuth2 login and redirect to Casdoor.
    - ``GET {prefix}/callback`` — Exchange OAuth2 code for tokens.
    - ``POST {prefix}/logout`` — Trigger Casdoor SSO logout and clear
      cookies.
    - ``GET {prefix}/me`` — Retrieve current user's profile.

    Args:
        sdk: Configured :class:`AsyncCasdoorSDK` instance.
        state_manager: OAuth ``state`` manager. Defaults to
            :class:`CookieStateManager`.
        access_token_cookie: Name of the access-token cookie.
        refresh_token_cookie: Name of the refresh-token cookie.
        redirect_after_login: Path or absolute URL to redirect to after
            successful login. Relative paths (``"/"``) redirect on the same
            host; absolute URLs (``"https://app.example.com/"``) redirect to
            another host. The value is set at configuration time and is not
            user-controlled, so it is not an open-redirect risk.
        cookie_secure: Set the ``Secure`` flag on cookies.
        cookie_httponly: Set the ``HttpOnly`` flag on cookies.
        cookie_samesite: ``SameSite`` policy (``"lax"``, ``"strict"``,
            or ``"none"``).
        cookie_domain: ``Domain`` attribute of the cookie. Use
            ``".example.com"`` (leading dot) to share cookies across
            subdomains, e.g. ``"*.my-site.ru"``.
        cookie_path: ``Path`` attribute of the cookie (default ``"/"``).
        cookie_max_age: ``Max-Age`` in seconds. ``None`` means a session
            cookie (deleted when the browser closes).
        prefix: Optional URL prefix for the router.

    """
    router = APIRouter(prefix=prefix)
    state_manager_impl = state_manager or CookieStateManager(
        cookie_secure=cookie_secure,
        cookie_httponly=cookie_httponly,
        cookie_samesite=cookie_samesite,
        cookie_domain=cookie_domain,
        cookie_path=cookie_path,
    )

    _cookie_kwargs = {
        "secure": cookie_secure,
        "httponly": cookie_httponly,
        "samesite": cookie_samesite,
        "domain": cookie_domain,
        "path": cookie_path,
    }

    _access_cookie_scheme = APIKeyCookie(
        name=access_token_cookie, auto_error=False
    )
    _refresh_cookie_scheme = APIKeyCookie(
        name=refresh_token_cookie, auto_error=False
    )

    @router.get("/login")
    async def login(request: Request) -> RedirectResponse:
        tmp = Response()
        state = await state_manager_impl.issue(tmp)
        auth_url = await _build_auth_url(
            sdk,
            redirect_uri=str(request.url_for("callback")),
            state=state,
        )
        response = RedirectResponse(url=auth_url, status_code=HTTP_302_FOUND)
        response.raw_headers.extend(tmp.raw_headers)
        return response

    @router.get("/callback")
    async def callback(
        request: Request,
        code: str,
        state: str,
    ) -> RedirectResponse:
        response = RedirectResponse(
            url=redirect_after_login,
            status_code=HTTP_302_FOUND,
        )
        is_valid_state = await state_manager_impl.verify(
            request=request,
            response=response,
            state=state,
        )
        if not is_valid_state:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)

        tokens = await sdk.get_oauth_token(code=code)
        if not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)

        for key, value in (
            (access_token_cookie, tokens["access_token"]),
            (refresh_token_cookie, tokens["refresh_token"]),
        ):
            response.set_cookie(
                key=key,
                value=value,
                max_age=cookie_max_age,
                **_cookie_kwargs,
            )
        return response

    @router.post("/logout")
    async def logout(
        response: Response,
        access_token: str | None = Security(_access_cookie_scheme),
    ) -> dict[str, str] | None:
        error_detail = None
        if access_token:
            error_detail = await _logout_from_casdoor(sdk, access_token)
        for key in (access_token_cookie, refresh_token_cookie):
            response.delete_cookie(key=key, **_cookie_kwargs)
        if error_detail is not None:
            response.status_code = HTTP_502_BAD_GATEWAY
            return {"detail": error_detail}
        return None

    @router.get("/me")
    async def me(
        access_token: str | None = Security(_access_cookie_scheme),
    ) -> dict[str, Any]:
        if access_token is None:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
        try:
            return sdk.parse_jwt_token(access_token)
        except (ValueError, jwt.PyJWTError) as e:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            ) from e

    return router
