"""
db.py — SQLAlchemy async engine + session factory.
Default: SQLite (aiosqlite) — zero-dependency local dev.
Switch to Postgres by setting DATABASE_URL=postgresql+asyncpg://...
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Build engine — no pool_pre_ping for SQLite (unsupported), yes for Postgres
_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    **({} if _is_sqlite else {"pool_pre_ping": True, "pool_size": 5}),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables. Called at app startup."""
    from app import models  # noqa: F401 — ensure models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine. Called at app shutdown."""
    await engine.dispose()
