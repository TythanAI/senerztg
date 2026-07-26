"""Owner panel: stats, broadcasts, promo codes, manual payment confirmation."""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import AdminCB, admin_menu, back_button
from ..payments import PaymentResult, PaymentStatus
from ..services import Broadcaster, CheckoutService
from ..utils import esc, fmt_datetime, fmt_money, truncate
from .common import _edit

log = logging.getLogger(__name__)
router = Router(name="admin")


class BroadcastFlow(StatesGroup):
    waiting_text = State()


class PromoFlow(StatesGroup):
    waiting_spec = State()


def _is_admin(user: User, admin_ids: tuple[int, ...]) -> bool:
    return user.is_admin or user.tg_id in admin_ids


async def _panel_text(config: NicheConfig, t: Translator, repos: Repos) -> str:
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return t(
        "admin.panel",
        users=await repos.users.count(),
        today=await repos.users.count_since(today),
        paid=await repos.orders.paid_count(),
        revenue=fmt_money(await repos.orders.revenue(), config.currency),
    )


@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await message.answer(t("admin.denied"))
        return
    await message.answer(await _panel_text(config, t, repos), reply_markup=admin_menu(t))


@router.callback_query(AdminCB.filter(F.action == "stats"))
async def show_stats(
    callback: CallbackQuery,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    now = dt.datetime.now(dt.timezone.utc)
    day = now - dt.timedelta(days=1)
    week = now - dt.timedelta(days=7)
    month = now - dt.timedelta(days=30)

    funnel = await repos.misc.funnel(since=week)
    starts = funnel.get("start", 0)
    views = funnel.get("product_view", 0)
    checkouts = funnel.get("checkout_started", 0)
    paid = funnel.get("paid", 0)

    def rate(part: int, whole: int) -> str:
        return f"{part / whole * 100:.1f}%" if whole else "—"

    lines = [
        "<b>📊 Статистика</b>",
        "",
        f"👥 Всего пользователей: <b>{await repos.users.count()}</b>",
        f"➕ За сутки: {await repos.users.count_since(day)} · "
        f"за неделю: {await repos.users.count_since(week)}",
        "",
        f"💰 Выручка за сутки: <b>{fmt_money(await repos.orders.revenue(day), config.currency)}</b>",
        f"💰 За неделю: <b>{fmt_money(await repos.orders.revenue(week), config.currency)}</b>",
        f"💰 За 30 дней: <b>{fmt_money(await repos.orders.revenue(month), config.currency)}</b>",
        f"💰 Всего: <b>{fmt_money(await repos.orders.revenue(), config.currency)}</b>",
        "",
        "<b>Воронка за 7 дней</b>",
        f"/start → {starts}",
        f"Карточка товара → {views} ({rate(views, starts)})",
        f"Оформление → {checkouts} ({rate(checkouts, views)})",
        f"Оплата → {paid} ({rate(paid, checkouts)})",
    ]
    await _edit(callback, "\n".join(lines), back_button(t))
    await callback.answer()


@router.callback_query(AdminCB.filter(F.action == "orders"))
async def show_orders(
    callback: CallbackQuery,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    pending = await repos.orders.pending(limit=15)
    lines = ["<b>🧾 Заказы в ожидании</b>", ""]
    if not pending:
        lines.append("Нет открытых заказов.")
    for order in pending:
        lines.append(
            f"#{order.id} · {esc(order.title)} · "
            f"{fmt_money(order.amount, order.currency)} · {order.provider} · "
            f"{fmt_datetime(order.created_at, config.lang)}"
        )
    await _edit(callback, truncate("\n".join(lines)), back_button(t))
    await callback.answer()


@router.callback_query(AdminCB.filter(F.action == "leads"))
async def show_leads(
    callback: CallbackQuery,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    leads = await repos.misc.open_leads(limit=20)
    lines = ["<b>📇 Заявки</b>", ""]
    if not leads:
        lines.append("Новых заявок нет.")
    for lead in leads:
        contact = lead.phone or lead.email or "—"
        lines.append(f"#{lead.id} · {lead.kind} · <code>{esc(contact)}</code>")
    await _edit(callback, truncate("\n".join(lines)), back_button(t))
    await callback.answer()


# ---------------------------------------------------------------- broadcast


@router.callback_query(AdminCB.filter(F.action == "broadcast"))
async def ask_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    t: Translator,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return
    await state.set_state(BroadcastFlow.waiting_text)
    await _edit(callback, t("admin.broadcast_prompt"), back_button(t))
    await callback.answer()


@router.message(BroadcastFlow.waiting_text, F.text)
async def run_broadcast(
    message: Message,
    state: FSMContext,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await state.clear()
        return

    await state.clear()
    recipients = await repos.users.all_tg_ids()
    await message.answer(t("admin.broadcast_started"))

    async def mark_blocked(chat_id: int) -> None:
        # Skip them next time — but they stay welcome if they ever come back.
        await repos.users.set_blocked(chat_id, True)

    report = await Broadcaster(bot).send(
        recipients, message.html_text or message.text or "", on_blocked=mark_blocked
    )
    await message.answer(
        t("admin.broadcast_done", sent=report.sent, failed=report.failed + report.blocked)
    )


# ------------------------------------------------------------------- promos


@router.callback_query(AdminCB.filter(F.action == "promos"))
async def ask_promo(
    callback: CallbackQuery,
    state: FSMContext,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    await state.set_state(PromoFlow.waiting_spec)
    existing = await repos.promos.all()
    lines = [t("admin.promo_prompt"), ""]
    for promo in list(existing)[:10]:
        status = "✅" if promo.is_usable() else "⛔️"
        lines.append(f"{status} <code>{esc(promo.code)}</code> −{promo.percent}% "
                     f"({promo.used}/{promo.max_uses or '∞'})")
    await _edit(callback, "\n".join(lines), back_button(t))
    await callback.answer()


@router.message(PromoFlow.waiting_spec, F.text)
async def create_promo(
    message: Message,
    state: FSMContext,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await state.clear()
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(t("admin.promo_prompt"))
        return

    code = parts[0].upper()
    try:
        percent = int(parts[1])
        max_uses = int(parts[2]) if len(parts) > 2 else 0
        days = int(parts[3]) if len(parts) > 3 else 0
    except ValueError:
        await message.answer(t("admin.promo_prompt"))
        return

    if not 1 <= percent <= 100:
        await message.answer("Процент должен быть от 1 до 100.")
        return

    if await repos.promos.get(code) is not None:
        await message.answer(f"Промокод {code} уже существует.")
        return

    promo = await repos.promos.create(code, percent, max_uses, days)
    await state.clear()
    await message.answer(
        t("admin.promo_created", code=esc(promo.code), percent=promo.percent),
        reply_markup=back_button(t),
    )


# -------------------------------------------------------------------- stock


class StockFlow(StatesGroup):
    waiting_items = State()


@router.callback_query(AdminCB.filter(F.action == "stock"))
async def show_stock(
    callback: CallbackQuery,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    counts = await repos.stock.counts()
    lines = ["<b>📦 Склад</b>", ""]
    account_products = [p for p in config.active_products() if p.kind == "account"]
    if not account_products:
        lines.append("В этом боте нет товаров со складом.")
    for product in account_products:
        left = counts.get(product.sku, 0)
        mark = "🟢" if left > 10 else "🟡" if left > 0 else "🔴"
        lines.append(f"{mark} <code>{esc(product.sku)}</code> — {left} шт. · {esc(product.title)}")

    lines += ["", t("admin.stock_hint")]
    await _edit(callback, truncate("\n".join(lines)), back_button(t))
    await callback.answer()


@router.message(Command("stock"))
async def cmd_stock(
    message: Message,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    """`/stock <sku>` then paste the units, one per line."""
    if not _is_admin(user, admin_ids):
        return

    parts = (message.text or "").split(maxsplit=1)
    counts = await repos.stock.counts()

    if len(parts) < 2:
        lines = ["<b>📦 Склад</b>", ""]
        for product in config.active_products():
            if product.kind == "account":
                lines.append(
                    f"<code>{esc(product.sku)}</code> — {counts.get(product.sku, 0)} шт."
                )
        lines += ["", t("admin.stock_hint")]
        await message.answer(truncate("\n".join(lines)))
        return

    sku = parts[1].strip().split()[0]
    product = config.product(sku)
    if product is None or product.kind != "account":
        await message.answer(f"Нет товара со складом с SKU <code>{esc(sku)}</code>.")
        return

    await state.set_state(StockFlow.waiting_items)
    await state.update_data(stock_sku=sku)
    await message.answer(
        t("admin.stock_prompt", sku=esc(sku), count=counts.get(sku, 0)),
        reply_markup=back_button(t),
    )


@router.message(StockFlow.waiting_items, F.text)
async def receive_stock(
    message: Message,
    state: FSMContext,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await state.clear()
        return

    data = await state.get_data()
    sku = str(data.get("stock_sku") or "")
    if not sku:
        await state.clear()
        return

    lines = [line for line in (message.text or "").splitlines() if line.strip()]
    if not lines:
        await message.answer(t("admin.stock_empty"))
        return

    added = await repos.stock.add(sku, lines, note=f"by {user.tg_id}")
    total = await repos.stock.available(sku)
    await state.clear()
    await message.answer(
        t("admin.stock_added", count=added, sku=esc(sku), total=total),
        reply_markup=back_button(t),
    )
    log.info("admin %s loaded %s units into %s", user.tg_id, added, sku)


# --------------------------------------------------- manual order confirming


@router.callback_query(AdminCB.filter(F.action == "confirm"))
async def confirm_order(
    callback: CallbackQuery,
    callback_data: AdminCB,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    checkout: CheckoutService,
    admin_ids: tuple[int, ...],
) -> None:
    if not _is_admin(user, admin_ids):
        await callback.answer(t("admin.denied"), show_alert=True)
        return

    try:
        order_id = int(callback_data.arg)
    except ValueError:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    order = await repos.orders.get(order_id)
    if order is None:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return
    if order.status != "pending":
        await callback.answer(f"Заказ #{order_id}: {order.status}", show_alert=True)
        return

    result = PaymentResult(
        status=PaymentStatus.PAID,
        external_id=order.external_id or f"manual-{order.id}",
        amount=order.amount,
        currency=order.currency,
        raw={"confirmed_by": user.tg_id},
    )
    settled = await checkout.settle(repos, bot, order, result)
    if settled:
        try:
            await bot.send_message(order.user.tg_id, t("checkout.paid"))
        except Exception:  # pragma: no cover
            pass
    await callback.answer(t("admin.order_confirmed", id=order_id), show_alert=True)


@router.message(Command("status"))
async def cmd_status(
    message: Message,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    """Readiness at a glance: what is sellable and what is still blocking."""
    if not _is_admin(user, admin_ids):
        return

    sellable = config.active_products()
    blocked = config.blocked_products()
    lines = [f"<b>{esc(config.name)}</b>", ""]
    lines.append(f"🛒 К продаже: <b>{len(sellable)}</b> из {len(config.catalog)}")

    if config.has("stock"):
        counts = await repos.stock.counts()
        total = sum(counts.values())
        lines.append(f"📦 На складе: <b>{total}</b> шт.")
        for product in config.catalog:
            if product.kind == "account":
                left = counts.get(product.sku, 0)
                mark = "🟢" if left > 10 else "🟡" if left else "🔴"
                lines.append(f"   {mark} <code>{esc(product.sku)}</code> — {left}")

    if blocked:
        lines.append("")
        lines.append("<b>Скрыто из каталога:</b>")
        for product in blocked[:10]:
            fields = ", ".join(product.missing_delivery())
            lines.append(f"• <code>{esc(product.sku)}</code> — не задано: {esc(fields)}")
        lines.append("Замените значения в config.yaml и перезапустите бота.")

    if config.has_placeholder_support():
        lines.append("")
        lines.append("⚠️ Не задан <code>support_username</code>.")

    if sellable:
        lines.append("")
        lines.append("✅ Бот готов принимать заказы.")

    await message.answer(truncate("\n".join(lines)))


@router.message(Command("reply"))
async def reply_to_user(
    message: Message,
    bot: Bot,
    t: Translator,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    """`/reply <tg_id> <text>` — answer a support ticket from the panel."""
    if not _is_admin(user, admin_ids):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: <code>/reply TG_ID текст</code>")
        return

    try:
        target = int(parts[1])
    except ValueError:
        await message.answer("Неверный TG_ID.")
        return

    try:
        await bot.send_message(target, t("support.reply", text=esc(parts[2])))
        await message.answer(t("common.done"))
    except Exception as exc:
        await message.answer(f"Не доставлено: {esc(exc)}")


@router.message(Command("ban"))
async def ban_user(
    message: Message, t: Translator, repos: Repos, user: User, admin_ids: tuple[int, ...]
) -> None:
    if not _is_admin(user, admin_ids):
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Формат: <code>/ban TG_ID</code>")
        return
    ok = await repos.users.set_ban(int(parts[1]), True)
    await message.answer(t("common.done") if ok else t("errors.not_found"))


@router.message(Command("unban"))
async def unban_user(
    message: Message, t: Translator, repos: Repos, user: User, admin_ids: tuple[int, ...]
) -> None:
    if not _is_admin(user, admin_ids):
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Формат: <code>/unban TG_ID</code>")
        return
    ok = await repos.users.set_ban(int(parts[1]), False)
    await message.answer(t("common.done") if ok else t("errors.not_found"))
