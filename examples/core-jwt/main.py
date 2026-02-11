"""Example using casbin-fastapi-decorator with JWT authentication."""

from pathlib import Path

import casbin
import jwt
from casbin_fastapi_decorator_jwt import JWTUserProvider
from fastapi import FastAPI, HTTPException

from casbin_fastapi_decorator import PermissionGuard

EXAMPLE_DIR = Path(__file__).parent

SECRET_KEY = "super-secret-key"  # noqa: S105
ALGORITHM = "HS256"


# --- JWT user provider ---

user_provider = JWTUserProvider(
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
)


# --- Casbin enforcer from files ---


async def get_enforcer() -> casbin.Enforcer:
    """Return a Casbin enforcer with file-based policies."""
    return casbin.Enforcer(
        str(EXAMPLE_DIR / "model.conf"),
        str(EXAMPLE_DIR / "policy.csv"),
    )


# --- Guard setup ---

guard = PermissionGuard(
    user_provider=user_provider,
    enforcer_provider=get_enforcer,
    error_factory=lambda _user, *_rvals: HTTPException(
        403, "Forbidden"
    ),
)

app = FastAPI(title="Core + JWT Example")


# --- Helper endpoint to generate tokens (for demo) ---


@app.post("/token")
async def login(username: str) -> dict:
    """Generate a JWT token for the given role."""
    token = jwt.encode(
        {"sub": username}, SECRET_KEY, algorithm=ALGORITHM
    )
    return {"access_token": token, "token_type": "bearer"}


# --- Protected routes ---


@app.get("/me")
@guard.auth_required()
async def me() -> dict:
    """Return current user info (valid JWT required)."""
    return {"message": "You are authenticated"}


@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles() -> list[dict]:
    """List all articles (requires articles:read)."""
    return [
        {"id": 1, "title": "First article"},
        {"id": 2, "title": "Second article"},
    ]


@app.post("/articles")
@guard.require_permission("articles", "write")
async def create_article() -> dict:
    """Create an article (requires articles:write)."""
    return {"id": 3, "title": "New article", "created": True}
