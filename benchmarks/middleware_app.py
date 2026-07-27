"""
Shared application builder for the two middleware-based libraries.

``fastapi-authz`` and ``fastapi-casbin-auth`` ship byte-identical
middleware, so they get the exact same app — only the imported class and
the pinned dependency set differ.  Both require an authentication
middleware in front of them to populate ``scope["user"]``.

This module is imported from the benchmark script's directory and is
only loaded inside those two environments, so importing starlette here
is safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import casbin
from fastapi import FastAPI
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    SimpleUser,
)
from starlette.middleware.authentication import AuthenticationMiddleware

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection


class BearerRoleBackend(AuthenticationBackend):
    """Map ``Authorization: Bearer <role>`` onto a Starlette user."""

    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, SimpleUser] | None:
        """Return credentials for the bearer role, or ``None``."""
        header = conn.headers.get("Authorization")
        if not header:
            return None
        role = header.removeprefix("Bearer ").strip()
        return AuthCredentials(["authenticated"]), SimpleUser(role)


def build_middleware_app(
    middleware_cls: type,
    model_path: str,
    policy_path: str,
) -> Any:
    """
    Build the benchmark app guarded by *middleware_cls*.

    Note that ``/health`` needs an explicit ``anonymous`` policy rule and
    still pays a full ``enforce()`` call — with middleware there is no
    such thing as an unguarded route.
    """
    enforcer = casbin.Enforcer(model_path, policy_path)

    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Needs a policy rule like any other route: middleware cannot ask
    # "is the caller authenticated" without also enforcing.
    @app.get("/api/profile")
    async def profile() -> dict[str, str]:
        return {"profile": "ok"}

    @app.get("/api/items")
    async def items() -> dict[str, str]:
        return {"items": "ok"}

    @app.get("/api/admin")
    async def admin() -> dict[str, str]:
        return {"admin": "ok"}

    # Added last => outermost, so the user is resolved before enforcing.
    app.add_middleware(middleware_cls, enforcer=enforcer)
    app.add_middleware(AuthenticationMiddleware, backend=BearerRoleBackend())

    return app
