"""Integration tests — CachedFileEnforcerProvider with real files and FastAPI."""
from __future__ import annotations

import asyncio
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

_WATCHDOG_SETTLE = 0.5  # seconds to wait for watchdog to pick up file changes


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
def policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy.csv"
    path.write_text("p, alice, data, read\n")
    return path


@pytest.mark.integration
@pytest.mark.file_provider
async def test_enforcer_loaded_and_request_allowed(
    model_path: Path, policy_path: Path
) -> None:
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    app = _build_app(provider)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/data/read")
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.file_provider
async def test_policy_change_picked_up_by_watchdog(
    model_path: Path, policy_path: Path
) -> None:
    """After overwriting policy.csv the enforcer reloads on the next call."""
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    async with provider:
        enforcer_before = await provider()
        assert enforcer_before.enforce("alice", "data", "write") is False

        # Grant write-access by updating the policy file
        policy_path.write_text(
            "p, alice, data, read\np, alice, data, write\n"
        )
        await asyncio.sleep(_WATCHDOG_SETTLE)

        enforcer_after = await provider()
        assert enforcer_after.enforce("alice", "data", "write") is True
        assert enforcer_before is not enforcer_after


@pytest.mark.integration
@pytest.mark.file_provider
async def test_model_change_picked_up_by_watchdog(
    model_path: Path, policy_path: Path
) -> None:
    """After overwriting model.conf the enforcer reloads with the new model."""
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    async with provider:
        enforcer_before = await provider()
        assert enforcer_before.enforce("alice", "data", "read") is True

        # Replace model with an always-deny matcher (sub must be "nobody")
        deny_model = _ACL_MODEL.replace(
            "m = r.sub == p.sub && r.obj == p.obj && r.act == p.act",
            'm = r.sub == "nobody"',
        )
        model_path.write_text(deny_model)
        policy_path.write_text("p, alice, data, read\n")
        await asyncio.sleep(_WATCHDOG_SETTLE)

        enforcer_after = await provider()
        assert enforcer_before is not enforcer_after
        assert enforcer_after.enforce("alice", "data", "read") is False


@pytest.mark.integration
@pytest.mark.file_provider
async def test_provider_works_without_context_manager(
    model_path: Path, policy_path: Path
) -> None:
    """Provider caches enforcer even when used without lifespan."""
    provider = CachedFileEnforcerProvider(
        model_path=model_path,
        policy_path=policy_path,
    )
    e1 = await provider()
    e2 = await provider()
    assert e1 is e2
