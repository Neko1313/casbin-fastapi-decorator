## Project Overview

`casbin-fastapi-decorator` is a FastAPI authorization library built on [casbin](https://casbin.org/) and [fastapi-decorators](https://github.com/nilssonr/fastapi-decorators). It provides a `PermissionGuard` factory that creates endpoint decorators for authentication and permission enforcement via dependency injection.

The workspace is a **uv monorepo** with:
- Core package: `src/casbin_fastapi_decorator/`
- Optional extensions: `packages/casbin-fastapi-decorator-jwt/` and `packages/casbin-fastapi-decorator-db/`
- Examples: `examples/core/`, `examples/core-jwt/`, `examples/core-db/`

## Commands

This project uses [Task](https://taskfile.dev) as the task runner. See `taskfile.dist.yaml` for all tasks.

```bash
# Install all dependencies (all workspace members and groups)
task install

# Lint the core package (ruff + bandit + ty)
task core:lint

# Run core tests with coverage
task core:test

# Lint all packages
task lint

# Test all packages
task tests
```

Run a single test file or marker:
```bash
task core:test PYTEST_ARGS="tests/unit/ -m unit"
task core:test PYTEST_ARGS="tests/integration/ -m integration"
task core:test PYTEST_ARGS="tests/ -k test_name"
```

Generate CI reports (XML/JSON artifacts):
```bash
task core:lint CI=true
task core:test CI=true
```

> **RULE: All linting and testing MUST be run exclusively via `task` commands.**
> Never invoke linters or test runners directly (e.g. `ruff`, `bandit`, `ty`, `pytest`, `uv run pytest`).
> The only permitted entry points are `task` targets defined in `taskfile.dist.yaml`.

## Architecture

The core is ~150 lines across 4 files:

- **`_types.py`** — `AccessSubject` dataclass: wraps a FastAPI dependency (`val`) with an optional `selector` function for extracting values from resolved dependencies.
- **`_guard.py`** — `PermissionGuard` factory: takes `user_provider`, `enforcer_provider`, and `error_factory` dependencies; exposes `auth_required()` and `require_permission(*args)` methods that return FastAPI endpoint decorators.
- **`_builder.py`** — Decorator builders called by `PermissionGuard`. `build_permission_decorator()` resolves all FastAPI dependencies, applies `selector` to `AccessSubject` values, calls `enforcer.enforce(user, *rvals)` (supporting both sync and async enforcers), and raises errors via `error_factory` on denial.
- **`__init__.py`** — Public API: exports `PermissionGuard` and `AccessSubject`.

**Key design pattern:** `PermissionGuard` is a factory (not a decorator itself). It stores shared providers and returns new decorators per-route. The decorators use `fastapi_decorators.depends()` to integrate with FastAPI's DI system.

## Code Style

Configured via `ruff.toml` (line length: 79, target Python: 3.10). Linting enforces many rule sets including ANN (type annotations) and D (docstrings) for non-test code. Tests relax ANN, D, S105, B008, and PLR2004.

## Testing

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. Integration tests spin up a real FastAPI app and use `httpx.AsyncClient`.

Pytest markers: `unit`, `integration`, `permission_guard`, `access_subject` — defined in `pyproject.toml`.

The DB package tests require Docker (testcontainers-postgres).

## Enforcer Provider Design Principle: Singleton + Async Context Manager

All enforcer providers that manage internal state (cached enforcer, file watcher, background
tasks) **must** follow the singleton provider pattern:

1. **Singleton instance** — the provider is created once at module level (or app startup)
   and reused across all requests.  Never create a new provider per-request.
2. **Caching** — the `casbin.Enforcer` is built once on the first `__call__` and cached
   in `self._enforcer`.  Subsequent calls return the cached instance.
3. **`asyncio.Lock` with double-checked locking** — prevents concurrent reloads when
   multiple requests trigger a stale check simultaneously:
   ```python
   if self._needs_reload or self._enforcer is None:
       async with self._lock:
           if self._needs_reload or self._enforcer is None:
               await self._reload()
   ```
4. **Async context manager for lifecycle** — file watchers and background polling tasks
   are started in `__aenter__` and stopped in `__aexit__`.  Users wire this into the
   FastAPI `lifespan`:
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
       async with enforcer_provider:
           yield
   ```
5. **Thread-safe dirty flag** — watchdog callbacks run in a background thread and set
   `self._needs_reload = True`.  This is safe because CPython's GIL makes boolean
   assignment atomic.  Never acquire `asyncio.Lock` from a watchdog callback.
6. **Blocking I/O in thread pool** — `casbin.Enforcer(...)` reads files from disk;
   always run it via `asyncio.to_thread(...)` to avoid blocking the event loop.

### Provider-specific reload triggers

| Package | File watch | Background poll |
|---|---|---|
| `casbin-fastapi-decorator-file` | `model.conf` + `policy.csv` (watchdog) | — |
| `casbin-fastapi-decorator-db` | `model.conf` only (watchdog) | DB hash every `poll_interval` s |
| `casbin-fastapi-decorator-casdoor` | — | — (remote API, always fresh) |

## Sub-package Development

Each package under `packages/` has its own `pyproject.toml` and task definitions (referenced as `task jwt:lint`, `task db:lint`, `task file:lint`, etc.). They reference the core package as a workspace dependency.
