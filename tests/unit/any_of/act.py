"""Unit tests — AnyOf combinator happy paths."""
from __future__ import annotations

import pytest

from casbin_fastapi_decorator._types import AccessSubject, AnyOf


async def _dep() -> str:
    return "value"


@pytest.mark.unit
@pytest.mark.any_of
def test_no_clauses_gives_empty_tuple() -> None:
    assert AnyOf().clauses == ()


@pytest.mark.unit
@pytest.mark.any_of
def test_stores_clauses_in_order() -> None:
    clause_a = ("domain-a", "read")
    clause_b = ("domain-b", "read")

    any_of = AnyOf(clause_a, clause_b)

    assert any_of.clauses == (clause_a, clause_b)


@pytest.mark.unit
@pytest.mark.any_of
def test_clause_may_contain_access_subject() -> None:
    subject = AccessSubject(val=_dep)
    clause = ("domain-a", subject, "read")

    any_of = AnyOf(clause)

    assert any_of.clauses == (clause,)
    assert any_of.clauses[0][1] is subject
