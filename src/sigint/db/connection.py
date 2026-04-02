"""Async database connection pool using asyncpg."""

from __future__ import annotations

import asyncpg

from sigint.config import Settings

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


async def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the asyncpg connection pool, creating it lazily on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        settings = Settings()  # type: ignore[call-arg]
        _pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
    return _pool
