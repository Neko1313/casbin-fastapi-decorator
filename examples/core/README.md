# Core Example

Minimal example using only `casbin-fastapi-decorator` with file-based Casbin policies.

## What it demonstrates

- `auth_required()` — authentication-only decorator
- `require_permission("resource", "action")` — static permission check
- `require_permission(AccessSubject(...), "action")` — dynamic permission check where the value is resolved from the request via FastAPI DI

## Casbin setup

- **model.conf** — RBAC model with role inheritance (`g = _, _`)
- **policy.csv** — policies and role assignments (alice=admin, bob=editor, charlie=viewer)

## Run

```bash
pip install casbin-fastapi-decorator uvicorn
uvicorn examples.core.main:app --reload
```

## Endpoints

| Method | Path                    | Permission        | Description                            |
|--------|-------------------------|-------------------|----------------------------------------|
| GET    | `/me`                   | auth only         | Returns current user                   |
| GET    | `/articles`             | `articles:read`   | List all articles                      |
| POST   | `/articles`             | `articles:write`  | Create an article                      |
| GET    | `/articles/{article_id}`| dynamic           | Read article (owner resolved from DI)  |

## Try it

```bash
# Authenticated endpoint
curl http://localhost:8000/me

# Static permission
curl http://localhost:8000/articles

# Dynamic permission (article owner is resolved and checked)
curl http://localhost:8000/articles/1
```

By default the app authenticates as `alice` (admin). Edit `get_current_user()` in `main.py` to switch users and test different permission levels.
