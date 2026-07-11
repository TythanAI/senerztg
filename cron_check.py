# -*- coding: utf-8 -*-
"""
Один проход монитора — для запуска по расписанию (GitHub Actions, cron).

В отличие от skin_monitor_bot.py не висит в памяти постоянно:
запустился -> проверил все предметы из watchlist.json -> разослал алерты
в Telegram -> сохранил состояние в state.json -> завершился.
Состояние коммитится обратно в репозиторий воркфлоу (.github/workflows/monitor.yml).

Токен подаётся через переменную окружения BOT_TOKEN.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

import aiohttp

from skin_monitor_bot import (
    ADMIN_ID,
    GLOBAL_STICKERS,
    ITEM_PAUSE,
    STEAM,
    STICKER_MIN_PRICE,
    WATCHLIST,
    SteamBlocked,
    fetch_listings,
    inspect_item,
    lowest_price,
    match_rules,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STATE_PATH = Path(__file__).with_name("state.json")

SPIKE_PCT = 12           # скачок цены в %...
SPIKE_WINDOW_MIN = 60    # ...за столько минут (шире, чем у живого бота: cron ходит реже)

SEEN_KEEP = 20000        # сколько последних listing_id помнить
PRICE_KEEP_SEC = 86400   # история цен — сутки
STICKER_TTL = 86400      # кэш цен наклеек — сутки
HEARTBEAT_SEC = 86400    # раз в сутки слать «я жив», даже если находок нет
PASS_BUDGET_SEC = 480    # жёсткий потолок на проход (8 мин) — не зависаем никогда

log = logging.getLogger("cron")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_state() -> dict:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state.setdefault("last_heartbeat", 0)
        state.setdefault("first_run_done", False)
        return state
    return {"seen": [], "prices": {}, "sticker_prices": {},
            "last_heartbeat": 0, "first_run_done": False}


def save_state(state: dict) -> None:
    now = int(time.time())
    state["seen"] = state["seen"][-SEEN_KEEP:]
    state["prices"] = {
        k: [(ts, p) for ts, p in v if ts >= now - PRICE_KEEP_SEC]
        for k, v in state["prices"].items()
    }
    state["sticker_prices"] = {
        k: v for k, v in state["sticker_prices"].items() if now - v[0] < STICKER_TTL
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


async def notify(session: aiohttp.ClientSession, text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": ADMIN_ID, "text": text}) as r:
            if r.status != 200:
                log.warning("telegram %s: %s", r.status, (await r.text())[:200])
    except Exception as e:
        log.warning("telegram: %s", e)


async def cached_sticker_price(session, state: dict, name: str) -> float | None:
    mhn = name if name.startswith("Sticker |") else f"Sticker | {name}"
    now = int(time.time())
    cached = state["sticker_prices"].get(mhn)
    if cached and now - cached[0] < STICKER_TTL:
        return cached[1] or None
    price = await lowest_price(session, mhn)
    await asyncio.sleep(ITEM_PAUSE)
    state["sticker_prices"][mhn] = [now, price or 0]
    return price


async def expensive_stickers(session, state: dict, info: dict) -> list[str]:
    reasons = []
    names = {s.get("name", "") for s in info.get("stickers", []) if s.get("name")}
    for n in names:
        p = await cached_sticker_price(session, state, n)
        if p and p >= STICKER_MIN_PRICE:
            count = sum(1 for s in info.get("stickers", []) if s.get("name") == n)
            mult = f" x{count}" if count > 1 else ""
            reasons.append(f"дорогая наклейка: {n}{mult} (~{p:.0f})")
    return reasons


def check_spike(state: dict, name: str, price: float) -> str | None:
    now = int(time.time())
    hist = state["prices"].setdefault(name, [])
    hist.append((now, price))
    window = [p for ts, p in hist if ts >= now - SPIKE_WINDOW_MIN * 60]
    base = min(window) if window else None
    if base and base > 0 and price >= base * (1 + SPIKE_PCT / 100):
        pct = (price / base - 1) * 100
        return (f"🚀 БУСТ ЦЕНЫ: {name}\n"
                f"{base:.2f} → {price:.2f} (+{pct:.1f}%) за {SPIKE_WINDOW_MIN} мин\n"
                f"⚠️ Комиссия маркета 15% — рост меньше неё = убыток.\n"
                f"{STEAM}/market/listings/730/{name}")
    return None


async def main() -> None:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN не задан! В репозитории: Settings -> Secrets and "
                  "variables -> Actions -> New repository secret, имя BOT_TOKEN.")
        raise SystemExit(1)

    state = load_state()
    seen = set(state["seen"])
    found = 0
    steam_ok = False   # достучались ли до Steam хоть раз за проход
    blocked = False    # Steam стабильно отдаёт 429/403
    deadline = time.monotonic() + PASS_BUDGET_SEC

    async with aiohttp.ClientSession() as session:
        try:
            for item in WATCHLIST:
                if time.monotonic() > deadline:
                    log.warning("исчерпан бюджет времени прохода, останавливаюсь")
                    break
                name = item["name"]
                low = await lowest_price(session, name)
                if low:
                    steam_ok = True
                    spike = check_spike(state, name, low)
                    if spike:
                        await notify(session, spike)
                await asyncio.sleep(ITEM_PAUSE)

                for lot in await fetch_listings(session, name):
                    if lot["listing_id"] in seen:
                        continue
                    seen.add(lot["listing_id"])
                    state["seen"].append(lot["listing_id"])

                    if low and lot["price"] > low * (1 + item.get("max_overpay_pct", 10) / 100):
                        continue
                    if not lot["inspect"]:
                        continue

                    info = await inspect_item(session, lot["inspect"])
                    await asyncio.sleep(1.5)
                    if not info:
                        continue
                    reasons = match_rules(item, info)
                    if item.get("check_sticker_value") and info.get("stickers"):
                        reasons += await expensive_stickers(session, state, info)
                    if not reasons:
                        continue

                    found += 1
                    await notify(session, (
                        f"🎯 НАХОДКА: {name}\n"
                        f"Цена лота: {lot['price']:.2f} (минимум: {low or '?'})\n"
                        f"Почему: {'; '.join(reasons)}\n"
                        f"Флоат: {info.get('floatvalue', '?')}, паттерн: {info.get('paintseed', '?')}\n"
                        f"Купить: {lot['buy_url']}"))

                await asyncio.sleep(ITEM_PAUSE)
        except SteamBlocked as e:
            blocked = True
            log.warning("проход прерван: %s", e)

        # подтверждение жизни: первый запуск + раз в сутки
        now = int(time.time())
        if blocked or not steam_ok:
            await notify(session,
                "⚠️ Монитор запустился, но Steam блокирует запросы с IP серверов "
                "GitHub (HTTP 403/429). Это ожидаемо для дата-центров. Монитор "
                "нужно запускать с домашнего IP — см. README, раздел про локальный "
                "запуск по расписанию.")
        elif not state["first_run_done"]:
            await notify(session,
                f"✅ Монитор подключён и работает! Слежу за {len(WATCHLIST)} "
                f"предметами. Буду писать, когда найду редкий паттерн, дорогую "
                f"наклейку или резкий буст цены. Тишина = просто пока ничего "
                f"подходящего на маркете. Команда /last покажет историю.")
            state["first_run_done"] = True
            state["last_heartbeat"] = now
        elif now - state["last_heartbeat"] >= HEARTBEAT_SEC:
            await notify(session,
                f"💓 Монитор жив, за сутки проверено {len(WATCHLIST)} предметов. "
                f"Находок за последний проход: {found}.")
            state["last_heartbeat"] = now

    save_state(state)
    log.info("проход завершён: находок %d, известных лотов %d, steam_ok=%s",
             found, len(state["seen"]), steam_ok)


if __name__ == "__main__":
    asyncio.run(main())
