"""Example: casbin-fastapi-decorator with CachedFileEnforcerProvider.

Demonstrates hot-reload: edit casbin/policy.csv while the app is running
and permission changes take effect on the next request — no restart needed.
"""
from pathlib import Path
from typing import Annotated

from auth import get_current_user
from authz import guard, lifespan
from fastapi import Depends, FastAPI, Form
from model import (
    Permission,
    PostCreatSchema,
    PostSchema,
    Resource,
    Role,
    UserSchema,
)

app = FastAPI(title="Core + File Hot-Reload Example", lifespan=lifespan)

MOCK_DB = [
    PostSchema(id=1, title="First Post"),
    PostSchema(id=2, title="Second Post"),
]


# --- Auth ---

@app.post("/login")
async def login(role: Role) -> str:
    """Return the role string as a Bearer token (demo only)."""
    return role


@app.get("/me")
@guard.auth_required()
async def me(
    user: Annotated[UserSchema, Depends(get_current_user)],
) -> UserSchema:
    """Return current user info."""
    return user


# --- Posts ---

@app.get("/articles")
@guard.require_permission(Resource.POST, Permission.READ)
async def list_posts() -> list[PostSchema]:
    """List all posts (requires post:read)."""
    return MOCK_DB


@app.post("/articles")
@guard.require_permission(Resource.POST, Permission.WRITE)
async def create_post(
    data: Annotated[PostCreatSchema, Form],
) -> PostSchema:
    """Create a post (requires post:write)."""
    pk = sorted(MOCK_DB, key=lambda p: p.id)[-1].id + 1
    post = PostSchema(id=pk, title=data.title)
    MOCK_DB.append(post)
    return post


@app.delete("/articles/{post_id}")
@guard.require_permission(Resource.POST, Permission.DELETE)
async def delete_post(post_id: int) -> dict:
    """Delete a post (requires post:delete)."""
    return {"id": post_id, "deleted": True}


# --- Hot-reload demo ---

@app.get("/policy")
async def current_policy() -> dict:
    """Show the current contents of policy.csv (for demo purposes)."""
    policy_path = Path("casbin/policy.csv")
    return {"policy": policy_path.read_text()}
