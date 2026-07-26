"""/start, the main menu, and navigation back to it."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import MenuCB, back_button, main_menu
from ..utils import esc

log = logging.getLogger(__name__)
router = Router(name="common")


def welcome_text(config: NicheConfig, t: Translator, user: User) -> str:
    return t(
        "start.welcome",
        name=esc(config.name),
        tagline=esc(config.tagline or config.description),
        first_name=esc(user.first_name or ""),
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    is_new_user: bool,
) -> None:
    await state.clear()
    await repos.misc.track(user.tg_id, "start", user.source)
    if is_new_user:
        log.info("new user %s (%s) source=%s", user.tg_id, user.display(), user.source)

    await message.answer(welcome_text(config, t, user), reply_markup=main_menu(config, t))


@router.callback_query(MenuCB.filter(F.action == "home"))
async def go_home(
    callback: CallbackQuery,
    state: FSMContext,
    config: NicheConfig,
    t: Translator,
    user: User,
) -> None:
    await state.clear()
    await _edit(callback, welcome_text(config, t, user), main_menu(config, t))
    await callback.answer()


@router.message(Command("menu"))
async def cmd_menu(
    message: Message, state: FSMContext, config: NicheConfig, t: Translator, user: User
) -> None:
    await state.clear()
    await message.answer(welcome_text(config, t, user), reply_markup=main_menu(config, t))


@router.message(Command("help"))
async def cmd_help(message: Message, config: NicheConfig, t: Translator) -> None:
    lines = [f"<b>{esc(config.name)}</b>", ""]
    if config.description:
        lines += [esc(config.description), ""]
    lines += [
        "/start — " + t("common.menu"),
        "/menu — " + t("common.menu"),
    ]
    if config.has("support"):
        lines.append("/support — " + t("menu.support"))
    if config.support_username:
        lines.append("")
        lines.append(t("support.contact", username=esc(config.support_username)))
    await message.answer("\n".join(lines), reply_markup=back_button(t))


@router.callback_query(MenuCB.filter(F.action == "faq"))
async def show_faq(callback: CallbackQuery, config: NicheConfig, t: Translator) -> None:
    if not config.faq:
        await callback.answer(t("faq.empty"), show_alert=True)
        return
    lines = [t("faq.title"), ""]
    for entry in config.faq:
        question = esc(entry.get("q", ""))
        answer = esc(entry.get("a", ""))
        lines.append(f"<b>{question}</b>\n{answer}\n")
    await _edit(callback, "\n".join(lines), back_button(t))
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "content"))
async def show_content(callback: CallbackQuery, config: NicheConfig, t: Translator) -> None:
    body = config.text("content", "") or config.description
    await _edit(callback, esc(body) if body else t("faq.empty"), back_button(t))
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "reviews"))
async def show_reviews(callback: CallbackQuery, config: NicheConfig, t: Translator) -> None:
    body = config.text("reviews", "") or t("faq.empty")
    await _edit(callback, body, back_button(t))
    await callback.answer()


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    """Edit in place when possible; fall back to a new message."""
    message = callback.message
    if message is None:
        return
    try:
        await message.edit_text(text, reply_markup=markup)
    except Exception:
        # Message too old, identical, or was a media post.
        try:
            await message.answer(text, reply_markup=markup)
        except Exception:  # pragma: no cover
            log.warning("could not render screen for %s", callback.from_user.id)
