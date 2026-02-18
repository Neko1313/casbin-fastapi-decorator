"""PostgreSQL testcontainer + engine + session_factory fixtures."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from tests.fixtures.entities.policy import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


def _pg_url(container: PostgresContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    user = container.username
    password = container.password
    db = container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, Any, None]:
    with PostgresContainer(image="postgres:16-alpine") as container:
        yield container


@pytest_asyncio.fixture(scope="session")
async def db_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(_pg_url(postgres_container), echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session_factory(
    db_engine: AsyncEngine,
    db_cleanup: None,
) -> async_sessionmaker[AsyncSession]:
    """Per-test session factory backed by a clean database state."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
