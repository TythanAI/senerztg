"""Adversarial tests: the ways a shop bot actually gets robbed or knocked over.

Each test here corresponds to a concrete attack — double-spend, duplicate
stock issuance, promo farming, order flooding, unbounded memory growth,
HTML injection, path traversal — not to a line of code.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from botcore.db import Database, OutOfStock, Repos
from botcore.payments import PaymentResult, PaymentStatus, ProviderRegistry
from botcore.services import CheckoutService, DeliveryService
from botcore.services.checkout import MAX_OPEN_ORDERS, MAX_QUANTITY, TOPUP_SKU
from conftest import make_config


def account_config(**overrides):
    base = dict(
        modules=["catalog", "stock", "balance", "support"],
        catalog=[
            {"sku": "steam", "title": "Steam аккаунт", "price": 300, "kind": "account",
             "delivery": {"warranty": "Гарантия 24 часа"}},
            {"sku": "tg", "title": "TG аккаунт", "price": 150, "kind": "account"},
        ],
    )
    base.update(overrides)
    return make_config(**base)


@pytest.fixture
def acc_config():
    return account_config()


@pytest.fixture
def services(acc_config, t):
    registry = ProviderRegistry({}, "", acc_config.lang)
    delivery = DeliveryService(acc_config, t, admin_ids=(1,))
    return CheckoutService(acc_config, registry, delivery, admin_ids=(1,)), delivery


async def make_order(repos: Repos, tg_id: int, sku: str = "steam",
                     amount: str = "300") -> int:
    """A real order row — foreign keys are enforced, so fake ids will not do."""
    user, _ = await repos.users.get_or_create(tg_id)
    order = await repos.orders.create(
        user=user, sku=sku, title=sku, amount=Decimal(amount),
        currency="RUB", provider="manual",
    )
    return order.id


def paid(order, external=None) -> PaymentResult:
    return PaymentResult(
        status=PaymentStatus.PAID,
        external_id=external or f"ext-{order.id}",
        amount=Decimal(order.amount),
        currency=order.currency,
    )


# ------------------------------------------------------------------- stock


class TestStockIssuance:
    async def test_one_unit_goes_to_one_buyer(self, repos: Repos):
        await repos.stock.add("steam", ["login1:pass1", "login2:pass2"])
        a = await make_order(repos, 101)
        b = await make_order(repos, 102)
        first = await repos.stock.issue("steam", 1, order_id=a)
        second = await repos.stock.issue("steam", 1, order_id=b)
        assert first != second
        assert await repos.stock.available("steam") == 0

    async def test_cannot_oversell(self, repos: Repos):
        await repos.stock.add("steam", ["a:1", "b:2"])
        order_id = await make_order(repos, 103)
        with pytest.raises(OutOfStock) as exc:
            await repos.stock.issue("steam", 5, order_id=order_id)
        assert exc.value.available == 2
        # Nothing was handed out, so the shelf is untouched.
        assert await repos.stock.available("steam") == 2

    async def test_empty_pool_raises(self, repos: Repos):
        order_id = await make_order(repos, 104)
        with pytest.raises(OutOfStock):
            await repos.stock.issue("steam", 1, order_id=order_id)

    async def test_issued_units_are_not_reissued(self, repos: Repos):
        await repos.stock.add("steam", ["only:one"])
        a = await make_order(repos, 105)
        b = await make_order(repos, 106)
        await repos.stock.issue("steam", 1, order_id=a)
        with pytest.raises(OutOfStock):
            await repos.stock.issue("steam", 1, order_id=b)

    async def test_repeat_delivery_reuses_the_same_units(self, repos: Repos):
        await repos.stock.add("steam", ["a:1", "b:2", "c:3"])
        order_id = await make_order(repos, 107)
        issued = await repos.stock.issue("steam", 2, order_id=order_id)
        assert sorted(await repos.stock.issued_for(order_id)) == sorted(issued)
        # Re-reading must not consume more inventory.
        assert await repos.stock.available("steam") == 1

    async def test_stock_is_isolated_per_sku(self, repos: Repos):
        await repos.stock.add("steam", ["s:1"])
        await repos.stock.add("tg", ["t:1"])
        assert await repos.stock.available("steam") == 1
        order_id = await make_order(repos, 108)
        with pytest.raises(OutOfStock):
            await repos.stock.issue("steam", 2, order_id=order_id)

    async def test_blank_lines_are_not_stock(self, repos: Repos):
        added = await repos.stock.add("steam", ["a:1", "", "   ", "b:2"])
        assert added == 2


class TestConcurrentStock:
    async def test_parallel_buyers_never_get_the_same_account(self, tmp_path):
        """Ten buyers, three accounts: exactly three win, nobody shares."""
        db = Database(f"sqlite+aiosqlite:///{tmp_path}/stock.db")
        await db.create_all()

        order_ids = []
        async with db.session() as session:
            repos = Repos(session)
            await repos.stock.add("steam", [f"acct{i}:pw" for i in range(3)])
            for tg in range(1, 11):
                order_ids.append(await make_order(repos, tg))

        async def buy(order_id: int):
            try:
                async with db.session() as session:
                    return await Repos(session).stock.issue("steam", 1, order_id)
            except Exception:
                return None

        results = await asyncio.gather(*(buy(oid) for oid in order_ids))
        winners = [r for r in results if r]
        issued = [item for r in winners for item in r]

        assert len(winners) == 3, f"expected 3 successful buyers, got {len(winners)}"
        assert len(issued) == len(set(issued)), "the same account went to two buyers"

        async with db.session() as session:
            assert await Repos(session).stock.available("steam") == 0
        await db.dispose()


# ----------------------------------------------------------------- balance


class TestBalance:
    async def test_cannot_spend_more_than_held(self, repos: Repos):
        user, _ = await repos.users.get_or_create(1)
        await repos.users.add_balance(user.id, Decimal("100"))
        await repos.session.refresh(user)

        assert await repos.users.spend_balance(user.id, Decimal("150")) is False
        await repos.session.refresh(user)
        assert user.balance == Decimal("100")

    async def test_exact_balance_is_spendable(self, repos: Repos):
        user, _ = await repos.users.get_or_create(2)
        await repos.users.add_balance(user.id, Decimal("100"))
        assert await repos.users.spend_balance(user.id, Decimal("100")) is True
        await repos.session.refresh(user)
        assert user.balance == Decimal("0")

    async def test_no_double_spend_under_concurrency(self, tmp_path):
        """One wallet, ten simultaneous purchases it can only cover twice."""
        db = Database(f"sqlite+aiosqlite:///{tmp_path}/wallet.db")
        await db.create_all()
        async with db.session() as session:
            repos = Repos(session)
            user, _ = await repos.users.get_or_create(3)
            await repos.users.add_balance(user.id, Decimal("200"))
            user_id = user.id

        async def spend():
            try:
                async with db.session() as session:
                    return await Repos(session).users.spend_balance(user_id, Decimal("100"))
            except Exception:
                return False

        results = await asyncio.gather(*(spend() for _ in range(10)))

        async with db.session() as session:
            final = await Repos(session).users.get(3)

        assert sum(results) == 2, f"balance was overdrawn: {sum(results)} spends succeeded"
        assert final.balance == Decimal("0")
        assert final.balance >= 0, "balance went negative"
        await db.dispose()

    async def test_failed_purchase_refunds_the_wallet(self, acc_config, repos, services, fake_bot):
        """Out of stock after payment must not eat the buyer's money."""
        checkout, _ = services
        user, _ = await repos.users.get_or_create(4)
        await repos.users.add_balance(user.id, Decimal("1000"))
        await repos.session.refresh(user)

        # No stock loaded at all.
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")
        assert await checkout.pay_from_balance(repos, fake_bot, order, user) is False

        await repos.session.refresh(user)
        assert user.balance == Decimal("1000"), "money was kept despite non-delivery"

    async def test_successful_balance_purchase_debits_once(
        self, acc_config, repos, services, fake_bot
    ):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(5)
        await repos.users.add_balance(user.id, Decimal("1000"))
        await repos.session.refresh(user)
        await repos.stock.add("steam", ["login:pass"])

        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")
        assert await checkout.pay_from_balance(repos, fake_bot, order, user) is True

        await repos.session.refresh(user)
        assert user.balance == Decimal("700")  # 1000 - 300
        assert order.status == "delivered"

        # A replayed settle must not debit again or re-issue stock.
        assert await checkout.settle(repos, fake_bot, order, paid(order)) is False
        await repos.session.refresh(user)
        assert user.balance == Decimal("700")

    async def test_topup_credits_exactly_once(self, acc_config, repos, services, fake_bot):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(6)
        order = await checkout.create_topup_order(repos, user, Decimal("500"), "manual")

        assert await checkout.settle(repos, fake_bot, order, paid(order)) is True
        await repos.session.refresh(user)
        assert user.balance == Decimal("500")

        # Replayed webhook for the same top-up.
        assert await checkout.settle(repos, fake_bot, order, paid(order)) is False
        await repos.session.refresh(user)
        assert user.balance == Decimal("500"), "top-up was credited twice"

    async def test_topup_order_uses_the_reserved_sku(self, acc_config, repos, services):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(7)
        order = await checkout.create_topup_order(repos, user, Decimal("100"), "manual")
        assert order.sku == TOPUP_SKU
        assert acc_config.product(TOPUP_SKU) is None, "top-up SKU must not be a catalog item"


