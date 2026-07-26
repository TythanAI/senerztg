"""Support tickets, lead capture, and the quiz funnel."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import MenuCB, QuizCB, back_button, catalog_menu, phone_request, quiz_keyboard
from ..utils import esc, truncate
from .common import _edit

log = logging.getLogger(__name__)
router = Router(name="support")


class SupportFlow(StatesGroup):
    waiting_message = State()


class LeadFlow(StatesGroup):
    waiting_contact = State()


@router.callback_query(MenuCB.filter(F.action == "support"))
async def open_support(
    callback: CallbackQuery, state: FSMContext, config: NicheConfig, t: Translator
) -> None:
    await state.set_state(SupportFlow.waiting_message)
    text = t("support.prompt")
    if config.support_username:
        text += "\n\n" + t("support.contact", username=esc(config.support_username))
    await _edit(callback, text, back_button(t))
    await callback.answer()


@router.message(Command("support"))
async def cmd_support(
    message: Message, state: FSMContext, config: NicheConfig, t: Translator
) -> None:
    await state.set_state(SupportFlow.waiting_message)
    text = t("support.prompt")
    if config.support_username:
        text += "\n\n" + t("support.contact", username=esc(config.support_username))
    await message.answer(text)


@router.message(SupportFlow.waiting_message, F.text)
async def receive_support_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    body = truncate(message.text or "", 3000)
    ticket = await repos.misc.add_ticket(user.id, body)
    await state.clear()
    await message.answer(t("support.sent"), reply_markup=back_button(t))

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"💬 Тикет #{ticket.id} от {esc(user.display())} "
                f"(<code>{user.tg_id}</code>)\n\n{esc(body)}\n\n"
                f"Ответить: <code>/reply {user.tg_id} текст</code>",
            )
        except Exception:  # pragma: no cover
            log.warning("could not forward ticket %s to admin %s", ticket.id, admin_id)


@router.callback_query(MenuCB.filter(F.action == "booking"))
async def open_booking(
    callback: CallbackQuery, state: FSMContext, config: NicheConfig, t: Translator
) -> None:
    booking_url = config.text("booking_url", "")
    if booking_url:
        await _edit(callback, f"{t('leadgen.prompt')}\n\n📅 {booking_url}", back_button(t))
        await callback.answer()
        return

    await state.set_state(LeadFlow.waiting_contact)
    if callback.message:
        await callback.message.answer(t("leadgen.prompt"), reply_markup=phone_request(t))
    await callback.answer()


@router.message(LeadFlow.waiting_contact, F.contact)
async def receive_contact(
    message: Message,
    state: FSMContext,
    bot: Bot,
    t: Translator,
    repos: Repos,
    user: User,
    admin_ids: tuple[int, ...],
) -> None:
    contact = message.contact
    phone = contact.phone_number if contact else None
    await repos.misc.add_lead(user.id, "booking", phone=phone)
    await state.clear()
    await message.answer(t("leadgen.saved"), reply_markup=ReplyKeyboardRemove())

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"📇 Заявка: {esc(user.display())} (<code>{user.tg_id}</code>)\n"
                f"Телефон: <code>{esc(phone or '—')}</code>",
            )
        except Exception:  # pragma: no cover
            pass


@router.message(LeadFlow.waiting_contact, F.text)
async def receive_contact_text(
    message: Message,
    state: FSMContext,
    t: Translator,
    repos: Repos,
    user: User,
) -> None:
    """Accept a typed phone or email when the share button is declined."""
    raw = (message.text or "").strip()
    email = raw if "@" in raw and "." in raw else None
    phone = raw if email is None else None
    await repos.misc.add_lead(user.id, "booking", phone=phone, email=email)
    await state.clear()
    await message.answer(t("leadgen.saved"), reply_markup=ReplyKeyboardRemove())


# --------------------------------------------------------------------- quiz


@router.callback_query(MenuCB.filter(F.action == "quiz"))
async def start_quiz(
    callback: CallbackQuery, state: FSMContext, config: NicheConfig, t: Translator
) -> None:
    if not config.quiz:
        await callback.answer(t("faq.empty"), show_alert=True)
        return
    await state.update_data(quiz_score=0)
    await _render_quiz_step(callback, config, t, 0)
    await callback.answer()


@router.callback_query(QuizCB.filter())
async def advance_quiz(
    callback: CallbackQuery,
    callback_data: QuizCB,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
) -> None:
    if not config.quiz:
        await callback.answer(t("errors.not_found"), show_alert=True)
        return

    data = await state.get_data()
    score = int(data.get("quiz_score", 0)) + callback_data.option
    await state.update_data(quiz_score=score)

    next_step = callback_data.step + 1
    if next_step < len(config.quiz):
        await _render_quiz_step(callback, config, t, next_step)
        await callback.answer()
        return

    # Higher score → higher tier. Clamp so a short quiz still maps cleanly.
    products = config.active_products()
    if not products:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return

    index = min(len(products) - 1, score * len(products) // max(1, len(config.quiz) * 3))
    pick = products[index]
    await state.update_data(quiz_score=0)
    await repos.misc.track(user.tg_id, "quiz_done", pick.sku)

    await _edit(
        callback,
        f"{t('quiz.done')}\n\n<b>{esc(pick.title)}</b>\n{esc(pick.description)}",
        catalog_menu([pick, *[p for p in products if p.sku != pick.sku]], config, t),
    )
    await callback.answer()


async def _render_quiz_step(
    callback: CallbackQuery, config: NicheConfig, t: Translator, step: int
) -> None:
    entry = config.quiz[step]
    question = esc(entry.get("q", ""))
    options = [str(o) for o in (entry.get("options") or [])]
    header = t("quiz.intro") if step == 0 else ""
    body = f"{header}\n\n<b>{step + 1}/{len(config.quiz)}. {question}</b>".strip()
    await _edit(callback, body, quiz_keyboard(step, options))
