"""Payment: method selection, invoice creation, verification, delivery.

All three methods converge on ``_finalize`` which relies on
``mark_paid_if_pending`` so an order is delivered exactly once, no matter how
many times a user taps "check payment" or how Telegram retries a callback.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from .. import keyboards as kb
from .. import texts, ui
from ..db import Order
from ..flows import deliver_paid_order, place_cod_order
from ..payments.cryptobot import CryptoBotError
from ..payments.telegram import send_invoice
from ..services import Services

router = Router(name="payment")
log = logging.getLogger("core.payment")


def _safe_oid(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _owned_pending(services: Services, cbq: CallbackQuery, order_id: int | None) -> Order | None:
    if order_id is None:
        await cbq.answer("Некорректный заказ", show_alert=True)
        return None
    order = await services.db.get_order(order_id)
    if not order or order.user_id != cbq.from_user.id:
        await cbq.answer("Заказ не найден", show_alert=True)
        return None
    if order.status != "pending":
        await cbq.answer("Этот заказ уже обработан", show_alert=True)
        return None
    return order


async def _finalize(services: Services, order: Order, method: str, ref: str) -> bool:
    """Flip pending->paid once and deliver. Returns True if we delivered."""
    first = await services.db.mark_paid_if_pending(order.id, method, ref)
    if not first:
        return False
    fresh = await services.db.get_order(order.id)
    await deliver_paid_order(services, fresh)
    return True


# ---------------- method selection ----------------
@router.callback_query(F.data.startswith("pay:telegram:"))
async def cb_pay_telegram(cbq: CallbackQuery, services: Services) -> None:
    order = await _owned_pending(services, cbq, _safe_oid(cbq.data.split(":")[-1]))
    if not order:
        return
    if not services.cfg.payments.telegram_enabled or not services.cfg.provider_token:
        await cbq.answer("Оплата картой временно недоступна", show_alert=True)
        return
    # Do NOT pre-set pay_ref here: the real charge id is written atomically on
    # successful payment. Pre-setting an empty ref would collide on the unique
    # (pay_method, pay_ref) index if two card orders are open at once.
    try:
        await send_invoice(
            services.bot,
            cbq.from_user.id,
            title=f"{services.cfg.name} — заказ #{order.id}",
            description=f"Оплата заказа #{order.id}",
            order_id=order.id,
            total=order.total,
            currency=services.cfg.currency,
            provider_token=services.cfg.provider_token,
        )
        await cbq.answer("Счёт отправлен ниже 👇")
    except Exception as exc:
        log.error("send_invoice failed for order %s: %s", order.id, exc)
        await cbq.answer("Не удалось создать счёт. Попробуйте другой способ.", show_alert=True)


@router.callback_query(F.data.startswith("pay:cryptobot:"))
async def cb_pay_crypto(cbq: CallbackQuery, services: Services) -> None:
    order = await _owned_pending(services, cbq, _safe_oid(cbq.data.split(":")[-1]))
    if not order:
        return
    if not services.crypto:
        await cbq.answer("Крипто-оплата временно недоступна", show_alert=True)
        return
    try:
        invoice = await services.crypto.create_invoice(
            amount=order.total,
            fiat=services.cfg.currency,
            description=f"{services.cfg.name} — заказ #{order.id}",
            payload=f"order:{order.id}",
        )
    except CryptoBotError as exc:
        log.error("crypto invoice failed for order %s: %s", order.id, exc)
        await cbq.answer("Не удалось создать счёт. Попробуйте позже.", show_alert=True)
        return
    await services.db.set_order_payref(order.id, "cryptobot", str(invoice.invoice_id))
    await ui.safe_edit(
        cbq,
        texts.payment_pending_crypto(invoice.pay_url, order.total, services.cfg.currency),
        kb.crypto_pay(invoice.pay_url, order.id),
    )


@router.callback_query(F.data.startswith("pay:cod:"))
async def cb_pay_cod(cbq: CallbackQuery, services: Services) -> None:
    order = await _owned_pending(services, cbq, _safe_oid(cbq.data.split(":")[-1]))
    if not order:
        return
    if not (services.cfg.payments.cod_enabled and services.cfg.fulfillment == "physical"):
        await cbq.answer("Способ недоступен", show_alert=True)
        return
    await services.db.set_order_payref(order.id, "cod", f"cod:{order.id}")
    fresh = await services.db.get_order(order.id)
    await place_cod_order(services, fresh)
    items = await services.db.order_items(order.id)
    await ui.safe_edit(cbq, texts.physical_created(services.cfg, fresh, items), kb.back_home())


# ---------------- crypto verification ----------------
@router.callback_query(F.data.startswith("paycheck:"))
async def cb_paycheck(cbq: CallbackQuery, services: Services) -> None:
    order_id = _safe_oid(cbq.data.split(":", 1)[1])
    if order_id is None:
        await cbq.answer("Некорректный заказ", show_alert=True)
        return
    order = await services.db.get_order(order_id)
    if not order or order.user_id != cbq.from_user.id:
        await cbq.answer("Заказ не найден", show_alert=True)
        return
    if order.status != "pending":
        await cbq.answer("Заказ уже обработан ✅")
        return
    if not services.crypto or not order.pay_ref:
        await cbq.answer("Проверка недоступна", show_alert=True)
        return
    try:
        status = await services.crypto.get_status(int(order.pay_ref))
    except (CryptoBotError, ValueError) as exc:
        log.warning("crypto status check failed for order %s: %s", order.id, exc)
        await cbq.answer("Не удалось проверить оплату. Попробуйте ещё раз.", show_alert=True)
        return
    if status == "paid":
        delivered = await _finalize(services, order, "cryptobot", order.pay_ref)
        await cbq.answer("Оплата получена ✅" if delivered else "Уже обработано ✅")
    else:
        await cbq.answer("Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)


# ---------------- cancel ----------------
@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(cbq: CallbackQuery, services: Services) -> None:
    order_id = _safe_oid(cbq.data.split(":", 1)[1])
    if order_id is None:
        await cbq.answer()
        return
    order = await services.db.get_order(order_id)
    if order and order.user_id == cbq.from_user.id and order.status == "pending":
        await services.db.release_order_stock(order.id)
        await services.db.set_order_status(order.id, "cancelled")
    text, markup = ui.home_screen(services, cbq.from_user.id)
    await ui.safe_edit(cbq, "Заказ отменён.\n\n" + text, markup)


# ---------------- Telegram native payments ----------------
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, services: Services) -> None:
    order_id = None
    if query.invoice_payload.startswith("order:"):
        order_id = _safe_oid(query.invoice_payload.split(":", 1)[1])
    order = await services.db.get_order(order_id) if order_id else None
    if not order or order.status != "pending":
        await query.answer(ok=False, error_message="Заказ не найден или уже оплачен.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, services: Services) -> None:
    sp = message.successful_payment
    if not sp.invoice_payload.startswith("order:"):
        return
    order_id = _safe_oid(sp.invoice_payload.split(":", 1)[1])
    if order_id is None:
        return
    order = await services.db.get_order(order_id)
    if not order:
        log.error("successful_payment for unknown order %s", order_id)
        return
    await _finalize(services, order, "telegram", sp.telegram_payment_charge_id)
