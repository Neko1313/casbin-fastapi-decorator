"""DTOs for the core-casdoor example."""
from enum import StrEnum

from pydantic import BaseModel


class ArticleCreateSchema(BaseModel):
    """Article create payload."""

    title: str


class ArticleSchema(ArticleCreateSchema):
    """Article response."""

    id: int


class Permission(StrEnum):
    """Available actions."""

    READ = "read"
    WRITE = "write"


class Resource(StrEnum):
    """Protected resources."""

    ARTICLES = "articles"
