<div align="center">
  <img src="https://neko1313.github.io/casbin-fastapi-decorator-docs/img/logo.png" alt="casbin-fastapi-decorator logo" width="120"/>

  <h1>casbin-fastapi-decorator</h1>

  <p>Authorization decorator factory for FastAPI based on <a href="https://casbin.org/">Casbin</a> and <a href="https://pypi.org/project/fastapi-decorators/">fastapi-decorators</a>.</p>

  [![PyPI](https://img.shields.io/pypi/v/casbin-fastapi-decorator?color=blue)](https://pypi.org/project/casbin-fastapi-decorator/)
  [![Python](https://img.shields.io/pypi/pyversions/casbin-fastapi-decorator)](https://pypi.org/project/casbin-fastapi-decorator/)
  [![PyPI Downloads](https://static.pepy.tech/personalized-badge/casbin-fastapi-decorator?period=total&units=INTERNATIONAL_SYSTEM&left_color=lightgrey&right_color=blue&left_text=downloads)](https://pepy.tech/projects/casbin-fastapi-decorator)
  [![License](https://img.shields.io/github/license/Neko1313/casbin-fastapi-decorator)](LICENSE)
  [![CI](https://img.shields.io/github/actions/workflow/status/Neko1313/casbin-fastapi-decorator/ci.yml?label=CI)](https://github.com/Neko1313/casbin-fastapi-decorator/actions)
  [![codecov](https://codecov.io/gh/Neko1313/casbin-fastapi-decorator/graph/badge.svg?token=05ZhOXGetg)](https://codecov.io/gh/Neko1313/casbin-fastapi-decorator)

  [📚 Documentation](https://neko1313.github.io/casbin-fastapi-decorator-docs/) · [PyPI](https://pypi.org/project/casbin-fastapi-decorator/) · [Casbin Ecosystem](https://casbin.org/ecosystem/)
</div>

---

Decorators are applied directly to routes — no middleware, no extra parameters in your function signatures.

## Why decorator, not middleware?

| Feature | **casbin-fastapi-decorator** | fastapi-authz / fastapi-casbin-auth |
|---|:---:|:---:|
| Approach | Decorator per route | Global middleware |
| Per-route permission config | ✅ | ❌ |
| Dynamic objects from request | ✅ `AccessSubject` | ❌ |
| No extra params in endpoint signature | ✅ | ❌ |
| Native FastAPI DI integration | ✅ | ⚠️ partial |
| JWT extras | ✅ | ❌ |
| DB-backed policies (SQLAlchemy async) | ✅ | ❌ |
| Casdoor OAuth2 integration | ✅ | ❌ |
| Works with `APIRouter` | ✅ | ✅ |

Middleware-based authorization checks every incoming request globally. With a decorator, you configure permissions exactly where the route is defined — no hidden side effects, no boilerplate dependencies in every function signature.

## Installation

```bash
pip install casbin-fastapi-decorator
```

Optional extras — install only what you need:

```bash
pip install "casbin-fastapi-decorator[jwt]"      # JWT authentication
pip install "casbin-fastapi-decorator[db]"       # Policies from DB (SQLAlchemy)
pip install "casbin-fastapi-decorator[casdoor]"  # Casdoor OAuth2
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

# 5. Dynamic check — object resolved from request
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
| `auth_required()` | Decorator: authentication only (user_provider must not raise) |
| `require_permission(*args)` | Decorator: permission check via `enforcer.enforce(user, *args)` |

### `AccessSubject`

```python
AccessSubject(
    val=get_item,                        # FastAPI dependency
    selector=lambda item: item["name"],  # transformation before enforce
)
```

Wraps a dependency whose value is resolved from the request and passed to the enforcer. By default, `selector` is identity (`lambda x: x`).

## JWT provider

[`casbin-fastapi-decorator-jwt`](packages/casbin-fastapi-decorator-jwt) — extracts and validates a JWT from the Bearer header and/or a cookie.

```bash
pip install "casbin-fastapi-decorator[jwt]"
```

See [packages/casbin-fastapi-decorator-jwt/README.md](packages/casbin-fastapi-decorator-jwt/README.md) for full API and usage.

## DB provider

[`casbin-fastapi-decorator-db`](packages/casbin-fastapi-decorator-db) — loads Casbin policies from a SQLAlchemy async session.

```bash
pip install "casbin-fastapi-decorator[db]"
```

See [packages/casbin-fastapi-decorator-db/README.md](packages/casbin-fastapi-decorator-db/README.md) for full API and usage.

## Casdoor provider

[`casbin-fastapi-decorator-casdoor`](packages/casbin-fastapi-decorator-casdoor) — Casdoor OAuth2 authentication and remote Casbin policy enforcement.

```bash
pip install "casbin-fastapi-decorator[casdoor]"
```

```python
from casbin_fastapi_decorator_casdoor import CasdoorEnforceTarget, CasdoorIntegration

casdoor = CasdoorIntegration(
    endpoint="http://localhost:8000",
    client_id="...", client_secret="...", certificate=cert,
    org_name="my_org", application_name="my_app",
    target=CasdoorEnforceTarget(
        enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer",
    ),
)
app.include_router(casdoor.router)   # GET /callback, POST /logout
guard = casdoor.create_guard()
```

`CasdoorEnforceTarget` selects the Casdoor enforce mode — by enforcer, permission, model, resource, or owner. Values can be static strings or callables resolved from the JWT payload at request time.

See [packages/casbin-fastapi-decorator-casdoor/README.md](packages/casbin-fastapi-decorator-casdoor/README.md) for full API, compose pattern, and usage.

## Examples

| Example | Description |
|---|---|
| [`examples/core`](examples/core) | Bearer token auth, file-based Casbin policies |
| [`examples/core-jwt`](examples/core-jwt) | JWT auth via `JWTUserProvider`, file-based policies |
| [`examples/core-db`](examples/core-db) | Bearer token auth, policies from SQLite via `DatabaseEnforcerProvider` |
| [`examples/core-casdoor`](examples/core-casdoor) | Casdoor OAuth2 auth + remote enforcement, facade and compose patterns |

## Development

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/), [task](https://taskfile.dev/).

```bash
task install           # uv sync --all-groups + install extras (jwt, db, casdoor)
task lint              # ruff + ty + bandit for all packages
task tests             # all tests (core + jwt + db + casdoor)
```

Individual package tasks:

```bash
task core:lint         task core:test
task jwt:lint          task jwt:test
task db:lint           task db:test         # requires Docker (testcontainers)
task casdoor:lint      task casdoor:test
```

## License

MIT
