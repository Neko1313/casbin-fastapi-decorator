from __future__ import annotations

from functools import wraps
from inspect import isawaitable
from typing import TYPE_CHECKING, Any

from fastapi import Depends
from fastapi_decorators import depends

from casbin_fastapi_decorator._types import AccessSubject

if TYPE_CHECKING:
    from collections.abc import Callable


def build_auth_decorator(user_provider: Callable[..., Any]) -> Callable:
    """Build an authentication-only decorator."""
    return depends(Depends(user_provider))


def build_permission_decorator(
    *,
    user_provider: Callable[..., Any],
    enforcer_provider: Callable[..., Any],
    error_factory: Callable[..., Exception],
    args: tuple[AccessSubject | Any, ...],
) -> Callable:
    """
    Build a permission-check decorator via casbin enforcer.

    Resolved values are passed to
    ``enforcer.enforce(user, *rvals)``
    in the same order as *args*.
    """
    depends_kwargs: dict[str, Any] = {
        "__fguard_user__": Depends(user_provider),
        "__fguard_enforcer__": Depends(enforcer_provider),
    }
    for i, arg in enumerate(args):
        if isinstance(arg, AccessSubject):
            depends_kwargs[f"__fguard_{i}__"] = Depends(arg.val)

    def decorator(func: Callable) -> Callable:
        @depends(**depends_kwargs)
        @wraps(func)
        async def wrapper(*fn_args: Any, **kw: Any) -> Any:
            user = kw.pop("__fguard_user__")
            enforcer = kw.pop("__fguard_enforcer__")

            rvals: list[Any] = []
            for i, arg in enumerate(args):
                if isinstance(arg, AccessSubject):
                    raw = kw.pop(f"__fguard_{i}__")
                    rvals.append(arg.selector(raw))
                else:
                    rvals.append(arg)

            result = enforcer.enforce(user, *rvals)
            if isawaitable(result):
                result = await result
            if not result:
                raise error_factory(user, *rvals)

            return await func(*fn_args, **kw)

        return wrapper

    return decorator
