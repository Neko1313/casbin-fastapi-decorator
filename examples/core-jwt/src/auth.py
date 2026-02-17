"""Auth via JWT."""
from casbin_fastapi_decorator_jwt import JWTUserProvider

from model import UserSchema

SECRET_KEY = "super-secret-key"  # noqa: S105
ALGORITHM = "HS256"

user_provider = JWTUserProvider(
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    user_model=UserSchema,
)
