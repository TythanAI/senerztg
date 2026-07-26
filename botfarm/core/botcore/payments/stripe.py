"""Stripe Checkout — cards, Apple/Google Pay, SEPA, iDEAL for EU/US buyers.

Docs: https://docs.stripe.com/api/checkout/sessions
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
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
    from_minor_units,
    to_minor_units,
)
from .http import HttpClient

log = logging.getLogger(__name__)


class StripeProvider(PaymentProvider):
    name = "stripe"
    title = "Card / Apple Pay / Google Pay"
    currencies = ("EUR", "USD", "GBP", "PLN")

    def __init__(
        self,
        secret_key: str,
        *,
        webhook_secret: str = "",
        success_url: str = "",
        cancel_url: str = "",
        payment_methods: tuple[str, ...] = ("card",),
        api_base: str = "https://api.stripe.com/v1",
        **options: Any,
    ) -> None:
        super().__init__(**options)
        if not secret_key:
            raise PaymentError("Stripe needs STRIPE_SECRET_KEY", provider=self.name)
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url
        self.payment_methods = payment_methods
        self.http = HttpClient(
            api_base,
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            provider=self.name,
        )

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        success = ctx.return_url or self.success_url or "https://t.me"
        cancel = self.cancel_url or success

        form: list[tuple[str, str]] = [
            ("mode", "payment"),
            ("success_url", success),
            ("cancel_url", cancel),
            ("client_reference_id", str(ctx.order_id)),
            ("line_items[0][quantity]", "1"),
            ("line_items[0][price_data][currency]", ctx.currency.lower()),
            ("line_items[0][price_data][product_data][name]", ctx.title[:250]),
            (
                "line_items[0][price_data][unit_amount]",
                str(to_minor_units(ctx.amount, ctx.currency)),
            ),
            ("metadata[order_id]", str(ctx.order_id)),
            ("metadata[tg_id]", str(ctx.user_tg_id)),
            ("metadata[sku]", ctx.sku),
            ("expires_at", str(int(time.time()) + 30 * 60)),
        ]
        if ctx.description:
            form.append(
                ("line_items[0][price_data][product_data][description]", ctx.description[:500])
            )
        for idx, method in enumerate(self.payment_methods):
            form.append((f"payment_method_types[{idx}]", method))
        if ctx.email:
            form.append(("customer_email", ctx.email))

        # Idempotency-Key stops a double-tap from creating two sessions.
        data = await self.http.post(
            "/checkout/sessions",
            data=form,
            headers={"Idempotency-Key": f"order-{ctx.order_id}"},
        )

        session_id = data.get("id")
        url = data.get("url")
        if not session_id or not url:
            raise PaymentError(f"Stripe returned no checkout url: {data}", provider=self.name)

        return Invoice(
            kind=InvoiceKind.URL,
            external_id=str(session_id),
            url=str(url),
            payload={"payment_status": data.get("payment_status")},
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        data = await self.http.get(f"/checkout/sessions/{external_id}")
        return self._to_result(data)

    async def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentResult | None:
        header = headers.get("stripe-signature") or headers.get("Stripe-Signature", "")
        if self.webhook_secret:
            if not self._verify(body, header):
                log.warning("stripe: bad webhook signature — rejected")
                return None
        else:
            log.warning("stripe: STRIPE_WEBHOOK_SECRET unset — verifying by API instead")

        try:
            event = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if event.get("type") not in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.expired",
        }:
            return None

        session = (event.get("data") or {}).get("object") or {}
        if not self.webhook_secret and session.get("id"):
            # Unsigned: re-fetch so a forged body cannot mark an order paid.
            try:
                return await self.check(str(session["id"]))
            except PaymentError:
                return None
        return self._to_result(session)

    def _verify(self, body: bytes, header: str, tolerance: int = 300) -> bool:
        """Stripe's `t=<ts>,v1=<sig>` scheme over `<ts>.<body>`."""
        parts = dict(
            piece.split("=", 1) for piece in header.split(",") if "=" in piece
        )
        timestamp, signature = parts.get("t"), parts.get("v1")
        if not timestamp or not signature:
            return False
        try:
            age = abs(time.time() - int(timestamp))
        except ValueError:
            return False
        if age > tolerance:  # replay protection
            return False
        signed = f"{timestamp}.".encode() + body
        expected = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _to_result(self, session: dict[str, Any]) -> PaymentResult:
        pay_status = str(session.get("payment_status", ""))
        session_status = str(session.get("status", ""))
        if pay_status == "paid":
            status = PaymentStatus.PAID
        elif session_status == "expired":
            status = PaymentStatus.EXPIRED
        elif session_status == "complete" and pay_status == "no_payment_required":
            status = PaymentStatus.PAID
        else:
            status = PaymentStatus.PENDING

        currency = str(session.get("currency", "") or "").upper()
        total = session.get("amount_total")
        amount = from_minor_units(total, currency) if total is not None else None

        return PaymentResult(
            status=status,
            external_id=str(session.get("id", "")),
            amount=amount,
            currency=currency,
            raw=session,
        )

    async def refund(self, payment_intent: str, amount: Decimal | None = None) -> dict[str, Any]:
        form = [("payment_intent", payment_intent)]
        if amount is not None:
            form.append(("amount", str(to_minor_units(amount, "EUR"))))
        return await self.http.post("/refunds", data=form)

    async def close(self) -> None:
        await self.http.close()
