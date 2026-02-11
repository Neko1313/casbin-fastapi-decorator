"""Authorization Guard."""
from auth import get_current_user
from casbin import Enforcer
from fastapi import HTTPException

from casbin_fastapi_decorator import PermissionGuard


async def get_enforcer() -> Enforcer:
    """Get enforcer."""
    return Enforcer("casbin/model.conf", "casbin/policy.csv")

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=get_enforcer,
    error_factory=lambda *_ : HTTPException(
        403, "Forbidden"
    ),
)
