"""Authorization Guard."""
from auth import user_provider
from casbin import Enforcer
from fastapi import HTTPException

from casbin_fastapi_decorator import PermissionGuard


async def get_enforcer() -> Enforcer:
    """Get enforcer."""
    return Enforcer("casbin/model.conf", "casbin/policy.csv")


guard = PermissionGuard(
    user_provider=user_provider,
    enforcer_provider=get_enforcer,
    error_factory=lambda *_: HTTPException(403, "Forbidden"),
)
