"""
File-based enforcer provider with hot-reload for casbin-fastapi-decorator.
"""  # noqa: D200

from casbin_fastapi_decorator_file._provider import CachedFileEnforcerProvider

__all__ = ["CachedFileEnforcerProvider"]
