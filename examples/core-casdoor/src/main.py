"""Example: casbin-fastapi-decorator with Casdoor OAuth2 + remote enforcement."""
from typing import Annotated

from authz import casdoor, guard
from casdoor import AsyncCasdoorSDK
from fastapi import Depends, FastAPI
from model import ArticleCreateSchema, ArticleSchema, Permission, Resource

app = FastAPI(title="Core + Casdoor Example")

# Register GET /login, GET /callback and POST /logout provided by the integration.
app.include_router(casdoor.router)

# ---------------------------------------------------------------------------
# Mock database
# ---------------------------------------------------------------------------
MOCK_DB: list[ArticleSchema] = [
    ArticleSchema(id=1, title="First Article"),
    ArticleSchema(id=2, title="Second Article"),
]


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> dict:
    """Return a welcome message with a link to start the OAuth2 flow."""
    return {
        "message": "Log in via Casdoor to access protected endpoints.",
        "login_url": "/login",
        "users": {
            "alice": {"password": "alice123", "can": ["read", "write"]},
            "bob": {"password": "bob123", "can": ["read"]},
        },
    }


# ---------------------------------------------------------------------------
# Protected endpoints
# ---------------------------------------------------------------------------


@app.get("/articles")
@guard.require_permission(Resource.ARTICLES, Permission.READ)
async def list_articles() -> list[ArticleSchema]:
    """List all articles (requires articles:read)."""
    return MOCK_DB


@app.post("/articles", status_code=201)
@guard.require_permission(Resource.ARTICLES, Permission.WRITE)
async def create_article(
    data: Annotated[ArticleCreateSchema, Depends()],
) -> ArticleSchema:
    """Create an article (requires articles:write)."""
    pk = max(a.id for a in MOCK_DB) + 1
    article = ArticleSchema(id=pk, title=data.title)
    MOCK_DB.append(article)
    return article


@app.get("/me")
@guard.auth_required()
async def me(
    token: Annotated[str, Depends(casdoor.user_provider)],
) -> dict:
    """Return the raw access-token payload (just to show auth works)."""
    sdk: AsyncCasdoorSDK = casdoor.sdk
    return sdk.parse_jwt_token(token)
