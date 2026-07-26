"""Background loops: reconcile pending invoices, expire stale orders, renew.

Webhooks get lost — the VPS reboots, TLS expires, a provider retries once and
gives up. Polling every minute is what makes the difference between "the bot
mostly works" and "no customer ever has to open a support ticket about a
payment that went through".
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import TYPE_CHECKING

from aiogram import Bot

from ..config import NicheConfig
from ..db import Database, Repos, User
from ..i18n import Translator
from ..utils import fmt_date

if TYPE_CHECKING:  # pragma: no cover
    from .checkout import CheckoutService

log = logging.getLogger(__name__)


class BackgroundJobs:
    def __init__(
        self,
        db: Database,
        bot: Bot,
        checkout: "CheckoutService",
        config: NicheConfig,
        t: Translator,
        *,
        poll_interval: int = 60,
        renew_interval: int = 6 * 3600,
        throttle=None,
        keep_events_days: int = 90,
    ) -> None:
        self.db = db
        self.bot = bot
        self.checkout = checkout
        self.config = config
        self.t = t
        self.poll_interval = poll_interval
        self.renew_interval = renew_interval
        self.throttle = throttle
        self.keep_events_days = keep_events_days
        self._tasks: list[asyncio.Task] = []

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = [
            asyncio.create_task(self._loop(self.reconcile, self.poll_interval, "reconcile")),
            asyncio.create_task(
                self._loop(self.subscription_reminders, self.renew_interval, "renewals")
            ),
            asyncio.create_task(self._loop(self.housekeeping, 3600, "housekeeping")),
        ]
        log.info("background jobs started")

    async def housekeeping(self) -> int:
        """Reclaim what would otherwise grow without bound.

        A long-running bot accumulates two things forever: per-user throttle
        buckets in memory, and analytics rows on disk. Neither is dangerous in
        a day and both are a slow denial of service over a year.
        """
        dropped = 0
        if self.throttle is not None:
            dropped = self.throttle.prune()

        async with self.db.session() as session:
            repos = Repos(session)
            events = await repos.misc.prune_events(keep_days=self.keep_events_days)

        if dropped or events:
            log.info("housekeeping: %s throttle buckets, %s old events", dropped, events)
        return dropped + events

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: B014 - shutdown is best-effort
                pass
        self._tasks.clear()
        log.info("background jobs stopped")

    async def _loop(self, coro, interval: int, name: str) -> None:
        # Stagger the first run so 300 bots on one VPS do not wake together.
        await asyncio.sleep(min(interval, 15))
        while True:
            try:
                await coro()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("background job %s failed", name)
            await asyncio.sleep(interval)

    async def reconcile(self) -> int:
        """Re-check every pending invoice, then expire what timed out."""
        settled = 0
        async with self.db.session() as session:
            repos = Repos(session)
            pending = await repos.orders.pending(limit=100)

            for order in pending:
                if not order.external_id:
                    continue
                provider = self.checkout.registry.get(order.provider)
                if provider is None or provider.native:
                    continue  # Stars/Telegram Payments confirm by update, not by poll

                result = await self.checkout.poll(repos, order, order.user)
                if result.is_paid:
                    if await self.checkout.settle(repos, self.bot, order, result):
                        settled += 1
                        try:
                            await self.bot.send_message(
                                order.user.tg_id, self.t("checkout.paid")
                            )
                        except Exception:  # pragma: no cover
                            pass

            expired = await repos.orders.expire_stale()

        if settled or expired:
            log.info("reconcile: %s settled, %s expired", settled, expired)
        return settled

    async def subscription_reminders(self) -> int:
        """Warn once, 48 hours out, that access is about to lapse."""
        if not self.config.has("subscription"):
            return 0

        now = dt.datetime.now(dt.timezone.utc)
        notified = 0
        async with self.db.session() as session:
            repos = Repos(session)
            for sub in await repos.subs.expiring_within(hours=48):
                if sub.notified_at is not None:
                    last = sub.notified_at
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=dt.timezone.utc)
                    if (now - last).total_seconds() < 72 * 3600:
                        continue

                owner = await session.get(User, sub.user_id)
                if owner is None:
                    continue

                try:
                    await self.bot.send_message(
                        owner.tg_id,
                        self.t(
                            "subscription.expiring",
                            sku=sub.sku,
                            until=fmt_date(sub.expires_at, self.config.lang),
                        ),
                    )
                    sub.notified_at = now
                    notified += 1
                except Exception as exc:  # pragma: no cover
                    log.info("renewal reminder to %s failed: %s", owner.tg_id, exc)

        if notified:
            log.info("renewal reminders sent: %s", notified)
        return notified