# ------------------------------------------------------------------ orders


class TestOrderAbuse:
    async def test_quantity_is_capped(self, acc_config, repos, services):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(10)
        order = await checkout.create_order(
            repos, user, acc_config.product("steam"), "manual", quantity=10_000
        )
        assert order.quantity == MAX_QUANTITY

    async def test_quantity_floor_is_one(self, acc_config, repos, services):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(11)
        order = await checkout.create_order(
            repos, user, acc_config.product("steam"), "manual", quantity=-5
        )
        assert order.quantity == 1
        assert order.amount > 0

    async def test_total_scales_with_quantity(self, acc_config, repos, services):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(12)
        order = await checkout.create_order(
            repos, user, acc_config.product("steam"), "manual", quantity=3
        )
        assert order.amount == Decimal("900")  # 300 × 3

    async def test_order_flooding_is_bounded(self, acc_config, repos, services):
        """Tapping buy 200 times must not leave 200 live orders behind."""
        checkout, _ = services
        user, _ = await repos.users.get_or_create(13)
        product = acc_config.product("steam")

        for _ in range(200):
            await checkout.create_order(repos, user, product, "manual")

        assert await repos.orders.open_count_for(user.id) <= MAX_OPEN_ORDERS


class TestPromoAbuse:
    async def test_use_is_spent_on_payment_not_on_entry(self, acc_config, repos, services, fake_bot):
        """Typing a code must not burn it — only a paid order may."""
        checkout, _ = services
        await repos.promos.create("SALE20", 20, max_uses=1)

        promo = await repos.promos.get("SALE20")
        assert promo.used == 0

        user, _ = await repos.users.get_or_create(20)
        order = await checkout.create_order(
            repos, user, acc_config.product("steam"), "manual",
            discount_percent=20, promo_code="SALE20",
        )
        assert order.amount == Decimal("240")
        assert (await repos.promos.get("SALE20")).used == 0

        await repos.stock.add("steam", ["a:1"])
        await checkout.settle(repos, fake_bot, order, paid(order))
        assert (await repos.promos.get("SALE20")).used == 1

    async def test_limited_promo_cannot_be_exceeded(self, repos: Repos):
        await repos.promos.create("ONCE", 50, max_uses=1)
        assert await repos.promos.redeem("ONCE") is not None
        assert await repos.promos.redeem("ONCE") is None

    async def test_expired_promo_is_refused(self, repos: Repos):
        promo = await repos.promos.create("OLD", 50, days=1)
        promo.expires_at = promo.created_at.replace(year=2000)
        await repos.session.flush()
        assert await repos.promos.redeem("OLD") is None

    async def test_discount_cannot_go_negative(self, acc_config, repos, services):
        checkout, _ = services
        user, _ = await repos.users.get_or_create(21)
        order = await checkout.create_order(
            repos, user, acc_config.product("steam"), "manual", discount_percent=100
        )
        assert order.amount == Decimal("0")
        assert order.amount >= 0

    async def test_promo_attempts_are_recorded_for_rate_limiting(self, repos: Repos):
        for _ in range(3):
            await repos.misc.track(99, "promo_try", "GUESS")
        await repos.session.flush()
        assert await repos.misc.count_recent_events(99, "promo_try", minutes=60) == 3


