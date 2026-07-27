# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "casbin-fastapi-decorator",
#   "fastapi==0.140.2",
#   "casbin==1.43.0",
# ]
#
# [tool.uv.sources]
# casbin-fastapi-decorator = { path = "../" }
# ///
"""
``casbin-fastapi-decorator``: per-route decorators via FastAPI DI.

``/health`` carries no decorator, so no user is resolved and no
``enforce()`` call happens on that path at all.  The guarded routes pass
the very same ``(sub, obj, act)`` triple the middleware libraries
compute from the request, so the enforcer does identical work.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Annotated, Any

import casbin
from fastapi import FastAPI, Header, HTTPException
from harness import run_suite

from casbin_fastapi_decorator import PermissionGuard


def _make_user_provider() -> Any:
    async def get_current_user(
        authorization: Annotated[str | None, Header()] = None,
    ) -> str:
        if not authorization:
            return "anonymous"
        return authorization.removeprefix("Bearer ").strip()

    return get_current_user


def build_app(model_path: str, policy_path: str) -> Any:
    """Build a FastAPI app guarded by ``PermissionGuard`` decorators."""
    enforcer = casbin.Enforcer(model_path, policy_path)

    # Must be ``async def``: FastAPI offloads *sync* dependencies to a
    # threadpool, which adds ~100 us per request on its own.  Every
    # enforcer provider shipped with this project is async for exactly
    # this reason.
    async def enforcer_provider() -> casbin.Enforcer:
        return enforcer

    guard = PermissionGuard(
        user_provider=_make_user_provider(),
        enforcer_provider=enforcer_provider,
        error_factory=lambda *_: HTTPException(403, "Forbidden"),
    )

    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Authentication only: the user dependency is resolved, but no
    # enforce() call is made.
    @app.get("/api/profile")
    @guard.auth_required()
    async def profile() -> dict[str, str]:
        return {"profile": "ok"}

    @app.get("/api/items")
    @guard.require_permission("/api/items", "GET")
    async def items() -> dict[str, str]:
        return {"items": "ok"}

    @app.get("/api/admin")
    @guard.require_permission("/api/admin", "GET")
    async def admin() -> dict[str, str]:
        return {"admin": "ok"}

    return app


if __name__ == "__main__":
    run_suite(
        library="casbin-fastapi-decorator",
        version=version("casbin-fastapi-decorator"),
        approach="decorator",
        build_app=build_app,
    )
