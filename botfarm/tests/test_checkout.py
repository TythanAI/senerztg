"""The money path: an order is settled exactly once, and only for the right amount."""

from __future__ import annotations

from decimal import Decimal

import pytest

from botcore.db import Repos
from botcore.payments import (
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    ProviderRegistry,
)
from botcore.payments.base import Invoice, InvoiceKind, OrderContext
from botcore.services import CheckoutService, DeliveryService
from botcore.utils import apply_discount


class StubProvider(PaymentProvider):
    """A provider we can steer from the test."""

    name = "stub"
    title = "Stub"
    currencies = ("RUB",)

    def __init__(self, status: PaymentStatus = PaymentStatus.PENDING) -> None:
        super().__init__()
        self.status = status
        self.amount: Decimal | None = None
        self.created = 0

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        self.created += 1
        return Invoice(
            kind=InvoiceKind.URL,
            external_id=f"ext-{ctx.order_id}",
            url=f"https://pay.example/{ctx.order_id}",
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        return PaymentResult(
            status=self.status,
            external_id=external_id,
            amount=self.amount,
            currency="RUB",
        )


@pytest.fixture
def provider() -> StubProvider:
    return StubProvider()


@pytest.fixture
def services(config, t, provider, secrets):
    registry = ProviderRegistry({"stub": provider}, "stub", config.lang)
    delivery = DeliveryService(config, t, admin_ids=(1,))
    checkout = CheckoutService(config, registry, delivery, admin_ids=(1,))
    return checkout, delivery, registry


@pytest.mark.asyncio
async def test_full_purchase_delivers_once(config, repos: Repos, services, fake_bot, provider):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(555, username="buyer")
    product = config.product("start")

    order = await checkout.create_order(repos, user, product, "stub")
    invoice = await checkout.bill(repos, order, user)

    assert invoice.url.endswith(str(order.id))
    assert order.external_id == f"ext-{order.id}"
    assert order.status == "pending"

    provider.status = PaymentStatus.PAID
    provider.amount = Decimal("1000")
    result = await checkout.poll(repos, order, user)

    assert await checkout.settle(repos, fake_bot, order, result) is True
    assert order.status == "delivered"
    assert "Ваши материалы" in "".join(fake_bot.texts_for(555))

    # The webhook arrives after the poll already settled it.
    assert await checkout.settle(repos, fake_bot, order, result) is False


@pytest.mark.asyncio
async def test_underpayment_is_refused(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(556)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID,
        external_id="ext-underpaid",
        amount=Decimal("10"),  # billed 1000
        currency="RUB",
    )
    assert await checkout.settle(repos, fake_bot, order, result) is False
    assert order.status == "pending"
    assert any("не совпала" in text for _, text in fake_bot.sent)


@pytest.mark.asyncio
async def test_one_cent_rounding_is_tolerated(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(557)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID,
        external_id="ext-rounded",
        amount=Decimal("999.99"),
        currency="RUB",
    )
    assert await checkout.settle(repos, fake_bot, order, result) is True


@pytest.mark.asyncio
async def test_overpayment_is_accepted(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(558)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="ext-over", amount=Decimal("1500"), currency="RUB"
    )
    assert await checkout.settle(repos, fake_bot, order, result) is True


@pytest.mark.asyncio
async def test_stars_charge_in_xtr_bypasses_fiat_check(config, repos: Repos, services, fake_bot):
    """A 1000 RUB order paid with 526 Stars must still settle."""
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(559)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="stars-1", amount=Decimal("526"), currency="XTR"
    )
    assert await checkout.settle(repos, fake_bot, order, result) is True


@pytest.mark.asyncio
async def test_wrong_currency_is_refused(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(560)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="ext-usd", amount=Decimal("1000"), currency="USD"
    )
    assert await checkout.settle(repos, fake_bot, order, result) is False
    assert order.status == "pending"


