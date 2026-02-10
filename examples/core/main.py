"""Minimal example using only casbin-fastapi-decorator core."""

from pathlib import Path

import casbin
from fastapi import FastAPI, HTTPException

from casbin_fastapi_decorator import AccessSubject, PermissionGuard

EXAMPLE_DIR = Path(__file__).parent

# --- Fake user database ---

USERS = {
    "alice": {"sub": "alice", "role": "admin"},
    "bob": {"sub": "bob", "role": "editor"},
    "charlie": {"sub": "charlie", "role": "viewer"},
}


# --- FastAPI dependencies ---


async def get_current_user() -> dict:
    """Simulate authentication."""
    return USERS["alice"]


async def get_enforcer() -> casbin.Enforcer:
    """Return a Casbin enforcer with file-based policies."""
    return casbin.Enforcer(
        str(EXAMPLE_DIR / "model.conf"),
        str(EXAMPLE_DIR / "policy.csv"),
    )


# --- Guard setup ---

guard = PermissionGuard(
    user_provider=get_current_user,
    enforcer_provider=get_enforcer,
    error_factory=lambda _user, *_rvals: HTTPException(
        403, "Forbidden"
    ),
)

app = FastAPI(title="Core Example")


# --- Routes ---


@app.get("/me")
@guard.auth_required()
async def me() -> dict:
    """Return current user info."""
    return {"message": "You are authenticated"}


@app.get("/articles")
@guard.require_permission("articles", "read")
async def list_articles() -> list[dict]:
    """List all articles (requires articles:read)."""
    return [
        {"id": 1, "title": "First article", "author": "alice"},
        {"id": 2, "title": "Second article", "author": "bob"},
    ]


@app.post("/articles")
@guard.require_permission("articles", "write")
async def create_article() -> dict:
    """Create an article (requires articles:write)."""
    return {"id": 3, "title": "New article", "created": True}


# --- Dynamic permission with AccessSubject ---

ARTICLES_DB = {
    1: {"id": 1, "title": "First article", "owner": "alice"},
    2: {"id": 2, "title": "Second article", "owner": "bob"},
}


async def get_article(article_id: int) -> dict:
    """Fetch an article by ID or raise 404."""
    article = ARTICLES_DB.get(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@app.get("/articles/{article_id}")
@guard.require_permission(
    AccessSubject(
        val=get_article, selector=lambda a: a["owner"]
    ),
    "read",
)
async def read_article(article_id: int) -> dict:
    """Read a single article (owner resolved via DI)."""
    return ARTICLES_DB[article_id]
