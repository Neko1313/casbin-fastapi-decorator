"""Unit tests — AccessSubject immutability / error cases."""
from __future__ import annotations

import pytest

from casbin_fastapi_decorator._types import AccessSubject


async def _dep() -> dict:
    return {"key": "value"}


@pytest.mark.unit
@pytest.mark.access_subject
def test_frozen_dataclass_raises_on_reassign() -> None:
    subject = AccessSubject(val=_dep)
    with pytest.raises(AttributeError):
        subject.val = None  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.access_subject
def test_frozen_selector_raises_on_reassign() -> None:
    subject = AccessSubject(val=_dep)
    with pytest.raises(AttributeError):
        subject.selector = lambda x: x  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.access_subject
def test_slots_no_arbitrary_attributes() -> None:
    # frozen + slots dataclass must reject arbitrary attributes;
    # Python 3.13 raises TypeError instead of AttributeError
    subject = AccessSubject(val=_dep)
    with pytest.raises((AttributeError, TypeError)):
        subject.nonexistent = "value"  # type: ignore[attr-defined]
