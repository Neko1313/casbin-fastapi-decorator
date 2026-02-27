# casbin-fastapi-decorator-casdoor

Casdoor OAuth2 authentication and Casbin authorization for [casbin-fastapi-decorator](https://github.com/Neko1313/casbin-fastapi-decorator).

## Installation

```bash
pip install casbin-fastapi-decorator-casdoor
# or as an optional extra:
pip install "casbin-fastapi-decorator[casdoor]"
```

## Quick start — facade

```python
from fastapi import FastAPI
from casbin_fastapi_decorator_casdoor import CasdoorEnforceTarget, CasdoorIntegration

casdoor = CasdoorIntegration(
    endpoint="http://localhost:8000",
    client_id="...",
    client_secret="...",
    certificate=cert,        # PEM string from Casdoor → Application → Cert
    org_name="my_org",
    application_name="my_app",
    target=CasdoorEnforceTarget(
        # enforce_id is resolved per-request from the user's JWT
        enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer",
    ),
)

app = FastAPI()
app.include_router(casdoor.router)   # GET /callback, POST /logout
guard = casdoor.create_guard()

@app.get("/protected")
@guard.require_permission("resource", "read")
async def protected():
    return {"ok": True}
```

## CasdoorEnforceTarget

Selects **which Casdoor API identifier** to use for `/api/enforce`.
Exactly one field must be set — static string or a callable that receives
the parsed JWT payload.

```python
from casbin_fastapi_decorator_casdoor import CasdoorEnforceTarget

# By enforcer (dynamic — org taken from the user's JWT)
CasdoorEnforceTarget(
    enforce_id=lambda parsed: f"{parsed['owner']}/my_enforcer"
)

# By enforcer (static)
CasdoorEnforceTarget(enforce_id="my_org/my_enforcer")

# By permission object
CasdoorEnforceTarget(permission_id="my_org/can_edit_posts")

# By Casbin model
CasdoorEnforceTarget(model_id="my_org/rbac_model")

# By resource
CasdoorEnforceTarget(resource_id="my_org/articles_resource")

# By owner (all policies of the organisation)
CasdoorEnforceTarget(owner="my_org")
```

## Manual composition

For advanced use cases — custom `user_factory`, multiple guards with
different targets, or fine-grained error handling — compose the building
blocks directly:

```python
from casdoor import AsyncCasdoorSDK
from fastapi import HTTPException
from casbin_fastapi_decorator import PermissionGuard
from casbin_fastapi_decorator_casdoor import (
    CasdoorEnforceTarget,
    CasdoorEnforcerProvider,
    CasdoorUserProvider,
    make_casdoor_router,
)

sdk = AsyncCasdoorSDK(endpoint=..., client_id=..., ...)

# Custom user identity: use e-mail instead of "owner/name"
def email_factory(parsed: dict) -> str:
    return parsed["email"]

target = CasdoorEnforceTarget(enforce_id="my_org/my_enforcer")

user_provider     = CasdoorUserProvider(sdk=sdk)
enforcer_provider = CasdoorEnforcerProvider(
    sdk=sdk,
    target=target,
    user_factory=email_factory,
)
router = make_casdoor_router(sdk=sdk, redirect_after_login="/docs")

guard = PermissionGuard(
    user_provider=user_provider,
    enforcer_provider=enforcer_provider,
    error_factory=lambda user, *rv: HTTPException(403, "Forbidden"),
)
```

## Components

### `CasdoorIntegration`

Main facade. Accepts all Casdoor SDK parameters plus:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `target` | required | :class:`CasdoorEnforceTarget` — which Casdoor API identifier to use |
| `access_token_cookie` | `"access_token"` | Cookie name for the access token |
| `refresh_token_cookie` | `"refresh_token"` | Cookie name for the refresh token |
| `redirect_after_login` | `"/"` | Path or absolute URL to redirect after OAuth2 callback. Relative (`"/"`) stays on the same host; absolute (`"https://app.example.com/"`) redirects to another host. |
| `cookie_secure` | `True` | Set `Secure` flag on cookies |
| `cookie_httponly` | `True` | Set `HttpOnly` flag on cookies |
| `cookie_samesite` | `"lax"` | `SameSite` policy (`"lax"`, `"strict"`, `"none"`) |
| `cookie_domain` | `None` | `Domain` attribute. Use `".example.com"` to share cookies across subdomains (e.g. `*.my-site.ru`) |
| `cookie_path` | `"/"` | `Path` attribute of the cookie |
| `cookie_max_age` | `None` | `Max-Age` in seconds; `None` = session cookie |
| `router_prefix` | `""` | URL prefix for `/callback` and `/logout` |

### `CasdoorUserProvider`

FastAPI dependency that validates both `access_token` and `refresh_token`
cookies via `sdk.parse_jwt_token()` and returns the raw `access_token` string.

Accepts optional `unauthorized_error` and `invalid_token_error` factories
for custom HTTP responses.

### `CasdoorEnforcerProvider`

FastAPI dependency that returns a shared `CasdoorEnforcer`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sdk` | required | `AsyncCasdoorSDK` instance |
| `target` | required | :class:`CasdoorEnforceTarget` |
| `user_factory` | `"{owner}/{name}"` | Callable `(parsed_jwt) -> str` |

### `make_casdoor_router`

Factory that returns a `fastapi.APIRouter` with two endpoints:

- `GET {prefix}/callback` — exchanges OAuth2 code for tokens, sets cookies
- `POST {prefix}/logout` — clears authentication cookies

> **Security note — OAuth2 state / CSRF.**
> The `state` query parameter sent by Casdoor is accepted but **not validated**.
> This is an intentional trade-off for stateless deployments.
> If your threat model requires CSRF protection, implement state validation
> yourself: generate a nonce before redirecting to Casdoor, store it in a
> short-lived cookie or session, and verify it in the callback handler before
> exchanging the code.
