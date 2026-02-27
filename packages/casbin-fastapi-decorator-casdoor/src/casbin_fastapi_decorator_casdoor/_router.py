from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response
from starlette.status import HTTP_302_FOUND, HTTP_401_UNAUTHORIZED

if TYPE_CHECKING:
    from casdoor import AsyncCasdoorSDK


def make_casdoor_router(  # noqa: PLR0913
    sdk: AsyncCasdoorSDK,
    *,
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

    - ``GET {prefix}/callback`` — Exchange OAuth2 code for tokens, set cookies.
    - ``POST {prefix}/logout`` — Clear authentication cookies.

    Args:
        sdk: Configured :class:`AsyncCasdoorSDK` instance.
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

    _cookie_kwargs = {
        "secure": cookie_secure,
        "httponly": cookie_httponly,
        "samesite": cookie_samesite,
        "domain": cookie_domain,
        "path": cookie_path,
    }

    @router.get("/callback")
    async def callback(code: str, _state: str = "") -> RedirectResponse:
        tokens = await sdk.get_oauth_token(code=code)
        if not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)

        response = RedirectResponse(
            url=redirect_after_login,
            status_code=HTTP_302_FOUND,
        )
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
    async def logout(response: Response) -> Response:
        for key in (access_token_cookie, refresh_token_cookie):
            response.delete_cookie(key=key, **_cookie_kwargs)
        return response

    return router