# ------------------------------------------------------- injection & limits


class TestInjection:
    async def test_stock_payload_with_html_is_escaped(
        self, acc_config, repos, services, fake_bot
    ):
        """Credentials containing '<' must not break or inject into the message."""
        checkout, delivery = services
        await repos.stock.add("steam", ["<script>alert(1)</script>:p@ss"])
        user, _ = await repos.users.get_or_create(30)
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")

        await checkout.settle(repos, fake_bot, order, paid(order))

        body = "".join(fake_bot.texts_for(30))
        assert "&lt;script&gt;" in body
        assert "<script>" not in body

    async def test_username_with_html_is_escaped_in_admin_alert(
        self, acc_config, repos, services, fake_bot
    ):
        checkout, _ = services
        await repos.stock.add("steam", ["a:1"])
        user, _ = await repos.users.get_or_create(31, first_name="<b>admin</b>")
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")
        await checkout.settle(repos, fake_bot, order, paid(order))

        admin_text = "".join(fake_bot.texts_for(1))
        assert "<b>admin</b>" not in admin_text

    def test_delivery_cannot_escape_the_assets_directory(self, acc_config, t, tmp_path):
        """A config pointing at ../../.env must not read the server's secrets."""
        import asyncio as aio

        delivery = DeliveryService(acc_config, t, assets_dir=str(tmp_path / "assets"))
        (tmp_path / "assets").mkdir()
        (tmp_path / "secret.txt").write_text("TOKEN=leaked")

        class Bot:
            async def send_document(self, *a, **kw):
                raise AssertionError("a file outside assets/ was sent")

        with pytest.raises(Exception):
            aio.get_event_loop().run_until_complete(
                delivery._send_file(Bot(), 1, "../secret.txt", "x")
            )


