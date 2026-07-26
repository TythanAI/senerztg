"""Manual transfer — card-to-card, IBAN, cash. An admin confirms in the panel.

Every shop needs this: it is the fallback when an acquirer goes down, and for
RU sellers without a legal entity it is often the only rail on day one.
"""

from __future__ import annotations

from typing import Any

from .base import (
    Invoice,
    InvoiceKind,
    OrderContext,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
)

DEFAULT_TEMPLATE_RU = (
    "Переведите <b>{amount} {currency}</b> по реквизитам:\n\n"
    "{requisites}\n\n"
    "В комментарии укажите: <code>{memo}</code>\n"
    "После перевода нажмите «Я оплатил» — оператор подтвердит в течение 15 минут."
)

DEFAULT_TEMPLATE_EN = (
    "Send <b>{amount} {currency}</b> to:\n\n"
    "{requisites}\n\n"
    "Use this reference: <code>{memo}</code>\n"
    "Then tap “I have paid” — an operator confirms within 15 minutes."
)


class ManualProvider(PaymentProvider):
    name = "manual"
    title = "Перевод по реквизитам"
    currencies = ("RUB", "EUR", "USD")

    def __init__(
        self, requisites: str = "", *, template: str = "", lang: str = "ru", **options: Any
    ) -> None:
        super().__init__(**options)
        self.requisites = requisites or "—"
        self.template = template or (DEFAULT_TEMPLATE_RU if lang == "ru" else DEFAULT_TEMPLATE_EN)

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        memo = f"ORDER{ctx.order_id}"
        text = self.template.format(
            amount=ctx.amount,
            currency=ctx.currency,
            requisites=self.requisites,
            memo=memo,
        )
        return Invoice(
            kind=InvoiceKind.MANUAL,
            external_id=memo,
            instructions=text,
            payload={"memo": memo},
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        # Only a human can settle this one.
        return PaymentResult(status=PaymentStatus.PENDING, external_id=external_id)
