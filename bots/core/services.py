"""Runtime services container, injected into every handler by aiogram DI."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot

from .config import BotConfig
from .db import Database
from .payments.cryptobot import CryptoBot

log = logging.getLogger("core.services")


class Services:
    def __init__(self, cfg: BotConfig, db: Database, bot: Bot):
        self.cfg = cfg
        self.db = db
        self.bot = bot
        self.admins = set(cfg.resolved_admins())
        self.crypto: Optional[CryptoBot] = None
        if cfg.payments.cryptobot_enabled and cfg.cryptobot_token:
            self.crypto = CryptoBot(cfg.cryptobot_token, testnet=cfg.payments.cryptobot_testnet)

    def is_admin(self, uid: int) -> bool:
        return uid in self.admins

    def payment_availability(self) -> dict[str, bool]:
        """Which payment methods can actually be used right now (enabled in
        config *and* configured with the needed token)."""
        p = self.cfg.payments
        return {
            "telegram": p.telegram_enabled and bool(self.cfg.provider_token),
            "crypto": p.cryptobot_enabled and self.crypto is not None,
            "cod": p.cod_enabled and self.cfg.fulfillment == "physical",
        }

    def has_any_payment(self) -> bool:
        return any(self.payment_availability().values())

    async def notify_admins(self, text: str, reply_markup=None) -> None:
        """Send order/ops notifications to the orders chat, or every admin."""
        targets = []
        if self.cfg.orders_chat_id is not None:
            targets = [self.cfg.orders_chat_id]
        else:
            targets = list(self.admins)
        for chat_id in targets:
            try:
                await self.bot.send_message(chat_id, text, reply_markup=reply_markup)
            except Exception as exc:  # admin never started the bot, etc.
                log.warning("notify_admins failed for %s: %s", chat_id, exc)

    async def close(self) -> None:
        if self.crypto:
            await self.crypto.close()
