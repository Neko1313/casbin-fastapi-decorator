"""PolicyModel — SQLAlchemy table used exclusively in tests."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PolicyModel(Base):
    """Minimal policy table: (sub, obj, act) triples."""

    __tablename__ = "policy"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sub: Mapped[str]
    obj: Mapped[str]
    act: Mapped[str]


@pytest.fixture
def policy_model() -> type[PolicyModel]:
    return PolicyModel
