"""Storefront: browse the catalog, open a product, choose how to pay."""

from __future__ import annotations

import logging

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
    back_button,
    catalog_menu,
    payment_methods,
    product_card,
    subscribe_keyboard,
)
from ..payments import ProviderRegistry
from ..services import CheckoutService
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

    await repos.misc.track(user.tg_id, "product_view", product.sku)

    if len(registry) == 0:
        await _edit(callback, t("checkout.no_methods"), back_button(t))
        await callback.answer()
        return

    data = await state.get_data()
    discount = int(data.get("promo_percent", 0) or 0)
    amount = apply_discount(product.price, discount)

    order = await checkout.create_order(repos, user, product, registry.default,
                                        discount_percent=discount)

    body = t(
        "checkout.choose_method",
        title=esc(product.title),
        price=fmt_money(amount, config.currency),
    )
    if discount:
        body += f"\n<s>{fmt_money(product.price, config.currency)}</s> · −{discount}%"
    elif config.has("catalog"):
        body += "\n\n" + t("checkout.promo_hint")

    await _edit(callback, body, payment_methods(order.id, registry, t))
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
) -> None:
    """A bare word might be a promo code — check before ignoring it."""
    code = (message.text or "").strip()
    promo = await repos.promos.get(code)
    if promo is None or not promo.is_usable():
        return  # not a promo; let other routers have it

    await repos.promos.redeem(code)
    await state.update_data(promo_percent=promo.percent)
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
