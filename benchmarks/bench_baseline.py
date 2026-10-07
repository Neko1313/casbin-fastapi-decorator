# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi==0.142.2",
#   "casbin==1.43.0",
# ]
# ///
"""
Baseline: the same FastAPI app with **no** authorization layer.

Everything the other benchmarks report is measured against this floor,
so the numbers answer "how much does authorization cost", not "how fast
is FastAPI".  Casbin is installed but unused, only so the import cost of
the environment matches the others.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from fastapi import FastAPI
from harness import run_suite


def build_app(_model_path: str, _policy_path: str) -> Any:
    """Build an unguarded FastAPI app exposing the benchmark routes."""
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/profile")
    async def profile() -> dict[str, str]:
        return {"profile": "ok"}

    @app.get("/api/items")
    async def items() -> dict[str, str]:
        return {"items": "ok"}

    @app.get("/api/admin")
    async def admin() -> dict[str, str]:
        return {"admin": "ok"}

    return app


if __name__ == "__main__":
    run_suite(
        library="(none)",
        version=version("fastapi"),
        approach="none",
        build_app=build_app,
        supports_deny=False,
    )
