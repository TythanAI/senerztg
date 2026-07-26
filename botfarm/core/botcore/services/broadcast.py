"""Mass messaging that respects Telegram's limits.

Telegram allows roughly 30 messages/second to distinct chats. Going faster
earns a 429 and, repeated, a temporary ban on the bot — so the sender is rate
limited, honours `retry_after`, and drops users who blocked the bot.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BroadcastReport:
    sent: int = 0
    failed: int = 0
    blocked: int = 0

    @property
    def total(self) -> int:
        return self.sent + self.failed + self.blocked


class Broadcaster:
    def __init__(self, bot: Bot, *, rate: int = 25) -> None:
        self.bot = bot
        self.delay = 1.0 / max(1, rate)
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def send(
        self,
        chat_ids: Sequence[int] | Iterable[int],
        text: str,
        *,
        keyboard: InlineKeyboardMarkup | None = None,
        on_blocked=None,
    ) -> BroadcastReport:
        report = BroadcastReport()
        self._running = True
        try:
            for chat_id in chat_ids:
                ok = await self._send_one(chat_id, text, keyboard, report, on_blocked)
                if ok is None:  # cancelled
                    break
                await asyncio.sleep(self.delay)
        finally:
            self._running = False
        log.info(
            "broadcast finished: %s sent, %s failed, %s blocked",
            report.sent,
            report.failed,
            report.blocked,
        )
        return report

    async def _send_one(
        self,
        chat_id: int,
        text: str,
        keyboard: InlineKeyboardMarkup | None,
        report: BroadcastReport,
        on_blocked,
    ) -> bool | None:
        for attempt in range(3):
            try:
                await self.bot.send_message(chat_id, text, reply_markup=keyboard)
                report.sent += 1
                return True
            except TelegramRetryAfter as exc:
                wait = exc.retry_after + 1
                log.warning("broadcast throttled, sleeping %ss", wait)
                await asyncio.sleep(wait)
            except TelegramForbiddenError:
                # User blocked the bot or deleted the account.
                report.blocked += 1
                if on_blocked is not None:
                    try:
                        await on_blocked(chat_id)
                    except Exception:  # pragma: no cover
                        log.exception("on_blocked hook failed for %s", chat_id)
                return False
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if attempt == 2:
                    log.warning("broadcast to %s failed: %s", chat_id, exc)
                    report.failed += 1
                    return False
                await asyncio.sleep(1 + attempt)
        report.failed += 1
        return False
