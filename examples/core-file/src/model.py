"""DTO schemas for the core-file example."""
from enum import StrEnum

from pydantic import BaseModel


class UserSchema(BaseModel):
    """User model."""

    role: str


class PostCreatSchema(BaseModel):
    """Post create schema."""

    title: str


class PostSchema(PostCreatSchema):
    """Post response schema."""

    id: int


class Permission(StrEnum):
    """Available permissions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class Resource(StrEnum):
    """Protected resources."""

    POST = "post"


class Role(StrEnum):
    """User roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
