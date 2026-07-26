"""Crypto Pay (@CryptoBot) — USDT/TON/BTC, works for both RU and EU buyers.

Docs: https://help.crypt.bot/crypto-pay-api
"""

from __future__ import annotations

import datetime as dt
import json
import logging
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

_STATUS_MAP = {
    "active": PaymentStatus.PENDING,
    "paid": PaymentStatus.PAID,
    "expired": PaymentStatus.EXPIRED,
}


class CryptoBotProvider(PaymentProvider):
    """Invoices priced in fiat, settled in crypto — no chargebacks, no KYC."""

    name = "cryptobot"
    title = "Crypto (USDT/TON/BTC)"
    currencies = ("RUB", "EUR", "USD")

    def __init__(
        self,
        token: str,
        *,
        asset: str = "USDT",
        assets: tuple[str, ...] = ("USDT", "TON", "BTC"),
        api_base: str = "https://pay.crypt.bot/api",
        fiat_pricing: bool = True,
        ttl_minutes: int = 60,
        **options: Any,
    ) -> None:
        super().__init__(**options)
        if not token:
            raise PaymentError("CryptoBot needs CRYPTOBOT_TOKEN", provider=self.name)
        self.token = token
        self.asset = asset
        self.assets = assets
        self.fiat_pricing = fiat_pricing
        self.ttl_minutes = ttl_minutes
        self.http = HttpClient(
            api_base,
            headers={"Crypto-Pay-API-Token": token, "Content-Type": "application/json"},
            provider=self.name,
        )

    async def _call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        data = await self.http.post(f"/{method}", json=payload or {})
        if not isinstance(data, dict) or not data.get("ok"):
            error = (data or {}).get("error") if isinstance(data, dict) else data
            raise PaymentError(f"CryptoBot {method} failed: {error}", provider=self.name)
        return data.get("result")

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        payload: dict[str, Any] = {
            "description": ctx.label()[:1024],
            "payload": json.dumps(
                {"order_id": ctx.order_id, "tg_id": ctx.user_tg_id, "sku": ctx.sku}
            ),
            "expires_in": max(60, self.ttl_minutes * 60),
            "allow_comments": False,
            "allow_anonymous": True,
        }

        if self.fiat_pricing:
            # Charge the fiat price; the buyer picks which coin to send.
            payload["currency_type"] = "fiat"
            payload["fiat"] = ctx.currency
            payload["amount"] = money(ctx.amount)
            payload["accepted_assets"] = ",".join(self.assets)
        else:
            payload["currency_type"] = "crypto"
            payload["asset"] = self.asset
            payload["amount"] = money(ctx.amount)

        result = await self._call("createInvoice", payload)
        invoice_id = result.get("invoice_id")
        url = result.get("mini_app_invoice_url") or result.get("bot_invoice_url") or result.get("pay_url")
        if not invoice_id or not url:
            raise PaymentError(f"CryptoBot returned no invoice url: {result}", provider=self.name)

        return Invoice(
            kind=InvoiceKind.URL,
            external_id=str(invoice_id),
            url=url,
            payload={"hash": result.get("hash")},
            expires_at=_parse_ts(result.get("expiration_date")),
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        result = await self._call("getInvoices", {"invoice_ids": str(external_id), "count": 1})
        items = (result or {}).get("items") or []
        if not items:
            return PaymentResult(status=PaymentStatus.PENDING, external_id=str(external_id))
        return self._to_result(items[0])

    async def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentResult | None:
        """Crypto Pay signs webhooks with HMAC-SHA256 over SHA256(token)."""
        import hashlib
        import hmac

        signature = headers.get("crypto-pay-api-signature") or headers.get(
            "Crypto-Pay-Api-Signature", ""
        )
        if not signature:
            log.warning("cryptobot: webhook without signature — rejected")
            return None

        secret = hashlib.sha256(self.token.encode()).digest()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            log.warning("cryptobot: bad webhook signature — rejected")
            return None

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if payload.get("update_type") != "invoice_paid":
            return None
        invoice = payload.get("payload") or {}
        return self._to_result(invoice)

    def _to_result(self, invoice: dict[str, Any]) -> PaymentResult:
        status = _STATUS_MAP.get(str(invoice.get("status", "")), PaymentStatus.PENDING)
        # For fiat-priced invoices the fiat amount is what we billed.
        if invoice.get("currency_type") == "fiat":
            amount_raw = invoice.get("amount")
            currency = str(invoice.get("fiat", ""))
        else:
            amount_raw = invoice.get("amount")
            currency = str(invoice.get("asset", ""))
        amount = Decimal(str(amount_raw)) if amount_raw is not None else None
        return PaymentResult(
            status=status,
            external_id=str(invoice.get("invoice_id", "")),
            amount=amount,
            currency=currency,
            raw=invoice,
        )

    async def get_balance(self) -> list[dict[str, Any]]:
        """Used by the admin panel to show what the shop has collected."""
        return await self._call("getBalance") or []

    async def close(self) -> None:
        await self.http.close()


def _parse_ts(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
