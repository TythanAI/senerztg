"""Config validation — the guard rail that keeps a broken bot off the VPS."""

from __future__ import annotations

from decimal import Decimal

import pytest

from botcore.config import ConfigError, NicheConfig, Product, Secrets
from botcore.i18n import Translator
from botcore.utils import apply_discount, fmt_money, parse_start_payload
from conftest import make_config


class TestNicheValidation:
    def test_valid_config_loads(self, config: NicheConfig):
        assert config.id == "ru-000-test"
        assert config.is_ru
        assert len(config.active_products()) == 3

    def test_ru_must_price_in_roubles(self):
        with pytest.raises(ConfigError, match="RUB"):
            make_config(currency="EUR")

    def test_eu_cannot_use_yookassa(self):
        with pytest.raises(ConfigError, match="not available in region"):
            make_config(
                region="eu",
                lang="en",
                currency="EUR",
                payments={"providers": ["yookassa"], "default": "yookassa"},
            )

    def test_default_provider_must_be_offered(self):
        with pytest.raises(ConfigError, match="not in providers"):
            make_config(payments={"providers": ["cryptobot"], "default": "stars",
                                  "stars_rate": "1.9"})

    def test_stars_without_a_rate_is_rejected(self):
        with pytest.raises(ConfigError, match="stars_rate"):
            make_config(payments={"providers": ["stars"], "default": "stars"})

    def test_duplicate_skus_are_rejected(self):
        with pytest.raises(ConfigError, match="duplicate SKUs"):
            make_config(
                catalog=[
                    {"sku": "a", "title": "A", "price": 1},
                    {"sku": "a", "title": "B", "price": 2},
                ]
            )

    def test_subscription_module_needs_a_subscription_product(self):
        with pytest.raises(ConfigError, match="no subscription product"):
            make_config(
                modules=["catalog", "subscription"],
                catalog=[{"sku": "a", "title": "A", "price": 1}],
            )

    def test_subscription_needs_a_period(self):
        with pytest.raises(ConfigError, match="period_days"):
            make_config(
                modules=["catalog", "subscription"],
                catalog=[{"sku": "a", "title": "A", "price": 1, "kind": "subscription"}],
            )

    def test_empty_catalog_with_catalog_module_is_rejected(self):
        with pytest.raises(ConfigError, match="catalog is empty"):
            make_config(modules=["catalog"], catalog=[])

    def test_unknown_module_is_rejected(self):
        with pytest.raises(ConfigError, match="unknown modules"):
            make_config(modules=["catalog", "teleportation"])

    def test_negative_price_is_rejected(self):
        with pytest.raises(ConfigError, match="negative price"):
            make_config(catalog=[{"sku": "a", "title": "A", "price": -5}])

    def test_referral_cap(self):
        with pytest.raises(ConfigError, match="referral_percent"):
            make_config(referral_percent=90)

    def test_unknown_product_kind_is_rejected(self):
        with pytest.raises(ConfigError, match="unknown kind"):
            make_config(catalog=[{"sku": "a", "title": "A", "price": 1, "kind": "magic"}])

    def test_missing_required_field(self):
        with pytest.raises(ConfigError, match="missing required field"):
            NicheConfig.from_dict({"name": "x"})


class TestProductLookup:
    def test_product_by_sku(self, config: NicheConfig):
        assert config.product("club").kind == "subscription"
        assert config.product("nope") is None

    def test_inactive_products_are_hidden(self):
        config = make_config(
            modules=["catalog", "support"],
            catalog=[
                {"sku": "on", "title": "On", "price": 10},
                {"sku": "off", "title": "Off", "price": 20, "active": False},
            ],
        )
        assert [p.sku for p in config.active_products()] == ["on"]

    def test_products_sort_by_sort_then_price(self):
        config = make_config(
            modules=["catalog", "support"],
            catalog=[
                {"sku": "c", "title": "C", "price": 300, "sort": 1},
                {"sku": "a", "title": "A", "price": 100, "sort": 0},
                {"sku": "b", "title": "B", "price": 200, "sort": 0},
            ],
        )
        assert [p.sku for p in config.active_products()] == ["a", "b", "c"]

    def test_free_product(self):
        product = Product.from_dict({"sku": "f", "title": "Free", "price": 0})
        assert product.is_free()


class TestSecrets:
    def test_reports_missing_credentials(self):
        secrets = Secrets(cryptobot_token="x")
        assert secrets.missing_for(["cryptobot", "stripe"]) == ["stripe"]

    def test_stars_never_needs_credentials(self):
        assert Secrets().missing_for(["stars"]) == []

    def test_yookassa_needs_both_halves(self):
        assert Secrets(yookassa_shop_id="1").missing_for(["yookassa"]) == ["yookassa"]
        assert Secrets(yookassa_shop_id="1", yookassa_secret_key="k").missing_for(
            ["yookassa"]
        ) == []


class TestFormatting:
    def test_roubles_use_thin_grouping(self):
        assert fmt_money(Decimal("1490"), "RUB") == "1 490 ₽"

    def test_euro_suffix(self):
        assert fmt_money(Decimal("29"), "EUR") == "29 €"

    def test_dollar_prefix(self):
        assert fmt_money(Decimal("19.99"), "USD") == "$19.99"

    def test_decimals_kept(self):
        assert fmt_money(Decimal("19.50"), "EUR") == "19.50 €"


class TestStartPayload:
    def test_referral_payload(self):
        assert parse_start_payload("ref12345") == (12345, None)

    def test_utm_payload(self):
        assert parse_start_payload("utm_ads") == (None, "utm_ads")

    def test_empty_payload(self):
        assert parse_start_payload("") == (None, None)

    def test_ref_without_digits_is_a_source(self):
        assert parse_start_payload("refer") == (None, "refer")


class TestTranslator:
    def test_language_pack(self):
        assert Translator("ru")("common.back") == "⬅️ Назад"

    def test_override_wins(self):
        t = Translator("ru", {"common.back": "Обратно"})
        assert t("common.back") == "Обратно"

    def test_falls_back_to_english(self):
        assert Translator("de")("admin.stats") == "📊 Stats"

    def test_missing_key_returns_the_key(self):
        assert Translator("ru")("nope.nothing") == "nope.nothing"

    def test_bad_format_does_not_raise(self):
        t = Translator("ru", {"x.y": "{missing_placeholder}"})
        assert t("x.y", other=1) == "{missing_placeholder}"

    def test_placeholders_substitute(self):
        assert "5" in Translator("ru")("promo.ok", percent=5)