@pytest.mark.asyncio
async def test_duplicate_external_id_books_once(config, repos: Repos, services, fake_bot):
    """Two different orders cannot both claim one provider payment."""
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(561)

    first = await checkout.create_order(repos, user, config.product("start"), "stub")
    second = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="same-id", amount=Decimal("1000"), currency="RUB"
    )
    assert await checkout.settle(repos, fake_bot, first, result) is True
    assert await checkout.settle(repos, fake_bot, second, result) is False
    assert second.status == "pending"


@pytest.mark.asyncio
async def test_pending_result_does_not_settle(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(562)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")

    result = PaymentResult(status=PaymentStatus.PENDING, external_id="x")
    assert await checkout.settle(repos, fake_bot, order, result) is False
    assert order.status == "pending"


@pytest.mark.asyncio
async def test_subscription_grants_access(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(563)
    order = await checkout.create_order(repos, user, config.product("club"), "stub")

    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="sub-1", amount=Decimal("2000"), currency="RUB"
    )
    assert await checkout.settle(repos, fake_bot, order, result) is True

    sub = await repos.subs.get(user.id, "club")
    assert sub is not None and sub.is_active()


@pytest.mark.asyncio
async def test_referral_bonus_is_paid(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    referrer, _ = await repos.users.get_or_create(900, username="inviter")
    buyer, _ = await repos.users.get_or_create(901, referrer_id=900)
    assert buyer.referrer_id == 900

    order = await checkout.create_order(repos, buyer, config.product("start"), "stub")
    result = PaymentResult(
        status=PaymentStatus.PAID, external_id="ref-1", amount=Decimal("1000"), currency="RUB"
    )
    await checkout.settle(repos, fake_bot, order, result)

    await repos.session.refresh(referrer)
    assert referrer.balance == Decimal("200.00")  # 20% of 1000
    assert referrer.referral_earned == Decimal("200.00")
    assert any("200" in text for text in fake_bot.texts_for(900))


@pytest.mark.asyncio
async def test_self_referral_is_ignored(repos: Repos):
    user, _ = await repos.users.get_or_create(902, referrer_id=902)
    assert user.referrer_id is None


@pytest.mark.asyncio
async def test_unknown_referrer_is_ignored(repos: Repos):
    user, _ = await repos.users.get_or_create(903, referrer_id=99999)
    assert user.referrer_id is None


@pytest.mark.asyncio
async def test_promo_discount_applies_to_the_order(config, repos: Repos, services):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(904)
    order = await checkout.create_order(
        repos, user, config.product("start"), "stub", discount_percent=20
    )
    assert order.amount == Decimal("800.00")
    assert order.note == "promo -20%"


@pytest.mark.asyncio
async def test_webhook_finds_the_order_by_external_id(config, repos: Repos, services, fake_bot):
    checkout, _, _ = services
    user, _ = await repos.users.get_or_create(905)
    order = await checkout.create_order(repos, user, config.product("start"), "stub")
    await checkout.bill(repos, order, user)

    result = PaymentResult(
        status=PaymentStatus.PAID,
        external_id=f"ext-{order.id}",
        amount=Decimal("1000"),
        currency="RUB",
    )
    assert await checkout.settle_by_external(repos, fake_bot, "stub", result) is True
    assert order.status == "delivered"


@pytest.mark.asyncio
async def test_webhook_for_unknown_payment_is_ignored(repos: Repos, services, fake_bot):
    checkout, _, _ = services
    result = PaymentResult(status=PaymentStatus.PAID, external_id="nope", amount=Decimal("1"))
    assert await checkout.settle_by_external(repos, fake_bot, "stub", result) is False


class TestDiscount:
    def test_zero_percent_is_a_no_op(self):
        assert apply_discount(Decimal("1000"), 0) == Decimal("1000")

    def test_normal_discount(self):
        assert apply_discount(Decimal("1490"), 20) == Decimal("1192.00")

    def test_hundred_percent_is_free_not_negative(self):
        assert apply_discount(Decimal("1000"), 100) == Decimal("0.00")

    def test_over_hundred_is_clamped(self):
        assert apply_discount(Decimal("1000"), 500) == Decimal("0.00")
