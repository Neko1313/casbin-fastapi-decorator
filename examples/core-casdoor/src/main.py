"""Example: casbin-fastapi-decorator with Casdoor OAuth2 + remote enforcement."""
from typing import Annotated
from urllib.parse import urlencode

from authz import _APP, _CLIENT_ID, _ENDPOINT, _ORG, casdoor, guard
from fastapi import Depends, FastAPI
from model import ArticleCreateSchema, ArticleSchema, Permission, Resource

app = FastAPI(title="Core + Casdoor Example")

# Register GET /callback and POST /logout provided by the Casdoor integration.
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
    """Return the Casdoor login URL so the user knows where to start."""
    params = urlencode(
        {
            "client_id": _CLIENT_ID,
            "response_type": "code",
            "redirect_uri": "http://localhost:8080/callback",
            "scope": "read",
            "state": "example",
        }
    )
    login_url = (
        f"{_ENDPOINT}/login/oauth/authorize?"
        f"organizationName={_ORG}&applicationName={_APP}&{params}"
    )
    return {
        "message": "Log in via Casdoor to access protected endpoints.",
        "login_url": login_url,
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
    from casdoor import AsyncCasdoorSDK  # noqa: PLC0415

    sdk: AsyncCasdoorSDK = casdoor.sdk
    return sdk.parse_jwt_token(token)
