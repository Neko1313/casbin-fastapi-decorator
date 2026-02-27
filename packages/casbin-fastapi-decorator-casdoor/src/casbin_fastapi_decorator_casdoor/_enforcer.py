from __future__ import annotations

from collections.abc import (
    Callable,  # noqa: TC003 — needed by Pydantic at runtime
)
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from casdoor import AsyncCasdoorSDK


class CasdoorEnforceTarget(BaseModel):
    """
    Selects which Casdoor API identifier to use for ``/api/enforce``.

    Exactly one field must be non-empty — mirrors the SDK's own
    ``_build_enforce_params`` validation.

    A field value can be a **static string** or a **callable** that
    receives the parsed JWT payload (``dict``) and returns a string.
    The callable form is useful when the identifier must be derived
    from the authenticated user at enforce-time.

    Static target::

        CasdoorEnforceTarget(enforce_id="my_org/my_enforcer")

    Dynamic target (org taken from the user's JWT)::

        CasdoorEnforceTarget(
            enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer"
        )

    By permission object::

        CasdoorEnforceTarget(permission_id="my_org/can_edit_posts")

    By model::

        CasdoorEnforceTarget(model_id="my_org/rbac_model")

    By owner (all policies in an organisation)::

        CasdoorEnforceTarget(owner="my_org")
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    enforce_id: str | Callable[[dict[str, Any]], str] = ""
    permission_id: str | Callable[[dict[str, Any]], str] = ""
    model_id: str | Callable[[dict[str, Any]], str] = ""
    resource_id: str | Callable[[dict[str, Any]], str] = ""
    owner: str | Callable[[dict[str, Any]], str] = ""

    @model_validator(mode="after")
    def _validate_exactly_one(self) -> CasdoorEnforceTarget:
        """Ensure exactly one field is set."""
        set_fields = [
            name for name in type(self).model_fields if getattr(self, name)
        ]
        if len(set_fields) != 1:
            msg = (
                "Exactly one of (enforce_id, permission_id, model_id, "
                f"resource_id, owner) must be set, got {len(set_fields)}"
                + (f": {set_fields}" if set_fields else "")
            )
            raise ValueError(msg)
        return self

    def resolve(self, parsed_jwt: dict[str, Any]) -> dict[str, str]:
        """
        Return all five SDK ``enforce()`` keyword arguments.

        The selected field is resolved (callable invoked if needed);
        all others are set to ``""`` so the SDK validates exactly one
        non-empty value.
        """
        result: dict[str, str] = dict.fromkeys(type(self).model_fields, "")
        for name in type(self).model_fields:
            val = getattr(self, name)
            if val:
                result[name] = (
                    val(parsed_jwt) if callable(val) else val
                )
                break
        return result


def _default_user_factory(parsed: dict[str, Any]) -> str:
    return f"{parsed['owner']}/{parsed['name']}"


class CasdoorEnforcer:
    """
    Enforcer that delegates policy checks to the Casdoor remote enforce API.

    The user identity string passed to ``sdk.enforce()`` is built by
    ``user_factory`` (default: ``"{owner}/{name}"`` from the JWT payload).

    The enforcement target (which Casdoor API identifier to use) is
    configured via :class:`CasdoorEnforceTarget`.

    Usage::

        target = CasdoorEnforceTarget(
            enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer"
        )
        enforcer = CasdoorEnforcer(sdk=sdk, target=target)
    """

    def __init__(
        self,
        *,
        sdk: AsyncCasdoorSDK,
        target: CasdoorEnforceTarget,
        user_factory: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self._sdk = sdk
        self._target = target
        self._user_factory = user_factory or _default_user_factory

    async def enforce(self, user: str, *rvals: Any) -> bool:
        """Enforce policy via the Casdoor API."""
        parsed = self._sdk.parse_jwt_token(user)
        user_path = self._user_factory(parsed)
        target_kwargs = self._target.resolve(parsed)
        return await self._sdk.enforce(
            **target_kwargs,
            casbin_request=[user_path, *rvals],
        )


class CasdoorEnforcerProvider:
    """
    FastAPI dependency that provides a :class:`CasdoorEnforcer`.

    Usage::

        target = CasdoorEnforceTarget(
            enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer"
        )
        enforcer_provider = CasdoorEnforcerProvider(sdk=sdk, target=target)
        guard = PermissionGuard(enforcer_provider=enforcer_provider, ...)
    """

    def __init__(
        self,
        *,
        sdk: AsyncCasdoorSDK,
        target: CasdoorEnforceTarget,
        user_factory: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self._enforcer = CasdoorEnforcer(
            sdk=sdk,
            target=target,
            user_factory=user_factory,
        )

    async def __call__(self) -> CasdoorEnforcer:
        """FastAPI dependency. Returns the shared :class:`CasdoorEnforcer`."""
        return self._enforcer
