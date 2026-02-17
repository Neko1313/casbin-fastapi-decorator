"""DTO fastapi app."""
from enum import StrEnum

from pydantic import BaseModel


class UserSchema(BaseModel):
    """User model."""

    role: str


class PostCreatSchema(BaseModel):
    """Post create model."""

    title: str


class PostSchema(PostCreatSchema):
    """Post model."""

    id: int


class Permission(StrEnum):
    """Permission model."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class Resource(StrEnum):
    """Resource model."""

    POST = "post"


class Role(StrEnum):
    """Role model."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
