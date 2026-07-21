"""Support contact form + a safe catch-all for stray messages."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import keyboards as kb
from .. import texts, ui
from ..services import Services
from ..states import SupportFSM

router = Router(name="support")


def _support_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✍️ Написать сообщение", callback_data="support:write")
    b.button(text="⬅️ В меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


@router.callback_query(F.data == "menu:support")
async def cb_support(cbq: CallbackQuery, services: Services) -> None:
    await ui.safe_edit(cbq, texts.support(services.cfg), _support_kb())


@router.callback_query(F.data == "support:write")
async def cb_support_write(cbq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportFSM.message)
    await ui.safe_edit(
        cbq, "Напишите ваше сообщение одним текстом — мы передадим его оператору.",
        kb.cancel_only(),
    )


@router.message(SupportFSM.message, F.text)
async def st_support_message(message: Message, state: FSMContext, services: Services) -> None:
    await state.clear()
    text = (message.text or "").strip()[:2000]
    user = message.from_user
    uname = f"@{user.username}" if user.username else "без ника"
    await services.notify_admins(
        f"💬 <b>Сообщение в поддержку</b>\n"
        f"От: {texts.esc(user.full_name)} ({uname}, id <code>{user.id}</code>)\n\n"
        f"{texts.esc(text)}"
    )
    await message.answer(texts.SUPPORT_SENT, reply_markup=kb.back_home())


# ---- safe catch-all: only when the user is NOT inside any FSM flow ----
@router.message(StateFilter(None), F.text)
async def fallback(message: Message, services: Services) -> None:
    text, markup = ui.home_screen(services, message.from_user.id)
    await message.answer(
        "Воспользуйтесь кнопками меню, чтобы сделать заказ 👇\n\n" + text,
        reply_markup=markup,
    )
