"""Small shared helpers: money formatting, HTML escaping, deep links."""

from __future__ import annotations

import datetime as dt
import html
import re
from decimal import Decimal

CURRENCY_SYMBOLS = {"RUB": "₽", "EUR": "€", "USD": "$", "XTR": "⭐"}
_DEEP_LINK_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def fmt_money(amount: Decimal | int | float, currency: str) -> str:
    """`1490 RUB` → `1 490 ₽`; `19.99 EUR` → `19.99 €`."""
    value = Decimal(str(amount))
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), currency.upper())

    if value == value.to_integral_value():
        body = f"{int(value):,}".replace(",", " " if currency.upper() == "RUB" else ",")
    else:
        body = f"{value:.2f}"
        if currency.upper() == "RUB":
            body = body.replace(",", " ")

    if currency.upper() in {"USD"}:
        return f"{symbol}{body}"
    return f"{body} {symbol}"


def fmt_date(value: dt.datetime | None, lang: str = "ru") -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.strftime("%d.%m.%Y" if lang == "ru" else "%Y-%m-%d")


def fmt_datetime(value: dt.datetime | None, lang: str = "ru") -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.strftime("%d.%m.%Y %H:%M" if lang == "ru" else "%Y-%m-%d %H:%M")


def esc(text: object) -> str:
    """Escape for Telegram HTML parse mode."""
    return html.escape(str(text), quote=False)


def deep_link(bot_username: str, payload: str) -> str:
    safe = _DEEP_LINK_SAFE.sub("", payload)[:64]
    return f"https://t.me/{bot_username.lstrip('@')}?start={safe}"


def parse_start_payload(payload: str) -> tuple[int | None, str | None]:
    """`ref123` → (123, None); `utm_ads` → (None, 'utm_ads')."""
    payload = (payload or "").strip()
    if not payload:
        return None, None
    if payload.startswith("ref") and payload[3:].isdigit():
        return int(payload[3:]), None
    return None, payload[:64]


def chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def truncate(text: str, limit: int = 4000) -> str:
    """Telegram caps messages at 4096 characters."""
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def apply_discount(amount: Decimal, percent: int) -> Decimal:
    """Never lets a promo drive a price below zero."""
    if percent <= 0:
        return Decimal(amount)
    percent = min(percent, 100)
    discounted = Decimal(amount) * (Decimal(100 - percent) / Decimal(100))
    return max(Decimal("0"), discounted.quantize(Decimal("0.01")))
