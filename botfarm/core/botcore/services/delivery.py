"""Fulfilment: what the buyer actually receives once the money lands.

Five product kinds, five behaviours:
  account       — issue N units from stock, exactly once, with a warranty
  digital       — send text / file / link straight away
  subscription  — extend access, then send the welcome payload
  service       — confirm and hand the lead to the operator
  consult       — confirm and offer a booking link
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile, URLInputFile

from ..config import NicheConfig
from ..db import Order, OutOfStock, Repos, User
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
        low_stock_threshold: int = 3,
    ) -> None:
        self.config = config
        self.t = t
        self.assets_dir = Path(assets_dir).resolve()
        self.admin_ids = admin_ids
        self.low_stock_threshold = low_stock_threshold

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
            if product.kind == "account":
                await self._deliver_accounts(repos, bot, order, user, product)
            elif product.kind == "subscription":
                await self._deliver_subscription(repos, bot, order, user, product)
            elif product.kind in {"service", "consult"}:
                await self._deliver_service(repos, bot, order, user, product)
            else:
                await self._deliver_digital(bot, user, product)
        except OutOfStock as exc:
            # Money arrived but inventory is gone. Never silently keep it.
            log.error("order %s: %s", order.id, exc)
            order.status = "paid"
            order.note = f"out of stock: {exc.available}/{exc.requested}"
            await repos.session.flush()
            await self._safe_send(bot, user.tg_id, self.t("delivery.out_of_stock"))
            await self._notify_admins(
                bot,
                f"🚨 Заказ #{order.id} оплачен, но товара нет на складе "
                f"({exc.available} из {exc.requested} шт., SKU <code>{esc(exc.sku)}</code>).\n"
                f"Покупатель: {esc(user.display())} (<code>{user.tg_id}</code>). "
                "Пополните склад и выдайте вручную или верните деньги.",
            )
            return False
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

    async def _deliver_accounts(
        self, repos: Repos, bot: Bot, order: Order, user: User, product: Any
    ) -> None:
        """Issue N units of stock — the account-shop path.

        Already-issued units are reused so a repeat delivery hands over the
        same credentials instead of burning fresh inventory.
        """
        already = await repos.stock.issued_for(order.id)
        needed = max(1, order.quantity) - len(already)
        payloads = list(already)
        if needed > 0:
            payloads += await repos.stock.issue(product.sku, needed, order.id)

        header = self.t(
            "delivery.accounts",
            title=esc(product.title),
            count=len(payloads),
        )
        # Credentials are user-supplied text going into an HTML message —
        # escape or a stray '<' silently truncates the whole delivery.
        body = "\n\n".join(f"<code>{esc(item)}</code>" for item in payloads)
        await self._safe_send(bot, user.tg_id, f"{header}\n\n{body}")

        instructions = (product.delivery or {}).get("text")
        if instructions:
            await self._safe_send(bot, user.tg_id, truncate(str(instructions)))

        warranty = (product.delivery or {}).get("warranty")
        if warranty:
            await self._safe_send(bot, user.tg_id, f"🛡 {esc(warranty)}")

        left = await repos.stock.available(product.sku)
        if left <= self.low_stock_threshold:
            await self._notify_admins(
                bot,
                f"📉 Мало товара: <code>{esc(product.sku)}</code> — осталось {left} шт.",
            )

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
                # Keep delivery inside assets/: a config saying "../../.env"
                # must not turn a purchase into a file-read of the server.
                full = (self.assets_dir / path).resolve()
                if not full.is_relative_to(self.assets_dir):
                    raise ValueError(f"{path!r} escapes the assets directory")
                document = FSInputFile(str(full))
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
