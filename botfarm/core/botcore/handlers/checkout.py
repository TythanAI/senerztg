"""Payment flow: issue the invoice, poll it, and accept Telegram's own updates."""

from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import (
    CheckCB,
    PayCB,
    back_button,
    confirm_payment_keyboard,
    invoice_keyboard,
)
from ..payments import InvoiceKind, PaymentError, PaymentResult, PaymentStatus, ProviderRegistry
from ..services import CheckoutService
from ..services.checkout import TOPUP_SKU
from ..utils import esc, fmt_money, truncate
from .common import _edit

log = logging.getLogger(__name__)
router = Router(name="checkout")


@router.callback_query(PayCB.filter())
async def start_payment(
    callback: CallbackQuery,
    callback_data: PayCB,
    bot: Bot,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    registry: ProviderRegistry,
    checkout: CheckoutService,
    admin_ids: tuple[int, ...],
) -> None:
    order = await repos.orders.get(callback_data.order_id)
    if order is None or order.user_id != user.id:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return
    if order.status != "pending":
        await callback.answer(t("checkout.expired"), show_alert=True)
        return

    # The wallet is not an external rail — settle it here and skip the acquirer.
    if callback_data.provider == "balance":
        if not config.has("balance"):
            await callback.answer(t("errors.not_found"), show_alert=True)
            return
        if order.sku == TOPUP_SKU:
            # Topping the wallet up from the wallet is a no-op loop.
            await callback.answer(t("errors.not_found"), show_alert=True)
            return

        await callback.answer(t("common.loading"))
        if await checkout.pay_from_balance(repos, bot, order, user):
            await _edit(callback, t("balance.paid"), back_button(t))
        else:
            await callback.answer(t("balance.not_enough"), show_alert=True)
        return

    if callback_data.provider not in registry:
        await callback.answer(t("checkout.error"), show_alert=True)
        return

    order.provider = callback_data.provider
    await repos.session.flush()

    await callback.answer(t("common.loading"))

    try:
        invoice = await checkout.bill(repos, order, user)
    except PaymentError as exc:
        log.error("order %s: could not create invoice via %s: %s",
                  order.id, order.provider, exc)
        await _edit(callback, t("checkout.error"), back_button(t))
        return

    if invoice.kind is InvoiceKind.NATIVE:
        await _send_native_invoice(callback, bot, invoice, order.id, t)
        return

    if invoice.kind is InvoiceKind.MANUAL:
        await _edit(
            callback,
            invoice.instructions,
            invoice_keyboard(order.id, "", t),
        )
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"🧾 Заказ #{order.id} ожидает ручного подтверждения\n"
                    f"{esc(order.title)} — {fmt_money(order.amount, order.currency)}\n"
                    f"Покупатель: {esc(user.display())} (<code>{user.tg_id}</code>)",
                    reply_markup=confirm_payment_keyboard(order.id, t),
                )
            except Exception:  # pragma: no cover
                pass
        return

    body = t("checkout.created")
    if invoice.instructions:
        body = invoice.instructions + "\n\n" + body
    await _edit(callback, truncate(body), invoice_keyboard(order.id, invoice.url, t))


async def _send_native_invoice(
    callback: CallbackQuery, bot: Bot, invoice, order_id: int, t: Translator
) -> None:
    """Telegram Payments / Stars: the invoice is a message, not a link."""
    args = dict(invoice.payload)
    prices = [LabeledPrice(**price) for price in args.pop("prices", [])]
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    try:
        await bot.send_invoice(chat_id=chat_id, prices=prices, **args)
    except Exception as exc:
        log.error("order %s: send_invoice failed: %s", order_id, exc)
        if callback.message:
            await callback.message.answer(t("checkout.error"))


@router.callback_query(CheckCB.filter())
async def check_payment(
    callback: CallbackQuery,
    callback_data: CheckCB,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    checkout: CheckoutService,
) -> None:
    order = await repos.orders.get(callback_data.order_id)
    if order is None or order.user_id != user.id:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    if order.status in {"paid", "delivered"}:
        await callback.answer(t("checkout.paid"), show_alert=True)
        return
    if order.status in {"expired", "cancelled"}:
        await callback.answer(t("checkout.expired"), show_alert=True)
        return

    await callback.answer(t("common.loading"))
    result = await checkout.poll(repos, order, user)

    if result.is_paid and await checkout.settle(repos, bot, order, result):
        await _edit(callback, t("checkout.paid"), back_button(t))
        return

    if result.status is PaymentStatus.EXPIRED:
        order.status = "expired"
        await repos.session.flush()
        await callback.answer(t("checkout.expired"), show_alert=True)
        return

    await callback.answer(t("checkout.pending"), show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, repos: Repos) -> None:
    """Telegram's last call before charging — must be answered within 10s."""
    order_id = _order_id_from_payload(query.invoice_payload)
    ok, reason = True, ""

    if order_id is not None:
        order = await repos.orders.get(order_id)
        if order is None:
            ok, reason = False, "Order not found"
        elif order.status != "pending":
            ok, reason = False, "This order is no longer payable"

    try:
        await query.answer(ok=ok, error_message=reason or None)
    except Exception as exc:  # pragma: no cover
        log.error("pre_checkout answer failed: %s", exc)


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    checkout: CheckoutService,
) -> None:
    """Telegram Payments and Stars land here, already charged."""
    payment = message.successful_payment
    if payment is None:  # pragma: no cover - guarded by the filter
        return

    order_id = _order_id_from_payload(payment.invoice_payload)
    if order_id is None:
        log.error("successful_payment with an unparsable payload: %s", payment.invoice_payload)
        await message.answer(t("checkout.paid"))
        return

    order = await repos.orders.get(order_id)
    if order is None:
        log.error("successful_payment for unknown order %s", order_id)
        await message.answer(t("checkout.paid"))
        return

    currency = payment.currency or order.currency
    amount = (
        Decimal(payment.total_amount)
        if currency == "XTR"
        else Decimal(payment.total_amount) / 100
    )
    external_id = (
        payment.telegram_payment_charge_id
        or payment.provider_payment_charge_id
        or f"tg-{order_id}"
    )

    result = PaymentResult(
        status=PaymentStatus.PAID,
        external_id=external_id,
        amount=amount,
        currency=currency,
        raw={
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "provider_payment_charge_id": payment.provider_payment_charge_id,
            "currency": currency,
            "total_amount": payment.total_amount,
        },
    )
    order.external_id = external_id
    await repos.session.flush()

    # Either this call books the payment or a webhook already did; the buyer
    # gets the same confirmation regardless.
    await checkout.settle(repos, bot, order, result)
    await message.answer(t("checkout.paid"))


def _order_id_from_payload(payload: str) -> int | None:
    import json

    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    try:
        return int(data.get("order_id"))
    except (TypeError, ValueError):
        return None
