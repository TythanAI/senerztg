"""Inline keyboards + a small, strict callback-data scheme.

Callback data is always ``<prefix>:<...>`` with short prefixes so we stay well
under Telegram's 64-byte limit. Every handler re-validates the parts it reads;
nothing here is trusted blindly.
"""
from __future__ import annotations

from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import BotConfig


def main_menu(cfg: BotConfig, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛍 Каталог", callback_data="menu:catalog")
    b.button(text="🛒 Корзина", callback_data="menu:cart")
    b.button(text="📦 Мои заказы", callback_data="menu:profile")
    b.button(text="💬 Поддержка", callback_data="menu:support")
    b.button(text="📄 Правила", callback_data="menu:rules")
    if is_admin:
        b.button(text="🛠 Админа", callback_data="adm:home")
    b.adjust(1, 2, 2)
    return b.as_markup()


def back_home() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ В меню", callback_data="menu:home")
    return b.as_markup()


def catalog(cfg: BotConfig) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cfg.catalog:
        b.button(text=f"{c.emoji} {c.title}", callback_data=f"cat:{c.id}")
    b.button(text="⬅️ В меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def category_products(
    cfg: BotConfig, category_id: str, stock: dict[str, int]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    cat = cfg.category(category_id)
    if cat:
        for p in cat.products:
            suffix = ""
            if cfg.fulfillment == "digital":
                left = stock.get(p.sku, 0)
                suffix = "  ·  ❌ нет" if left <= 0 else f"  ·  {left} шт."
            b.button(
                text=f"{p.title} — {p.price:.2f} {cfg.currency}{suffix}",
                callback_data=f"prod:{p.sku}",
            )
    b.button(text="⬅️ Каталог", callback_data="menu:catalog")
    b.adjust(1)
    return b.as_markup()


def product_card(cfg: BotConfig, sku: str, in_stock: bool, category_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if in_stock or cfg.fulfillment == "physical":
        b.button(text="➕ В корзину", callback_data=f"add:{sku}")
    b.button(text="🛒 Корзина", callback_data="menu:cart")
    b.button(text="⬅️ Назад", callback_data=f"cat:{category_id}")
    b.adjust(1, 2)
    return b.as_markup()


def cart(rows: Iterable[tuple[str, str]], has_items: bool) -> InlineKeyboardMarkup:
    """rows: (sku, title) per line — we add +/-/remove controls per sku."""
    b = InlineKeyboardBuilder()
    for sku, title in rows:
        b.row(
            InlineKeyboardButton(text="➖", callback_data=f"cart:dec:{sku}"),
            InlineKeyboardButton(text=title, callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart:inc:{sku}"),
        )
    if has_items:
        b.row(InlineKeyboardButton(text="✅ Оформить заказ", callback_data="cart:checkout"))
        b.row(InlineKeyboardButton(text="🗑 Очистить", callback_data="cart:clear"))
    b.row(InlineKeyboardButton(text="🛍 В каталог", callback_data="menu:catalog"))
    b.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home"))
    return b.as_markup()


def choose_payment(
    order_id: int, *, telegram: bool, crypto: bool, cod: bool
) -> InlineKeyboardMarkup:
    """Only methods that are actually usable right now are shown."""
    b = InlineKeyboardBuilder()
    if telegram:
        b.button(text="💳 Картой", callback_data=f"pay:telegram:{order_id}")
    if crypto:
        b.button(text="🪙 Криптовалютой", callback_data=f"pay:cryptobot:{order_id}")
    if cod:
        b.button(text="💵 При получении", callback_data=f"pay:cod:{order_id}")
    b.button(text="❌ Отменить", callback_data=f"cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()


def crypto_pay(pay_url: str, order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🪙 Оплатить", url=pay_url)
    b.button(text="🔄 Проверить оплату", callback_data=f"paycheck:{order_id}")
    b.button(text="❌ Отменить", callback_data=f"cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()


def skip_comment() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Пропустить", callback_data="co:skip")
    b.button(text="❌ Отменить", callback_data="menu:home")
    b.adjust(2)
    return b.as_markup()


def cancel_only() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отменить", callback_data="menu:home")
    return b.as_markup()


# ---------------- admin ----------------
def admin_home(cfg: BotConfig) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="adm:stats")
    if cfg.fulfillment == "digital":
        b.button(text="➕ Пополнить склад", callback_data="adm:stock")
    b.button(text="🧾 Последние заказы", callback_data="adm:orders")
    b.button(text="📢 Рассылка", callback_data="adm:broadcast")
    b.button(text="⬅️ В меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def admin_stock_pick(cfg: BotConfig) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in cfg.all_products():
        b.button(text=p.title, callback_data=f"adm:stock_sku:{p.sku}")
    b.button(text="⬅️ Назад", callback_data="adm:home")
    b.adjust(1)
    return b.as_markup()


def admin_order_actions(order_id: int, fulfillment: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if fulfillment == "physical":
        b.button(text="👨‍🍳 Готовится", callback_data=f"adm:ostatus:{order_id}:preparing")
        b.button(text="✅ Выполнен", callback_data=f"adm:ostatus:{order_id}:completed")
    b.button(text="❌ Отменить", callback_data=f"adm:ostatus:{order_id}:cancelled")
    b.button(text="⬅️ Назад", callback_data="adm:orders")
    b.adjust(2, 1, 1)
    return b.as_markup()
