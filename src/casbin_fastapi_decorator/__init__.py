"""Casbin authorization decorator factory for FastAPI."""

from casbin_fastapi_decorator._guard import PermissionGuard
from casbin_fastapi_decorator._types import AccessSubject

__all__ = ["AccessSubject", "PermissionGuard"]
