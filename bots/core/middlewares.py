"""Middlewares: user registration, ban gate, anti-flood, error safety-net.

Registered as *outer* middlewares on the dispatcher so they run for every
update and, crucially, so a bug in any handler can never crash the bot.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from . import texts
from .services import Services

log = logging.getLogger("core.mw")


def _user_from_event(event: TelegramObject):
    return getattr(event, "from_user", None)


class UserMiddleware(BaseMiddleware):
    """Register/refresh the user and expose a ban gate."""

    async def __call__(self, handler, event: Update, data: Dict[str, Any]) -> Any:
        services: Services = data["services"]
        inner = event.message or event.callback_query or event.pre_checkout_query
        user = getattr(inner, "from_user", None)
        if user is not None and not user.is_bot:
            try:
                await services.db.upsert_user(
                    user.id, user.username or "", (user.full_name or "")[:128]
                )
            except Exception as exc:
                log.warning("upsert_user failed: %s", exc)
            if await services.db.is_banned(user.id):
                if event.callback_query:
                    await event.callback_query.answer(texts.BANNED, show_alert=True)
                return None  # swallow the update
        return await handler(event, data)


class AntiFloodMiddleware(BaseMiddleware):
    """Cheap per-user throttle. Drops bursts, keeps the bot responsive."""

    def __init__(self, rate: float = 0.5):
        self._rate = rate
        self._last: Dict[int, float] = {}

    async def __call__(self, handler, event: Update, data: Dict[str, Any]) -> Any:
        inner = event.message or event.callback_query
        user = getattr(inner, "from_user", None)
        if user is not None:
            now = time.monotonic()
            prev = self._last.get(user.id, 0.0)
            if now - prev < self._rate:
                if event.callback_query:
                    try:
                        await event.callback_query.answer(texts.ANTIFLOOD)
                    except Exception:
                        pass
                return None
            self._last[user.id] = now
            # Opportunistic cleanup so the dict cannot grow forever.
            if len(self._last) > 10000:
                cutoff = now - 3600
                self._last = {k: v for k, v in self._last.items() if v > cutoff}
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """Last line of defence: no handler exception ever reaches the poller."""

    async def __call__(self, handler, event: Update, data: Dict[str, Any]) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            log.exception("Unhandled error while processing update")
            try:
                if event.callback_query:
                    await event.callback_query.answer(texts.ERROR_GENERIC, show_alert=True)
                elif event.message:
                    await event.message.answer(texts.ERROR_GENERIC)
            except Exception:
                pass
            return None
