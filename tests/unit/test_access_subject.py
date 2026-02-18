"""Unit tests for AccessSubject dataclass."""
from __future__ import annotations

import pytest

from casbin_fastapi_decorator._types import AccessSubject


async def _dep() -> dict:
    return {"key": "value"}


def test_default_selector_is_identity() -> None:
    subject = AccessSubject(val=_dep)
    assert subject.selector("anything") == "anything"
    assert subject.selector({"key": "val"}) == {"key": "val"}
    assert subject.selector(42) == 42


def test_custom_selector_transforms_value() -> None:
    subject = AccessSubject(val=_dep, selector=lambda x: x["key"])
    assert subject.selector({"key": "extracted"}) == "extracted"


def test_frozen_dataclass_raises_on_reassign() -> None:
    subject = AccessSubject(val=_dep)
    with pytest.raises(AttributeError):
        subject.val = None  # type: ignore[misc]


def test_frozen_selector_raises_on_reassign() -> None:
    subject = AccessSubject(val=_dep)
    with pytest.raises(AttributeError):
        subject.selector = lambda x: x  # type: ignore[misc]


def test_equality_same_val_and_selector() -> None:
    selector = lambda x: x  # noqa: E731
    s1 = AccessSubject(val=_dep, selector=selector)
    s2 = AccessSubject(val=_dep, selector=selector)
    assert s1 == s2


def test_inequality_different_val() -> None:
    async def other_dep() -> dict:
        return {}

    s1 = AccessSubject(val=_dep)
    s2 = AccessSubject(val=other_dep)
    assert s1 != s2


def test_inequality_different_selector() -> None:
    sel1 = lambda x: x  # noqa: E731
    sel2 = str
    s1 = AccessSubject(val=_dep, selector=sel1)
    s2 = AccessSubject(val=_dep, selector=sel2)
    assert s1 != s2


def test_slots_no_arbitrary_attributes() -> None:
    # frozen+slots dataclass must reject arbitrary attributes;
    # Python 3.13 raises TypeError here instead of AttributeError
    subject = AccessSubject(val=_dep)
    with pytest.raises((AttributeError, TypeError)):
        subject.nonexistent = "value"  # type: ignore[attr-defined]


def test_val_attribute_accessible() -> None:
    subject = AccessSubject(val=_dep)
    assert subject.val is _dep


def test_selector_attribute_accessible() -> None:
    sel = lambda x: x["name"]  # noqa: E731
    subject = AccessSubject(val=_dep, selector=sel)
    assert subject.selector is sel
