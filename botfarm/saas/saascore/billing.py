"""Self-serve upgrades: Stripe Checkout for cards, Crypto Pay for crypto.

The bot fleet and the API rack share the same payment philosophy — the
webhook is verified, the plan change is idempotent, and a replayed callback
can never grant a second month.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from .store import PLANS, ApiKey, Store

if TYPE_CHECKING:  # pragma: no cover
    from .app import ServiceSpec

log = logging.getLogger(__name__)


class BillingRouter:
    def __init__(self, store: Store, spec: "ServiceSpec") -> None:
        self.store = store
        self.spec = spec
        self.router = APIRouter()
        self._register()

    # ------------------------------------------------------------- endpoints

    def _register(self) -> None:
        router = self.router

        @router.get("/plans")
        async def plans() -> dict[str, Any]:
            """Public price sheet — what an upgrade costs and what it unlocks."""
            return {
                "service": self.spec.name,
                "currency": "EUR",
                "plans": [
                    {
                        "name": name,
                        "price_eur": self.spec.price(name),
                        "quota_per_month": cfg["quota"],
                        "requests_per_minute": cfg["rpm"],
                    }
                    for name, cfg in PLANS.items()
                ],
            }

        @router.post("/upgrade")
        async def upgrade(request: Request, plan: str, method: str = "stripe") -> dict[str, Any]:
            key: ApiKey = await _key_from(request)
            if plan not in PLANS:
                raise HTTPException(400, f"Unknown plan {plan!r}")
            price = self.spec.price(plan)
            if price <= 0:
                raise HTTPException(400, "That plan is free — no payment needed")

            if method == "stripe":
                return await self._stripe_checkout(key, plan, price)
            if method in {"crypto", "cryptobot"}:
                return await self._crypto_invoice(key, plan, price)
            raise HTTPException(400, "method must be 'stripe' or 'crypto'")

        @router.post("/webhook/stripe")
        async def stripe_webhook(request: Request) -> dict[str, str]:
            body = await request.body()
            secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
            signature = request.headers.get("stripe-signature", "")

            if secret and not _verify_stripe(body, signature, secret):
                log.warning("stripe: rejected a webhook with a bad signature")
                raise HTTPException(400, "Bad signature")
            if not secret:
                log.warning("STRIPE_WEBHOOK_SECRET unset — webhook accepted unverified")

            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(400, "Malformed JSON") from None

            if event.get("type") != "checkout.session.completed":
                return {"status": "ignored"}

            session = (event.get("data") or {}).get("object") or {}
            if session.get("payment_status") != "paid":
                return {"status": "unpaid"}

            key = self.store.mark_invoice_paid("stripe", str(session.get("id", "")), session)
            if key is None:
                return {"status": "duplicate"}
            log.info("stripe: key %s upgraded to %s", key.id, key.plan)
            return {"status": "ok"}

        @router.post("/webhook/cryptobot")
        async def crypto_webhook(request: Request) -> dict[str, str]:
            body = await request.body()
            token = os.getenv("CRYPTOBOT_TOKEN", "")
            signature = request.headers.get("crypto-pay-api-signature", "")

            if not token:
                raise HTTPException(503, "CRYPTOBOT_TOKEN is not configured")
            secret = hashlib.sha256(token.encode()).digest()
            expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                log.warning("cryptobot: rejected a webhook with a bad signature")
                raise HTTPException(400, "Bad signature")

            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(400, "Malformed JSON") from None

            if event.get("update_type") != "invoice_paid":
                return {"status": "ignored"}

            invoice = event.get("payload") or {}
            key = self.store.mark_invoice_paid(
                "cryptobot", str(invoice.get("invoice_id", "")), invoice
            )
            if key is None:
                return {"status": "duplicate"}
            log.info("cryptobot: key %s upgraded to %s", key.id, key.plan)
            return {"status": "ok"}

    # -------------------------------------------------------------- providers

    async def _stripe_checkout(self, key: ApiKey, plan: str, price: int) -> dict[str, Any]:
        secret_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not secret_key:
            raise HTTPException(503, "Card payments are not configured on this server")

        base = os.getenv("PUBLIC_BASE_URL", "https://api.example.com").rstrip("/")
        form = {
            "mode": "payment",
            "success_url": f"{base}/v1/billing/thanks",
            "cancel_url": f"{base}/",
            "client_reference_id": str(key.id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "eur",
            "line_items[0][price_data][product_data][name]":
                f"{self.spec.title} — {plan} plan (1 month)",
            "line_items[0][price_data][unit_amount]": str(price * 100),
            "payment_method_types[0]": "card",
            "metadata[key_id]": str(key.id),
            "metadata[plan]": plan,
            "metadata[service]": self.spec.name,
            "expires_at": str(int(time.time()) + 1800),
        }
        if key.email:
            form["customer_email"] = key.email

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=form,
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Idempotency-Key": f"key{key.id}-{plan}-{int(time.time() // 900)}",
                },
            )
        if response.status_code >= 400:
            log.error("stripe checkout failed: %s", response.text[:300])
            raise HTTPException(502, "Payment provider error")

        data = response.json()
        self.store.create_invoice(
            key_id=key.id,
            provider="stripe",
            external_id=str(data["id"]),
            plan=plan,
            amount=float(price),
            currency="EUR",
        )
        return {"provider": "stripe", "plan": plan, "amount_eur": price, "pay_url": data["url"]}

    async def _crypto_invoice(self, key: ApiKey, plan: str, price: int) -> dict[str, Any]:
        token = os.getenv("CRYPTOBOT_TOKEN", "")
        if not token:
            raise HTTPException(503, "Crypto payments are not configured on this server")

        payload = {
            "currency_type": "fiat",
            "fiat": "EUR",
            "amount": str(price),
            "accepted_assets": "USDT,TON,BTC",
            "description": f"{self.spec.title} — {plan} plan (1 month)",
            "payload": json.dumps({"key_id": key.id, "plan": plan}),
            "expires_in": 3600,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://pay.crypt.bot/api/createInvoice",
                json=payload,
                headers={"Crypto-Pay-API-Token": token},
            )
        data = response.json() if response.status_code < 500 else {}
        if not data.get("ok"):
            log.error("cryptobot invoice failed: %s", response.text[:300])
            raise HTTPException(502, "Payment provider error")

        result = data["result"]
        self.store.create_invoice(
            key_id=key.id,
            provider="cryptobot",
            external_id=str(result["invoice_id"]),
            plan=plan,
            amount=float(price),
            currency="EUR",
        )
        return {
            "provider": "cryptobot",
            "plan": plan,
            "amount_eur": price,
            "pay_url": result.get("mini_app_invoice_url") or result["bot_invoice_url"],
        }


async def _key_from(request: Request) -> ApiKey:
    """Resolve the caller's key without spending a quota call on billing."""
    store: Store = request.app.state.store
    spec = request.app.state.spec

    authorization = request.headers.get("authorization", "")
    raw = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    raw = raw or request.headers.get("x-api-key", "").strip()
    if not raw:
        raise HTTPException(401, "Missing API key")

    key = store.get_key(raw)
    if key is None or not key.is_valid():
        raise HTTPException(401, "Invalid or revoked API key")
    if not key.allows(spec.name):
        raise HTTPException(403, "This key is not valid for this service")
    return key


def _verify_stripe(body: bytes, header: str, secret: str, tolerance: int = 300) -> bool:
    parts = dict(piece.split("=", 1) for piece in header.split(",") if "=" in piece)
    timestamp, signature = parts.get("t"), parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            return False
    except ValueError:
        return False
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
