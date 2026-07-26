"""Middlewares: DB session, user resolution, anti-flood, error shielding."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from .db import Database, Repos
from .utils import parse_start_payload

log = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Opens one transaction per update and injects `repos`."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.db.session() as session:
            data["session"] = session
            data["repos"] = Repos(session)
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Upserts the Telegram user, applies the ban list, records the referrer."""

    def __init__(self, admin_ids: tuple[int, ...], default_lang: str = "ru") -> None:
        self.admin_ids = set(admin_ids)
        self.default_lang = default_lang

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        repos: Repos = data["repos"]

        referrer_id: int | None = None
        source: str | None = None
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            parts = event.text.split(maxsplit=1)
            if len(parts) == 2:
                referrer_id, source = parse_start_payload(parts[1])

        user, created = await repos.users.get_or_create(
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            lang=self.default_lang,
            referrer_id=referrer_id,
            source=source,
        )

        if user.is_banned:
            log.info("blocked banned user %s", user.tg_id)
            return None

        if user.is_blocked:
            # They are talking to us again, so broadcasts can resume.
            user.is_blocked = False

        if tg_user.id in self.admin_ids and not user.is_admin:
            user.is_admin = True

        data["user"] = user
        data["is_admin"] = user.is_admin or tg_user.id in self.admin_ids
        data["is_new_user"] = created
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Per-user token bucket. Protects the acquirer APIs from tap-spam."""

    def __init__(self, rate: float = 0.6, burst: int = 5, warn_every: float = 5.0) -> None:
        self.rate = rate
        self.burst = burst
        self.warn_every = warn_every
        self._tokens: dict[int, float] = defaultdict(lambda: float(burst))
        self._last: dict[int, float] = {}
        self._warned: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        uid = tg_user.id
        now = time.monotonic()
        elapsed = now - self._last.get(uid, now)
        self._last[uid] = now

        tokens = min(self.burst, self._tokens[uid] + elapsed / self.rate)
        if tokens < 1:
            self._tokens[uid] = tokens
            if now - self._warned.get(uid, 0) > self.warn_every:
                self._warned[uid] = now
                t = data.get("t")
                text = t("errors.flood") if t else "Too many requests."
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer(text, show_alert=False)
                    elif isinstance(event, Message):
                        await event.answer(text)
                except Exception:  # pragma: no cover - best effort
                    pass
            return None

        self._tokens[uid] = tokens - 1
        return await handler(event, data)

    def prune(self, max_age: float = 3600) -> int:
        """Drop idle buckets so a long-lived bot does not leak memory."""
        now = time.monotonic()
        stale = [uid for uid, seen in self._last.items() if now - seen > max_age]
        for uid in stale:
            self._last.pop(uid, None)
            self._tokens.pop(uid, None)
            self._warned.pop(uid, None)
        return len(stale)


class ContextMiddleware(BaseMiddleware):
    """Injects the immutable per-bot objects into every handler."""

    def __init__(self, **context: Any) -> None:
        self.context = context

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data.update(self.context)
        return await handler(event, data)


class ErrorShieldMiddleware(BaseMiddleware):
    """Last line of defence: one broken handler must not kill the poller."""

    def __init__(self, notify_admins: tuple[int, ...] = ()) -> None:
        self.notify_admins = notify_admins

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except asyncio.CancelledError:
            raise
        except Exception:
            update_id = event.update_id if isinstance(event, Update) else "?"
            log.exception("unhandled error while processing update %s", update_id)

            t = data.get("t")
            text = t("common.error") if t else "Something went wrong."
            inner = getattr(event, "event", None) if isinstance(event, Update) else event
            try:
                if isinstance(inner, CallbackQuery):
                    await inner.answer(text, show_alert=True)
                elif isinstance(inner, Message):
                    await inner.answer(text)
            except Exception:  # pragma: no cover - the chat may be gone
                pass
            return None
