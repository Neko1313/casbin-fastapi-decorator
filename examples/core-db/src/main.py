"""Example using casbin-fastapi-decorator with DB-backed policies."""
from typing import Annotated

from auth import get_current_user
from authz import guard
from db import Policy, async_session, lifespan
from fastapi import Depends, FastAPI, Form
from model import (
    Permission,
    PostCreatSchema,
    PostSchema,
    Resource,
    Role,
    UserSchema,
)
from sqlalchemy import select

app = FastAPI(title="Core + DB Example", lifespan=lifespan)

MOCK_DB = [
    PostSchema(id=1, title="First Post"),
    PostSchema(id=2, title="Second Post"),
]


@app.post("/login")
async def login(role: Role) -> str:
    """Log user in."""
    return role


@app.get("/me")
@guard.auth_required()
async def me(
    user: Annotated[UserSchema, Depends(get_current_user)],
) -> UserSchema:
    """Return current user info."""
    return user


@app.get("/articles")
@guard.require_permission(Resource.POST, Permission.READ)
async def list_posts() -> list[PostSchema]:
    """List all posts."""
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


@app.get("/policies")
async def list_policies() -> list[dict]:
    """View all policies from the database."""
    async with async_session() as session:
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
    return [{"sub": p.sub, "obj": p.obj, "act": p.act} for p in policies]
