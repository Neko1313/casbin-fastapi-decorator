"""Unit tests for CasdoorEnforceTarget — all modes, callable, resolve, validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from casbin_fastapi_decorator_casdoor import CasdoorEnforceTarget

PARSED = {"owner": "my_org", "name": "alice", "email": "alice@example.com"}


# ---------------------------------------------------------------------------
# Construction — valid (one field set)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enforce_id_static() -> None:
    t = CasdoorEnforceTarget(enforce_id="my_org/enforcer")
    assert t.enforce_id == "my_org/enforcer"


@pytest.mark.unit
def test_permission_id_static() -> None:
    t = CasdoorEnforceTarget(permission_id="my_org/perm")
    assert t.permission_id == "my_org/perm"


@pytest.mark.unit
def test_model_id_static() -> None:
    t = CasdoorEnforceTarget(model_id="my_org/model")
    assert t.model_id == "my_org/model"


@pytest.mark.unit
def test_resource_id_static() -> None:
    t = CasdoorEnforceTarget(resource_id="my_org/resource")
    assert t.resource_id == "my_org/resource"


@pytest.mark.unit
def test_owner_static() -> None:
    t = CasdoorEnforceTarget(owner="my_org")
    assert t.owner == "my_org"


@pytest.mark.unit
def test_enforce_id_callable() -> None:
    fn = lambda parsed: f"{parsed['owner']}/enforcer"  # noqa: E731
    t = CasdoorEnforceTarget(enforce_id=fn)
    assert callable(t.enforce_id)


@pytest.mark.unit
def test_permission_id_callable() -> None:
    fn = lambda parsed: f"{parsed['owner']}/perm"  # noqa: E731
    t = CasdoorEnforceTarget(permission_id=fn)
    assert callable(t.permission_id)


# ---------------------------------------------------------------------------
# Construction — invalid
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_field_raises() -> None:
    with pytest.raises(ValidationError, match="Exactly one"):
        CasdoorEnforceTarget()


@pytest.mark.unit
def test_two_fields_raises() -> None:
    with pytest.raises(ValidationError, match="Exactly one"):
        CasdoorEnforceTarget(enforce_id="a/b", permission_id="a/c")


@pytest.mark.unit
def test_all_fields_raises() -> None:
    with pytest.raises(ValidationError, match="Exactly one"):
        CasdoorEnforceTarget(
            enforce_id="a/b",
            permission_id="a/c",
            model_id="a/d",
            resource_id="a/e",
            owner="a",
        )


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_frozen() -> None:
    t = CasdoorEnforceTarget(enforce_id="my_org/enforcer")
    with pytest.raises(ValidationError, match="frozen"):
        t.enforce_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# resolve() — static values
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_enforce_id_static() -> None:
    t = CasdoorEnforceTarget(enforce_id="my_org/enforcer")
    result = t.resolve(PARSED)
    assert result["enforce_id"] == "my_org/enforcer"
    assert result["permission_id"] == ""
    assert result["model_id"] == ""
    assert result["resource_id"] == ""
    assert result["owner"] == ""


@pytest.mark.unit
def test_resolve_permission_id_static() -> None:
    t = CasdoorEnforceTarget(permission_id="my_org/perm")
    result = t.resolve(PARSED)
    assert result["permission_id"] == "my_org/perm"
    assert result["enforce_id"] == ""


@pytest.mark.unit
def test_resolve_model_id_static() -> None:
    t = CasdoorEnforceTarget(model_id="my_org/model")
    result = t.resolve(PARSED)
    assert result["model_id"] == "my_org/model"
    assert result["enforce_id"] == ""


@pytest.mark.unit
def test_resolve_resource_id_static() -> None:
    t = CasdoorEnforceTarget(resource_id="my_org/res")
    result = t.resolve(PARSED)
    assert result["resource_id"] == "my_org/res"


@pytest.mark.unit
def test_resolve_owner_static() -> None:
    t = CasdoorEnforceTarget(owner="my_org")
    result = t.resolve(PARSED)
    assert result["owner"] == "my_org"


# ---------------------------------------------------------------------------
# resolve() — callable values
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_enforce_id_callable_receives_parsed_jwt() -> None:
    received: list[dict] = []

    def factory(parsed: dict) -> str:  # type: ignore[type-arg]
        received.append(parsed)
        return f"{parsed['owner']}/enforcer"

    t = CasdoorEnforceTarget(enforce_id=factory)
    result = t.resolve(PARSED)

    assert received == [PARSED]
    assert result["enforce_id"] == "my_org/enforcer"


@pytest.mark.unit
def test_resolve_callable_returns_correct_value() -> None:
    t = CasdoorEnforceTarget(
        permission_id=lambda parsed: f"{parsed['owner']}/can_read",
    )
    result = t.resolve(PARSED)
    assert result["permission_id"] == "my_org/can_read"


@pytest.mark.unit
def test_resolve_callable_owner_uses_email() -> None:
    t = CasdoorEnforceTarget(enforce_id=lambda p: p["email"])
    result = t.resolve(PARSED)
    assert result["enforce_id"] == "alice@example.com"


# ---------------------------------------------------------------------------
# resolve() — exactly five keys always returned
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_always_returns_five_keys() -> None:
    t = CasdoorEnforceTarget(enforce_id="a/b")
    result = t.resolve(PARSED)
    assert set(result.keys()) == {
        "enforce_id",
        "permission_id",
        "model_id",
        "resource_id",
        "owner",
    }


@pytest.mark.unit
def test_resolve_exactly_one_non_empty_value() -> None:
    for field in ("enforce_id", "permission_id", "model_id", "resource_id", "owner"):
        t = CasdoorEnforceTarget(**{field: "my_org/value"})
        result = t.resolve(PARSED)
        non_empty = [k for k, v in result.items() if v]
        assert non_empty == [field], f"Expected only {field!r} to be set"
