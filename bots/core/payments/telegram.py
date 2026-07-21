"""Telegram native payments (Bot Payments API).

The provider token comes from BotFather after connecting a real provider
(Stripe, YooKassa, …). Amounts are sent in the currency's smallest units.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import LabeledPrice


def minor_units(amount: float) -> int:
    """Two-decimal currencies (USD, EUR, RUB, …). Rounded to avoid float drift."""
    return int(round(amount * 100))


async def send_invoice(
    bot: Bot,
    chat_id: int,
    *,
    title: str,
    description: str,
    order_id: int,
    total: float,
    currency: str,
    provider_token: str,
) -> None:
    # Telegram limits: title <=32, description <=255.
    title = title[:32]
    description = description[:255]
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=f"order:{order_id}",
        provider_token=provider_token,
        currency=currency,
        prices=[LabeledPrice(label=title, amount=minor_units(total))],
        start_parameter=f"order{order_id}",
        protect_content=False,
    )
