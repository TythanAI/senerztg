"""Provider-level behaviour: amounts, signatures, and status mapping."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal

import pytest

from botcore.payments import (
    CryptoBotProvider,
    InvoiceKind,
    ManualProvider,
    OrderContext,
    PaymentError,
    PaymentStatus,
    StarsProvider,
    StripeProvider,
    from_minor_units,
    to_minor_units,
)
from botcore.payments.telegram import MAX_STARS, TelegramPaymentsProvider
from botcore.payments.yookassa import YooKassaProvider


def ctx(amount="1000", currency="RUB", order_id=1) -> OrderContext:
    return OrderContext(
        order_id=order_id,
        user_tg_id=42,
        sku="start",
        title="Старт",
        description="Описание",
        amount=Decimal(amount),
        currency=currency,
    )


class TestMinorUnits:
    def test_roubles_to_kopecks(self):
        assert to_minor_units(Decimal("1490"), "RUB") == 149000
        assert to_minor_units(Decimal("19.99"), "EUR") == 1999

    def test_half_cent_rounds_up(self):
        assert to_minor_units(Decimal("0.005"), "EUR") == 1

    def test_stars_stay_whole(self):
        assert to_minor_units(Decimal("250"), "XTR") == 250

    def test_round_trip(self):
        assert from_minor_units(to_minor_units(Decimal("19.99"), "EUR"), "EUR") == Decimal("19.99")


class TestStars:
    def test_converts_fiat_to_stars(self):
        provider = StarsProvider(rate=Decimal("1.9"))
        assert provider.to_stars(Decimal("1900"), "RUB") == 1000

    def test_eur_uses_fractional_rate(self):
        provider = StarsProvider(rate=Decimal("0.019"))
        # A €29 product must not become 29 Stars (~€0.55).
        assert provider.to_stars(Decimal("29"), "EUR") == 1526

    def test_rejects_amount_above_telegram_limit(self):
        provider = StarsProvider(rate=Decimal("1.9"))
        with pytest.raises(PaymentError, match="Star invoice limit"):
            provider.to_stars(Decimal("100000"), "RUB")

    def test_limit_boundary_is_allowed(self):
        provider = StarsProvider(rate=Decimal("1"))
        assert provider.to_stars(Decimal(MAX_STARS), "RUB") == MAX_STARS

    def test_missing_rate_is_an_error(self):
        with pytest.raises(PaymentError, match="stars_rate"):
            StarsProvider(rate=0).to_stars(Decimal("100"), "RUB")

    @pytest.mark.asyncio
    async def test_invoice_is_native_with_empty_token(self):
        invoice = await StarsProvider(rate=Decimal("1.9")).create_invoice(ctx())
        assert invoice.kind is InvoiceKind.NATIVE
        assert invoice.payload["provider_token"] == ""
        assert invoice.payload["currency"] == "XTR"
        assert json.loads(invoice.payload["payload"])["order_id"] == 1


class TestTelegramPayments:
    @pytest.mark.asyncio
    async def test_builds_native_invoice(self):
        provider = TelegramPaymentsProvider("prov:token")
        invoice = await provider.create_invoice(ctx())
        assert invoice.kind is InvoiceKind.NATIVE
        assert invoice.payload["prices"][0]["amount"] == 100000

    @pytest.mark.asyncio
    async def test_rejects_below_minimum(self):
        provider = TelegramPaymentsProvider("prov:token")
        with pytest.raises(PaymentError, match="under"):
            await provider.create_invoice(ctx(amount="10"))

    def test_requires_a_token(self):
        with pytest.raises(PaymentError, match="TELEGRAM_PROVIDER_TOKEN"):
            TelegramPaymentsProvider("")


class TestStripeSignature:
    def provider(self) -> StripeProvider:
        return StripeProvider("sk_test_x", webhook_secret="whsec_test")

    def sign(self, body: bytes, secret: str = "whsec_test", ts: int | None = None) -> str:
        ts = ts or int(time.time())
        signed = f"{ts}.".encode() + body
        mac = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return f"t={ts},v1={mac}"

    def test_accepts_a_valid_signature(self):
        body = b'{"type":"checkout.session.completed"}'
        assert self.provider()._verify(body, self.sign(body)) is True

    def test_rejects_a_forged_signature(self):
        body = b'{"type":"checkout.session.completed"}'
        assert self.provider()._verify(body, self.sign(body, secret="wrong")) is False

    def test_rejects_a_replayed_signature(self):
        body = b"{}"
        old = self.sign(body, ts=int(time.time()) - 3600)
        assert self.provider()._verify(body, old) is False

    def test_rejects_a_malformed_header(self):
        assert self.provider()._verify(b"{}", "garbage") is False

    @pytest.mark.asyncio
    async def test_forged_webhook_does_not_settle(self):
        provider = self.provider()
        body = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_1", "payment_status": "paid",
                                    "amount_total": 9900, "currency": "eur"}},
            }
        ).encode()
        assert await provider.parse_webhook(body, {"stripe-signature": "t=1,v1=deadbeef"}) is None

    @pytest.mark.asyncio
    async def test_signed_webhook_is_parsed(self):
        provider = self.provider()
        body = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_1", "payment_status": "paid",
                                    "amount_total": 9900, "currency": "eur"}},
            }
        ).encode()
        result = await provider.parse_webhook(body, {"stripe-signature": self.sign(body)})
        assert result is not None
        assert result.is_paid
        assert result.amount == Decimal("99.00")
        assert result.currency == "EUR"

    def test_unpaid_session_is_pending(self):
        result = self.provider()._to_result(
            {"id": "cs_2", "payment_status": "unpaid", "status": "open"}
        )
        assert result.status is PaymentStatus.PENDING


class TestCryptoBotSignature:
    def test_valid_signature_is_accepted(self):
        provider = CryptoBotProvider("token-abc")
        body = json.dumps(
            {"update_type": "invoice_paid",
             "payload": {"invoice_id": 7, "status": "paid", "amount": "10",
                         "currency_type": "fiat", "fiat": "EUR"}}
        ).encode()
        secret = hashlib.sha256(b"token-abc").digest()
        signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

        import asyncio

        result = asyncio.run(
            provider.parse_webhook(body, {"crypto-pay-api-signature": signature})
        )
        assert result is not None and result.is_paid
        assert result.amount == Decimal("10")

    def test_bad_signature_is_rejected(self):
        import asyncio

        provider = CryptoBotProvider("token-abc")
        body = b'{"update_type":"invoice_paid","payload":{"invoice_id":7,"status":"paid"}}'
        assert asyncio.run(provider.parse_webhook(body, {"crypto-pay-api-signature": "no"})) is None

    def test_missing_signature_is_rejected(self):
        import asyncio

        provider = CryptoBotProvider("token-abc")
        assert asyncio.run(provider.parse_webhook(b"{}", {})) is None


class TestYooKassa:
    def test_requires_credentials(self):
        with pytest.raises(PaymentError, match="YOOKASSA_SHOP_ID"):
            YooKassaProvider("", "")

    def test_status_mapping(self):
        provider = YooKassaProvider("shop", "key")
        paid = provider._to_result(
            {"id": "p1", "status": "succeeded", "paid": True,
             "amount": {"value": "1490.00", "currency": "RUB"}}
        )
        assert paid.is_paid and paid.amount == Decimal("1490.00")

        assert provider._to_result({"id": "p2", "status": "pending"}).status is PaymentStatus.PENDING
        assert (
            provider._to_result({"id": "p3", "status": "canceled"}).status
            is PaymentStatus.CANCELLED
        )

    def test_succeeded_but_unpaid_is_not_paid(self):
        provider = YooKassaProvider("shop", "key")
        result = provider._to_result({"id": "p4", "status": "succeeded", "paid": False})
        assert result.status is PaymentStatus.PENDING

    def test_only_settles_roubles(self):
        import asyncio

        provider = YooKassaProvider("shop", "key")
        with pytest.raises(PaymentError, match="RUB only"):
            asyncio.run(provider.create_invoice(ctx(currency="EUR")))


class TestManual:
    @pytest.mark.asyncio
    async def test_shows_requisites_and_memo(self):
        provider = ManualProvider("Карта 1234", lang="ru")
        invoice = await provider.create_invoice(ctx(order_id=77))
        assert invoice.kind is InvoiceKind.MANUAL
        assert "Карта 1234" in invoice.instructions
        assert "ORDER77" in invoice.instructions

    @pytest.mark.asyncio
    async def test_never_self_confirms(self):
        provider = ManualProvider("Карта")
        assert (await provider.check("ORDER1")).status is PaymentStatus.PENDING
