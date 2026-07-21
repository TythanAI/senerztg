"""Small UI helpers shared by handlers (home screen, safe message editing)."""
from __future__ import annotations

from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from . import keyboards as kb
from . import texts
from .services import Services


def home_screen(services: Services, uid: int) -> tuple[str, InlineKeyboardMarkup]:
    text = texts.start(services.cfg)
    markup = kb.main_menu(services.cfg, is_admin=services.is_admin(uid))
    return text, markup


async def safe_edit(
    cbq: CallbackQuery,
    text: str,
    markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Edit the message behind a callback, tolerating 'not modified' and
    messages that have no editable text (e.g. an invoice message)."""
    msg = cbq.message
    if msg is None:
        await cbq.answer()
        return
    try:
        if msg.text is not None:
            await msg.edit_text(text, reply_markup=markup)
        else:
            await msg.answer(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            pass
        else:
            # Fall back to a fresh message rather than failing the update.
            try:
                await msg.answer(text, reply_markup=markup)
            except TelegramBadRequest:
                pass
    await cbq.answer()


async def show_home_cb(services: Services, cbq: CallbackQuery) -> None:
    text, markup = home_screen(services, cbq.from_user.id)
    await safe_edit(cbq, text, markup)
