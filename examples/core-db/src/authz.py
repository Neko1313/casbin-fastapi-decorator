"""Authorization Guard."""
from auth import get_current_user
from casbin_fastapi_decorator_db import DatabaseEnforcerProvider
from db import Policy, async_session
from fastapi import HTTPException

from casbin_fastapi_decorator import PermissionGuard

enforcer_provider = DatabaseEnforcerProvider(
    model_path="casbin/model.conf",
    session_factory=async_session,
    policy_model=Policy,
    policy_mapper=lambda p: (p.sub, p.obj, p.act),
)

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=enforcer_provider,
    error_factory=lambda *_: HTTPException(403, "Forbidden"),
)
