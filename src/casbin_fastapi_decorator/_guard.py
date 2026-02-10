from __future__ import annotations

from typing import TYPE_CHECKING, Any

from casbin_fastapi_decorator._builder import (
    build_auth_decorator,
    build_permission_decorator,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from casbin_fastapi_decorator._types import AccessSubject


class PermissionGuard:
    """
    Factory for authorization decorators.

    Args:
        user_provider: FastAPI dependency returning
            the current user.
        enforcer_provider: FastAPI dependency returning
            a casbin Enforcer (``.enforce()``).
        error_factory: Callable that creates an exception
            on access denial. Receives ``(user, *rvals)``.

    """

    def __init__(
        self,
        *,
        user_provider: Callable[..., Any],
        enforcer_provider: Callable[..., Any],
        error_factory: Callable[..., Exception],
    ) -> None:
        self._user_provider = user_provider
        self._enforcer_provider = enforcer_provider
        self._error_factory = error_factory

    def auth_required(self) -> Callable:
        """Return an authentication-only decorator."""
        return build_auth_decorator(self._user_provider)

    def require_permission(self, *args: AccessSubject | Any) -> Callable:
        """
        Return a permission-check decorator.

        Positional arguments are passed to
        ``enforcer.enforce(user, *resolved_values)``
        in the same order. ``AccessSubject`` values are
        resolved via FastAPI DI and transformed with
        their selector. Other values are passed as-is.
        """
        return build_permission_decorator(
            user_provider=self._user_provider,
            enforcer_provider=self._enforcer_provider,
            error_factory=self._error_factory,
            args=args,
        )
