# Core + DB Example

Example using `casbin-fastapi-decorator` with `DatabaseEnforcerProvider` to load Casbin policies from a SQLAlchemy database.

## What it demonstrates

- `DatabaseEnforcerProvider` loads policies from a DB table on each request
- Policies are seeded on startup and can be managed at runtime via the database
- Same auth as core example (Bearer token = role) — only the enforcer changes

## Casbin setup

- **casbin/model.conf** — basic model, matcher: `r.sub.role == p.sub`
- Policies come from SQLite DB (seeded on startup), not a CSV file

## Database setup

Uses SQLite (`aiosqlite`) for simplicity. On startup the app creates the `policies` table and seeds it:

| sub    | obj  | act    |
|--------|------|--------|
| admin  | post | read   |
| admin  | post | write  |
| admin  | post | delete |
| editor | post | read   |
| editor | post | write  |
| viewer | post | read   |

> In production replace `sqlite+aiosqlite` with `asyncpg` (PostgreSQL) or another async driver.

## Run

```bash
uv run fastapi dev src/main.py
```

## Endpoints

| Method | Path                | Permission     | Description                  |
|--------|---------------------|----------------|------------------------------|
| POST   | `/login`            | public         | Returns role as token        |
| GET    | `/me`               | auth only      | Returns current user         |
| GET    | `/articles`         | `post:read`    | List all posts               |
| POST   | `/articles`         | `post:write`   | Create a post                |
| DELETE | `/articles/{id}`    | `post:delete`  | Delete a post (admin only)   |
| GET    | `/policies`         | public         | View all policies from DB    |

## Try it

```bash
# View current policies from DB
curl http://localhost:8000/policies

# Get a token
TOKEN=$(curl -s -X POST "http://localhost:8000/login?role=admin" | jq -r '.')

# Authentication check
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# Permission checks
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "New post"}' \
  http://localhost:8000/articles
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/articles/1

# Try editor — write allowed, delete denied
TOKEN_ED=$(curl -s -X POST "http://localhost:8000/login?role=editor" | jq -r '.')
curl -X DELETE -H "Authorization: Bearer $TOKEN_ED" http://localhost:8000/articles/1  # 403
```
