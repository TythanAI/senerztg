"""The aiohttp side-car: health, metrics, and webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from botcore.config import NicheConfig, Secrets
from botcore.db import Repos
from botcore.payments import CryptoBotProvider, ProviderRegistry
from botcore.services import CheckoutService, DeliveryService
from botcore.webapp import build_webapp

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def crypto_provider() -> CryptoBotProvider:
    return CryptoBotProvider("test-token")


@pytest.fixture
def checkout(config, t, crypto_provider) -> CheckoutService:
    registry = ProviderRegistry({"cryptobot": crypto_provider}, "cryptobot", config.lang)
    return CheckoutService(
        config, registry, DeliveryService(config, t, admin_ids=()), admin_ids=()
    )


@pytest_asyncio.fixture
async def client(config, db, fake_bot, crypto_provider, checkout):
    app = build_webapp(
        config=config,
        secrets=Secrets(webhook_secret="s3cret"),
        db=db,
        bot=fake_bot,
        registry=checkout.registry,
        checkout=checkout,
    )
    async with TestClient(TestServer(app)) as test_client:
        yield test_client

    await crypto_provider.close()


@pytest.mark.asyncio
async def test_healthz_reports_ok(client, config: NicheConfig):
    response = await client.get("/healthz")
    assert response.status == 200
    body = await response.json()
    assert body["status"] == "ok"
    assert body["bot"] == config.id
    assert body["database"] == "ok"
    assert "cryptobot" in body["providers"]


@pytest.mark.asyncio
async def test_metrics_require_the_token(client):
    assert (await client.get("/metrics")).status == 403
    ok = await client.get("/metrics", params={"token": "s3cret"})
    assert ok.status == 200
    assert "bot_users_total" in await ok.text()


@pytest.mark.asyncio
async def test_unknown_provider_webhook_is_404(client):
    response = await client.post("/webhook/paypal", data=b"{}")
    assert response.status == 404


@pytest.mark.asyncio
async def test_unsigned_webhook_is_ignored(client):
    response = await client.post("/webhook/cryptobot", data=b'{"update_type":"invoice_paid"}')
    assert response.status == 200
    assert await response.text() == "ignored"


@pytest.mark.asyncio
async def test_signed_webhook_settles_the_order(client, db, config, checkout):
    """The full loop: order in the database, signed webhook, order delivered."""
    async with db.session() as session:
        repos = Repos(session)
        user, _ = await repos.users.get_or_create(4242)
        order = await checkout.create_order(repos, user, config.product("start"), "cryptobot")
        order.external_id = "inv-900"
        order_id = order.id

    payload = {
        "update_type": "invoice_paid",
        "payload": {
            "invoice_id": "inv-900",
            "status": "paid",
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": "1000",
        },
    }
    body = json.dumps(payload).encode()
    secret = hashlib.sha256(b"test-token").digest()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

    response = await client.post(
        "/webhook/cryptobot", data=body, headers={"Crypto-Pay-API-Signature": signature}
    )
    assert response.status == 200
    assert await response.text() == "ok"

    async with db.session() as session:
        settled = await Repos(session).orders.get(order_id)
        assert settled.status == "delivered"
        assert settled.paid_at is not None


@pytest.mark.asyncio
async def test_replayed_webhook_does_not_double_deliver(client, db, config, checkout):
    async with db.session() as session:
        repos = Repos(session)
        user, _ = await repos.users.get_or_create(4243)
        order = await checkout.create_order(repos, user, config.product("start"), "cryptobot")
        order.external_id = "inv-901"

    payload = {
        "update_type": "invoice_paid",
        "payload": {"invoice_id": "inv-901", "status": "paid", "currency_type": "fiat",
                    "fiat": "RUB", "amount": "1000"},
    }
    body = json.dumps(payload).encode()
    secret = hashlib.sha256(b"test-token").digest()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    headers = {"Crypto-Pay-API-Signature": signature}

    await client.post("/webhook/cryptobot", data=body, headers=headers)
    await client.post("/webhook/cryptobot", data=body, headers=headers)

    async with db.session() as session:
        from sqlalchemy import func, select

        from botcore.db import Payment

        count = await session.scalar(select(func.count(Payment.id)))
        assert count == 1, "a replayed webhook must not create a second ledger row"


@pytest.mark.asyncio
async def test_metrics_reflect_revenue(client, db, config, fake_bot, checkout):
    from botcore.payments import PaymentResult, PaymentStatus

    async with db.session() as session:
        repos = Repos(session)
        user, _ = await repos.users.get_or_create(4244)
        order = await checkout.create_order(repos, user, config.product("club"), "cryptobot")
        await checkout.settle(
            repos,
            fake_bot,
            order,
            PaymentResult(
                status=PaymentStatus.PAID,
                external_id="inv-902",
                amount=Decimal("2000"),
                currency="RUB",
            ),
        )

    text = await (await client.get("/metrics", params={"token": "s3cret"})).text()
    assert "bot_revenue_total" in text
    assert "2000" in text
