"""Auth type application."""
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from model import UserSchema

HEADER_AUTH_SCHEME = HTTPBearer(auto_error=False)

async def get_current_user(
    header_auth: Annotated[
        HTTPAuthorizationCredentials | None, Security(HEADER_AUTH_SCHEME)
    ],
) -> UserSchema:
    """Get current user."""
    if not header_auth:
        raise HTTPException(401, "Unauthorized")

    return UserSchema(role=header_auth.credentials)
