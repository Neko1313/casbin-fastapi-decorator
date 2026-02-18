# casbin-fastapi-decorator

Authorization decorator factory for FastAPI based on [Casbin](https://casbin.org/) and [fastapi-decorators](https://pypi.org/project/fastapi-decorators/).

Decorators are applied to routes — no middleware or dependencies in the endpoint signature.

## Installation

```bash
pip install casbin-fastapi-decorator
```

Additional providers:

```bash
pip install "casbin-fastapi-decorator[jwt]"   # JWT authentication
pip install "casbin-fastapi-decorator[db]"    # Policies from DB (SQLAlchemy)
```

## Quick start

```python
import casbin
from fastapi import FastAPI, HTTPException
from casbin_fastapi_decorator import AccessSubject, PermissionGuard

# 1. Providers — regular FastAPI dependencies
async def get_current_user() -> dict:
    return {"sub": "alice", "role": "admin"}

async def get_enforcer() -> casbin.Enforcer:
    return casbin.Enforcer("model.conf", "policy.csv")

# 2. Decorator factory
guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=get_enforcer,
    error_factory=lambda user, *rv: HTTPException(403, "Forbidden"),
)

app = FastAPI()

# 3. Authentication only
@app.get("/me")
@guard.auth_required()
async def me():
    return {"ok": True}

# 4. Static permission check
@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles():
    return []

# 5. Dynamic check — value from request
async def get_article(article_id: int) -> dict:
    return {"id": article_id, "owner": "alice"}

@app.get("/articles/{article_id}")
@guard.require_permission(
    AccessSubject(val=get_article, selector=lambda a: a["owner"]),
    "read",
)
async def read_article(article_id: int):
    return {"article_id": article_id}
```

Arguments of `require_permission` are passed to `enforcer.enforce(user, *args)` in the same order. `AccessSubject` is resolved via FastAPI DI, then transformed by the `selector`.

## API

### `PermissionGuard`

```python
PermissionGuard(
    user_provider=...,       # FastAPI dependency that returns the current user
    enforcer_provider=...,   # FastAPI dependency that returns a casbin.Enforcer
    error_factory=...,       # callable(user, *rvals) -> Exception
)
```

| Method | Description |
|---|---|
| `auth_required()` | Decorator: authentication only (user_provider must not raise an exception) |
| `require_permission(*args)` | Decorator: permission check via `enforcer.enforce(user, *args)` |

### `AccessSubject`

```python
AccessSubject(
    val=get_item,                        # FastAPI dependency
    selector=lambda item: item["name"],  # transformation before enforce
)
```

Wraps a dependency whose value needs to be obtained from the request and passed to the enforcer. By default, `selector` is identity (`lambda x: x`).

## JWT provider

```python
from casbin_fastapi_decorator_jwt import JWTUserProvider

user_provider = JWTUserProvider(
    secret_key="your-secret",
    algorithm="HS256",             # default
    cookie_name="access_token",    # optional, enables reading from cookie
    user_model=UserSchema,         # optional, Pydantic model for payload validation
)
```

Extracts JWT from the Bearer header and/or cookie. If `user_model` is specified, validates the payload via `model_validate()`.

## DB provider

```python
from casbin_fastapi_decorator_db import DatabaseEnforcerProvider

enforcer_provider = DatabaseEnforcerProvider(
    model_path="model.conf",
    session_factory=get_async_session,
    policy_model=PolicyORM,
    policy_mapper=lambda p: (p.sub, p.obj, p.act),
    default_policies=[("admin", "*", "*")],  # optional
)
```

Loads policies from a SQLAlchemy async session and creates a `casbin.Enforcer` per request. `default_policies` are added on top of the DB policies.

## Examples

| Example | Description |
|---|---|
| [`examples/core`](examples/core) | Bearer token auth, file-based Casbin policies |
| [`examples/core-jwt`](examples/core-jwt) | JWT auth via `JWTUserProvider`, file-based policies |
| [`examples/core-db`](examples/core-db) | Bearer token auth, policies from SQLite via `DatabaseEnforcerProvider` |

## Development

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/), [task](https://taskfile.dev/).

```bash
task install           # uv sync --all-groups + install extras (jwt, db)
task lint              # ruff + ty + bandit for all packages
task tests             # all tests (core + jwt + db)
```

Individual package tasks:

```bash
task core:lint         # lint core only
task core:test         # test core only
task jwt:lint          # lint JWT package
task jwt:test          # test JWT package
task db:lint           # lint DB package
task db:test           # test DB package (requires Docker for testcontainers)
```

## License

MIT
