"""Storefront: browse the catalog, open a product, choose how to pay."""

from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import (
    BuyCB,
    MenuCB,
    QtyCB,
    back_button,
    catalog_menu,
    checkout_keyboard,
    product_card,
    quantity_keyboard,
    subscribe_keyboard,
)
from ..payments import ProviderRegistry
from ..services import CheckoutService
from ..services.checkout import MAX_PROMO_ATTEMPTS, MAX_QUANTITY
from ..utils import apply_discount, esc, fmt_date, fmt_money
from .common import _edit

log = logging.getLogger(__name__)
router = Router(name="catalog")


@router.callback_query(MenuCB.filter(F.action == "catalog"))
async def show_catalog(
    callback: CallbackQuery, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    products = [p for p in config.active_products() if p.kind != "subscription"] or list(
        config.active_products()
    )
    if not products:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return

    await repos.misc.track(user.tg_id, "catalog_view")
    await _edit(callback, t("catalog.title"), catalog_menu(products, config, t))
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "subscription"))
async def show_subscriptions(
    callback: CallbackQuery, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    products = [p for p in config.active_products() if p.kind == "subscription"]
    if not products:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return

    active = await repos.subs.active_for(user.id)
    lines = [t("subscription.title", description=esc(config.tagline or config.description))]
    if active:
        for sub in active:
            lines.append(t("subscription.active", until=fmt_date(sub.expires_at, config.lang)))
    else:
        lines.append(t("subscription.inactive"))

    offer_trial = bool(config.trial_days) and not active
    await _edit(
        callback,
        "\n\n".join(lines),
        subscribe_keyboard(products, config, t, trial=offer_trial),
    )
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "trial"))
async def start_trial(
    callback: CallbackQuery, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    if not config.trial_days:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    sub_products = [p for p in config.active_products() if p.kind == "subscription"]
    if not sub_products:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    sku = sub_products[0].sku
    existing = await repos.subs.get(user.id, sku)
    if existing is not None:
        # One trial per user, ever — even after it lapsed.
        await callback.answer(t("subscription.trial_used"), show_alert=True)
        return

    await repos.subs.grant(user.id, sku, config.trial_days, is_trial=True)
    await repos.misc.track(user.tg_id, "trial_started", sku)
    await callback.answer(t("subscription.trial", days=config.trial_days), show_alert=True)


@router.callback_query(BuyCB.filter())
async def open_product(
    callback: CallbackQuery,
    callback_data: BuyCB,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
) -> None:
    product = config.product(callback_data.sku)
    if product is None or not product.active:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    # A stale keyboard can still point at a product whose delivery is not
    # configured. Never take money for something we cannot hand over.
    if not product.is_deliverable():
        log.error(
            "%s: purchase of %s blocked — delivery fields %s are placeholders",
            config.id, product.sku, product.missing_delivery(),
        )
        await callback.answer(t("catalog.unavailable"), show_alert=True)
        return

    await repos.misc.track(user.tg_id, "product_view", product.sku)

    # Stock-backed goods: never let someone start paying for an empty shelf.
    if product.kind == "account":
        left = await repos.stock.available(product.sku)
        if left <= 0:
            await _edit(
                callback,
                t("catalog.sold_out", title=esc(product.title)),
                back_button(t, "catalog"),
            )
            await callback.answer(t("catalog.sold_out_short"), show_alert=True)
            return
        if left > 1:
            options = [n for n in (1, 2, 3, 5, 10) if n <= min(left, MAX_QUANTITY)]
            await _edit(
                callback,
                t(
                    "catalog.item_stock",
                    title=esc(product.title),
                    description=esc(product.description),
                    price=fmt_money(product.price, config.currency),
                    stock=left,
                ),
                quantity_keyboard(product.sku, options, t),
            )
            await callback.answer()
            return

    await _start_checkout(callback, state, config, t, repos, user, registry, checkout,
                          product, quantity=1)


@router.callback_query(QtyCB.filter())
async def choose_quantity(
    callback: CallbackQuery,
    callback_data: QtyCB,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
) -> None:
    product = config.product(callback_data.sku)
    if product is None or not product.active or not product.is_deliverable():
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    quantity = max(1, min(callback_data.qty, MAX_QUANTITY))
    if product.kind == "account":
        left = await repos.stock.available(product.sku)
        if left < quantity:
            await callback.answer(t("catalog.only_left", count=left), show_alert=True)
            return

    await _start_checkout(callback, state, config, t, repos, user, registry, checkout,
                          product, quantity=quantity)


async def _start_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
    product,
    *,
    quantity: int,
) -> None:
    if len(registry) == 0 and not config.has("balance"):
        await _edit(callback, t("checkout.no_methods"), back_button(t))
        await callback.answer()
        return

    data = await state.get_data()
    discount = int(data.get("promo_percent", 0) or 0)
    promo_code = data.get("promo_code") or None
    unit = apply_discount(product.price, discount)
    total = unit * quantity

    order = await checkout.create_order(
        repos,
        user,
        product,
        registry.default,
        discount_percent=discount,
        quantity=quantity,
        promo_code=promo_code,
    )

    title = esc(product.title)
    if quantity > 1:
        title += f" × {quantity}"
    body = t("checkout.choose_method", title=title,
             price=fmt_money(order.amount, config.currency))
    if discount:
        body += f"\n<s>{fmt_money(product.price * quantity, config.currency)}</s> · −{discount}%"
    elif config.has("catalog"):
        body += "\n\n" + t("checkout.promo_hint")

    enough = config.has("balance") and Decimal(user.balance) >= Decimal(order.amount)
    if config.has("balance"):
        body += "\n\n" + t("balance.current",
                           balance=fmt_money(user.balance, config.currency))

    await _edit(callback, body, checkout_keyboard(order.id, registry, t,
                                                  balance_enough=enough))
    await callback.answer()


@router.message(Command("catalog"))
async def cmd_catalog(
    message: Message, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    products = config.active_products()
    if not products:
        await message.answer(t("catalog.empty"))
        return
    await repos.misc.track(user.tg_id, "catalog_view")
    await message.answer(t("catalog.title"), reply_markup=catalog_menu(products, config, t))


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{3,32}$"))
async def maybe_promo(
    message: Message,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
) -> None:
    """A bare word might be a promo code — check before ignoring it.

    Two things matter here. The attempt is rate limited, because this handler
    would otherwise be a free oracle for brute-forcing codes. And a valid code
    is only *remembered*, not consumed: the use is spent in `settle()` when the
    order is actually paid, so nobody can exhaust a limited promo for free.
    """
    code = (message.text or "").strip()

    attempts = await repos.misc.count_recent_events(user.tg_id, "promo_try", minutes=60)
    if attempts >= MAX_PROMO_ATTEMPTS:
        return

    promo = await repos.promos.get(code)
    if promo is None or not promo.is_usable():
        await repos.misc.track(user.tg_id, "promo_try", code[:32])
        return  # not a promo; let other routers have it

    await state.update_data(promo_percent=promo.percent, promo_code=promo.code)
    await message.answer(t("promo.ok", percent=promo.percent))

    products = config.active_products()
    if products:
        await message.answer(t("catalog.title"), reply_markup=catalog_menu(products, config, t))


def product_screen(product, config: NicheConfig, t: Translator) -> tuple[str, object]:
    text = t(
        "catalog.item",
        title=esc(product.title),
        description=esc(product.description),
        price=fmt_money(product.price, config.currency),
    )
    if product.kind == "subscription" and product.period_days:
        text += "\n" + t("catalog.period", days=product.period_days)
    return text, product_card(product, config, t)
