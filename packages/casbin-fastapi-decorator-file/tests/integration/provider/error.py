"""Integration tests — CachedFileEnforcerProvider denial cases."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from casbin_fastapi_decorator_file import CachedFileEnforcerProvider
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from casbin_fastapi_decorator import PermissionGuard

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

_ACL_MODEL = """\
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
"""


def _build_app(provider: CachedFileEnforcerProvider) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async with provider:
            yield

    guard = PermissionGuard(
        user_provider=lambda: "alice",
        enforcer_provider=provider,
        error_factory=lambda *_: HTTPException(403, "Forbidden"),
    )

    app = FastAPI(lifespan=lifespan)

    @app.get("/data/read")
    @guard.require_permission("data", "read")
    async def read_data() -> dict:
        return {"ok": True}

    @app.get("/data/write")
    @guard.require_permission("data", "write")
    async def write_data() -> dict:
        return {"ok": True}

    return app


@pytest.fixture
def model_path(tmp_path: Path) -> Path:
    path = tmp_path / "model.conf"
    path.write_text(_ACL_MODEL)
    return path


@pytest.fixture
def empty_policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy.csv"
    path.write_text("")
    return path


@pytest.fixture
def partial_policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy.csv"
    path.write_text("p, alice, data, read\n")
    return path


@pytest.mark.integration
@pytest.mark.file_provider
async def test_denies_all_when_policy_empty(
    model_path: Path, empty_policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=empty_policy_path,
    )
    app = _build_app(provider)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/data/read")).status_code == 403
        assert (await client.get("/data/write")).status_code == 403


@pytest.mark.integration
@pytest.mark.file_provider
async def test_denies_unlisted_action(
    model_path: Path, partial_policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=partial_policy_path,
    )
    app = _build_app(provider)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/data/read")).status_code == 200
        assert (await client.get("/data/write")).status_code == 403
