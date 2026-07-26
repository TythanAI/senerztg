"""Configuration: niche spec (config.yaml, in git) + secrets (.env, never in git)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import yaml

SUPPORTED_REGIONS = {"ru", "eu"}
SUPPORTED_LANGS = {"ru", "en", "de", "es", "pl", "fr"}
SUPPORTED_CURRENCIES = {"RUB", "EUR", "USD", "XTR"}

# Which payment rails make sense where. The generator validates against this,
# so a RU bot can never ship with a Stripe-only checkout by accident.
REGION_PROVIDERS = {
    "ru": {"yookassa", "sbp", "cryptobot", "stars", "telegram_native", "ton", "manual"},
    "eu": {"stripe", "cryptobot", "stars", "telegram_native", "ton", "manual"},
}


#: Marker the generator leaves wherever the owner must supply their own value.
PLACEHOLDER_MARK = "REPLACE"


class ConfigError(ValueError):
    """Raised when a niche spec is structurally invalid."""


@dataclass(slots=True)
class Product:
    """One purchasable item. `kind` decides what happens after payment."""

    sku: str
    title: str
    price: Decimal
    kind: str = "digital"  # digital | subscription | service | consult
    description: str = ""
    period_days: int = 0  # subscriptions only
    delivery: dict[str, Any] = field(default_factory=dict)
    sort: int = 0
    active: bool = True

    VALID_KINDS = ("digital", "subscription", "service", "consult", "account")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Product":
        try:
            sku = str(raw["sku"]).strip()
            title = str(raw["title"]).strip()
            price = Decimal(str(raw["price"]))
        except KeyError as exc:  # pragma: no cover - guarded by validator
            raise ConfigError(f"product is missing required field {exc}") from exc
        except Exception as exc:
            raise ConfigError(f"product {raw!r} has an unparsable price") from exc

        kind = str(raw.get("kind", "digital"))
        if kind not in cls.VALID_KINDS:
            raise ConfigError(f"product {sku}: unknown kind {kind!r}")
        if price < 0:
            raise ConfigError(f"product {sku}: negative price")
        period = int(raw.get("period_days", 0) or 0)
        if kind == "subscription" and period <= 0:
            raise ConfigError(f"product {sku}: subscription needs period_days > 0")
        if kind == "account" and period:
            raise ConfigError(f"product {sku}: account products have no period_days")

        return cls(
            sku=sku,
            title=title,
            price=price,
            kind=kind,
            description=str(raw.get("description", "")),
            period_days=period,
            delivery=dict(raw.get("delivery") or {}),
            sort=int(raw.get("sort", 0) or 0),
            active=bool(raw.get("active", True)),
        )

    def is_free(self) -> bool:
        return self.price <= 0

    def missing_delivery(self) -> list[str]:
        """Delivery fields the owner has not filled in yet.

        A shipped config carries placeholders on purpose — nobody can guess a
        buyer's download link. But taking money for a product whose delivery
        is still `REPLACE-WITH-...` means the customer pays and receives a
        dead link, so the catalog hides these until they are real.

        Stock-backed goods are exempt: what they deliver comes from inventory,
        not from the config, and emptiness is already handled as "sold out".
        """
        if self.kind == "account":
            return []

        found: list[str] = []
        for key, value in self.delivery.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                if PLACEHOLDER_MARK in str(item):
                    found.append(key)
                    break
        return found

    def is_deliverable(self) -> bool:
        return not self.missing_delivery()


@dataclass(slots=True)
class PaymentConfig:
    providers: tuple[str, ...] = ("cryptobot",)
    default: str = "cryptobot"
    #: How many currency units one Telegram Star is worth, e.g. 1.9 for RUB or
    #: 0.019 for EUR. 0 disables Stars pricing. Telegram sells Stars at roughly
    #: $0.02 each — re-check this figure before launching a bot.
    stars_rate: Decimal = Decimal("0")
    crypto_assets: tuple[str, ...] = ("USDT", "TON", "BTC")
    invoice_ttl_minutes: int = 60

    @classmethod
    def from_dict(cls, raw: dict[str, Any], region: str) -> "PaymentConfig":
        providers = tuple(dict.fromkeys(raw.get("providers") or ["cryptobot"]))
        if not providers:
            raise ConfigError("payments.providers must not be empty")

        allowed = REGION_PROVIDERS[region]
        unknown = [p for p in providers if p not in allowed]
        if unknown:
            raise ConfigError(
                f"providers {unknown} are not available in region {region!r} "
                f"(allowed: {sorted(allowed)})"
            )

        default = str(raw.get("default") or providers[0])
        if default not in providers:
            raise ConfigError(f"payments.default {default!r} is not in providers {providers}")

        ttl = int(raw.get("invoice_ttl_minutes", 60) or 60)
        if ttl < 5:
            raise ConfigError("payments.invoice_ttl_minutes must be >= 5")

        try:
            stars_rate = Decimal(str(raw.get("stars_rate", 0) or 0))
        except Exception as exc:
            raise ConfigError(f"payments.stars_rate is not a number: {raw.get('stars_rate')!r}") from exc
        if stars_rate < 0:
            raise ConfigError("payments.stars_rate must not be negative")
        if "stars" in providers and stars_rate <= 0:
            raise ConfigError("payments.stars is enabled but stars_rate is 0")

        return cls(
            providers=providers,
            default=default,
            stars_rate=stars_rate,
            crypto_assets=tuple(raw.get("crypto_assets") or ("USDT", "TON", "BTC")),
            invoice_ttl_minutes=ttl,
        )


@dataclass(slots=True)
class NicheConfig:
    """The whole personality of one bot, loaded from config.yaml."""

    id: str
    name: str
    region: str
    lang: str
    currency: str
    niche: str
    tagline: str
    description: str
    modules: tuple[str, ...]
    payments: PaymentConfig
    catalog: tuple[Product, ...]
    texts: dict[str, str]
    support_username: str = ""
    referral_percent: int = 0
    trial_days: int = 0
    price_tier: str = "standard"
    faq: tuple[dict[str, str], ...] = ()
    quiz: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    KNOWN_MODULES = (
        "catalog",
        "subscription",
        "referral",
        "support",
        "faq",
        "quiz",
        "leadgen",
        "content",
        "booking",
        "reviews",
        "balance",
        "stock",
    )

    @property
    def is_ru(self) -> bool:
        return self.region == "ru"

    def product(self, sku: str) -> Product | None:
        for item in self.catalog:
            if item.sku == sku:
                return item
        return None

    def active_products(self, *, sellable_only: bool = True) -> list[Product]:
        """What the storefront shows.

        `sellable_only` drops products whose delivery is still a placeholder,
        so the bot cannot charge for something it has no way to hand over.
        Pass False to list the full catalog (admin views, doctor checks).
        """
        items = [p for p in self.catalog if p.active]
        if sellable_only:
            items = [p for p in items if p.is_deliverable()]
        return sorted(items, key=lambda p: (p.sort, p.price, p.sku))

    def blocked_products(self) -> list[Product]:
        """Active products held back because their delivery is unfinished."""
        return [p for p in self.catalog if p.active and not p.is_deliverable()]

    def has_placeholder_support(self) -> bool:
        return PLACEHOLDER_MARK in self.support_username

    def manual_requisites(self) -> str:
        """Payment details for the manual rail, empty when still a placeholder."""
        value = str(self.raw.get("manual_requisites", ""))
        return "" if PLACEHOLDER_MARK in value.upper() else value

    def has(self, module: str) -> bool:
        return module in self.modules

    def text(self, key: str, default: str = "") -> str:
        return self.texts.get(key, default)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "NicheConfig":
        if not isinstance(raw, dict):
            raise ConfigError("config root must be a mapping")

        for required in ("id", "name", "region", "lang", "currency", "niche"):
            if not raw.get(required):
                raise ConfigError(f"config is missing required field {required!r}")

        region = str(raw["region"]).lower()
        if region not in SUPPORTED_REGIONS:
            raise ConfigError(f"unsupported region {region!r}")
        lang = str(raw["lang"]).lower()
        if lang not in SUPPORTED_LANGS:
            raise ConfigError(f"unsupported lang {lang!r}")
        currency = str(raw["currency"]).upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ConfigError(f"unsupported currency {currency!r}")
        if region == "ru" and currency != "RUB":
            raise ConfigError("RU bots must price in RUB")
        if region == "eu" and currency not in {"EUR", "USD"}:
            raise ConfigError("EU/US bots must price in EUR or USD")

        modules = tuple(dict.fromkeys(raw.get("modules") or ["catalog", "support"]))
        unknown_modules = [m for m in modules if m not in cls.KNOWN_MODULES]
        if unknown_modules:
            raise ConfigError(f"unknown modules: {unknown_modules}")

        catalog = tuple(Product.from_dict(p) for p in (raw.get("catalog") or ()))
        if "catalog" in modules and not catalog:
            raise ConfigError("module 'catalog' is enabled but the catalog is empty")

        skus = [p.sku for p in catalog]
        dupes = {s for s in skus if skus.count(s) > 1}
        if dupes:
            raise ConfigError(f"duplicate SKUs: {sorted(dupes)}")

        if "subscription" in modules and not any(p.kind == "subscription" for p in catalog):
            raise ConfigError("module 'subscription' is enabled but no subscription product exists")

        if "stock" in modules and not any(p.kind == "account" for p in catalog):
            raise ConfigError("module 'stock' is enabled but no account product exists")

        referral = int(raw.get("referral_percent", 0) or 0)
        if not 0 <= referral <= 50:
            raise ConfigError("referral_percent must be between 0 and 50")

        return cls(
            id=str(raw["id"]),
            name=str(raw["name"]),
            region=region,
            lang=lang,
            currency=currency,
            niche=str(raw["niche"]),
            tagline=str(raw.get("tagline", "")),
            description=str(raw.get("description", "")),
            modules=modules,
            payments=PaymentConfig.from_dict(raw.get("payments") or {}, region),
            catalog=catalog,
            texts={str(k): str(v) for k, v in (raw.get("texts") or {}).items()},
            support_username=str(raw.get("support_username", "")),
            referral_percent=referral,
            trial_days=int(raw.get("trial_days", 0) or 0),
            price_tier=str(raw.get("price_tier", "standard")),
            faq=tuple(raw.get("faq") or ()),
            quiz=tuple(raw.get("quiz") or ()),
            raw=raw,
        )

    @classmethod
    def load(cls, path: str | Path) -> "NicheConfig":
        path = Path(path)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config not found: {path}") from exc
        except yaml.YAMLError as exc:
            raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
        try:
            return cls.from_dict(data)
        except ConfigError as exc:
            raise ConfigError(f"{path}: {exc}") from exc


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_ids(name: str) -> tuple[int, ...]:
    raw = os.getenv(name, "")
    out: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError:
            continue
    return tuple(out)


@dataclass(slots=True)
class Secrets:
    """Everything that must never enter git. Read from the process env."""

    bot_token: str = ""
    admin_ids: tuple[int, ...] = ()
    db_url: str = "sqlite+aiosqlite:///bot.db"

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    cryptobot_token: str = ""
    cryptobot_api: str = "https://pay.crypt.bot/api"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    telegram_provider_token: str = ""
    ton_wallet: str = ""
    tonapi_key: str = ""

    webhook_base: str = ""
    webhook_secret: str = ""
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    log_level: str = "INFO"
    sentry_dsn: str = ""
    use_webhook: bool = False
    dry_run: bool = False

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            admin_ids=_env_ids("ADMIN_IDS"),
            db_url=os.getenv("DB_URL", "sqlite+aiosqlite:///bot.db").strip(),
            yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID", "").strip(),
            yookassa_secret_key=os.getenv("YOOKASSA_SECRET_KEY", "").strip(),
            cryptobot_token=os.getenv("CRYPTOBOT_TOKEN", "").strip(),
            cryptobot_api=os.getenv("CRYPTOBOT_API", "https://pay.crypt.bot/api").strip(),
            stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", "").strip(),
            stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", "").strip(),
            telegram_provider_token=os.getenv("TELEGRAM_PROVIDER_TOKEN", "").strip(),
            ton_wallet=os.getenv("TON_WALLET", "").strip(),
            tonapi_key=os.getenv("TONAPI_KEY", "").strip(),
            webhook_base=os.getenv("WEBHOOK_BASE", "").strip().rstrip("/"),
            webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
            web_host=os.getenv("WEB_HOST", "0.0.0.0").strip(),
            web_port=int(os.getenv("WEB_PORT", "8080") or 8080),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            sentry_dsn=os.getenv("SENTRY_DSN", "").strip(),
            use_webhook=_env_bool("USE_WEBHOOK", False),
            dry_run=_env_bool("DRY_RUN", False),
        )

    def configured_providers(self) -> set[str]:
        """Rails that actually have credentials right now."""
        ready: set[str] = {"manual"}
        if self.yookassa_shop_id and self.yookassa_secret_key:
            ready.add("yookassa")
        if self.cryptobot_token:
            ready.add("cryptobot")
        if self.stripe_secret_key:
            ready.add("stripe")
        if self.telegram_provider_token:
            ready.add("telegram_native")
        if self.ton_wallet:
            ready.add("ton")
        ready.add("stars")  # Stars need no external merchant account
        return ready

    def missing_for(self, providers: Iterable[str]) -> list[str]:
        ready = self.configured_providers()
        return [p for p in providers if p not in ready]
