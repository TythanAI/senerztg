"""Engine/session wiring. SQLite by default, Postgres by env var."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

log = logging.getLogger(__name__)


class Database:
    """Owns the engine and hands out sessions."""

    def __init__(self, url: str, echo: bool = False) -> None:
        self.url = url
        kwargs: dict = {"echo": echo, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            # aiosqlite has no real pool; pre_ping/pool sizing do not apply.
            kwargs.pop("pool_pre_ping")
        self.engine: AsyncEngine = create_async_engine(url, **kwargs)

        if url.startswith("sqlite"):
            self._install_sqlite_pragmas()
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    def _install_sqlite_pragmas(self) -> None:
        """Make SQLite behave under concurrency.

        Default SQLite serialises on a single writer lock and fails a
        contending transaction immediately with "database is locked". Two
        buyers tapping the same product at once is normal traffic for a shop
        bot, so WAL (readers never block the writer) plus a busy timeout
        (a contending writer waits instead of erroring) are not tuning —
        they are what makes concurrent purchases work at all.
        """

        @event.listens_for(self.engine.sync_engine, "connect")
        def _set_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=10000")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
            # Hand transaction control to us so the "begin" hook below can
            # choose the locking mode; otherwise the driver opens its own.
            dbapi_connection.isolation_level = None

        @event.listens_for(self.engine.sync_engine, "begin")
        def _begin_immediate(conn):  # pragma: no cover - driver hook
            """Take the write lock up front.

            A default DEFERRED transaction starts as a reader and asks for the
            write lock later. If another writer got there first, SQLite fails
            that upgrade with SQLITE_BUSY *immediately* — busy_timeout does not
            apply to it, because waiting could deadlock. The result is that two
            people buying at once, one loses with an error instead of queueing.
            BEGIN IMMEDIATE acquires the lock at the start, where the timeout
            does apply, so the second buyer waits their turn. Costs some read
            concurrency; a shop bot would rather queue than drop a sale.
            """
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("database ready: %s", self._safe_url())

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Session that commits on success and rolls back on error."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _safe_url(self) -> str:
        """URL with the password stripped, safe for logs."""
        url = self.url
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            creds, host = rest.rsplit("@", 1)
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
        return url
