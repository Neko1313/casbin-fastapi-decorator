"""Bearer-token authentication for the core-file example."""
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
    """Return the current user extracted from the Bearer token."""
    if not header_auth:
        raise HTTPException(401, "Unauthorized")
    return UserSchema(role=header_auth.credentials)
