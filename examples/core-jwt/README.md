# Core + JWT Example

Example using `casbin-fastapi-decorator` with `JWTUserProvider` for JWT Bearer authentication and file-based Casbin policies.

## What it demonstrates

- `JWTUserProvider` decodes a JWT and maps claims to `UserSchema` via `user_model`
- JWT payload carries `role` directly — same matcher as the core example: `r.sub.role == p.sub`
- `auth_required()` — rejects requests with missing or invalid tokens
- `require_permission(Resource, Permission)` — checks permissions using the role from the token

## Casbin setup

- **casbin/model.conf** — basic model, matcher: `r.sub.role == p.sub`
- **casbin/policy.csv** — policies for `admin`, `editor`, `viewer` roles on `post` resource

## Run

```bash
uv run fastapi dev src/main.py
```

## Endpoints

| Method | Path        | Permission   | Description                    |
|--------|-------------|--------------|--------------------------------|
| POST   | `/login`    | public       | Generate a JWT for a given role |
| GET    | `/me`       | auth only    | Returns current user            |
| GET    | `/articles` | `post:read`  | List all posts                  |
| POST   | `/articles` | `post:write` | Create a post                   |

## Try it

```bash
# Get a JWT token for admin
TOKEN=$(curl -s -X POST "http://localhost:8000/login?role=admin" | jq -r '.')

# Authentication check
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# Permission check — allowed (admin has post:read)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles

# Permission check — allowed (admin has post:write)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "New post"}' \
  http://localhost:8000/articles

# Try viewer — read allowed, write denied
TOKEN_VIEW=$(curl -s -X POST "http://localhost:8000/login?role=viewer" | jq -r '.')
curl -H "Authorization: Bearer $TOKEN_VIEW" http://localhost:8000/articles          # 200
curl -X POST -H "Authorization: Bearer $TOKEN_VIEW" \
  -H "Content-Type: application/json" \
  -d '{"title": "New post"}' \
  http://localhost:8000/articles  # 403
```
