from __future__ import annotations

from inspect import Parameter, Signature
from typing import TYPE_CHECKING, Any

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import (
    APIKeyCookie,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel


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


class JWTUserProvider:
    """
    JWT user provider for FastAPI.

    Supports Cookie + Header (Bearer) token extraction.
    Configurable via constructor parameters.

    Usage::

        user_provider = JWTUserProvider(
            secret_key="secret",
            cookie_name="access_token",
        )
        guard = PermissionGuard(
            user_provider=user_provider, ...,
        )
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        secret_key: str,
        algorithm: str = "HS256",
        cookie_name: str | None = None,
        user_model: type[BaseModel] | None = None,
        unauthorized_error: Callable[
            [], Exception
        ] = _default_unauthorized_error,
        invalid_token_error: Callable[
            [str], Exception
        ] = _default_invalid_token_error,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._user_model = user_model
        self._unauthorized_error = unauthorized_error
        self._invalid_token_error = invalid_token_error

        self._cookie_scheme = (
            APIKeyCookie(name=cookie_name, auto_error=False)
            if cookie_name
            else None
        )
        self._bearer_scheme = HTTPBearer(auto_error=False)

        # Set __signature__ on the instance so FastAPI
        # can discover Security dependencies
        params: list[Parameter] = []
        if self._cookie_scheme:
            params.append(
                Parameter(
                    "cookie_token",
                    kind=Parameter.KEYWORD_ONLY,
                    default=Security(self._cookie_scheme),
                    annotation=str | None,
                ),
            )
        params.append(
            Parameter(
                "header_auth",
                kind=Parameter.KEYWORD_ONLY,
                default=Security(self._bearer_scheme),
                annotation=HTTPAuthorizationCredentials | None,
            ),
        )
        self.__signature__ = Signature(parameters=params)

    async def __call__(
        self,
        *,
        cookie_token: str | None = None,
        header_auth: HTTPAuthorizationCredentials | None = None,
    ) -> Any:
        """FastAPI dependency. Extracts and validates JWT token."""
        token = cookie_token or (
            header_auth.credentials if header_auth else None
        )
        if not token:
            raise self._unauthorized_error()

        try:
            payload = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm],
            )
        except jwt.InvalidTokenError as e:
            raise self._invalid_token_error(str(e)) from e

        if self._user_model:
            return self._user_model.model_validate(payload)
        return payload
