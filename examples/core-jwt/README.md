# Core + JWT Example

Example using `casbin-fastapi-decorator` with `JWTUserProvider` for Bearer token authentication and file-based Casbin policies.

## What it demonstrates

- `JWTUserProvider` extracts and validates JWT from the `Authorization: Bearer <token>` header
- `auth_required()` — rejects requests without a valid JWT
- `require_permission()` — checks permissions using the `sub` claim from the token

## Casbin setup

- **model.conf** — RBAC model with role inheritance
- **policy.csv** — `alice` has admin role (read + write), `bob` has viewer role (read only)

## Run

```bash
pip install "casbin-fastapi-decorator[jwt]" uvicorn
uvicorn examples.core-jwt.main:app --reload
```

## Endpoints

| Method | Path        | Permission       | Description                  |
|--------|-------------|------------------|------------------------------|
| POST   | `/token`    | public           | Generate a JWT for a user    |
| GET    | `/me`       | auth only        | Requires valid JWT           |
| GET    | `/articles` | `articles:read`  | List articles                |
| POST   | `/articles` | `articles:write` | Create an article            |

## Try it

```bash
# Get a token for alice (admin)
TOKEN=$(curl -s -X POST "http://localhost:8000/token?username=alice" | jq -r .access_token)

# Authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# Permission check — allowed (admin has articles:read)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles

# Permission check — allowed (admin has articles:write)
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles

# Now try with bob (viewer — read only)
TOKEN_BOB=$(curl -s -X POST "http://localhost:8000/token?username=bob" | jq -r .access_token)

# Allowed (viewer has articles:read)
curl -H "Authorization: Bearer $TOKEN_BOB" http://localhost:8000/articles

# Denied — 403 (viewer has no articles:write)
curl -X POST -H "Authorization: Bearer $TOKEN_BOB" http://localhost:8000/articles
```
