"""YooKassa — the workhorse for the RU segment: bank cards, SBP, SberPay, wallets.

Docs: https://yookassa.ru/developers/api
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import uuid
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
    money,
)
from .http import HttpClient

log = logging.getLogger(__name__)

API = "https://api.yookassa.ru/v3"

_STATUS_MAP = {
    "pending": PaymentStatus.PENDING,
    "waiting_for_capture": PaymentStatus.PENDING,
    "succeeded": PaymentStatus.PAID,
    "canceled": PaymentStatus.CANCELLED,
}


class YooKassaProvider(PaymentProvider):
    """Cards + SBP for Russia. `method` picks the rail shown to the buyer."""

    name = "yookassa"
    title = "Карта / СБП"
    currencies = ("RUB",)

    def __init__(
        self,
        shop_id: str,
        secret_key: str,
        *,
        method: str = "",
        return_url: str = "",
        receipt_email: str = "",
        tax_system_code: int = 0,
        vat_code: int = 1,
        api_base: str = API,
        **options: Any,
    ) -> None:
        super().__init__(**options)
        if not shop_id or not secret_key:
            raise PaymentError("YooKassa needs YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY",
                               provider=self.name)
        self.shop_id = shop_id
        self.method = method  # "" = let the user choose, "sbp", "bank_card", "sberbank"
        self.return_url = return_url
        self.receipt_email = receipt_email
        self.tax_system_code = tax_system_code
        self.vat_code = vat_code
        token = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
        self.http = HttpClient(
            api_base,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
            provider=self.name,
        )

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        if ctx.currency != "RUB":
            raise PaymentError(f"YooKassa settles in RUB only, got {ctx.currency}",
                               provider=self.name)

        body: dict[str, Any] = {
            "amount": {"value": money(ctx.amount), "currency": "RUB"},
            "capture": True,
            "description": ctx.label()[:128],
            "confirmation": {
                "type": "redirect",
                "return_url": ctx.return_url or self.return_url or "https://t.me",
            },
            "metadata": {
                "order_id": str(ctx.order_id),
                "tg_id": str(ctx.user_tg_id),
                "sku": ctx.sku,
            },
        }
        if self.method:
            body["payment_method_data"] = {"type": self.method}

        # 54-ФЗ receipt. Required by YooKassa for most Russian merchants.
        email = ctx.email or self.receipt_email
        if email:
            receipt: dict[str, Any] = {
                "customer": {"email": email},
                "items": [
                    {
                        "description": ctx.title[:128],
                        "quantity": "1.00",
                        "amount": {"value": money(ctx.amount), "currency": "RUB"},
                        "vat_code": self.vat_code,
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            }
            if self.tax_system_code:
                receipt["tax_system_code"] = self.tax_system_code
            body["receipt"] = receipt

        # Idempotence key: a retried POST must never double-charge.
        key = f"order-{ctx.order_id}-{uuid.uuid4().hex[:8]}"
        data = await self.http.post("/payments", json=body, headers={"Idempotence-Key": key})

        payment_id = data.get("id")
        url = (data.get("confirmation") or {}).get("confirmation_url", "")
        if not payment_id or not url:
            raise PaymentError(f"YooKassa returned no confirmation_url: {data}",
                               provider=self.name)

        expires: dt.datetime | None = None
        raw_expiry = data.get("expires_at")
        if raw_expiry:
            expires = _parse_ts(raw_expiry)

        return Invoice(
            kind=InvoiceKind.URL,
            external_id=str(payment_id),
            url=url,
            payload={"status": data.get("status")},
            expires_at=expires,
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        data = await self.http.get(f"/payments/{external_id}")
        return self._to_result(data)

    async def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentResult | None:
        """YooKassa posts notifications unsigned — we always re-verify by API."""
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("yookassa: webhook body is not JSON")
            return None

        event = payload.get("event", "")
        obj = payload.get("object") or {}
        payment_id = obj.get("id")
        if not payment_id:
            return None

        if event not in {"payment.succeeded", "payment.canceled", "payment.waiting_for_capture"}:
            return None

        # Never trust the notification body for the money decision.
        try:
            return await self.check(str(payment_id))
        except PaymentError as exc:
            log.error("yookassa: could not verify webhook payment %s: %s", payment_id, exc)
            return None

    def _to_result(self, data: dict[str, Any]) -> PaymentResult:
        status = _STATUS_MAP.get(str(data.get("status", "")), PaymentStatus.PENDING)
        amount_block = data.get("amount") or {}
        amount = None
        if amount_block.get("value") is not None:
            amount = Decimal(str(amount_block["value"]))
        # A payment can be "succeeded" but not actually captured/paid.
        if status is PaymentStatus.PAID and data.get("paid") is False:
            status = PaymentStatus.PENDING
        return PaymentResult(
            status=status,
            external_id=str(data.get("id", "")),
            amount=amount,
            currency=str(amount_block.get("currency", "RUB")),
            raw=data,
        )

    async def close(self) -> None:
        await self.http.close()


class SbpProvider(YooKassaProvider):
    """СБП as its own button — buyers pick it by name, so surface it by name."""

    name = "sbp"
    title = "СБП (QR)"

    def __init__(self, shop_id: str, secret_key: str, **options: Any) -> None:
        options.pop("method", None)
        super().__init__(shop_id, secret_key, method="sbp", **options)


def _parse_ts(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
