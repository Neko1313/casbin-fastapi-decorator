"""Example using casbin-fastapi-decorator with JWT authentication."""
from typing import Annotated

import jwt
from auth import ALGORITHM, SECRET_KEY, user_provider
from authz import guard
from fastapi import Depends, FastAPI, Form
from model import (
    Permission,
    PostCreatSchema,
    PostSchema,
    Resource,
    Role,
    UserSchema,
)

app = FastAPI(title="Core + JWT Example")

MOCK_DB = [
    PostSchema(id=1, title="First Post"),
    PostSchema(id=2, title="Second Post"),
]


@app.post("/login")
async def login(role: Role) -> str:
    """Generate a JWT token for the given role."""
    return jwt.encode({"role": role}, SECRET_KEY, algorithm=ALGORITHM)


@app.get("/me")
@guard.auth_required()
async def me(
    user: Annotated[UserSchema, Depends(user_provider)],
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
