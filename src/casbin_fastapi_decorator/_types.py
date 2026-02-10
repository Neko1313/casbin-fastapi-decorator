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
