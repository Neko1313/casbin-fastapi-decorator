from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import casbin
from sqlalchemy import select

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseEnforcerProvider:
    """
    Enforcer provider: loads policies from a database via SQLAlchemy.

    Accepts an SQLAlchemy async session factory and a policy table model.

    Usage::

        enforcer_provider = DatabaseEnforcerProvider(
            model_path="model.conf",
            session_factory=get_session,
            policy_model=Policy,
            policy_mapper=lambda p: (p.sub_rule, p.obj_rule, p.sub_obj, p.act),
        )
        guard = PermissionGuard(enforcer_provider=enforcer_provider, ...)
    """

    def __init__(
        self,
        *,
        model_path: str | Path,
        session_factory: Callable[..., AsyncSession],
        policy_model: type,
        policy_mapper: Callable[[Any], tuple[Any, ...]],
        default_policies: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._session_factory = session_factory
        self._policy_model = policy_model
        self._policy_mapper = policy_mapper
        self._default_policies = default_policies or []

    async def __call__(self) -> casbin.Enforcer:
        """Create an enforcer with policies from the DB."""
        async with self._session_factory() as session:
            result = await session.execute(select(self._policy_model))
            policies = [self._policy_mapper(row) for row in result.scalars()]

        all_policies = self._default_policies + policies
        enforcer = casbin.Enforcer(str(self._model_path))
        if all_policies:
            enforcer.add_policies(all_policies)
        return enforcer
