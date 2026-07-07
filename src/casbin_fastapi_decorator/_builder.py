from collections.abc import Callable
from functools import wraps
from inspect import isawaitable
from typing import Any
from uuid import uuid4

from fastapi import Depends
from fastapi_decorators import depends

from casbin_fastapi_decorator._types import AccessSubject


def build_auth_decorator(user_provider: "Callable[..., Any]") -> Callable:
    """Build an authentication-only decorator."""
    return depends(Depends(user_provider))


def build_permission_decorator(
    *,
    user_provider: "Callable[..., Any]",
    enforcer_provider: "Callable[..., Any]",
    error_factory: "Callable[..., Exception]",
    args: tuple[AccessSubject | Any, ...],
) -> "Callable":
    """
    Build a permission-check decorator via casbin enforcer.

    Resolved values are passed to
    ``enforcer.enforce(user, *rvals)``
    in the same order as *args*.

    Dependency parameter names are namespaced with a
    per-call token so that stacking multiple decorators
    (e.g. several ``require_permission()`` calls on one
    route) does not collide on shared kwarg names.
    """
    token = uuid4().hex
    user_key = f"__fguard_{token}_user__"
    enforcer_key = f"__fguard_{token}_enforcer__"

    depends_kwargs: dict[str, Any] = {
        user_key: Depends(user_provider),
        enforcer_key: Depends(enforcer_provider),
    }
    arg_keys: list[str | None] = []
    for i, arg in enumerate(args):
        if isinstance(arg, AccessSubject):
            key = f"__fguard_{token}_{i}__"
            depends_kwargs[key] = Depends(arg.val)
            arg_keys.append(key)
        else:
            arg_keys.append(None)

    def decorator(func: "Callable") -> "Callable":
        @depends(**depends_kwargs)
        @wraps(func)
        async def wrapper(*fn_args: Any, **kw: Any) -> Any:
            user = kw.pop(user_key)
            enforcer = kw.pop(enforcer_key)

            rvals: list[Any] = []
            for i, arg in enumerate(args):
                arg_key = arg_keys[i]
                if arg_key is not None:
                    raw = kw.pop(arg_key)
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
