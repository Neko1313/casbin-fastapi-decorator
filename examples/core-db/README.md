# Core + DB Example

Example using `casbin-fastapi-decorator` with `DatabaseEnforcerProvider` to load Casbin policies from a SQLAlchemy database.

## What it demonstrates

- `DatabaseEnforcerProvider` loads policies from a database table on each request
- `default_policies` are merged with DB policies (e.g. a built-in superadmin rule)
- Policies can be managed at runtime via the database
- **model.conf** is still a file — only policies come from the DB

## Database setup

Uses SQLite (`aiosqlite`) for simplicity. On startup the app creates the `policies` table and seeds it with sample data:

| sub     | obj      | act    |
|---------|----------|--------|
| admin   | articles | read   |
| admin   | articles | write  |
| admin   | articles | delete |
| editor  | articles | read   |
| editor  | articles | write  |
| viewer  | articles | read   |

## Run

```bash
pip install "casbin-fastapi-decorator[db]" aiosqlite uvicorn
uvicorn examples.core-db.main:app --reload
```

> `aiosqlite` is needed for the SQLite async driver. In production you would use `asyncpg` (PostgreSQL) or another async driver.

## Endpoints

| Method | Path                      | Permission         | Description                 |
|--------|---------------------------|--------------------|-----------------------------|
| GET    | `/me`                     | auth only          | Requires authentication     |
| GET    | `/articles`               | `articles:read`    | List articles               |
| POST   | `/articles`               | `articles:write`   | Create an article           |
| DELETE  | `/articles/{article_id}` | `articles:delete`  | Delete (admin only)         |
| GET    | `/policies`               | public             | View all policies from DB   |

## Try it

```bash
# Check current policies
curl http://localhost:8000/policies

# Authenticated endpoint (default user: alice/admin)
curl http://localhost:8000/me

# Permission checks
curl http://localhost:8000/articles
curl -X POST http://localhost:8000/articles
curl -X DELETE http://localhost:8000/articles/1
```

By default the app authenticates as `alice` (admin). Edit `get_current_user()` in `main.py` to switch users. For example, change to `charlie` (viewer) and the write/delete endpoints will return 403.
