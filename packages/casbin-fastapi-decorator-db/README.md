# casbin-fastapi-decorator-db

Database enforcer provider for [casbin-fastapi-decorator](https://github.com/Neko1313/casbin-fastapi-decorator).

Loads Casbin policies from a SQLAlchemy async session and creates a `casbin.Enforcer` per request.

## Installation

```bash
pip install casbin-fastapi-decorator-db
```

Or via the core package extra:

```bash
pip install "casbin-fastapi-decorator[db]"
```

## Usage

Define a SQLAlchemy ORM model for your policy table:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class PolicyORM(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    sub: Mapped[str]
    obj: Mapped[str]
    act: Mapped[str]
```

Create the provider and pass it to `PermissionGuard`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from casbin_fastapi_decorator_db import DatabaseEnforcerProvider
from casbin_fastapi_decorator import PermissionGuard
from fastapi import FastAPI, HTTPException

engine = create_async_engine("sqlite+aiosqlite:///./policies.db")
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession)

async def get_current_user() -> dict:
    return {"sub": "alice", "role": "admin"}

enforcer_provider = DatabaseEnforcerProvider(
    model_path="model.conf",
    session_factory=AsyncSessionLocal,
    policy_model=PolicyORM,
    policy_mapper=lambda p: (p.sub, p.obj, p.act),
    default_policies=[("admin", "*", "*")],  # optional
)

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=enforcer_provider,
    error_factory=lambda user, *rv: HTTPException(403, "Forbidden"),
)

app = FastAPI()

@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles():
    return []
```

## API

### `DatabaseEnforcerProvider`

```python
DatabaseEnforcerProvider(
    model_path: str,
    session_factory: async_sessionmaker[AsyncSession],
    policy_model: type,
    policy_mapper: Callable[[Any], tuple],
    default_policies: list[tuple] = [],
)
```

| Parameter | Description |
|---|---|
| `model_path` | Path to the Casbin model `.conf` file |
| `session_factory` | SQLAlchemy `async_sessionmaker` |
| `policy_model` | ORM model class representing the policy table |
| `policy_mapper` | Function that maps an ORM row to a `(sub, obj, act)` tuple |
| `default_policies` | Static policies added on top of the database policies (default: `[]`) |

On each request the provider opens a session, loads all rows from the policy table, maps them via `policy_mapper`, merges with `default_policies`, and returns a fresh `casbin.Enforcer`.

## Development

See the [workspace README](../../README.md) for setup instructions.

```bash
task db:lint    # ruff + bandit + ty
task db:test    # pytest (requires Docker for testcontainers)
```
