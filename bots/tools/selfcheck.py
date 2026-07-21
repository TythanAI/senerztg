#!/usr/bin/env python3
"""Offline health check — no bot token or network required.

Validates every config, exercises the stock-reservation + payment-idempotency
logic on a scratch database, and builds the full dispatcher. Run before you
deploy (or in CI):

    python tools/selfcheck.py
"""
from __future__ import annotations

import asyncio
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402

from core.config import BotConfig, load_config  # noqa: E402
from core.db import Database, OrderItem  # noqa: E402
from core.handlers import setup_routers  # noqa: E402
from core.middlewares import (  # noqa: E402
    AntiFloodMiddleware, ErrorMiddleware, UserMiddleware,
)

DUMMY_TOKEN = "123456:" + "A" * 40
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_configs() -> int:
    paths = sorted(glob.glob(os.path.join(ROOT, "config", "*.yaml")))
    for path in paths:
        cfg = load_config(path)
        for p in cfg.all_products():
            assert len(("prod:" + p.sku).encode()) <= 60, f"SKU too long in {cfg.slug}: {p.sku}"
        assert cfg.all_products(), f"{cfg.slug} has no products"
    print(f"configs: {len(paths)} loaded and validated")
    return len(paths)


async def check_db() -> None:
    tmp = tempfile.mktemp(suffix=".db")
    db = Database(tmp)
    await db.connect()
    try:
        await db.add_stock("s1", ["a", "b", "c"])
        oid = await db.create_order(1, 10.0, "USD", "digital", [OrderItem("s1", "P", 5.0, 2)])
        assert await db.reserve_stock("s1", 2, oid)
        assert not await db.reserve_stock("s1", 2, oid)          # only 1 left
        assert await db.mark_paid_if_pending(oid, "cryptobot", "x")
        assert not await db.mark_paid_if_pending(oid, "cryptobot", "x")   # idempotent
        assert len(await db.sell_order_stock(oid)) == 2
    finally:
        await db.close()
        os.unlink(tmp)
    print("db: reservation + idempotency OK")


async def check_wiring() -> None:
    cfg = BotConfig(
        name="X", slug="x", catalog=[{"id": "c", "title": "C", "products": [
            {"sku": "s", "title": "S", "price": 1.0}]}],
        payments={"cryptobot_enabled": True},
    )
    cfg.validate_semantics()
    bot = Bot(token=DUMMY_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(ErrorMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(AntiFloodMiddleware())
    setup_routers(dp)
    used = dp.resolve_used_update_types()
    assert {"message", "callback_query", "pre_checkout_query"} <= set(used), used
    await bot.session.close()
    print("wiring: dispatcher + routers OK")


async def main() -> None:
    n = check_configs()
    await check_db()
    await check_wiring()
    print(f"\n✅ selfcheck passed — {n} bots ready.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"\n❌ selfcheck FAILED: {exc}")
        sys.exit(1)
