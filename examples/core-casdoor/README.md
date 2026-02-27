# Core + Casdoor Example

Full OAuth2 authentication and remote Casbin policy enforcement via
[`casbin-fastapi-decorator-casdoor`](../../packages/casbin-fastapi-decorator-casdoor).

## What it demonstrates

- `CasdoorIntegration` facade — one object wires the SDK, cookies, router, and guard
- `GET /callback` — OAuth2 code exchange; issues `access_token` + `refresh_token` cookies
- `POST /logout` — clears authentication cookies
- `guard.require_permission(resource, action)` — delegates policy check to Casdoor's
  remote `/api/enforce` endpoint using the seeded ACL enforcer
- `guard.auth_required()` — rejects requests without valid cookies

## Pre-seeded data (`casdoor/init_data.json`)

| Entity | Name | Details |
|---|---|---|
| Organization | `example-org` | plain-text passwords, base for all entities |
| Certificate | `cert-example` | 2048-bit RSA, used to sign JWTs |
| Application | `app-example` | `client_id=example-client-id`, redirect → `localhost:8080/callback` |
| User | `alice` / `alice123` | can **read** and **write** articles |
| User | `bob` / `bob123` | can **read** articles only |
| Casbin model | `model-acl` | ACL: `r.sub == p.sub && r.obj == p.obj && r.act == p.act` |
| Enforcer | `enforcer-example` | uses `model-acl` with Casdoor's permission table as adapter |
| Permissions | 3 entries | alice→read, alice→write, bob→read |

## Run

### 1 — Start Casdoor

```bash
docker compose up -d
```

The `casbin/casdoor-all-in-one` image bundles MySQL.
Casdoor loads `init_data.json` on every start (idempotent upsert).
Wait ~20 seconds for MySQL and Casdoor to finish initialising.

```bash
# Check readiness
curl -s http://localhost:8000/ | head -1
```

### 2 — Start the FastAPI app

```bash
uv run fastapi dev src/main.py --port 8080
```

### 3 — Try it (browser or curl)

Open `http://localhost:8080/` to get the Casdoor login URL, then:

```bash
# ── Step 1: get the login URL ────────────────────────────────────────────────
curl -s http://localhost:8080/ | python3 -m json.tool

# The response contains "login_url" — open it in a browser.
# Log in as alice / alice123.
# Casdoor redirects to http://localhost:8080/callback?code=...
# The app exchanges the code for tokens and sets cookies.

# ── Step 2: copy the cookies from the browser and use them below ─────────────
ACCESS=<paste access_token cookie value>
REFRESH=<paste refresh_token cookie value>

# ── Alice: read allowed ───────────────────────────────────────────────────────
curl -s http://localhost:8080/articles \
  -H "Cookie: access_token=$ACCESS; refresh_token=$REFRESH" | python3 -m json.tool

# ── Alice: write allowed ──────────────────────────────────────────────────────
curl -s -X POST http://localhost:8080/articles \
  -H "Cookie: access_token=$ACCESS; refresh_token=$REFRESH" \
  -H "Content-Type: application/json" \
  -d '{"title": "New article"}' | python3 -m json.tool

# ── Alice: identity ───────────────────────────────────────────────────────────
curl -s http://localhost:8080/me \
  -H "Cookie: access_token=$ACCESS; refresh_token=$REFRESH" | python3 -m json.tool

# ── Log out ───────────────────────────────────────────────────────────────────
curl -s -X POST http://localhost:8080/logout \
  -H "Cookie: access_token=$ACCESS; refresh_token=$REFRESH"

# ── Now repeat with Bob (bob / bob123) ────────────────────────────────────────
# GET /articles → 200 (bob can read)
# POST /articles → 403 (bob cannot write)
```

## Endpoints

| Method | Path | Auth | Permission | Description |
|---|---|---|---|---|
| `GET` | `/` | public | — | Returns Casdoor login URL |
| `GET` | `/callback` | public | — | OAuth2 callback; sets cookies |
| `POST` | `/logout` | public | — | Clears cookies |
| `GET` | `/me` | required | — | Returns decoded JWT payload |
| `GET` | `/articles` | required | `articles:read` | List articles |
| `POST` | `/articles` | required | `articles:write` | Create article |

## How policy enforcement works

```
Browser/Client
    │ cookies: access_token, refresh_token
    ▼
FastAPI  @guard.require_permission("articles", "read")
    │ CasdoorUserProvider validates both cookies via sdk.parse_jwt_token()
    │ returns access_token string as "user"
    ▼
CasdoorEnforcer.enforce(user="<jwt>", "articles", "read")
    │ parse_jwt_token(jwt) → {"owner": "example-org", "name": "alice", ...}
    │ user_path = "example-org/alice"
    │ target_kwargs = {"enforce_id": "example-org/enforcer-example"}
    ▼
Casdoor /api/enforce
    │ enforcer "example-org/enforcer-example"
    │   model:   r.sub == p.sub && r.obj == p.obj && r.act == p.act
    │   adapter: permission table (seeded from init_data.json)
    │   policies: [("example-org/alice","articles","read"), ...]
    │ casbin_request: ["example-org/alice", "articles", "read"]
    ▼
true → 200 OK   /   false → 403 Forbidden
```

## Customise `init_data.json`

To add a new user or change permissions, edit `casdoor/init_data.json` and restart:

```bash
docker compose restart casdoor
```

Casdoor upserts the data on startup (existing records are updated, new ones created).

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `401 Invalid token` | Wrong certificate in `authz.py` | Must match `cert-example` in `init_data.json` |
| `403 Forbidden` for alice | Enforcer not loaded yet | Restart Casdoor; check permissions in admin panel |
| `404` on `/callback` | Router not included | `app.include_router(casdoor.router)` |
| Login page shows wrong app | Wrong `org_name` / `app_name` | Must match `example-org` / `app-example` |
| Casdoor not ready | MySQL still initialising | Wait 20 s, retry `curl http://localhost:8000/` |
