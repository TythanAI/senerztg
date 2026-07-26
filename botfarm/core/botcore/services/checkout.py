"""Checkout: create an order, bill it, and settle it exactly once.

`settle()` is the single funnel through which every rail confirms a payment —
webhook, polling, Telegram's `successful_payment`, or an admin tapping confirm.
It is idempotent by construction: the ledger has a unique index on
(provider, external_id) and the order only leaves `pending` once.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from aiogram import Bot

from ..config import NicheConfig, Product
from ..db import Order, Repos, User
from ..payments import (
    Invoice,
    InvoiceKind,
    OrderContext,
    PaymentError,
    PaymentResult,
    PaymentStatus,
    ProviderRegistry,
)
from ..utils import apply_discount, esc, fmt_money

if TYPE_CHECKING:  # pragma: no cover
    from .delivery import DeliveryService

log = logging.getLogger(__name__)


class CheckoutService:
    def __init__(
        self,
        config: NicheConfig,
        registry: ProviderRegistry,
        delivery: "DeliveryService",
        *,
        admin_ids: tuple[int, ...] = (),
        bot_username: str = "",
    ) -> None:
        self.config = config
        self.registry = registry
        self.delivery = delivery
        self.admin_ids = admin_ids
        self.bot_username = bot_username

    # ---------------------------------------------------------------- orders

    async def create_order(
        self,
        repos: Repos,
        user: User,
        product: Product,
        provider: str,
        *,
        discount_percent: int = 0,
    ) -> Order:
        amount = apply_discount(Decimal(product.price), discount_percent)
        order = await repos.orders.create(
            user=user,
            sku=product.sku,
            title=product.title,
            amount=amount,
            currency=self.config.currency,
            provider=provider,
            ttl_minutes=self.config.payments.invoice_ttl_minutes,
        )
        if discount_percent:
            order.note = f"promo -{discount_percent}%"
        await repos.misc.track(user.tg_id, "checkout_started", product.sku)
        return order

    async def bill(self, repos: Repos, order: Order, user: User) -> Invoice:
        """Ask the provider for an invoice and remember its external id."""
        provider = self.registry.require(order.provider)
        ctx = self.context_for(order, user)
        invoice = await provider.create_invoice(ctx)

        order.external_id = invoice.external_id
        order.pay_url = invoice.url or None
        if invoice.expires_at is not None:
            order.expires_at = invoice.expires_at
        await repos.session.flush()
        return invoice

    def context_for(self, order: Order, user: User) -> OrderContext:
        product = self.config.product(order.sku)
        return OrderContext(
            order_id=order.id,
            user_tg_id=user.tg_id,
            sku=order.sku,
            title=order.title or (product.title if product else order.sku),
            description=(product.description if product else "")[:255],
            amount=Decimal(order.amount),
            currency=order.currency,
            return_url=f"https://t.me/{self.bot_username}" if self.bot_username else "",
            lang=self.config.lang,
        )

    # -------------------------------------------------------------- checking

    async def poll(self, repos: Repos, order: Order, user: User) -> PaymentResult:
        """Ask the provider whether this order has been paid."""
        provider = self.registry.get(order.provider)
        if provider is None or not order.external_id:
            return PaymentResult(status=PaymentStatus.PENDING)
        try:
            return await provider.check(order.external_id, self.context_for(order, user))
        except PaymentError as exc:
            log.warning("order %s: status check failed: %s", order.id, exc)
            return PaymentResult(status=PaymentStatus.PENDING)

    # -------------------------------------------------------------- settling

    async def settle(
        self,
        repos: Repos,
        bot: Bot,
        order: Order,
        result: PaymentResult,
        *,
        deliver: bool = True,
    ) -> bool:
        """Book a confirmed payment. Returns True only on the first success."""
        if not result.is_paid:
            return False

        if not self._amount_ok(order, result):
            log.error(
                "order %s: amount mismatch — expected %s %s, provider reported %s %s",
                order.id,
                order.amount,
                order.currency,
                result.amount,
                result.currency,
            )
            order.note = f"amount mismatch: {result.amount} {result.currency}"
            await self._alert_admins(
                bot,
                f"⚠️ Заказ #{order.id}: сумма не совпала "
                f"({result.amount} {result.currency} вместо {order.amount} {order.currency}). "
                "Проверьте вручную.",
            )
            return False

        external_id = result.external_id or order.external_id or f"order-{order.id}"
        payment = await repos.payments.record(
            order=order,
            provider=order.provider,
            external_id=external_id,
            amount=result.amount if result.amount is not None else Decimal(order.amount),
            currency=result.currency or order.currency,
            raw=result.raw,
        )
        if payment is None:
            log.info("order %s: payment %s already booked — skipping", order.id, external_id)
            return False

        if not await repos.orders.mark_paid(order):
            log.info("order %s: already left pending state", order.id)
            return False

        user = order.user
        await repos.misc.track(user.tg_id, "paid", order.sku)
        log.info(
            "order %s settled: %s %s via %s (user %s)",
            order.id,
            order.amount,
            order.currency,
            order.provider,
            user.tg_id,
        )

        await self._pay_referral(repos, bot, order, user)

        if deliver:
            await self.delivery.deliver(repos, bot, order, user)

        await self._alert_admins(
            bot,
            f"💰 Оплата #{order.id}\n"
            f"{esc(order.title)} — <b>{fmt_money(order.amount, order.currency)}</b>\n"
            f"Способ: {order.provider}\n"
            f"Покупатель: {esc(user.display())} (<code>{user.tg_id}</code>)",
        )
        return True

    def _amount_ok(self, order: Order, result: PaymentResult) -> bool:
        """Guard against a spoofed or partial payment."""
        if result.amount is None:
            return True  # provider did not report an amount (Stars, manual)
        if result.currency and order.currency and result.currency.upper() not in {
            order.currency.upper(),
            "TON",  # on-chain rails settle in coin, already rate-checked
            "XTR",
        }:
            return False
        if result.currency.upper() in {"TON", "XTR"}:
            return True
        # Allow a one-cent rounding drift, reject genuine underpayment.
        return Decimal(result.amount) >= Decimal(order.amount) - Decimal("0.01")

    async def _pay_referral(self, repos: Repos, bot: Bot, order: Order, user: User) -> None:
        percent = self.config.referral_percent
        if percent <= 0 or not user.referrer_id:
            return

        referrer = await repos.users.get(user.referrer_id)
        if referrer is None:
            return

        bonus = (Decimal(order.amount) * Decimal(percent) / Decimal(100)).quantize(Decimal("0.01"))
        if bonus <= 0:
            return

        await repos.users.add_balance(referrer.id, bonus)
        referrer.referral_earned = Decimal(referrer.referral_earned) + bonus
        await repos.session.flush()

        try:
            await bot.send_message(
                referrer.tg_id,
                self.delivery.t(
                    "referral.bonus", amount=fmt_money(bonus, order.currency)
                ),
            )
        except Exception as exc:  # pragma: no cover - referrer may have blocked us
            log.info("could not notify referrer %s: %s", referrer.tg_id, exc)

    async def _alert_admins(self, bot: Bot, text: str) -> None:
        for admin_id in self.admin_ids:
            try:
                await bot.send_message(admin_id, text)
            except Exception as exc:  # pragma: no cover
                log.warning("could not alert admin %s: %s", admin_id, exc)

    # -------------------------------------------------------------- webhooks

    async def settle_by_external(
        self, repos: Repos, bot: Bot, provider_name: str, result: PaymentResult
    ) -> bool:
        """Entry point for webhooks, which know the external id, not the order."""
        if not result.external_id:
            return False
        order = await repos.orders.by_external(provider_name, result.external_id)
        if order is None:
            log.warning(
                "webhook from %s references unknown payment %s",
                provider_name,
                result.external_id,
            )
            return False
        return await self.settle(repos, bot, order, result)

    def invoice_kind(self, provider_name: str) -> InvoiceKind:
        provider = self.registry.get(provider_name)
        if provider is None:
            return InvoiceKind.URL
        return InvoiceKind.NATIVE if provider.native else InvoiceKind.URL

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - debug aid
        return {"providers": self.registry.names, "default": self.registry.default}
