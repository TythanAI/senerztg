"""Cart: add items, adjust quantities, view, clear."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from .. import keyboards as kb
from .. import texts, ui
from ..services import Services

router = Router(name="cart")


async def render_cart(services: Services, uid: int) -> tuple[str, InlineKeyboardMarkup]:
    cfg = services.cfg
    raw = await services.db.cart_items(uid)
    rows_text: list[tuple[str, float, int]] = []
    rows_kb: list[tuple[str, str]] = []
    total = 0.0
    for sku, qty in raw:
        product = cfg.find_product(sku)
        if not product:  # product removed from config -> drop from cart
            await services.db.cart_set(uid, sku, 0)
            continue
        rows_text.append((product.title, product.price, qty))
        rows_kb.append((sku, f"{product.title} ×{qty}"))
        total += product.price * qty
    total = round(total, 2)
    text = texts.cart_view(rows_text, total, cfg.currency)
    markup = kb.cart(rows_kb, has_items=bool(rows_text))
    return text, markup


async def _available(services: Services, sku: str) -> int | None:
    if services.cfg.fulfillment != "digital":
        return None
    return await services.db.stock_count(sku)


@router.callback_query(F.data.startswith("add:"))
async def cb_add(cbq: CallbackQuery, services: Services) -> None:
    sku = cbq.data.split(":", 1)[1]
    product = services.cfg.find_product(sku)
    if not product:
        await cbq.answer("Товар не найден", show_alert=True)
        return
    current = dict(await services.db.cart_items(cbq.from_user.id)).get(sku, 0)
    avail = await _available(services, sku)
    if avail is not None and current + 1 > avail:
        await cbq.answer("Больше нет в наличии", show_alert=True)
        return
    cap = product.max_per_order if avail is None else min(product.max_per_order, avail)
    await services.db.cart_add(cbq.from_user.id, sku, 1, max_qty=cap)
    await cbq.answer("✅ Добавлено в корзину")


@router.callback_query(F.data == "menu:cart")
async def cb_cart(cbq: CallbackQuery, services: Services) -> None:
    text, markup = await render_cart(services, cbq.from_user.id)
    await ui.safe_edit(cbq, text, markup)


@router.callback_query(F.data.startswith("cart:inc:"))
async def cb_inc(cbq: CallbackQuery, services: Services) -> None:
    sku = cbq.data.split(":", 2)[2]
    product = services.cfg.find_product(sku)
    if not product:
        await cbq.answer()
        return
    current = dict(await services.db.cart_items(cbq.from_user.id)).get(sku, 0)
    avail = await _available(services, sku)
    if avail is not None and current + 1 > avail:
        await cbq.answer("Больше нет в наличии", show_alert=True)
        return
    cap = product.max_per_order if avail is None else min(product.max_per_order, avail)
    await services.db.cart_add(cbq.from_user.id, sku, 1, max_qty=cap)
    text, markup = await render_cart(services, cbq.from_user.id)
    await ui.safe_edit(cbq, text, markup)


@router.callback_query(F.data.startswith("cart:dec:"))
async def cb_dec(cbq: CallbackQuery, services: Services) -> None:
    sku = cbq.data.split(":", 2)[2]
    await services.db.cart_add(cbq.from_user.id, sku, -1)
    text, markup = await render_cart(services, cbq.from_user.id)
    await ui.safe_edit(cbq, text, markup)


@router.callback_query(F.data == "cart:clear")
async def cb_clear(cbq: CallbackQuery, services: Services) -> None:
    await services.db.cart_clear(cbq.from_user.id)
    text, markup = await render_cart(services, cbq.from_user.id)
    await ui.safe_edit(cbq, text, markup)
    await cbq.answer("Корзина очищена")
