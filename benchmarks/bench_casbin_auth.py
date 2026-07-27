# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi-casbin-auth==1.5.0",
# ]
# ///
"""
``fastapi-casbin-auth``: a repackaging of ``fastapi-authz``.

Its ``CasbinMiddleware`` is byte-identical to the one in
``fastapi-authz``; the only difference is that every transitive
dependency is pinned to an exact version (``fastapi==0.121.2``,
``pycasbin==2.6.0``).  Those pins are why this benchmark cannot declare
its own FastAPI/casbin versions — the resolved ones are reported in the
JSON output so the comparison stays honest.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from fastapi_casbin_auth import CasbinMiddleware
from harness import run_suite
from middleware_app import build_middleware_app


def build_app(model_path: str, policy_path: str) -> Any:
    """Build an app guarded by ``fastapi_casbin_auth.CasbinMiddleware``."""
    return build_middleware_app(CasbinMiddleware, model_path, policy_path)


if __name__ == "__main__":
    run_suite(
        library="fastapi-casbin-auth",
        version=version("fastapi-casbin-auth"),
        approach="middleware",
        build_app=build_app,
    )
