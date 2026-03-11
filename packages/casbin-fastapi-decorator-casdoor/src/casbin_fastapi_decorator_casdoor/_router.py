from __future__ import annotations

from secrets import token_urlsafe
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.status import (
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
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

    def __init__(
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
        return bool(expected_state) and expected_state == state


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
    - ``GET {prefix}/callback`` — Exchange OAuth2 code for tokens, set cookies.
    - ``POST {prefix}/logout`` — Clear authentication cookies.

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

    @router.get("/login")
    async def login(request: Request) -> RedirectResponse:
        response = RedirectResponse(url=redirect_after_login)
        state = await state_manager_impl.issue(response)
        auth_url = await _build_auth_url(
            sdk,
            redirect_uri=str(request.url_for("callback")),
            state=state,
        )
        response.headers["location"] = auth_url
        return response

    @router.get("/callback")
    async def callback(
        request: Request,
        code: str,
        state: str | None = None,
    ) -> RedirectResponse:
        if not state:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)

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
            return Response(
                status_code=HTTP_401_UNAUTHORIZED,
                headers=dict(response.headers),
            )

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
    async def logout(response: Response) -> None:
        for key in (access_token_cookie, refresh_token_cookie):
            response.delete_cookie(key=key, **_cookie_kwargs)

    return router
