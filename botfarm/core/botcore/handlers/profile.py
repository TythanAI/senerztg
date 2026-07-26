"""Profile, order history, and the affiliate program."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..config import NicheConfig
from ..db import Repos, User
from ..i18n import Translator
from ..keyboards import MenuCB, back_button
from ..utils import deep_link, esc, fmt_date, fmt_money
from .common import _edit

router = Router(name="profile")

STATUS_LABELS = {
    "ru": {
        "pending": "ожидает оплаты",
        "paid": "оплачен",
        "delivered": "выдан",
        "cancelled": "отменён",
        "refunded": "возврат",
        "expired": "истёк",
    },
    "en": {
        "pending": "awaiting payment",
        "paid": "paid",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "refunded": "refunded",
        "expired": "expired",
    },
}


async def profile_text(
    config: NicheConfig, t: Translator, repos: Repos, user: User
) -> str:
    orders = await repos.orders.last_for_user(user.id, limit=5)
    paid = [o for o in orders if o.status in {"paid", "delivered"}]
    labels = STATUS_LABELS.get(config.lang, STATUS_LABELS["en"])

    lines = [
        t(
            "profile.title",
            tg_id=user.tg_id,
            orders=len(paid),
            balance=fmt_money(user.balance, config.currency),
        )
    ]

    if config.has("subscription"):
        subs = await repos.subs.active_for(user.id)
        lines.append("")
        lines.append(t("profile.subs"))
        if subs:
            for sub in subs:
                lines.append(
                    t(
                        "profile.sub_line",
                        sku=esc(sub.sku),
                        until=fmt_date(sub.expires_at, config.lang),
                    )
                )
        else:
            lines.append(t("profile.no_subs"))

    lines.append("")
    lines.append(t("profile.orders"))
    if orders:
        for order in orders:
            lines.append(
                t(
                    "profile.order_line",
                    id=order.id,
                    title=esc(order.title or order.sku),
                    amount=fmt_money(order.amount, order.currency),
                    status=labels.get(order.status, order.status),
                )
            )
    else:
        lines.append(t("profile.no_orders"))

    return "\n".join(lines)


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def show_profile(
    callback: CallbackQuery, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    await _edit(callback, await profile_text(config, t, repos, user), back_button(t))
    await callback.answer()


@router.message(Command("profile"))
async def cmd_profile(
    message: Message, config: NicheConfig, t: Translator, repos: Repos, user: User
) -> None:
    await message.answer(
        await profile_text(config, t, repos, user), reply_markup=back_button(t)
    )


@router.callback_query(MenuCB.filter(F.action == "referral"))
async def show_referral(
    callback: CallbackQuery,
    config: NicheConfig,
    t: Translator,
    repos: Repos,
    user: User,
    bot_username: str,
) -> None:
    if not config.referral_percent:
        await callback.answer(t("referral.disabled"), show_alert=True)
        return

    count = await repos.users.referrals_of(user.tg_id)
    text = t(
        "referral.title",
        percent=config.referral_percent,
        link=deep_link(bot_username, f"ref{user.tg_id}"),
        count=count,
        earned=fmt_money(user.referral_earned, config.currency),
    )
    await _edit(callback, text, back_button(t))
    await callback.answer()