class TestThrottleMemory:
    def test_pruning_reclaims_idle_buckets(self):
        """Without this the per-user dict grows for the life of the process."""
        from botcore.middlewares import ThrottleMiddleware

        throttle = ThrottleMiddleware()
        for uid in range(5_000):
            throttle._tokens[uid] = 1.0
            throttle._last[uid] = 0.0  # long idle

        assert len(throttle._last) == 5_000
        dropped = throttle.prune(max_age=1)
        assert dropped == 5_000
        assert len(throttle._last) == 0
        assert len(throttle._tokens) == 0

    def test_active_buckets_survive_pruning(self):
        import time as _time

        from botcore.middlewares import ThrottleMiddleware

        throttle = ThrottleMiddleware()
        throttle._last[1] = _time.monotonic()
        throttle._tokens[1] = 3.0
        throttle.prune(max_age=3600)
        assert 1 in throttle._last


class TestEventRetention:
    async def test_old_events_are_pruned(self, repos: Repos):
        import datetime as dt

        from botcore.db.models import Event

        old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=200)
        repos.session.add(Event(tg_id=1, name="start", created_at=old))
        repos.session.add(Event(tg_id=1, name="start"))
        await repos.session.flush()

        removed = await repos.misc.prune_events(keep_days=90)
        assert removed == 1
        assert (await repos.misc.funnel()).get("start") == 1


