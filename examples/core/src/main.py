"""Minimal example using only casbin-fastapi-decorator core."""
from typing import Annotated

from auth import get_current_user
from authz import guard, lifespan
from fastapi import Depends, FastAPI, Form, HTTPException
from model import (
    Permission,
    PostCreatSchema,
    PostSchema,
    Resource,
    Role,
    UserSchema,
)

app = FastAPI(title="Core Example", lifespan=lifespan)

MOCK_DB = [
    PostSchema(
        id=1,
        title="First Post",
    ),
    PostSchema(
        id=2,
        title="Second Post",
    ),
]


def article_not_found_error(
    _user: UserSchema,
    *_rvals: object,
) -> HTTPException:
    """Return a route-specific error for denied draft access."""
    return HTTPException(status_code=404, detail="Article not found")


# --- Routes ---

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
async def list_post() -> list[PostSchema]:
    """List all posts."""
    return MOCK_DB


@app.get("/articles/draft")
@guard.require_permission(
    Resource.POST,
    Permission.WRITE,
    error_factory=article_not_found_error,
)
async def read_draft() -> dict[str, str]:
    """Return draft post with route-specific denial error."""
    return {"title": "Draft Post"}


@app.post("/articles")
@guard.require_permission(Resource.POST, Permission.WRITE)
async def create_article(
    data: Annotated[PostCreatSchema, Form],
) -> PostSchema:
    """Create port (requires articles:write)."""
    pk = sorted(MOCK_DB, key=lambda post: post.id)[-1].id + 1
    model = PostSchema(
        id=pk,
        title=data.title
    )
    MOCK_DB.append(model)
    return model
