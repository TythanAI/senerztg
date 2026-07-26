"""Telegram-native rails: Telegram Payments (provider_token) and Telegram Stars.

Neither one redirects the buyer anywhere — the invoice is a Telegram message —
so `create_invoice` only prepares the arguments and the checkout handler calls
`bot.send_invoice`. Confirmation arrives as a `successful_payment` update, so
`check()` is never authoritative here.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from .base import (
    Invoice,
    InvoiceKind,
    OrderContext,
    PaymentError,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    to_minor_units,
)

# Telegram requires the total to be at least ~$1 equivalent for most providers.
MIN_AMOUNTS = {"RUB": Decimal("60"), "EUR": Decimal("1"), "USD": Decimal("1")}


class TelegramPaymentsProvider(PaymentProvider):
    """Cards through a BotFather-connected acquirer (YooKassa, Stripe, …)."""

    name = "telegram_native"
    title = "Оплата картой в Telegram"
    currencies = ("RUB", "EUR", "USD")
    native = True

    def __init__(self, provider_token: str, *, need_email: bool = False, **options: Any) -> None:
        super().__init__(**options)
        if not provider_token:
            raise PaymentError(
                "Telegram Payments needs TELEGRAM_PROVIDER_TOKEN from @BotFather",
                provider=self.name,
            )
        self.provider_token = provider_token
        self.need_email = need_email

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        minimum = MIN_AMOUNTS.get(ctx.currency.upper())
        if minimum is not None and ctx.amount < minimum:
            raise PaymentError(
                f"Telegram Payments rejects amounts under {minimum} {ctx.currency}",
                provider=self.name,
            )

        payload = json.dumps({"order_id": ctx.order_id, "sku": ctx.sku})
        args = {
            "title": ctx.title[:32],
            "description": (ctx.description or ctx.title)[:255],
            "payload": payload,
            "provider_token": self.provider_token,
            "currency": ctx.currency.upper(),
            "prices": [
                {"label": ctx.title[:32], "amount": to_minor_units(ctx.amount, ctx.currency)}
            ],
            "need_email": self.need_email,
            "send_email_to_provider": self.need_email,
        }
        return Invoice(
            kind=InvoiceKind.NATIVE,
            external_id=f"tg-{ctx.order_id}",
            payload=args,
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        # Telegram pushes `successful_payment`; there is nothing to poll.
        return PaymentResult(status=PaymentStatus.PENDING, external_id=external_id)


#: Telegram rejects a Stars invoice above this amount.
MAX_STARS = 2500


class StarsProvider(PaymentProvider):
    """Telegram Stars (XTR). No merchant account, works in every country.

    Fiat prices are converted with `rate` (currency units per Star) so the
    catalog stays priced in RUB/EUR while the buyer pays in Stars.
    """

    name = "stars"
    title = "⭐ Telegram Stars"
    currencies = ("XTR", "RUB", "EUR", "USD")
    native = True

    def __init__(
        self, rate: Decimal | float | int = 0, *, min_stars: int = 1, **options: Any
    ) -> None:
        super().__init__(**options)
        self.rate = Decimal(str(rate))
        self.min_stars = max(1, min_stars)

    def to_stars(self, amount: Decimal, currency: str) -> int:
        if currency.upper() == "XTR":
            stars = int(amount)
        else:
            if self.rate <= 0:
                raise PaymentError(
                    "Stars pricing needs payments.stars_rate in config.yaml "
                    "(how many currency units one Star is worth)",
                    provider=self.name,
                )
            stars = int(Decimal(amount) / self.rate)

        stars = max(self.min_stars, stars)
        if stars > MAX_STARS:
            raise PaymentError(
                f"{amount} {currency} is {stars} Stars, above Telegram's "
                f"{MAX_STARS}-Star invoice limit — sell this tier on another rail",
                provider=self.name,
            )
        return stars

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        stars = self.to_stars(ctx.amount, ctx.currency)
        payload = json.dumps({"order_id": ctx.order_id, "sku": ctx.sku})
        args = {
            "title": ctx.title[:32],
            "description": (ctx.description or ctx.title)[:255],
            "payload": payload,
            "provider_token": "",  # Stars must be sent with an empty token
            "currency": "XTR",
            "prices": [{"label": ctx.title[:32], "amount": stars}],
        }
        return Invoice(
            kind=InvoiceKind.NATIVE,
            external_id=f"stars-{ctx.order_id}",
            payload=args,
            instructions=f"{stars} ⭐",
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        return PaymentResult(status=PaymentStatus.PENDING, external_id=external_id)
