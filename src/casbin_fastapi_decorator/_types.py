from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class AccessSubject:
    """
    Wrapper around a FastAPI dependency with a selector.

    val: callable — FastAPI dep, wrapped in Depends()
    selector: transforms the resolved value before enforce
    """

    val: Callable[..., Any]
    selector: Callable[[Any], Any] = field(default=lambda x: x)


class AnyOf:
    """
    Logical OR of ``require_permission()`` clauses.

    Each positional argument is a clause: a tuple shaped exactly
    like the ``*args`` accepted by ``require_permission()`` (a mix
    of ``AccessSubject`` and static values). The route is allowed
    if at least one clause's ``enforcer.enforce(user, *rvals)``
    call succeeds; remaining clauses are skipped once one passes.

    Example::

        guard.require_permission(
            AnyOf(
                (Domain.GALLERY_EMPLOYEE, subject, Action.READ),
                (Domain.GALLERY_CRIMINAL, subject, Action.READ),
            ),
        )

    """

    __slots__ = ("clauses",)

    def __init__(
        self, *clauses: tuple[AccessSubject | Any, ...]
    ) -> None:
        self.clauses: tuple[
            tuple[AccessSubject | Any, ...], ...
        ] = clauses
