"""Authorization guard with hot-reload via CachedFileEnforcerProvider."""
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from auth import get_current_user
from fastapi import FastAPI, HTTPException

from casbin_fastapi_decorator import PermissionGuard
from casbin_fastapi_decorator_file import CachedFileEnforcerProvider

if TYPE_CHECKING:
    pass

# Single instance — loaded once, reloaded automatically when files change.
enforcer_provider = CachedFileEnforcerProvider(
    model_path="casbin/model.conf",
    policy_path="casbin/policy.csv",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start the file watcher on startup; stop it on shutdown."""
    async with enforcer_provider:
        yield


guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=enforcer_provider,
    error_factory=lambda *_: HTTPException(403, "Forbidden"),
)
