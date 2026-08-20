from collections.abc import Callable
from functools import wraps
from inspect import isawaitable
from typing import Any
from uuid import uuid4

from fastapi import Depends
from fastapi_decorators import depends

from casbin_fastapi_decorator._types import AccessSubject, AnyOf


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
    route) does not collide on shared kwarg names. Stacking
    decorators also gives AND semantics: every decorator must
    pass, in order, before the route body runs.

    If *args* is a single ``AnyOf(...)`` instance, the
    decorator instead gives OR semantics across its clauses —
    see ``build_any_of_decorator``.
    """
    if len(args) == 1 and isinstance(args[0], AnyOf):
        return build_any_of_decorator(
            user_provider=user_provider,
            enforcer_provider=enforcer_provider,
            error_factory=error_factory,
            any_of=args[0],
        )

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


def build_any_of_decorator(
    *,
    user_provider: "Callable[..., Any]",
    enforcer_provider: "Callable[..., Any]",
    error_factory: "Callable[..., Exception]",
    any_of: AnyOf,
) -> "Callable":
    """
    Build a permission-check decorator with OR semantics.

    Each clause in *any_of* is resolved and checked via
    ``enforcer.enforce(user, *rvals)`` in order; the route is
    allowed as soon as one clause passes. If every clause is
    denied, ``error_factory`` is called with the user and the
    resolved values of each clause (one tuple per clause).
    """
    token = uuid4().hex
    user_key = f"__fguard_{token}_user__"
    enforcer_key = f"__fguard_{token}_enforcer__"

    depends_kwargs: dict[str, Any] = {
        user_key: Depends(user_provider),
        enforcer_key: Depends(enforcer_provider),
    }
    clause_arg_keys: list[list[str | None]] = []
    for ci, clause in enumerate(any_of.clauses):
        arg_keys: list[str | None] = []
        for i, arg in enumerate(clause):
            if isinstance(arg, AccessSubject):
                key = f"__fguard_{token}_{ci}_{i}__"
                depends_kwargs[key] = Depends(arg.val)
                arg_keys.append(key)
            else:
                arg_keys.append(None)
        clause_arg_keys.append(arg_keys)

    def decorator(func: "Callable") -> "Callable":
        @depends(**depends_kwargs)
        @wraps(func)
        async def wrapper(*fn_args: Any, **kw: Any) -> Any:
            user = kw.pop(user_key)
            enforcer = kw.pop(enforcer_key)

            all_rvals: list[tuple[Any, ...]] = []
            allowed = False
            for ci, clause in enumerate(any_of.clauses):
                rvals: list[Any] = []
                for i, arg in enumerate(clause):
                    arg_key = clause_arg_keys[ci][i]
                    if arg_key is not None:
                        raw = kw.pop(arg_key)
                        rvals.append(arg.selector(raw))
                    else:
                        rvals.append(arg)
                all_rvals.append(tuple(rvals))

                if allowed:
                    continue

                result = enforcer.enforce(user, *rvals)
                if isawaitable(result):
                    result = await result
                if result:
                    allowed = True

            if not allowed:
                raise error_factory(user, *all_rvals)

            return await func(*fn_args, **kw)

        return wrapper

    return decorator