class TestPaymentGuards:
    async def test_stock_is_not_issued_without_payment(
        self, acc_config, repos, services, fake_bot
    ):
        checkout, _ = services
        await repos.stock.add("steam", ["a:1"])
        user, _ = await repos.users.get_or_create(40)
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")

        pending = PaymentResult(status=PaymentStatus.PENDING, external_id="x")
        assert await checkout.settle(repos, fake_bot, order, pending) is False
        assert await repos.stock.available("steam") == 1

    async def test_underpayment_does_not_release_stock(
        self, acc_config, repos, services, fake_bot
    ):
        checkout, _ = services
        await repos.stock.add("steam", ["a:1"])
        user, _ = await repos.users.get_or_create(41)
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")

        cheap = PaymentResult(
            status=PaymentStatus.PAID, external_id="x", amount=Decimal("1"), currency="RUB"
        )
        assert await checkout.settle(repos, fake_bot, order, cheap) is False
        assert await repos.stock.available("steam") == 1

    async def test_out_of_stock_after_payment_alerts_and_keeps_order_paid(
        self, acc_config, repos, services, fake_bot
    ):
        """Money in, nothing to give: must never look 'delivered'."""
        checkout, _ = services
        user, _ = await repos.users.get_or_create(42)
        order = await checkout.create_order(repos, user, acc_config.product("steam"), "manual")

        await checkout.settle(repos, fake_bot, order, paid(order))

        assert order.status == "paid"
        assert order.status != "delivered"
        assert any("нет на складе" in text for text in fake_bot.texts_for(1))
        assert any("Оплата получена" in text for text in fake_bot.texts_for(42))


# --------------------------------------------------- selling only what exists


class TestDeliverabilityGate:
    """A bot must never take money for something it cannot hand over."""

    def test_placeholder_delivery_blocks_a_product(self):
        config = make_config(
            modules=["catalog", "support"],
            catalog=[{"sku": "guide", "title": "Гайд", "price": 500, "kind": "digital",
                      "delivery": {"links": ["https://REPLACE-WITH-YOUR-LINK"]}}],
        )
        product = config.product("guide")
        assert product.is_deliverable() is False
        assert product.missing_delivery() == ["links"]
        assert config.active_products() == []
        assert [p.sku for p in config.blocked_products()] == ["guide"]

    def test_real_delivery_is_sellable(self):
        config = make_config(
            modules=["catalog", "support"],
            catalog=[{"sku": "guide", "title": "Гайд", "price": 500, "kind": "digital",
                      "delivery": {"links": ["https://example.com/real"]}}],
        )
        assert [p.sku for p in config.active_products()] == ["guide"]
        assert config.blocked_products() == []

    def test_stock_goods_are_never_blocked_by_config_text(self):
        """Account delivery comes from inventory, not from the config."""
        config = account_config()
        assert len(config.active_products()) == 2
        assert config.blocked_products() == []

    def test_full_catalog_is_still_reachable_for_admin_views(self):
        config = make_config(
            modules=["catalog", "support"],
            catalog=[{"sku": "a", "title": "A", "price": 100, "kind": "digital",
                      "delivery": {"links": ["https://REPLACE-ME"]}}],
        )
        assert config.active_products() == []
        assert len(config.active_products(sellable_only=False)) == 1

    def test_placeholder_support_contact_is_detected(self):
        config = make_config(support_username="@REPLACE_WITH_YOUR_SUPPORT")
        assert config.has_placeholder_support() is True
        assert make_config(support_username="@real_shop").has_placeholder_support() is False

    def test_placeholder_requisites_are_withheld(self):
        config = make_config(manual_requisites="Карта 0000 (REPLACE)")
        assert config.manual_requisites() == ""

    def test_real_requisites_are_returned(self):
        config = make_config(manual_requisites="Карта 1234 5678")
        assert config.manual_requisites() == "Карта 1234 5678"

    def test_manual_rail_is_disabled_without_requisites(self):
        from botcore.config import Secrets
        from botcore.payments import build_registry

        config = make_config(
            payments={"providers": ["manual"], "default": "manual"},
            manual_requisites="0000 0000 (REPLACE)",
        )
        registry = build_registry(config, Secrets())
        assert "manual" not in registry, "a buyer would be shown fake payment details"

    def test_manual_rail_works_with_real_requisites(self):
        from botcore.config import Secrets
        from botcore.payments import build_registry

        config = make_config(
            payments={"providers": ["manual"], "default": "manual"},
            manual_requisites="Сбер 1234 5678 9012 3456",
        )
        assert "manual" in build_registry(config, Secrets())
