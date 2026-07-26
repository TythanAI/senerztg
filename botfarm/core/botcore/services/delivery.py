"""Fulfilment: what the buyer actually receives once the money lands.

Four product kinds, four behaviours:
  digital       — send text / file / link straight away
  subscription  — extend access, then send the welcome payload
  service       — confirm and hand the lead to the operator
  consult       — confirm and offer a booking link
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile, URLInputFile

from ..config import NicheConfig
from ..db import Order, Repos, User
from ..i18n import Translator
from ..utils import esc, fmt_date, truncate

log = logging.getLogger(__name__)


class DeliveryService:
    def __init__(
        self,
        config: NicheConfig,
        t: Translator,
        *,
        assets_dir: str = "assets",
        admin_ids: tuple[int, ...] = (),
    ) -> None:
        self.config = config
        self.t = t
        self.assets_dir = assets_dir
        self.admin_ids = admin_ids

    async def deliver(self, repos: Repos, bot: Bot, order: Order, user: User) -> bool:
        """Fulfil a paid order. Never raises — a failure is reported, not fatal."""
        product = self.config.product(order.sku)
        if product is None:
            log.error("order %s: SKU %r is no longer in the catalog", order.id, order.sku)
            await self._notify_admins(
                bot, f"⚠️ Заказ #{order.id}: товар {order.sku} отсутствует в каталоге."
            )
            await self._safe_send(bot, user.tg_id, self.t("delivery.fallback"))
            return False

        try:
            if product.kind == "subscription":
                await self._deliver_subscription(repos, bot, order, user, product)
            elif product.kind in {"service", "consult"}:
                await self._deliver_service(repos, bot, order, user, product)
            else:
                await self._deliver_digital(bot, user, product)
        except Exception:
            log.exception("order %s: delivery failed", order.id)
            await self._notify_admins(
                bot,
                f"⚠️ Заказ #{order.id} оплачен, но доставка не удалась. "
                f"Покупатель: {esc(user.display())} ({user.tg_id}). Выдайте вручную.",
            )
            return False

        order.status = "delivered"
        order.delivered_at = dt.datetime.now(dt.timezone.utc)
        await repos.session.flush()
        await repos.misc.track(user.tg_id, "delivered", order.sku)
        return True

    # ----------------------------------------------------------- per kind

    async def _deliver_digital(self, bot: Bot, user: User, product: Any) -> None:
        delivery = product.delivery or {}
        text = delivery.get("text") or product.description or self.t("delivery.fallback")

        await self._safe_send(
            bot,
            user.tg_id,
            self.t("delivery.digital", title=esc(product.title), payload=text),
        )

        for link in _as_list(delivery.get("links")):
            await self._safe_send(bot, user.tg_id, str(link))

        for path in _as_list(delivery.get("files")):
            await self._send_file(bot, user.tg_id, str(path), product.title)

        invite = delivery.get("invite_link")
        if invite:
            await self._safe_send(bot, user.tg_id, f"🔐 {invite}")

    async def _deliver_subscription(
        self, repos: Repos, bot: Bot, order: Order, user: User, product: Any
    ) -> None:
        sub = await repos.subs.grant(user.id, product.sku, product.period_days)
        await self._safe_send(
            bot,
            user.tg_id,
            self.t(
                "delivery.subscription",
                title=esc(product.title),
                until=fmt_date(sub.expires_at, self.config.lang),
            ),
        )

        delivery = product.delivery or {}
        if delivery.get("text"):
            await self._safe_send(bot, user.tg_id, truncate(str(delivery["text"])))
        invite = delivery.get("invite_link")
        if invite:
            await self._safe_send(bot, user.tg_id, f"🔐 {invite}")

    async def _deliver_service(
        self, repos: Repos, bot: Bot, order: Order, user: User, product: Any
    ) -> None:
        await repos.misc.add_lead(
            user.id,
            kind=product.kind,
            payload={"sku": product.sku, "order_id": order.id, "title": product.title},
        )
        await self._safe_send(
            bot, user.tg_id, self.t("delivery.service", title=esc(product.title))
        )

        booking = (product.delivery or {}).get("booking_url")
        if booking:
            await self._safe_send(bot, user.tg_id, f"📅 {booking}")

        await self._notify_admins(
            bot,
            f"📇 Новая заявка по услуге «{esc(product.title)}»\n"
            f"Заказ #{order.id}, клиент {esc(user.display())} (<code>{user.tg_id}</code>)",
        )

    # ------------------------------------------------------------- helpers

    async def _send_file(self, bot: Bot, chat_id: int, path: str, caption: str) -> None:
        try:
            if path.startswith(("http://", "https://")):
                document: Any = URLInputFile(path)
            else:
                full = f"{self.assets_dir}/{path}" if not path.startswith("/") else path
                document = FSInputFile(full)
            await bot.send_document(chat_id, document, caption=truncate(caption, 900))
        except Exception as exc:
            log.error("could not send %s to %s: %s", path, chat_id, exc)
            raise

    async def _safe_send(self, bot: Bot, chat_id: int, text: str) -> bool:
        try:
            await bot.send_message(chat_id, truncate(text))
            return True
        except Exception as exc:
            log.warning("send to %s failed: %s", chat_id, exc)
            return False

    async def _notify_admins(self, bot: Bot, text: str) -> None:
        for admin_id in self.admin_ids:
            try:
                await bot.send_message(admin_id, text)
            except Exception:  # pragma: no cover
                pass


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
