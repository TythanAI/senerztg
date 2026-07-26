"""Callback-data factories and every keyboard the bots render."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from .utils import fmt_money

if TYPE_CHECKING:  # pragma: no cover
    from .config import NicheConfig, Product
    from .i18n import Translator
    from .payments import ProviderRegistry


class MenuCB(CallbackData, prefix="m"):
    action: str


class BuyCB(CallbackData, prefix="buy"):
    sku: str


class PayCB(CallbackData, prefix="pay"):
    order_id: int
    provider: str


class CheckCB(CallbackData, prefix="chk"):
    order_id: int


class QuizCB(CallbackData, prefix="qz"):
    step: int
    option: int


class QtyCB(CallbackData, prefix="qty"):
    sku: str
    qty: int


class AdminCB(CallbackData, prefix="adm"):
    action: str
    arg: str = ""


#: Which main-menu buttons a module contributes.
MODULE_BUTTONS: dict[str, tuple[str, str]] = {
    "catalog": ("menu.catalog", "catalog"),
    "balance": ("menu.balance", "balance"),
    "subscription": ("menu.subscription", "subscription"),
    "content": ("menu.content", "content"),
    "quiz": ("menu.quiz", "quiz"),
    "booking": ("menu.booking", "booking"),
    "faq": ("menu.faq", "faq"),
    "referral": ("menu.referral", "referral"),
    "reviews": ("menu.reviews", "reviews"),
    "support": ("menu.support", "support"),
}


def main_menu(config: "NicheConfig", t: "Translator") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    count = 0
    for module, (key, action) in MODULE_BUTTONS.items():
        if config.has(module):
            builder.button(text=t(key), callback_data=MenuCB(action=action).pack())
            count += 1
    builder.button(text=t("menu.profile"), callback_data=MenuCB(action="profile").pack())
    count += 1

    # Two per row reads best on a phone; a lone last button spans the width.
    # `builder.buttons` is a generator, so the count is tracked as we go.
    builder.adjust(*([2] * (count // 2) + ([1] if count % 2 else [])))
    return builder.as_markup()


def catalog_menu(
    products: Sequence["Product"], config: "NicheConfig", t: "Translator"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        price = "0" if product.is_free() else fmt_money(product.price, config.currency)
        builder.button(
            text=f"{product.title} · {price}",
            callback_data=BuyCB(sku=product.sku).pack(),
        )
    builder.button(text=t("common.menu"), callback_data=MenuCB(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def product_card(
    product: "Product", config: "NicheConfig", t: "Translator"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("catalog.buy", price=fmt_money(product.price, config.currency)),
        callback_data=BuyCB(sku=product.sku).pack(),
    )
    builder.button(text=t("common.back"), callback_data=MenuCB(action="catalog").pack())
    builder.adjust(1)
    return builder.as_markup()


def payment_methods(
    order_id: int, registry: "ProviderRegistry", t: "Translator"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name in registry.names:
        builder.button(
            text=registry.label(name),
            callback_data=PayCB(order_id=order_id, provider=name).pack(),
        )
    builder.button(text=t("common.cancel"), callback_data=MenuCB(action="catalog").pack())
    builder.adjust(1)
    return builder.as_markup()


def invoice_keyboard(
    order_id: int, pay_url: str, t: "Translator", *, show_check: bool = True
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if pay_url:
        rows.append([InlineKeyboardButton(text=t("checkout.pay"), url=pay_url)])
    if show_check:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("checkout.check"),
                    callback_data=CheckCB(order_id=order_id).pack(),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text=t("common.menu"), callback_data=MenuCB(action="home").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_button(t: "Translator", action: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("common.back"), callback_data=MenuCB(action=action).pack())]
        ]
    )


def subscribe_keyboard(
    products: Sequence["Product"], config: "NicheConfig", t: "Translator", *, trial: bool = False
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=f"{product.title} · {fmt_money(product.price, config.currency)}",
            callback_data=BuyCB(sku=product.sku).pack(),
        )
    if trial:
        builder.button(text="🎁 " + t("menu.subscription"), callback_data=MenuCB(action="trial").pack())
    builder.button(text=t("common.menu"), callback_data=MenuCB(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def topup_keyboard(
    presets: Sequence[int], config: "NicheConfig", t: "Translator"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in presets:
        builder.button(
            text=fmt_money(Decimal(amount), config.currency),
            callback_data=MenuCB(action=f"topup:{amount}").pack(),
        )
    builder.button(text=t("balance.custom"), callback_data=MenuCB(action="topup_custom").pack())
    builder.button(text=t("common.menu"), callback_data=MenuCB(action="home").pack())

    rows = [3] * (len(presets) // 3)
    if len(presets) % 3:
        rows.append(len(presets) % 3)
    builder.adjust(*rows, 1, 1)
    return builder.as_markup()


def quantity_keyboard(
    sku: str, options: Sequence[int], t: "Translator"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for count in options:
        builder.button(text=f"{count} шт." if t.lang == "ru" else f"{count} pcs",
                       callback_data=QtyCB(sku=sku, qty=count).pack())
    builder.button(text=t("common.back"), callback_data=MenuCB(action="catalog").pack())
    builder.adjust(3)
    return builder.as_markup()


def checkout_keyboard(
    order_id: int,
    registry: "ProviderRegistry",
    t: "Translator",
    *,
    balance_enough: bool = False,
) -> InlineKeyboardMarkup:
    """Payment methods, with the wallet first when it can cover the order."""
    builder = InlineKeyboardBuilder()
    if balance_enough:
        builder.button(
            text=t("balance.pay_with"),
            callback_data=PayCB(order_id=order_id, provider="balance").pack(),
        )
    for name in registry.names:
        builder.button(
            text=registry.label(name),
            callback_data=PayCB(order_id=order_id, provider=name).pack(),
        )
    builder.button(text=t("common.cancel"), callback_data=MenuCB(action="catalog").pack())
    builder.adjust(1)
    return builder.as_markup()


def quiz_keyboard(step: int, options: Sequence[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.button(text=option, callback_data=QuizCB(step=step, option=index).pack())
    builder.adjust(1)
    return builder.as_markup()


def phone_request(t: "Translator") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=t("leadgen.phone_button"), request_contact=True))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def admin_menu(t: "Translator") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, action in (
        ("admin.stats", "stats"),
        ("admin.broadcast", "broadcast"),
        ("admin.promos", "promos"),
        ("admin.orders", "orders"),
        ("admin.stock", "stock"),
        ("admin.leads", "leads"),
    ):
        builder.button(text=t(key), callback_data=AdminCB(action=action).pack())
    builder.adjust(2)
    return builder.as_markup()


def confirm_payment_keyboard(order_id: int, t: "Translator") -> InlineKeyboardMarkup:
    """Sent to admins for manual-transfer orders."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("admin.confirm_paid"),
                    callback_data=AdminCB(action="confirm", arg=str(order_id)).pack(),
                )
            ]
        ]
    )


def url_button(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


def price_of(product: "Product", config: "NicheConfig") -> str:
    return fmt_money(Decimal(product.price), config.currency)
