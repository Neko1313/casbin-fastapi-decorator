# casbin-fastapi-decorator-file

File-based enforcer provider with hot-reload for [casbin-fastapi-decorator](https://github.com/Neko1313/casbin-fastapi-decorator).

Provides `CachedFileEnforcerProvider` — loads the casbin `Enforcer` once from `model.conf` + `policy.csv` and automatically reloads when either file changes on disk (via [watchdog](https://github.com/gorakhargosh/watchdog)).

## Install

```bash
pip install casbin-fastapi-decorator-file
```

## Usage

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from casbin_fastapi_decorator import PermissionGuard
from casbin_fastapi_decorator_file import CachedFileEnforcerProvider

provider = CachedFileEnforcerProvider(
    model_path="casbin/model.conf",
    policy_path="casbin/policy.csv",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with provider:   # starts file watcher
        yield              # stops file watcher on shutdown

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=provider,
    error_factory=lambda *_: HTTPException(403, "Forbidden"),
)

app = FastAPI(lifespan=lifespan)

@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles(): ...
```

Any change to `model.conf` or `policy.csv` is detected automatically — the enforcer reloads on the next request with zero downtime.
