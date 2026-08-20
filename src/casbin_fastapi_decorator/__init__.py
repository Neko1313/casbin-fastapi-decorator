"""Casbin authorization decorator factory for FastAPI."""

from casbin_fastapi_decorator._guard import PermissionGuard
from casbin_fastapi_decorator._types import AccessSubject, AnyOf

__all__ = ["AccessSubject", "AnyOf", "PermissionGuard"]
