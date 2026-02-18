"""Truncate all public tables before each integration test."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest_asyncio.fixture(scope="function")
async def db_cleanup(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public'"
            )
        )
        tables = [row[0] for row in result]
        if tables:
            await conn.execute(
                text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
            )
