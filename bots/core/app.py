"""Application factory + runner. One process = one bot.

Usage:
    python -m core --config config/tg_accounts_01.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)
from aiogram.utils.token import TokenValidationError

from .config import BotConfig, load_config
from .db import Database
from .handlers import setup_routers
from .logger import setup_logging
from .middlewares import AntiFloodMiddleware, ErrorMiddleware, UserMiddleware
from .services import Services

log = logging.getLogger("core.app")

DEFAULT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="help", description="Поддержка"),
]


def _db_path(cfg: BotConfig) -> str:
    override = os.getenv("DB_PATH", "").strip()
    if override:
        return override
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{cfg.slug}.db")


async def _set_commands(bot: Bot, services: Services) -> None:
    try:
        await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeDefault())
        admin_cmds = DEFAULT_COMMANDS + [BotCommand(command="admin", description="Админ-панель")]
        for admin_id in services.admins:
            try:
                await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception:
                pass  # admin has not opened the bot yet
    except Exception as exc:
        log.warning("set_my_commands failed: %s", exc)


async def _cleanup_loop(services: Services) -> None:
    while True:
        await asyncio.sleep(600)
        try:
            # Wider than the 1h invoice lifetime, so a just-paid invoice is
            # never cancelled out from under the buyer between checks.
            n = await services.db.expire_pending_orders(7200)
            if n:
                log.info("expired %d stale pending order(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("cleanup loop error: %s", exc)


async def run(config_path: str) -> None:
    cfg = load_config(config_path)
    setup_logging(cfg.slug)
    log.info("Starting bot '%s' (slug=%s, fulfillment=%s)", cfg.name, cfg.slug, cfg.fulfillment)

    if not cfg.bot_token:
        raise SystemExit(
            f"Bot token is missing. Set env var '{cfg.token_env}' before starting."
        )
    if not cfg.resolved_admins():
        log.warning("No admins configured — admin panel will be unreachable. "
                    "Set '%s' or add ids to the config.", cfg.admin_env)

    try:
        bot = Bot(
            token=cfg.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    except TokenValidationError as exc:
        raise SystemExit(f"Invalid bot token: {exc}")

    db = Database(_db_path(cfg))
    await db.connect()
    services = Services(cfg, db, bot)

    dp = Dispatcher(storage=MemoryStorage())
    # Outer middlewares wrap every update (updates that carry a user).
    dp.update.outer_middleware(ErrorMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(AntiFloodMiddleware(rate=0.5))
    setup_routers(dp)

    await _set_commands(bot, services)
    cleanup = asyncio.create_task(_cleanup_loop(services))
    try:
        await dp.start_polling(bot, services=services, allowed_updates=dp.resolve_used_update_types())
    finally:
        cleanup.cancel()
        try:
            await cleanup
        except asyncio.CancelledError:
            pass
        await services.close()
        await db.close()
        await bot.session.close()
        log.info("Bot '%s' stopped", cfg.slug)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a shop bot from a config file.")
    parser.add_argument("--config", "-c", required=True, help="Path to the bot YAML config")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.config))
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code:
            raise
        log.info("Shutdown requested")


if __name__ == "__main__":
    main()
