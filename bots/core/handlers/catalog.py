"""Catalog browsing: categories -> products -> product card."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import keyboards as kb
from .. import texts, ui
from ..services import Services

router = Router(name="catalog")


def _category_id_for(services: Services, sku: str) -> str:
    for c in services.cfg.catalog:
        if any(p.sku == sku for p in c.products):
            return c.id
    return ""


@router.callback_query(F.data == "menu:catalog")
async def cb_catalog(cbq: CallbackQuery, services: Services) -> None:
    if not services.cfg.catalog:
        await ui.safe_edit(cbq, "Каталог пока пуст. Загляните позже.", kb.back_home())
        return
    await ui.safe_edit(cbq, "🛍 <b>Каталог</b>\n\nВыберите категорию:", kb.catalog(services.cfg))


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(cbq: CallbackQuery, services: Services) -> None:
    cid = cbq.data.split(":", 1)[1]
    cat = services.cfg.category(cid)
    if not cat:
        await cbq.answer("Категория не найдена", show_alert=True)
        return
    stock = await services.db.stock_counts() if services.cfg.fulfillment == "digital" else {}
    await ui.safe_edit(
        cbq,
        texts.category_header(cat.title, cat.emoji),
        kb.category_products(services.cfg, cid, stock),
    )


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(cbq: CallbackQuery, services: Services) -> None:
    sku = cbq.data.split(":", 1)[1]
    product = services.cfg.find_product(sku)
    if not product:
        await cbq.answer("Товар не найден", show_alert=True)
        return
    stock: int | None = None
    if services.cfg.fulfillment == "digital":
        stock = await services.db.stock_count(sku)
    text = texts.product_card(
        product.title, product.description, product.price, services.cfg.currency, stock
    )
    cid = _category_id_for(services, sku)
    in_stock = stock is None or stock > 0
    await ui.safe_edit(cbq, text, kb.product_card(services.cfg, sku, in_stock, cid))
