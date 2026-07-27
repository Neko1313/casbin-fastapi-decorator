# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi-authz==1.0.0",
#   "fastapi==0.140.2",
#   "casbin==1.43.0",
# ]
# ///
"""
``fastapi-authz``: ASGI middleware enforcing on ``(user, path, method)``.

FastAPI and casbin are pinned to the same versions as the baseline and
the decorator benchmark so that only the authorization layer differs.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from fastapi_authz import CasbinMiddleware
from harness import run_suite
from middleware_app import build_middleware_app


def build_app(model_path: str, policy_path: str) -> Any:
    """Build a FastAPI app guarded by ``fastapi_authz.CasbinMiddleware``."""
    return build_middleware_app(CasbinMiddleware, model_path, policy_path)


if __name__ == "__main__":
    run_suite(
        library="fastapi-authz",
        version=version("fastapi-authz"),
        approach="middleware",
        build_app=build_app,
    )
