# -*- coding: utf-8 -*-
"""
Монитор скинов CS2 на Торговой площадке Steam.

1. Следит за предметами из watchlist.json: тянет свежие лоты, проверяет
   флоат / паттерн (paint seed) / наклейки через бесплатный API csfloat.com
   и шлёт уведомление в Telegram, если лот подходит и не переоценён.
2. Наклейки Katowice 2014 (global_sticker_keywords) проверяются на КАЖДОМ
   лоте любого отслеживаемого предмета.
3. Ловит резкие скачки цены: +SPIKE_PCT% за SPIKE_WINDOW_MIN минут.

Запуск:
    pip install -r requirements.txt
    export BOT_TOKEN="токен_от_BotFather"
    python skin_monitor_bot.py

Команды: /status — что мониторится, /last — последние события.

ЛИМИТЫ: Steam банит по IP за частые запросы. Не опускай паузы ниже
установленных и не раздувай watchlist сверх ~20 предметов.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ======================= КОНФИГ =======================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "СЮДА_ТОКЕН_ОТ_BOTFATHER")
ADMIN_ID = 1164070668

CURRENCY = 5             # 5 = рубли, 1 = доллары
POLL_SECONDS = 45        # пауза между полными кругами опроса
ITEM_PAUSE = 3           # пауза между запросами к Steam (меньше — риск бана)
LISTINGS_PER_ITEM = 10   # сколько свежих лотов проверять у каждого предмета

SPIKE_PCT = 12           # скачок цены в %...
SPIKE_WINDOW_MIN = 30    # ...за столько минут = уведомление о бусте

DB_PATH = "skin_monitor.db"
WATCHLIST_PATH = Path(__file__).with_name("watchlist.json")

# =======================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("skins")

STEAM = "https://steamcommunity.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def load_watchlist() -> tuple[list[dict], list[str], float]:
    data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    return (data["items"], data.get("global_sticker_keywords", []),
            data.get("sticker_min_price", 500))


WATCHLIST, GLOBAL_STICKERS, STICKER_MIN_PRICE = load_watchlist()

STICKER_CACHE_TTL = 86400  # цены наклеек кэшируются на сутки


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS seen (listing_id TEXT PRIMARY KEY, ts INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS prices (item TEXT, ts INTEGER, price REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS events (ts INTEGER, text TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS sticker_prices"
                 " (name TEXT PRIMARY KEY, ts INTEGER, price REAL)")
    return conn


def parse_price(s: str) -> float | None:
    """'1 234,56 pуб.' / '$12.34' / '1.234,50€' -> float"""
    if not s:
        return None
    m = re.search(r"\d[\d\s .,]*", s)
    if not m:
        return None
    t = m.group().replace(" ", "").replace(" ", "").strip(".,")
    last = max(t.rfind(","), t.rfind("."))
    try:
        if last != -1 and len(t) - last - 1 in (1, 2):
            return float(re.sub(r"[.,]", "", t[:last]) + "." + t[last + 1:])
        return float(re.sub(r"[.,]", "", t))
    except ValueError:
        return None


class SteamBlocked(Exception):
    """Steam стабильно отвечает 429/403 — дальше долбить бессмысленно."""


# счётчик подряд идущих отказов Steam; сбрасывается при успешном ответе
_consecutive_blocks = 0
BLOCK_LIMIT = 5  # столько 429/403 подряд = прерываем проход


async def get_json(session: aiohttp.ClientSession, url: str) -> dict | None:
    global _consecutive_blocks
    try:
        async with session.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status in (429, 403):
                _consecutive_blocks += 1
                log.warning("HTTP %s (блок %d/%d): %s",
                            r.status, _consecutive_blocks, BLOCK_LIMIT, url[:80])
                if _consecutive_blocks >= BLOCK_LIMIT:
                    raise SteamBlocked(f"Steam вернул {r.status} {BLOCK_LIMIT} раз подряд")
                await asyncio.sleep(2)
                return None
            if r.status != 200:
                log.warning("HTTP %s: %s", r.status, url[:90])
                return None
            _consecutive_blocks = 0
            return await r.json(content_type=None)
    except SteamBlocked:
        raise
    except Exception as e:
        log.warning("сеть: %s", e)
        return None


async def lowest_price(session: aiohttp.ClientSession, name: str) -> float | None:
    url = (f"{STEAM}/market/priceoverview/?appid=730&currency={CURRENCY}"
           f"&market_hash_name={quote(name)}")
    data = await get_json(session, url)
    if data and data.get("success"):
        return parse_price(data.get("lowest_price") or data.get("median_price") or "")
    return None


async def fetch_listings(session: aiohttp.ClientSession, name: str) -> list[dict]:
    url = (f"{STEAM}/market/listings/730/{quote(name)}/render/"
           f"?start=0&count={LISTINGS_PER_ITEM}&currency={CURRENCY}&format=json")
    data = await get_json(session, url)
    if not data or not data.get("listinginfo"):
        return []

    assets = data.get("assets", {}).get("730", {})
    out = []
    for lid, li in data["listinginfo"].items():
        price_cents = (li.get("converted_price") or 0) + (li.get("converted_fee") or 0)
        if not price_cents:
            continue
        asset = li.get("asset", {})
        a_id = asset.get("id")
        inspect = None
        desc = assets.get(str(asset.get("contextid", 2)), {}).get(str(a_id), {})
        for act in (desc.get("market_actions") or desc.get("actions") or []):
            link = act.get("link", "")
            if "csgo_econ_action_preview" in link:
                inspect = link.replace("%listingid%", lid).replace("%assetid%", str(a_id))
        out.append({
            "listing_id": lid,
            "price": price_cents / 100,
            "inspect": inspect,
            "buy_url": f"{STEAM}/market/listings/730/{quote(name)}",
        })
    return out


async def inspect_item(session: aiohttp.ClientSession, inspect_link: str) -> dict | None:
    url = "https://api.csfloat.com/?url=" + quote(inspect_link, safe="")
    data = await get_json(session, url)
    return (data or {}).get("iteminfo")


async def sticker_price(session: aiohttp.ClientSession, sticker_name: str) -> float | None:
    """Цена наклейки на маркете, с кэшем на сутки (0 в кэше = 'не нашли')."""
    mhn = sticker_name if sticker_name.startswith("Sticker |") else f"Sticker | {sticker_name}"
    now = int(time.time())
    with db() as conn:
        row = conn.execute(
            "SELECT price, ts FROM sticker_prices WHERE name = ?", (mhn,)).fetchone()
    if row and now - row[1] < STICKER_CACHE_TTL:
        return row[0] or None
    price = await lowest_price(session, mhn)
    await asyncio.sleep(ITEM_PAUSE)  # это тоже запрос к Steam
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO sticker_prices VALUES (?, ?, ?)",
                     (mhn, now, price or 0))
    return price


async def expensive_stickers(session: aiohttp.ClientSession, info: dict) -> list[str]:
    """Причины вида 'дорогая наклейка: X (~N)' для наклеек дороже порога."""
    reasons = []
    names = {s.get("name", "") for s in info.get("stickers", []) if s.get("name")}
    for n in names:
        p = await sticker_price(session, n)
        if p and p >= STICKER_MIN_PRICE:
            count = sum(1 for s in info.get("stickers", []) if s.get("name") == n)
            mult = f" x{count}" if count > 1 else ""
            reasons.append(f"дорогая наклейка: {n}{mult} (~{p:.0f})")
    return reasons


def match_rules(item: dict, info: dict) -> list[str]:
    """Причины, почему лот интересен (пустой список = не подходит)."""
    reasons = []
    fv = info.get("floatvalue")
    if item.get("max_float") is not None and fv is not None and fv <= item["max_float"]:
        reasons.append(f"низкий флоат {fv:.4f} ≤ {item['max_float']}")
    if item.get("min_float") is not None and fv is not None and fv >= item["min_float"]:
        reasons.append(f"экстремальный флоат {fv:.5f} ≥ {item['min_float']}")
    if item.get("paint_seeds") and info.get("paintseed") in item["paint_seeds"]:
        reasons.append(f"редкий паттерн #{info['paintseed']}")

    sticker_names = " | ".join(s.get("name", "") for s in info.get("stickers", []))
    for kw in list(item.get("sticker_keywords", [])) + GLOBAL_STICKERS:
        if kw and kw.lower() in sticker_names.lower():
            reasons.append(f"наклейка: {kw}")
    return reasons


def remember_event(text: str) -> None:
    with db() as conn:
        conn.execute("INSERT INTO events VALUES (?, ?)", (int(time.time()), text))


async def check_spike(name: str, price: float, bot: Bot) -> None:
    now = int(time.time())
    with db() as conn:
        conn.execute("INSERT INTO prices VALUES (?, ?, ?)", (name, now, price))
        conn.execute("DELETE FROM prices WHERE ts < ?", (now - 86400,))
        row = conn.execute(
            "SELECT MIN(price) FROM prices WHERE item = ? AND ts >= ?",
            (name, now - SPIKE_WINDOW_MIN * 60),
        ).fetchone()
    base = row[0]
    if base and base > 0 and price >= base * (1 + SPIKE_PCT / 100):
        pct = (price / base - 1) * 100
        text = (f"🚀 БУСТ ЦЕНЫ: {name}\n"
                f"{base:.2f} → {price:.2f} (+{pct:.1f}%) за {SPIKE_WINDOW_MIN} мин\n"
                f"⚠️ Комиссия маркета 15% — рост меньше неё = убыток.\n"
                f"{STEAM}/market/listings/730/{quote(name)}")
        remember_event(text.splitlines()[0])
        await bot.send_message(ADMIN_ID, text)


async def monitor_loop(bot: Bot) -> None:
    async with aiohttp.ClientSession() as session:
        await bot.send_message(
            ADMIN_ID,
            f"👁 Монитор запущен. Предметов: {len(WATCHLIST)}. "
            f"Буст: +{SPIKE_PCT}% за {SPIKE_WINDOW_MIN} мин.")
        while True:
            for item in WATCHLIST:
                name = item["name"]
                low = await lowest_price(session, name)
                if low:
                    await check_spike(name, low, bot)
                await asyncio.sleep(ITEM_PAUSE)

                for lot in await fetch_listings(session, name):
                    with db() as conn:
                        seen = conn.execute(
                            "SELECT 1 FROM seen WHERE listing_id = ?",
                            (lot["listing_id"],)).fetchone()
                    if seen:
                        continue
                    with db() as conn:
                        conn.execute("INSERT OR IGNORE INTO seen VALUES (?, ?)",
                                     (lot["listing_id"], int(time.time())))

                    if low and lot["price"] > low * (1 + item.get("max_overpay_pct", 10) / 100):
                        continue
                    if not lot["inspect"]:
                        continue

                    info = await inspect_item(session, lot["inspect"])
                    await asyncio.sleep(1.5)  # лимит csfloat
                    if not info:
                        continue
                    reasons = match_rules(item, info)
                    if item.get("check_sticker_value") and info.get("stickers"):
                        reasons += await expensive_stickers(session, info)
                    if not reasons:
                        continue

                    text = (f"🎯 НАХОДКА: {name}\n"
                            f"Цена лота: {lot['price']:.2f} (минимум: {low or '?'})\n"
                            f"Почему: {'; '.join(reasons)}\n"
                            f"Флоат: {info.get('floatvalue', '?')}, паттерн: {info.get('paintseed', '?')}\n"
                            f"Купить: {lot['buy_url']}")
                    remember_event(text.splitlines()[0])
                    await bot.send_message(ADMIN_ID, text)

                await asyncio.sleep(ITEM_PAUSE)
            await asyncio.sleep(POLL_SECONDS)


dp = Dispatcher()


@dp.message(Command("start", "status"))
async def cmd_status(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    lines = [f"👁 Слежу за {len(WATCHLIST)} предметами:"]
    for it in WATCHLIST:
        cond = []
        if it.get("max_float") is not None:
            cond.append(f"флоат ≤ {it['max_float']}")
        if it.get("min_float") is not None:
            cond.append(f"флоат ≥ {it['min_float']}")
        if it.get("paint_seeds"):
            cond.append(f"{len(it['paint_seeds'])} редких паттернов")
        if it.get("check_sticker_value"):
            cond.append(f"наклейки от {STICKER_MIN_PRICE:.0f}")
        lines.append(f"• {it['name']} — {'; '.join(cond) or 'наклейки/буст'}")
    if GLOBAL_STICKERS:
        lines.append(f"\n🏷 На всех лотах ищу наклейки: {', '.join(GLOBAL_STICKERS)}")
    lines.append(f"🚀 Буст: +{SPIKE_PCT}% за {SPIKE_WINDOW_MIN} мин")
    await message.answer("\n".join(lines))


@dp.message(Command("last"))
async def cmd_last(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    with db() as conn:
        rows = conn.execute(
            "SELECT ts, text FROM events ORDER BY ts DESC LIMIT 10").fetchall()
    if not rows:
        await message.answer("Событий пока не было.")
        return
    out = [time.strftime("%d.%m %H:%M", time.localtime(ts)) + " — " + txt
           for ts, txt in rows]
    await message.answer("Последние события:\n" + "\n".join(out))


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    asyncio.create_task(monitor_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
