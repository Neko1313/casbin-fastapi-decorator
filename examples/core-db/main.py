"""Example using casbin-fastapi-decorator with DB policies."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider
from fastapi import FastAPI, HTTPException
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from casbin_fastapi_decorator import PermissionGuard

EXAMPLE_DIR = Path(__file__).parent

# --- Database setup (SQLite for demo) ---

engine = create_async_engine(
    "sqlite+aiosqlite:///./example.db"
)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Policy(Base):
    """Casbin policy stored in the database."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    sub: Mapped[str] = mapped_column(String(100))
    obj: Mapped[str] = mapped_column(String(100))
    act: Mapped[str] = mapped_column(String(100))


# --- Seed the database on startup ---


async def seed_policies() -> None:
    """Insert sample policies if the table is empty."""
    async with async_session() as session:
        result = await session.execute(select(Policy))
        if result.scalars().first() is not None:
            return

        policies = [
            Policy(sub="admin", obj="articles", act="read"),
            Policy(
                sub="admin", obj="articles", act="write"
            ),
            Policy(
                sub="admin", obj="articles", act="delete"
            ),
            Policy(
                sub="editor", obj="articles", act="read"
            ),
            Policy(
                sub="editor", obj="articles", act="write"
            ),
            Policy(
                sub="viewer", obj="articles", act="read"
            ),
        ]
        session.add_all(policies)
        await session.commit()


@asynccontextmanager
async def lifespan(
    _app: FastAPI,
) -> AsyncIterator[None]:
    """Initialize the database and seed policies."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_policies()
    yield
    await engine.dispose()


# --- Simulated user provider ---

USERS = {
    "alice": {"sub": "alice", "role": "admin"},
    "bob": {"sub": "bob", "role": "editor"},
    "charlie": {"sub": "charlie", "role": "viewer"},
}


async def get_current_user() -> dict:
    """Simulate authentication."""
    return USERS["alice"]


# --- DB enforcer provider ---

enforcer_provider = DatabaseEnforcerProvider(
    model_path=str(EXAMPLE_DIR / "model.conf"),
    session_factory=async_session,
    policy_model=Policy,
    policy_mapper=lambda p: (p.sub, p.obj, p.act),
    default_policies=[("superadmin", "*", "*")],
)

# --- Guard setup ---

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=enforcer_provider,
    error_factory=lambda _user, *_rvals: HTTPException(
        403, "Forbidden"
    ),
)

app = FastAPI(
    title="Core + DB Example", lifespan=lifespan
)


# --- Routes ---


@app.get("/me")
@guard.auth_required()
async def me() -> dict:
    """Return current user info."""
    return {"message": "You are authenticated"}


@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles() -> list[dict]:
    """List all articles (requires articles:read)."""
    return [
        {"id": 1, "title": "First article"},
        {"id": 2, "title": "Second article"},
    ]


@app.post("/articles")
@guard.require_permission("articles", "write")
async def create_article() -> dict:
    """Create an article (requires articles:write)."""
    return {"id": 3, "title": "New article", "created": True}


@app.delete("/articles/{article_id}")
@guard.require_permission("articles", "delete")
async def delete_article(article_id: int) -> dict:
    """Delete an article (requires articles:delete)."""
    return {"id": article_id, "deleted": True}


# --- Admin endpoint to manage policies at runtime ---


@app.get("/policies")
async def list_policies() -> list[dict]:
    """List all policies from the database."""
    async with async_session() as session:
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
    return [
        {"sub": p.sub, "obj": p.obj, "act": p.act}
        for p in policies
    ]
