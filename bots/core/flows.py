"""Business flows shared by the handlers.

Keeping order creation, stock reservation and delivery here (rather than in the
handlers) means the digital and physical paths, and all three payment methods,
go through exactly one audited code path.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from . import keyboards as kb
from . import texts
from .db import Order, OrderItem
from .services import Services

log = logging.getLogger("core.flows")


async def build_cart_items(services: Services, uid: int) -> Tuple[List[OrderItem], float]:
    """Turn the stored cart into priced order items using **config** prices
    (never client input). Digital quantities are clamped to available stock."""
    cfg = services.cfg
    raw = await services.db.cart_items(uid)
    stock = await services.db.stock_counts() if cfg.fulfillment == "digital" else {}
    items: List[OrderItem] = []
    for sku, qty in raw:
        product = cfg.find_product(sku)
        if not product:
            continue
        qty = max(1, min(qty, product.max_per_order))
        if cfg.fulfillment == "digital":
            avail = stock.get(sku, 0)
            if avail <= 0:
                continue
            qty = min(qty, avail)
        items.append(OrderItem(sku=sku, title=product.title, price=product.price, qty=qty))
    total = round(sum(it.price * it.qty for it in items), 2)
    return items, total


async def create_digital_order(
    services: Services, uid: int
) -> Tuple[Optional[int], Optional[str]]:
    """Create a pending order and atomically reserve its stock.

    Returns (order_id, None) on success, or (None, reason) where reason is a
    product title that could not be reserved, or "empty"."""
    cfg = services.cfg
    items, total = await build_cart_items(services, uid)
    if not items:
        return None, "empty"
    order_id = await services.db.create_order(
        user_id=uid,
        total=total,
        currency=cfg.currency,
        fulfillment="digital",
        items=items,
    )
    for it in items:
        ok = await services.db.reserve_stock(it.sku, it.qty, order_id)
        if not ok:
            await services.db.release_order_stock(order_id)
            await services.db.set_order_status(order_id, "cancelled")
            return None, it.title
    await services.db.cart_clear(uid)
    return order_id, None


async def create_physical_order(
    services: Services,
    uid: int,
    name: str,
    phone: str,
    address: str,
    comment: str,
) -> Tuple[Optional[int], Optional[str]]:
    cfg = services.cfg
    items, total = await build_cart_items(services, uid)
    if not items:
        return None, "empty"
    order_id = await services.db.create_order(
        user_id=uid,
        total=total,
        currency=cfg.currency,
        fulfillment="physical",
        items=items,
        contact_name=name,
        contact_phone=phone,
        contact_addr=address,
        comment=comment,
    )
    await services.db.cart_clear(uid)
    return order_id, None


def _admin_order_card(order: Order, items: List[OrderItem]) -> str:
    lines = [f"🧾 <b>Заказ #{order.id}</b>", texts.order_summary(items, order.total, order.currency)]
    if order.fulfillment == "physical":
        lines.append(
            f"\n👤 {texts.esc(order.contact_name or '—')}\n"
            f"📞 {texts.esc(order.contact_phone or '—')}\n"
            f"📍 {texts.esc(order.contact_addr or '—')}\n"
            f"💬 {texts.esc(order.comment or '—')}"
        )
    lines.append(f"\nСпособ оплаты: {order.pay_method or '—'}")
    return "\n".join(lines)


async def deliver_paid_order(services: Services, order: Order) -> None:
    """Idempotent post-payment delivery. Caller must have already flipped the
    order to 'paid' via mark_paid_if_pending (which returns True once)."""
    db = services.db
    items = await db.order_items(order.id)
    if order.fulfillment == "digital":
        payloads = await db.sell_order_stock(order.id)
        await db.set_order_status(order.id, "delivered")
        try:
            await services.bot.send_message(
                order.user_id, texts.digital_delivery(order.id, payloads)
            )
        except Exception as exc:
            log.error("could not deliver order %s to user: %s", order.id, exc)
        await services.notify_admins(
            f"💰 Оплачен заказ <b>#{order.id}</b> на "
            f"{texts.money(order.total, order.currency)}. Выдано позиций: {len(payloads)}."
        )
    else:
        await db.set_order_status(order.id, "preparing")
        try:
            await services.bot.send_message(
                order.user_id,
                f"✅ Оплата заказа <b>#{order.id}</b> получена. Мы начали готовить!",
            )
        except Exception as exc:
            log.error("could not notify buyer of order %s: %s", order.id, exc)
        await services.notify_admins(
            _admin_order_card(order, items),
            reply_markup=kb.admin_order_actions(order.id, "physical"),
        )


async def place_cod_order(services: Services, order: Order) -> None:
    """Physical cash-on-delivery: no online payment, straight to the kitchen."""
    await services.db.set_order_status(order.id, "preparing")
    items = await services.db.order_items(order.id)
    await services.notify_admins(
        _admin_order_card(order, items) + "\n\n💵 <b>Оплата при получении</b>",
        reply_markup=kb.admin_order_actions(order.id, "physical"),
    )
