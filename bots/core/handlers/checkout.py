"""Checkout: digital orders go straight to payment; physical orders collect
delivery details via an FSM first."""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts, ui
from ..flows import build_cart_items, create_digital_order, create_physical_order
from ..services import Services
from ..states import Checkout

router = Router(name="checkout")

_DIGITS = re.compile(r"\d")


def _payment_screen(services: Services, order_id: int, items, total: float):
    avail = services.payment_availability()
    text = (
        texts.order_summary(items, total, services.cfg.currency)
        + "\n\nВыберите способ оплаты:"
    )
    markup = kb.choose_payment(
        order_id, telegram=avail["telegram"], crypto=avail["crypto"], cod=avail["cod"]
    )
    return text, markup


@router.callback_query(F.data == "cart:checkout")
async def cb_checkout(cbq: CallbackQuery, state: FSMContext, services: Services) -> None:
    uid = cbq.from_user.id
    items, total = await build_cart_items(services, uid)
    if not items:
        await cbq.answer("Корзина пуста", show_alert=True)
        return
    if not services.has_any_payment():
        await cbq.answer(
            "Оплата временно недоступна. Напишите в поддержку.", show_alert=True
        )
        return

    if services.cfg.fulfillment == "digital":
        order_id, err = await create_digital_order(services, uid)
        if err == "empty":
            await cbq.answer("Корзина пуста", show_alert=True)
            return
        if err is not None:
            await ui.safe_edit(cbq, texts.out_of_stock(err), kb.back_home())
            return
        order = await services.db.get_order(order_id)
        oitems = await services.db.order_items(order_id)
        text, markup = _payment_screen(services, order_id, oitems, order.total)
        await ui.safe_edit(cbq, text, markup)
        return

    # physical -> collect delivery details
    await state.set_state(Checkout.name)
    await ui.safe_edit(cbq, texts.ask_name(), kb.cancel_only())


@router.message(Checkout.name, F.text)
async def st_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Попробуйте ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Checkout.phone)
    await message.answer(texts.ask_phone(), reply_markup=kb.cancel_only())


@router.message(Checkout.phone, F.text)
async def st_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()[:32]
    if len(_DIGITS.findall(phone)) < 5:
        await message.answer("Похоже, это не номер телефона. Укажите корректный номер.")
        return
    await state.update_data(phone=phone)
    await state.set_state(Checkout.address)
    await message.answer(texts.ask_address(), reply_markup=kb.cancel_only())


@router.message(Checkout.address, F.text)
async def st_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()[:256]
    if len(address) < 5:
        await message.answer("Адрес слишком короткий. Уточните, пожалуйста.")
        return
    await state.update_data(address=address)
    await state.set_state(Checkout.comment)
    await message.answer(texts.ask_comment(), reply_markup=kb.skip_comment())


async def _finish_physical(message: Message, state: FSMContext, services: Services, comment: str):
    data = await state.get_data()
    await state.clear()
    order_id, err = await create_physical_order(
        services,
        message.chat.id,
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        comment=comment,
    )
    if err == "empty" or order_id is None:
        await message.answer("Корзина пуста.", reply_markup=kb.back_home())
        return
    order = await services.db.get_order(order_id)
    oitems = await services.db.order_items(order_id)
    text, markup = _payment_screen(services, order_id, oitems, order.total)
    await message.answer(text, reply_markup=markup)


@router.message(Checkout.comment, F.text)
async def st_comment(message: Message, state: FSMContext, services: Services) -> None:
    comment = (message.text or "").strip()[:512]
    await _finish_physical(message, state, services, comment)


@router.callback_query(Checkout.comment, F.data == "co:skip")
async def st_comment_skip(cbq: CallbackQuery, state: FSMContext, services: Services) -> None:
    await cbq.answer()
    await _finish_physical(cbq.message, state, services, "")
