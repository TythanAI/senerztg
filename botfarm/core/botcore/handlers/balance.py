"""Wallet: top up once, buy instantly afterwards.

Account shops live on this — a buyer who has topped up completes the next
purchase in one tap instead of going through an acquirer again.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import MenuCB, back_button, payment_methods, topup_keyboard
from ..payments import ProviderRegistry
from ..services import CheckoutService
from ..services.checkout import TOPUP_SKU
from ..utils import fmt_money
from .common import _edit

log = logging.getLogger(__name__)
router = Router(name="balance")

#: Guard rails for a free-text amount. Also stops absurd values reaching an
#: acquirer, which some of them answer with an opaque 500.
MIN_TOPUP = {"RUB": Decimal("100"), "EUR": Decimal("5"), "USD": Decimal("5")}
MAX_TOPUP = {"RUB": Decimal("500000"), "EUR": Decimal("5000"), "USD": Decimal("5000")}

#: Quick-pick buttons, in units of the bot's currency.
PRESETS = {
    "RUB": (300, 500, 1000, 3000, 5000),
    "EUR": (5, 10, 25, 50, 100),
    "USD": (5, 10, 25, 50, 100),
}


class TopUpFlow(StatesGroup):
    waiting_amount = State()


def _limits(currency: str) -> tuple[Decimal, Decimal]:
    return (
        MIN_TOPUP.get(currency, Decimal("1")),
        MAX_TOPUP.get(currency, Decimal("10000")),
    )


async def balance_text(config: NicheConfig, t: Translator, user: User) -> str:
    low, high = _limits(config.currency)
    return t(
        "balance.title",
        balance=fmt_money(user.balance, config.currency),
        min=fmt_money(low, config.currency),
        max=fmt_money(high, config.currency),
    )


@router.callback_query(MenuCB.filter(F.action == "balance"))
async def show_balance(
    callback: CallbackQuery, config: NicheConfig, t: Translator, user: User
) -> None:
    await _edit(
        callback,
        await balance_text(config, t, user),
        topup_keyboard(PRESETS.get(config.currency, ()), config, t),
    )
    await callback.answer()


@router.message(Command("balance"))
async def cmd_balance(
    message: Message, config: NicheConfig, t: Translator, user: User
) -> None:
    await message.answer(
        await balance_text(config, t, user),
        reply_markup=topup_keyboard(PRESETS.get(config.currency, ()), config, t),
    )


@router.callback_query(MenuCB.filter(F.action.startswith("topup:")))
async def topup_preset(
    callback: CallbackQuery,
    callback_data: MenuCB,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
) -> None:
    """One of the quick-pick amounts."""
    raw = callback_data.action.split(":", 1)[1]
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        await callback.answer(t("common.error"), show_alert=True)
        return
    await _start_topup(callback.message, callback, amount, config, t, repos, user,
                       registry, checkout)


@router.callback_query(MenuCB.filter(F.action == "topup_custom"))
async def ask_amount(
    callback: CallbackQuery, state: FSMContext, config: NicheConfig, t: Translator
) -> None:
    low, high = _limits(config.currency)
    await state.set_state(TopUpFlow.waiting_amount)
    await _edit(
        callback,
        t(
            "balance.ask_amount",
            min=fmt_money(low, config.currency),
            max=fmt_money(high, config.currency),
        ),
        back_button(t, "balance"),
    )
    await callback.answer()


@router.message(TopUpFlow.waiting_amount, F.text)
async def receive_amount(
    message: Message,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
) -> None:
    raw = (message.text or "").strip().replace(",", ".").replace(" ", "")
    low, high = _limits(config.currency)

    try:
        amount = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        await message.answer(t("balance.bad_amount"))
        return

    if not low <= amount <= high:
        await message.answer(
            t(
                "balance.out_of_range",
                min=fmt_money(low, config.currency),
                max=fmt_money(high, config.currency),
            )
        )
        return

    await state.clear()
    await _start_topup(message, None, amount, config, t, repos, user, registry, checkout)


async def _start_topup(
    message: Message | None,
    callback: CallbackQuery | None,
    amount: Decimal,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
) -> None:
    low, high = _limits(config.currency)
    if not low <= amount <= high:
        if callback:
            await callback.answer(t("balance.bad_amount"), show_alert=True)
        return

    if len(registry) == 0:
        text = t("checkout.no_methods")
        if callback:
            await _edit(callback, text, back_button(t))
            await callback.answer()
        elif message:
            await message.answer(text, reply_markup=back_button(t))
        return

    order = await checkout.create_topup_order(repos, user, amount, registry.default)
    body = t("balance.confirm", amount=fmt_money(amount, config.currency))
    markup = payment_methods(order.id, registry, t)

    if callback:
        await _edit(callback, body, markup)
        await callback.answer()
    elif message:
        await message.answer(body, reply_markup=markup)


@router.callback_query(MenuCB.filter(F.action == "buy_with_balance"))
async def unavailable(callback: CallbackQuery, t: Translator) -> None:
    """Placeholder so a stale keyboard cannot raise an unhandled callback."""
    await callback.answer(t("errors.not_found"), show_alert=True)
