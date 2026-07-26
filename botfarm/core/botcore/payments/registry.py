"""Builds the live set of payment providers from config.yaml + .env.

A provider whose credentials are missing is skipped with a warning rather than
crashing the bot: a shop that sells three ways should keep selling when one
acquirer has not been connected yet.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable

from .base import PaymentError, PaymentProvider
from .cryptobot import CryptoBotProvider
from .manual import ManualProvider
from .stripe import StripeProvider
from .telegram import StarsProvider, TelegramPaymentsProvider
from .ton import TonProvider
from .yookassa import SbpProvider, YooKassaProvider

if TYPE_CHECKING:  # pragma: no cover
    from ..config import NicheConfig, Secrets

log = logging.getLogger(__name__)

#: Buyer-facing button labels per language.
LABELS = {
    "yookassa": {"ru": "💳 Банковская карта", "en": "💳 Bank card"},
    "sbp": {"ru": "🏦 СБП (по QR)", "en": "🏦 SBP (QR)"},
    "cryptobot": {"ru": "🪙 Крипта (USDT/TON/BTC)", "en": "🪙 Crypto (USDT/TON/BTC)"},
    "stripe": {"ru": "💳 Card / Apple Pay", "en": "💳 Card / Apple Pay"},
    "telegram_native": {"ru": "💳 Оплата в Telegram", "en": "💳 Pay in Telegram"},
    "stars": {"ru": "⭐ Telegram Stars", "en": "⭐ Telegram Stars"},
    "ton": {"ru": "💎 TON", "en": "💎 TON"},
    "manual": {"ru": "🧾 Перевод по реквизитам", "en": "🧾 Bank transfer"},
}


class ProviderRegistry:
    """Ordered, ready-to-use providers for one bot."""

    def __init__(self, providers: dict[str, PaymentProvider], default: str, lang: str = "ru") -> None:
        self._providers = providers
        self._default = default if default in providers else next(iter(providers), "")
        self.lang = lang

    def __contains__(self, name: object) -> bool:
        return name in self._providers

    def __len__(self) -> int:
        return len(self._providers)

    def __iter__(self):
        return iter(self._providers.values())

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)

    @property
    def default(self) -> str:
        return self._default

    def get(self, name: str) -> PaymentProvider | None:
        return self._providers.get(name)

    def require(self, name: str) -> PaymentProvider:
        provider = self._providers.get(name)
        if provider is None:
            raise PaymentError(f"payment provider {name!r} is not configured")
        return provider

    def label(self, name: str) -> str:
        per_lang = LABELS.get(name, {})
        return per_lang.get(self.lang) or per_lang.get("en") or name

    def for_currency(self, currency: str) -> list[PaymentProvider]:
        return [p for p in self._providers.values() if p.supports(currency)]

    async def close(self) -> None:
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:  # pragma: no cover - shutdown must not raise
                log.exception("failed to close provider %s", provider.name)


def build_registry(config: "NicheConfig", secrets: "Secrets") -> ProviderRegistry:
    """Instantiate every provider the niche asks for and the env can back."""
    providers: dict[str, PaymentProvider] = {}

    for name in config.payments.providers:
        try:
            provider = _build_one(name, config, secrets)
        except PaymentError as exc:
            log.warning("payment provider %r disabled: %s", name, exc)
            continue
        if provider is None:
            continue
        if not provider.supports(config.currency) and name not in {"stars"}:
            log.warning(
                "payment provider %r cannot settle %s — disabled", name, config.currency
            )
            continue
        providers[name] = provider

    if not providers:
        log.error(
            "no payment provider is configured for %s — checkout will be unavailable",
            config.id,
        )

    return ProviderRegistry(providers, config.payments.default, config.lang)


def _build_one(
    name: str, config: "NicheConfig", secrets: "Secrets"
) -> PaymentProvider | None:
    ttl = config.payments.invoice_ttl_minutes
    success_url = f"{secrets.webhook_base}/paid" if secrets.webhook_base else ""

    if name == "yookassa":
        return YooKassaProvider(
            secrets.yookassa_shop_id,
            secrets.yookassa_secret_key,
            return_url=success_url,
        )
    if name == "sbp":
        return SbpProvider(
            secrets.yookassa_shop_id,
            secrets.yookassa_secret_key,
            return_url=success_url,
        )
    if name == "cryptobot":
        return CryptoBotProvider(
            secrets.cryptobot_token,
            assets=config.payments.crypto_assets,
            api_base=secrets.cryptobot_api,
            ttl_minutes=ttl,
        )
    if name == "stripe":
        return StripeProvider(
            secrets.stripe_secret_key,
            webhook_secret=secrets.stripe_webhook_secret,
            success_url=success_url,
        )
    if name == "telegram_native":
        return TelegramPaymentsProvider(secrets.telegram_provider_token)
    if name == "stars":
        return StarsProvider(rate=config.payments.stars_rate)
    if name == "ton":
        return TonProvider(secrets.ton_wallet, api_key=secrets.tonapi_key)
    if name == "manual":
        return ManualProvider(
            requisites=config.raw.get("manual_requisites", ""), lang=config.lang
        )

    log.warning("unknown payment provider %r in %s", name, config.id)
    return None


def describe(providers: Iterable[str], lang: str = "ru") -> str:
    """Human-readable rail list for READMEs and sales copy."""
    return ", ".join(
        LABELS.get(name, {}).get(lang) or LABELS.get(name, {}).get("en") or name
        for name in providers
    )
