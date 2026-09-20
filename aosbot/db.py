"""Lazily-created asyncpg pool. Only the sentiment bot needs this now."""

from __future__ import annotations

import os

import asyncpg

_POOL: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is None:
        dsn = os.getenv("AOS_EVENTS_DB_URL") or os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Set AOS_EVENTS_DB_URL or DATABASE_URL for Postgres connection")
        _POOL = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    return _POOL
