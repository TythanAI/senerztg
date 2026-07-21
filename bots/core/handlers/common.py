"""Start, main-menu navigation, rules, profile."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts, ui
from ..services import Services

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    text, markup = ui.home_screen(services, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    text, markup = ui.home_screen(services, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    text, markup = ui.home_screen(services, message.from_user.id)
    await message.answer("Действие отменено.", reply_markup=markup)


@router.message(Command("help"))
async def cmd_help(message: Message, services: Services) -> None:
    await message.answer(texts.support(services.cfg), reply_markup=kb.back_home())


@router.callback_query(F.data == "menu:home")
async def cb_home(cbq: CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    await ui.show_home_cb(services, cbq)


@router.callback_query(F.data == "menu:rules")
async def cb_rules(cbq: CallbackQuery, services: Services) -> None:
    await ui.safe_edit(cbq, texts.rules(services.cfg), kb.back_home())


@router.callback_query(F.data == "menu:profile")
async def cb_profile(cbq: CallbackQuery, services: Services) -> None:
    orders = await services.db.user_orders(cbq.from_user.id, limit=10)
    if not orders:
        body = "📦 У вас пока нет заказов."
    else:
        lines = ["📦 <b>Ваши заказы</b>\n"]
        lines += [texts.order_status_line(o) for o in orders]
        body = "\n".join(lines)
    await ui.safe_edit(cbq, body, kb.back_home())


@router.callback_query(F.data == "noop")
async def cb_noop(cbq: CallbackQuery) -> None:
    await cbq.answer()
