from __future__ import annotations

from typing import TYPE_CHECKING

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
    cookie_samesite: str = "lax",
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
        redirect_after_login: URL to redirect to after successful login.
        cookie_secure: Set the ``Secure`` flag on cookies.
        cookie_samesite: ``SameSite`` policy (``"lax"``, ``"strict"``,
            or ``"none"``).
        prefix: Optional URL prefix for the router.

    """
    router = APIRouter(prefix=prefix)

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
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
            )
        return response

    @router.post("/logout")
    async def logout(response: Response) -> Response:
        response.delete_cookie(key=access_token_cookie)
        response.delete_cookie(key=refresh_token_cookie)
        return response

    return router
