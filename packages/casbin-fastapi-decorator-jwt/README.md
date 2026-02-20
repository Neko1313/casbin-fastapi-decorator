# casbin-fastapi-decorator-jwt

JWT user provider for [casbin-fastapi-decorator](https://github.com/Neko1313/casbin-fastapi-decorator).

Extracts and validates a JWT from the Bearer header and/or a cookie, returning the payload as the current user.

## Installation

```bash
pip install casbin-fastapi-decorator-jwt
```

Or via the core package extra:

```bash
pip install "casbin-fastapi-decorator[jwt]"
```

## Usage

```python
from casbin_fastapi_decorator_jwt import JWTUserProvider

user_provider = JWTUserProvider(
    secret_key="your-secret",
    algorithm="HS256",             # default
    cookie_name="access_token",    # optional, enables reading from cookie
    user_model=UserSchema,         # optional, Pydantic model for payload validation
)
```

Pass it to `PermissionGuard` as the `user_provider`:

```python
import casbin
from fastapi import FastAPI, HTTPException
from casbin_fastapi_decorator import PermissionGuard

async def get_enforcer() -> casbin.Enforcer:
    return casbin.Enforcer("model.conf", "policy.csv")

guard = PermissionGuard(
    user_provider=user_provider,
    enforcer_provider=get_enforcer,
    error_factory=lambda user, *rv: HTTPException(403, "Forbidden"),
)

app = FastAPI()

@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles():
    return []
```

## API

### `JWTUserProvider`

```python
JWTUserProvider(
    secret_key: str,
    algorithm: str = "HS256",
    cookie_name: str | None = None,
    user_model: type[BaseModel] | None = None,
)
```

| Parameter | Description |
|---|---|
| `secret_key` | Secret used to verify the JWT signature |
| `algorithm` | JWT algorithm (default: `"HS256"`) |
| `cookie_name` | If set, also reads the token from this cookie name |
| `user_model` | Pydantic model — if provided, the payload is validated via `model_validate()` |

When called as a FastAPI dependency, the provider reads the token from:
1. `Authorization: Bearer <token>` header (always)
2. Cookie `<cookie_name>` (if `cookie_name` is set)

## Development

See the [workspace README](../../README.md) for setup instructions.

```bash
task jwt:lint    # ruff + bandit + ty
task jwt:test    # pytest
```
