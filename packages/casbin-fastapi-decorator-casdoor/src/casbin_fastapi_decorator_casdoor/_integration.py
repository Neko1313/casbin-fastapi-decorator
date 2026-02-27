from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from casdoor import AsyncCasdoorSDK
from fastapi import APIRouter, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from casbin_fastapi_decorator_casdoor._enforcer import (
    CasdoorEnforcerProvider,
    CasdoorEnforceTarget,
)
from casbin_fastapi_decorator_casdoor._provider import CasdoorUserProvider
from casbin_fastapi_decorator_casdoor._router import make_casdoor_router

if TYPE_CHECKING:
    from collections.abc import Callable

    from casbin_fastapi_decorator import PermissionGuard


def _default_forbidden_error(_user: Any, *_rvals: Any) -> Exception:
    return HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Forbidden")


class CasdoorIntegration:
    """
    Facade combining Casdoor OAuth2 authentication and Casbin authorization.

    Wires together the Casdoor SDK, user provider, enforcer provider, and
    OAuth2 router for use with
    :class:`casbin_fastapi_decorator.PermissionGuard`.

    Usage::

        casdoor = CasdoorIntegration(
            endpoint="http://localhost:8000",
            client_id="...",
            client_secret="...",
            certificate=cert,
            org_name="my_org",
            application_name="my_app",
            target=CasdoorEnforceTarget(
                enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer"
            ),
        )

        app.include_router(casdoor.router)
        guard = casdoor.create_guard()

        @app.get("/protected")
        @guard.require_permission("resource", "read")
        async def protected():
            ...

    For advanced customisation (custom ``user_factory``, different enforce
    target per route, etc.) compose the components manually::

        sdk = AsyncCasdoorSDK(...)
        target = CasdoorEnforceTarget(permission_id="my_org/can_read")
        user_provider = CasdoorUserProvider(sdk=sdk)
        enforcer_provider = CasdoorEnforcerProvider(
            sdk=sdk, target=target,
        )
        router = make_casdoor_router(sdk=sdk, ...)
        guard = PermissionGuard(
            user_provider=user_provider,
            enforcer_provider=enforcer_provider,
            error_factory=lambda user, *rv: HTTPException(403),
        )
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        endpoint: str,
        client_id: str,
        client_secret: str,
        certificate: str,
        org_name: str,
        application_name: str,
        target: CasdoorEnforceTarget,
        access_token_cookie: str = "access_token",
        refresh_token_cookie: str = "refresh_token",
        redirect_after_login: str = "/",
        cookie_secure: bool = True,
        cookie_httponly: bool = True,
        cookie_samesite: Literal["lax", "strict", "none"] = "lax",
        cookie_domain: str | None = None,
        cookie_path: str = "/",
        cookie_max_age: int | None = None,
        router_prefix: str = "",
    ) -> None:
        self._sdk = AsyncCasdoorSDK(
            endpoint=endpoint,
            client_id=client_id,
            client_secret=client_secret,
            certificate=certificate,
            org_name=org_name,
            application_name=application_name,
        )
        self._user_provider = CasdoorUserProvider(
            sdk=self._sdk,
            access_token_cookie=access_token_cookie,
            refresh_token_cookie=refresh_token_cookie,
        )
        self._enforcer_provider = CasdoorEnforcerProvider(
            sdk=self._sdk,
            target=target,
        )
        self._router = make_casdoor_router(
            self._sdk,
            access_token_cookie=access_token_cookie,
            refresh_token_cookie=refresh_token_cookie,
            redirect_after_login=redirect_after_login,
            cookie_secure=cookie_secure,
            cookie_httponly=cookie_httponly,
            cookie_samesite=cookie_samesite,
            cookie_domain=cookie_domain,
            cookie_path=cookie_path,
            cookie_max_age=cookie_max_age,
            prefix=router_prefix,
        )

    @property
    def sdk(self) -> AsyncCasdoorSDK:
        """Underlying :class:`AsyncCasdoorSDK` instance."""
        return self._sdk

    @property
    def user_provider(self) -> CasdoorUserProvider:
        """FastAPI dependency: validates cookies, returns the access token."""
        return self._user_provider

    @property
    def enforcer_provider(self) -> CasdoorEnforcerProvider:
        """FastAPI dependency: returns a :class:`CasdoorEnforcer`."""
        return self._enforcer_provider

    @property
    def router(self) -> APIRouter:
        """
        :class:`APIRouter` with ``GET /callback`` and ``POST /logout``.

        Include it in your FastAPI app::

            app.include_router(casdoor.router)
        """
        return self._router

    def create_guard(
        self,
        error_factory: Callable[..., Exception] | None = None,
    ) -> PermissionGuard:
        """
        Create a :class:`PermissionGuard` pre-configured with this integration.

        Args:
            error_factory: Called with ``(user, *rvals)`` when access
                is denied. Defaults to ``HTTPException(403, "Forbidden")``.

        """
        from casbin_fastapi_decorator import PermissionGuard  # noqa: PLC0415

        return PermissionGuard(
            user_provider=self._user_provider,
            enforcer_provider=self._enforcer_provider,
            error_factory=error_factory or _default_forbidden_error,
        )
