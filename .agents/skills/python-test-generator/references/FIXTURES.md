# Fixture Patterns

## Containers

### PostgreSQL — container.py

```python
# tests/fixtures/containers/postgres/container.py
from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.database import Base  # your declarative base
from src.uow import UnitOfWork


def _has_integration_marker(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("integration") is not None


def _pg_url(container: PostgresContainer, driver: str = "asyncpg") -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    user = container.username
    password = container.password
    db = container.dbname
    return f"postgresql+{driver}://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture(scope="session")
def postgres_container(
    request: pytest.FixtureRequest,
) -> Generator[PostgresContainer, Any, None]:
    if not _has_integration_marker(request):

        class _MockPostgres:
            username = "test"
            password = "test"
            dbname = "test"

            def get_container_host_ip(self) -> str:
                return os.getenv("DB_HOST", "localhost")

            def get_exposed_port(self, port: int) -> int:  # noqa: ARG002
                return int(os.getenv("DB_PORT", "5432"))

        yield _MockPostgres()  # type: ignore[misc]
        return

    with PostgresContainer(image="postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
async def db_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(_pg_url(postgres_container), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def uow(
    db_engine: AsyncEngine,
    db_cleanup: None,  # ensure cleanup runs before each test
) -> AsyncGenerator[UnitOfWork, None]:
    async with UnitOfWork(db_engine) as uow:
        yield uow
```

### PostgreSQL — cleanup.py

```python
# tests/fixtures/containers/postgres/cleanup.py
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_cleanup(db_engine: AsyncEngine) -> None:
    """Truncate all tables before each test for isolation."""
    async with db_engine.begin() as conn:
        # Get all table names excluding alembic
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' "
                "AND tablename != 'alembic_version'"
            )
        )
        tables = [row[0] for row in result]
        if tables:
            await conn.execute(
                text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
            )
```

### Redis — container.py

```python
# tests/fixtures/containers/redis/container.py
from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from testcontainers.redis import RedisContainer


def _has_integration_marker(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("integration") is not None


def _redis_url(container: RedisContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}"


@pytest.fixture(scope="session")
def redis_container(
    request: pytest.FixtureRequest,
) -> Generator[RedisContainer, Any, None]:
    if not _has_integration_marker(request):

        class _MockRedis:
            port = 6379

            def get_container_host_ip(self) -> str:
                return "localhost"

            def get_exposed_port(self, port: int) -> int:  # noqa: ARG002
                return 6379

        yield _MockRedis()  # type: ignore[misc]
        return

    with RedisContainer(image="redis:7.2-alpine") as container:
        yield container


@pytest_asyncio.fixture(scope="session")
async def redis_client(
    redis_container: RedisContainer,
) -> AsyncGenerator:
    from redis import asyncio as aioredis  # noqa: PLC0415

    redis = aioredis.from_url(_redis_url(redis_container))
    yield redis
    await redis.aclose()
```

### Redis — cleanup.py

```python
# tests/fixtures/containers/redis/cleanup.py
import pytest_asyncio
from redis.asyncio import Redis


@pytest_asyncio.fixture(scope="function", autouse=True)
async def redis_cleanup(redis_client: Redis) -> None:
    """Flush all Redis data before each test."""
    await redis_client.flushdb()
```

---

## Entity Factories

Use `polyfactory` to build model instances without hitting the database.

### Pattern — fixtures/entities/annotation.py

```python
# tests/fixtures/entities/annotation.py
from __future__ import annotations

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
# OR for SQLAlchemy models:
# from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from src.models import Annotation


class AnnotationFactory(ModelFactory[Annotation]):
    __model__ = Annotation
    # Override specific fields if needed:
    # name = "test-annotation"
    # is_active = True


@pytest.fixture
def annotation_factory() -> type[AnnotationFactory]:
    return AnnotationFactory
```

### SQLAlchemy model factory (async persistence)

```python
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory
from sqlalchemy.ext.asyncio import AsyncSession


class AnnotationFactory(SQLAlchemyFactory[Annotation]):
    __model__ = Annotation
    __async_session__ = None  # injected via fixture

    @classmethod
    def set_session(cls, session: AsyncSession) -> None:
        cls.__async_session__ = session


@pytest.fixture
def annotation_factory(db_session: AsyncSession) -> type[AnnotationFactory]:
    AnnotationFactory.set_session(db_session)
    return AnnotationFactory
```

### Building vs creating

```python
# build() — creates instance in memory, no DB
annotation = annotation_factory.build()
annotation = annotation_factory.build(floor_id=floor.id)

# batch(n) — creates n instances in memory
annotations = annotation_factory.batch(3, floor_id=floor.id)

# create() — persists to DB (requires AsyncSession)
annotation = await annotation_factory.create_async()
```

---

## HTTP Client Fixtures

```python
# tests/fixtures/entities/clients.py
from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app  # your FastAPI app
from src.auth import create_access_token  # your JWT helper


@dataclass
class ClientTuple:
    user: AsyncClient
    manager: AsyncClient
    anonymous: AsyncClient

    def __iter__(self):
        return iter((self.user, self.manager, self.anonymous))


def _make_auth_headers(role: str) -> dict[str, str]:
    token = create_access_token(subject="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def clients_v1() -> AsyncGenerator[ClientTuple, None]:
    transport = ASGITransport(app=app)
    base = "http://test/api/v1"

    async with (
        AsyncClient(transport=transport, base_url=base, headers=_make_auth_headers("user")) as user,
        AsyncClient(transport=transport, base_url=base, headers=_make_auth_headers("manager")) as manager,
        AsyncClient(transport=transport, base_url=base) as anonymous,
    ):
        yield ClientTuple(user=user, manager=manager, anonymous=anonymous)
```