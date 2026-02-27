from __future__ import annotations

from inspect import Parameter, Signature
from typing import TYPE_CHECKING, Any

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyCookie

if TYPE_CHECKING:
    from collections.abc import Callable

    from casdoor import AsyncCasdoorSDK


def _default_unauthorized_error() -> Exception:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def _default_invalid_token_error(reason: str) -> Exception:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid token: {reason}",
    )


class CasdoorUserProvider:
    """
    Casdoor user provider for FastAPI.

    Validates ``access_token`` and ``refresh_token`` cookies via the Casdoor
    SDK and returns the raw ``access_token`` string as the user identity for
    downstream permission enforcement.

    Usage::

        sdk = AsyncCasdoorSDK(...)
        user_provider = CasdoorUserProvider(sdk=sdk)
        guard = PermissionGuard(user_provider=user_provider, ...)
    """

    def __init__(
        self,
        *,
        sdk: AsyncCasdoorSDK,
        access_token_cookie: str = "access_token",
        refresh_token_cookie: str = "refresh_token",
        unauthorized_error: Callable[
            [], Exception
        ] = _default_unauthorized_error,
        invalid_token_error: Callable[
            [str], Exception
        ] = _default_invalid_token_error,
    ) -> None:
        self._sdk = sdk
        self._unauthorized_error = unauthorized_error
        self._invalid_token_error = invalid_token_error

        self._access_cookie_scheme = APIKeyCookie(
            name=access_token_cookie, auto_error=False
        )
        self._refresh_cookie_scheme = APIKeyCookie(
            name=refresh_token_cookie, auto_error=False
        )

        # Set __signature__ on the instance so FastAPI
        # can discover Security dependencies (same pattern as JWTUserProvider)
        self.__signature__ = Signature(
            parameters=[
                Parameter(
                    "access_token",
                    kind=Parameter.KEYWORD_ONLY,
                    default=Security(self._access_cookie_scheme),
                    annotation=str | None,
                ),
                Parameter(
                    "refresh_token",
                    kind=Parameter.KEYWORD_ONLY,
                    default=Security(self._refresh_cookie_scheme),
                    annotation=str | None,
                ),
            ],
        )

    async def __call__(
        self,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> Any:
        """FastAPI dependency. Validates Casdoor JWT cookies."""
        if access_token is None or refresh_token is None:
            raise self._unauthorized_error()
        try:
            self._sdk.parse_jwt_token(access_token)
            self._sdk.parse_jwt_token(refresh_token)
        except (ValueError, jwt.PyJWTError) as e:
            raise self._invalid_token_error(str(e)) from e
        return access_token
