# core-file example

Demonstrates `CachedFileEnforcerProvider` from [`casbin-fastapi-decorator-file`](../../packages/casbin-fastapi-decorator-file).

The enforcer is **loaded once** at startup and **hot-reloaded automatically** when `casbin/model.conf` or `casbin/policy.csv` changes on disk — no restart required.

## Run

```bash
cd examples/core-file
uv run fastapi dev src/main.py
```

## Try it

```bash
# Login (returns a role as a Bearer token)
TOKEN=$(curl -s -X POST "http://localhost:8000/login?role=admin" | tr -d '"')

# Access protected endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles

# View current policy
curl http://localhost:8000/policy
```

## Hot-reload demo

While the app is running, edit `casbin/policy.csv` and add or remove permissions. On the next request the enforcer reloads automatically — changes take effect immediately.

```bash
# Remove viewer read-access (while app is running):
echo "p, admin, post, read
p, admin, post, write
p, editor, post, read
p, editor, post, write" > casbin/policy.csv

# Viewer is now denied:
curl -H "Authorization: Bearer viewer" http://localhost:8000/articles
# → 403 Forbidden
```

## Key pattern

```python
# authz.py
from casbin_fastapi_decorator_file import CachedFileEnforcerProvider

enforcer_provider = CachedFileEnforcerProvider(
    model_path="casbin/model.conf",
    policy_path="casbin/policy.csv",
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with enforcer_provider:   # starts watchdog
        yield                       # stops watchdog on shutdown

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=enforcer_provider,
    error_factory=lambda *_: HTTPException(403, "Forbidden"),
)
```
