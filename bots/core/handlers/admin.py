"""Admin panel: stats, stock top-up, order management, broadcast.

The whole router is gated by an ``IsAdmin`` filter, so none of these handlers
are reachable by ordinary users even if they somehow craft the callback data.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from .. import keyboards as kb
from .. import texts, ui
from ..services import Services
from ..states import AdminFSM

router = Router(name="admin")
log = logging.getLogger("core.admin")

_ALLOWED_STATUS = {"preparing", "completed", "cancelled"}


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, services: Services) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and services.is_admin(user.id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def _show_home(services: Services, cbq: CallbackQuery) -> None:
    await ui.safe_edit(cbq, "🛠 <b>Панель администратора</b>", kb.admin_home(services.cfg))


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=kb.admin_home(services.cfg))


@router.callback_query(F.data == "adm:home")
async def cb_home(cbq: CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    await _show_home(services, cbq)


@router.callback_query(F.data == "adm:stats")
async def cb_stats(cbq: CallbackQuery, services: Services) -> None:
    s = await services.db.stats()
    lines = [
        "📊 <b>Статистика</b>\n",
        f"Пользователей: <b>{s['users']}</b>",
        f"Заказов всего: <b>{s['orders_total']}</b>",
        f"Оплачено: <b>{s['orders_paid']}</b>",
        f"Выручка: <b>{texts.money(s['revenue'], services.cfg.currency)}</b>",
    ]
    if services.cfg.fulfillment == "digital":
        counts = await services.db.stock_counts()
        lines.append("\n<b>Остатки на складе:</b>")
        for p in services.cfg.all_products():
            lines.append(f"• {texts.esc(p.title)}: {counts.get(p.sku, 0)} шт.")
    await ui.safe_edit(cbq, "\n".join(lines), kb.admin_home(services.cfg))


# ---------------- stock top-up ----------------
@router.callback_query(F.data == "adm:stock")
async def cb_stock(cbq: CallbackQuery, services: Services) -> None:
    if services.cfg.fulfillment != "digital":
        await cbq.answer("Недоступно для этого бота", show_alert=True)
        return
    await ui.safe_edit(cbq, "Выберите товар для пополнения:", kb.admin_stock_pick(services.cfg))


@router.callback_query(F.data.startswith("adm:stock_sku:"))
async def cb_stock_sku(cbq: CallbackQuery, state: FSMContext, services: Services) -> None:
    sku = cbq.data.split(":", 2)[2]
    product = services.cfg.find_product(sku)
    if not product:
        await cbq.answer("Товар не найден", show_alert=True)
        return
    await state.set_state(AdminFSM.add_stock_pick)
    await state.update_data(sku=sku)
    await ui.safe_edit(
        cbq,
        f"Пополнение: <b>{texts.esc(product.title)}</b>\n\n"
        "Отправьте позиции сообщением — <b>по одной на строку</b> "
        "(например, логин:пароль или ключ). Каждая строка — отдельная единица товара.",
        kb.cancel_only(),
    )


@router.message(AdminFSM.add_stock_pick, F.text)
async def st_add_stock(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    sku = data.get("sku", "")
    await state.clear()
    product = services.cfg.find_product(sku)
    if not product:
        await message.answer("Товар не найден.", reply_markup=kb.admin_home(services.cfg))
        return
    lines = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    added = await services.db.add_stock(sku, lines)
    left = await services.db.stock_count(sku)
    await message.answer(
        f"✅ Добавлено позиций: <b>{added}</b>.\n"
        f"Всего в наличии «{texts.esc(product.title)}»: <b>{left}</b>.",
        reply_markup=kb.admin_home(services.cfg),
    )


# ---------------- orders ----------------
@router.callback_query(F.data == "adm:orders")
async def cb_orders(cbq: CallbackQuery, services: Services) -> None:
    orders = await services.db.recent_orders(limit=15)
    if not orders:
        await ui.safe_edit(cbq, "Заказов пока нет.", kb.admin_home(services.cfg))
        return
    lines = ["🧾 <b>Последние заказы</b>\n"]
    lines += [texts.order_status_line(o) for o in orders]
    lines.append("\nУправление физическими заказами — из уведомлений о заказе.")
    await ui.safe_edit(cbq, "\n".join(lines), kb.admin_home(services.cfg))


@router.callback_query(F.data.startswith("adm:ostatus:"))
async def cb_order_status(cbq: CallbackQuery, services: Services) -> None:
    parts = cbq.data.split(":")
    if len(parts) != 4:
        await cbq.answer()
        return
    try:
        order_id = int(parts[2])
    except ValueError:
        await cbq.answer()
        return
    status = parts[3]
    if status not in _ALLOWED_STATUS:
        await cbq.answer()
        return
    order = await services.db.get_order(order_id)
    if not order:
        await cbq.answer("Заказ не найден", show_alert=True)
        return
    await services.db.set_order_status(order_id, status)
    human = {"preparing": "готовится 👨‍🍳", "completed": "выполнен ✅", "cancelled": "отменён ❌"}[status]
    try:
        await services.bot.send_message(order.user_id, f"Статус заказа #{order_id}: {human}.")
    except Exception as exc:
        log.warning("could not notify buyer %s: %s", order.user_id, exc)
    await cbq.answer(f"Статус: {human}")


# ---------------- broadcast ----------------
@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast(cbq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.broadcast)
    await ui.safe_edit(
        cbq, "Отправьте текст рассылки. Он будет доставлен всем пользователям бота.",
        kb.cancel_only(),
    )


@router.message(AdminFSM.broadcast, F.text)
async def st_broadcast(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    text = message.html_text or message.text or ""
    user_ids = await services.db.all_user_ids()
    ok = fail = 0
    for uid in user_ids:
        try:
            await services.bot.send_message(uid, text)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # stay well under Telegram's rate limit
    await message.answer(
        texts.BROADCAST_DONE.format(ok=ok, fail=fail),
        reply_markup=kb.admin_home(services.cfg),
    )
