"""Unit tests — AccessSubject happy paths."""
from __future__ import annotations

import pytest

from casbin_fastapi_decorator._types import AccessSubject


async def _dep() -> dict:
    return {"key": "value"}


@pytest.mark.unit
@pytest.mark.access_subject
def test_default_selector_is_identity() -> None:
    subject = AccessSubject(val=_dep)
    assert subject.selector("anything") == "anything"
    assert subject.selector({"key": "val"}) == {"key": "val"}
    assert subject.selector(42) == 42


@pytest.mark.unit
@pytest.mark.access_subject
def test_custom_selector_transforms_value() -> None:
    subject = AccessSubject(val=_dep, selector=lambda x: x["key"])
    assert subject.selector({"key": "extracted"}) == "extracted"


@pytest.mark.unit
@pytest.mark.access_subject
def test_equality_same_val_and_selector() -> None:
    selector = lambda x: x  # noqa: E731
    s1 = AccessSubject(val=_dep, selector=selector)
    s2 = AccessSubject(val=_dep, selector=selector)
    assert s1 == s2


@pytest.mark.unit
@pytest.mark.access_subject
def test_inequality_different_val() -> None:
    async def other_dep() -> dict:
        return {}

    s1 = AccessSubject(val=_dep)
    s2 = AccessSubject(val=other_dep)
    assert s1 != s2


@pytest.mark.unit
@pytest.mark.access_subject
def test_inequality_different_selector() -> None:
    sel1 = lambda x: x  # noqa: E731
    sel2 = str
    s1 = AccessSubject(val=_dep, selector=sel1)
    s2 = AccessSubject(val=_dep, selector=sel2)
    assert s1 != s2


@pytest.mark.unit
@pytest.mark.access_subject
def test_val_attribute_accessible() -> None:
    subject = AccessSubject(val=_dep)
    assert subject.val is _dep


@pytest.mark.unit
@pytest.mark.access_subject
def test_selector_attribute_accessible() -> None:
    sel = lambda x: x["name"]  # noqa: E731
    subject = AccessSubject(val=_dep, selector=sel)
    assert subject.selector is sel
