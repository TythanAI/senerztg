"""Fleet-wide integrity: all 1000 generated bots must be deployable as shipped."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from botcore.config import NicheConfig
from botcore.i18n import Translator
from botcore.payments.telegram import MAX_STARS

ROOT = Path(__file__).resolve().parents[1]
BOTS = ROOT / "bots"

CONFIG_PATHS = sorted(BOTS.glob("*/*/config.yaml"))


def load_all() -> list[NicheConfig]:
    return [NicheConfig.load(path) for path in CONFIG_PATHS]


@pytest.fixture(scope="module")
def fleet() -> list[NicheConfig]:
    return load_all()


@pytest.fixture(scope="module")
def index() -> list[dict]:
    return json.loads((BOTS / "index.json").read_text(encoding="utf-8"))


def test_fleet_size(fleet):
    assert len(fleet) == 1000
    assert sum(1 for c in fleet if c.region == "ru") == 500
    assert sum(1 for c in fleet if c.region == "eu") == 500


def test_every_config_parses(fleet):
    # NicheConfig.load already validates; reaching here means all 1000 are legal.
    assert all(c.id for c in fleet)


def test_ids_are_unique(fleet):
    ids = [c.id for c in fleet]
    assert len(ids) == len(set(ids))


def test_names_are_unique(fleet):
    names = [c.name for c in fleet]
    assert len(names) == len(set(names))


def test_every_bot_has_a_catalog(fleet):
    for config in fleet:
        assert config.active_products(sellable_only=False), f"{config.id} has no product"


def test_most_of_the_fleet_sells_on_day_one(fleet):
    """A bot whose delivery is fully configured should need no content work."""
    ready = [c for c in fleet if not c.blocked_products()]
    assert len(ready) >= 850, f"only {len(ready)} bots are sellable as shipped"


def test_stock_and_service_bots_are_sellable_as_shipped(fleet):
    """These models deliver from inventory or an operator — never from a link."""
    instant = {"accounts", "keys", "topup", "monitor", "consult", "leadgen"}
    for config in fleet:
        archetype = config.niche.split("/")[0]
        if archetype not in instant:
            continue
        assert not config.blocked_products(), (
            f"{config.id} ({archetype}) has unsellable products: "
            f"{[(p.sku, p.missing_delivery()) for p in config.blocked_products()]}"
        )
        assert config.active_products(), config.id


def test_blocked_products_name_the_field_to_fix(fleet):
    """When something is held back the owner must be told exactly what to set."""
    for config in fleet:
        for product in config.blocked_products():
            missing = product.missing_delivery()
            assert missing, f"{config.id}/{product.sku} blocked for no stated reason"
            for field in missing:
                assert field in product.delivery, f"{config.id}/{product.sku}: {field}"


def test_account_products_are_never_blocked_by_placeholders(fleet):
    """Stock goods deliver from inventory, so config text cannot block them."""
    for config in fleet:
        for product in config.catalog:
            if product.kind == "account":
                assert product.is_deliverable(), f"{config.id}/{product.sku}"


def test_prices_are_positive(fleet):
    for config in fleet:
        for product in config.catalog:
            assert product.price > 0, f"{config.id}/{product.sku} is not priced"


def test_no_customer_ever_sees_a_placeholder(fleet):
    """Whatever the storefront shows must be fully deliverable."""
    for config in fleet:
        for product in config.active_products():
            for value in product.delivery.values():
                items = value if isinstance(value, (list, tuple)) else [value]
                for item in items:
                    assert "REPLACE" not in str(item), f"{config.id}/{product.sku}"


def test_every_bot_takes_money(fleet):
    for config in fleet:
        rails = set(config.payments.providers)
        assert rails - {"manual"}, f"{config.id} has no automated payment rail"


def test_ru_bots_offer_a_russian_card_rail(fleet):
    for config in (c for c in fleet if c.region == "ru"):
        assert {"yookassa", "sbp"} & set(config.payments.providers), config.id


def test_eu_bots_offer_stripe(fleet):
    for config in (c for c in fleet if c.region == "eu"):
        assert "stripe" in config.payments.providers, config.id


def test_every_bot_offers_crypto(fleet):
    for config in fleet:
        assert "cryptobot" in config.payments.providers, config.id


def test_stars_only_where_the_invoice_fits(fleet):
    """A Stars button that always errors would be worse than no button."""
    for config in fleet:
        if "stars" not in config.payments.providers:
            continue
        rate = config.payments.stars_rate
        assert rate > 0, config.id
        top = max(p.price for p in config.catalog)
        assert int(Decimal(top) / rate) <= MAX_STARS, f"{config.id} exceeds the Stars limit"


def test_subscription_products_have_periods(fleet):
    for config in fleet:
        for product in config.catalog:
            if product.kind == "subscription":
                assert product.period_days > 0, f"{config.id}/{product.sku}"


def test_trials_only_with_subscriptions(fleet):
    for config in fleet:
        if config.trial_days:
            assert config.has("subscription"), f"{config.id} offers a trial but sells no subscription"


def test_manual_rail_is_disabled_while_requisites_are_placeholders(fleet):
    """Printing fake card details to a paying customer must be impossible."""
    for config in fleet:
        if "manual" in config.payments.providers:
            assert config.manual_requisites() == "", (
                f"{config.id} ships real-looking manual requisites"
            )


def test_quiz_module_has_questions(fleet):
    for config in fleet:
        if config.has("quiz"):
            assert config.quiz, f"{config.id} enables the quiz module with no questions"
            for step in config.quiz:
                assert len(step.get("options") or []) >= 2, config.id


def test_faq_is_populated(fleet):
    for config in fleet:
        if config.has("faq"):
            assert len(config.faq) >= 3, config.id


def test_texts_render_without_placeholders_left_over(fleet):
    """Every override must survive .format() with the arguments we pass."""
    for config in fleet:
        t = Translator(config.lang, config.texts)
        rendered = t("start.welcome", name=config.name, tagline=config.tagline, first_name="X")
        assert "{" not in rendered, f"{config.id}: unresolved placeholder in start.welcome"


def test_languages_are_supported(fleet):
    from botcore.i18n import available_languages

    packs = set(available_languages())
    for config in fleet:
        assert config.lang in packs, f"{config.id} uses lang {config.lang} with no pack"


def test_each_bot_ships_every_deploy_file():
    expected = {
        "config.yaml",
        "bot.py",
        ".env.example",
        "README.md",
        "Dockerfile",
        "docker-compose.yml",
        ".gitignore",
    }
    for path in CONFIG_PATHS:
        directory = path.parent
        present = {p.name for p in directory.iterdir()}
        missing = expected - present
        assert not missing, f"{directory.name} is missing {missing}"
        assert any(p.suffix == ".service" for p in directory.iterdir()), directory.name


def test_env_example_lists_the_needed_credentials(fleet):
    for config in fleet:
        directory = _dir_for(config)
        env = (directory / ".env.example").read_text(encoding="utf-8")
        assert "BOT_TOKEN=" in env and "ADMIN_IDS=" in env, config.id
        if "yookassa" in config.payments.providers:
            assert "YOOKASSA_SHOP_ID=" in env, config.id
        if "stripe" in config.payments.providers:
            assert "STRIPE_SECRET_KEY=" in env, config.id
        if "cryptobot" in config.payments.providers:
            assert "CRYPTOBOT_TOKEN=" in env, config.id
        if "ton" in config.payments.providers:
            assert "TON_WALLET=" in env, config.id


def test_no_secret_ever_landed_in_a_config():
    """A committed key would be handed to the buyer along with the bot."""
    forbidden = ("sk_live_", "sk_test_", "whsec_", "AAF", "bot1")
    for path in CONFIG_PATHS:
        body = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in body, f"{path} looks like it contains a real secret"


def test_no_env_files_were_committed():
    assert not list(BOTS.glob("*/*/.env")), "a real .env must never be generated"


def test_index_matches_the_tree(index, fleet):
    assert len(index) == len(fleet)
    ids_on_disk = {c.id for c in fleet}
    assert {row["id"] for row in index} == ids_on_disk


def test_ports_are_unique(index):
    ports = [row["port"] for row in index]
    assert len(ports) == len(set(ports)), "two bots would fight over one port"


def test_ports_stay_in_the_unprivileged_range(index):
    for row in index:
        assert 1024 < row["port"] < 65536, row["id"]


def test_systemd_units_are_unique(index):
    units = [row["unit"] for row in index]
    assert len(units) == len(set(units))


def test_index_paths_exist(index):
    for row in index:
        assert (ROOT / row["path"] / "config.yaml").exists(), row["id"]


def test_compose_ports_match_the_index(index):
    for row in index:
        compose = yaml.safe_load((ROOT / row["path"] / "docker-compose.yml").read_text())
        service = compose["services"][row["unit"]]
        assert service["ports"] == [f"{row['port']}:{row['port']}"], row["id"]


def test_archetype_coverage(index):
    """Every business model we authored is actually represented."""
    used = {row["archetype"] for row in index}
    assert used == {
        "course", "club", "signals", "service", "consult", "shop", "saas",
        "leadgen", "accounts", "keys", "topup", "monitor",
    }


def test_account_shops_dominate_the_fleet(index):
    """The brief asked for a heavy tilt toward account sales."""
    stock_backed = [r for r in index if r["archetype"] in {"accounts", "keys"}]
    assert len(stock_backed) >= 400, f"only {len(stock_backed)} stock-backed shops"


def test_stock_module_implies_account_products(fleet):
    for config in fleet:
        if config.has("stock"):
            assert any(p.kind == "account" for p in config.catalog), config.id


def test_account_products_have_a_warranty(fleet):
    """A shop selling credentials without a stated warranty invites disputes."""
    for config in fleet:
        for product in config.catalog:
            if product.kind == "account":
                assert product.delivery.get("warranty"), f"{config.id}/{product.sku}"


def test_stock_shops_offer_a_wallet(fleet):
    """Repeat buyers are the whole economics of an account shop."""
    for config in fleet:
        if config.has("stock"):
            assert config.has("balance"), config.id


def test_account_products_have_no_period(fleet):
    for config in fleet:
        for product in config.catalog:
            if product.kind == "account":
                assert product.period_days == 0, f"{config.id}/{product.sku}"


def test_price_tiers_are_spread(index):
    tiers = {row["tier"] for row in index}
    assert tiers == {"budget", "standard", "premium", "elite"}


def _dir_for(config: NicheConfig) -> Path:
    for path in CONFIG_PATHS:
        if path.parent.name.endswith(config.id.split("-", 2)[2]) and path.parent.parent.name == config.region:
            return path.parent
    raise AssertionError(f"directory for {config.id} not found")


def test_router_builds_and_refuses_a_second_build(fleet):
    """One process hosts one bot; a second build must fail loudly, not subtly."""
    import botcore.handlers as handlers

    handlers._BUILT = False
    router = handlers.build_router(fleet[0].modules)
    assert router.name == "root"

    with pytest.raises(RuntimeError, match="own process"):
        handlers.build_router(fleet[1].modules)


def test_fleet_uses_many_module_combinations(fleet):
    combos = {tuple(sorted(c.modules)) for c in fleet}
    assert len(combos) >= 5, f"only {len(combos)} module combinations across the fleet"


def test_every_keyboard_renders_for_every_bot(fleet):
    """Catch a menu that would crash the moment a user taps /start."""
    from botcore.i18n import Translator
    from botcore.keyboards import catalog_menu, main_menu

    for config in fleet:
        t = Translator(config.lang, config.texts)
        menu = main_menu(config, t)
        assert menu.inline_keyboard, config.id
        products = config.active_products()
        assert catalog_menu(products, config, t).inline_keyboard, config.id


def test_wallet_bots_price_within_topup_limits(fleet):
    """A product nobody can afford with a maximum top-up is a dead end."""
    from botcore.handlers.balance import MAX_TOPUP

    for config in fleet:
        if not config.has("balance"):
            continue
        ceiling = MAX_TOPUP.get(config.currency)
        if ceiling is None:
            continue
        top = max(p.price for p in config.catalog)
        assert top <= ceiling, f"{config.id}: {top} exceeds the max top-up {ceiling}"
