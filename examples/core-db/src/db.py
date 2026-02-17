"""Database setup and models."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from model import Permission, Resource, Role
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_async_engine("sqlite+aiosqlite:///./example.db")
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Policy(Base):
    """Casbin policy stored in the database."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sub: Mapped[str] = mapped_column(String(100))
    obj: Mapped[str] = mapped_column(String(100))
    act: Mapped[str] = mapped_column(String(100))


async def seed_policies() -> None:
    """Insert sample policies if the table is empty."""
    async with async_session() as session:
        result = await session.execute(select(Policy))
        if result.scalars().first() is not None:
            return

        policies = [
            Policy(sub=Role.ADMIN, obj=Resource.POST, act=Permission.READ),
            Policy(sub=Role.ADMIN, obj=Resource.POST, act=Permission.WRITE),
            Policy(sub=Role.ADMIN, obj=Resource.POST, act=Permission.DELETE),
            Policy(sub=Role.EDITOR, obj=Resource.POST, act=Permission.READ),
            Policy(sub=Role.EDITOR, obj=Resource.POST, act=Permission.WRITE),
            Policy(sub=Role.VIEWER, obj=Resource.POST, act=Permission.READ),
        ]
        session.add_all(policies)
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database and seed policies on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_policies()
    yield
    await engine.dispose()
