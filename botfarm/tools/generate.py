#!/usr/bin/env python3
"""Expand the niche catalogue into 1000 deployable bots.

    python tools/generate.py            # write everything
    python tools/generate.py --check    # validate without writing

Every bot gets its own directory with config.yaml, bot.py, .env.example,
README, Dockerfile, compose file and systemd unit. The generator is
idempotent: re-running it reproduces the tree byte for byte.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from archetypes import (  # noqa: E402
    MODULES,
    REFERRAL,
    TRIAL_DAYS,
    build_catalog,
    build_faq,
    build_quiz,
)
from niches import eu_entries, ru_entries  # noqa: E402
from niches_shop import eu_shop_entries, ru_shop_entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOTS = ROOT / "bots"

#: Bots whose topic touches crypto also accept TON directly.
CRYPTO_HINTS = (
    "crypt", "крипт", "ton", "nft", "defi", "airdrop", "web3", "mining",
    "майнинг", "btc", "altcoin", "альт", "stable", "стейбл", "solidity", "p2p",
)

STARS_RATE = {"RUB": "1.9", "EUR": "0.019", "USD": "0.02"}
#: Telegram's per-invoice ceiling; a tier above this cannot be sold in Stars.
MAX_STARS = 2500

# The first web port of the fleet. Each bot gets the next one.
BASE_PORT = 9000


def payment_plan(entry: dict, catalog: list[dict]) -> dict[str, Any]:
    """Pick the rails for one bot, based on region, topic and price point."""
    currency = entry["currency"]
    rate = Decimal(STARS_RATE[currency])
    top_price = max((Decimal(str(p["price"])) for p in catalog), default=Decimal("0"))

    if entry["region"] == "ru":
        providers = ["yookassa", "sbp", "cryptobot"]
        default = "yookassa"
    else:
        providers = ["stripe", "cryptobot"]
        default = "stripe"

    # Stars only where the most expensive tier still fits in one invoice.
    if top_price > 0 and int(top_price / rate) <= MAX_STARS:
        providers.append("stars")

    haystack = f"{entry['slug']} {entry['topic']}".lower()
    if any(hint in haystack for hint in CRYPTO_HINTS):
        providers.append("ton")

    # A manual rail keeps the shop selling when an acquirer is not connected.
    providers.append("manual")

    return {
        "providers": providers,
        "default": default,
        "stars_rate": STARS_RATE[currency],
        "crypto_assets": ["USDT", "TON", "BTC"],
        "invoice_ttl_minutes": 60,
    }


def build_config(entry: dict, index: int) -> dict[str, Any]:
    archetype = entry["archetype"]
    catalog = build_catalog(entry)
    modules = list(MODULES[archetype])

    # Only offer a quiz when we actually authored questions for it.
    quiz = build_quiz(entry)
    if not quiz and "quiz" in modules:
        modules.remove("quiz")

    config: dict[str, Any] = {
        "id": f"{entry['region']}-{index:03d}-{entry['slug']}",
        "name": entry["name"],
        "region": entry["region"],
        "lang": entry["lang"],
        "currency": entry["currency"],
        "niche": f"{archetype}/{entry['slug']}",
        "tagline": entry["tagline"],
        "description": _description(entry),
        "price_tier": entry["tier"],
        "modules": modules,
        "referral_percent": REFERRAL[archetype],
        "trial_days": TRIAL_DAYS.get(archetype, 0),
        "support_username": "@REPLACE_WITH_YOUR_SUPPORT",
        "payments": payment_plan(entry, catalog),
        "catalog": catalog,
        "faq": build_faq(entry),
        "texts": _texts(entry),
    }
    if quiz:
        config["quiz"] = quiz
    if entry["region"] == "ru":
        # The REPLACE marker is load-bearing: the engine disables the manual
        # rail while it is present, so a buyer can never be shown fake details.
        config["manual_requisites"] = (
            "Карта: <code>0000 0000 0000 0000</code> (REPLACE — впишите свои реквизиты)\n"
            "Получатель: REPLACE"
        )
    else:
        config["manual_requisites"] = (
            "IBAN: <code>DE00 0000 0000 0000 0000 00</code> (REPLACE with your own)\n"
            "Beneficiary: REPLACE"
        )
    return config


def _description(entry: dict) -> str:
    lang = entry["lang"]
    topic = entry["topic"]
    if lang == "ru":
        return (
            f"{entry['name']} — бот по теме «{topic}». Каталог с тарифами, приём оплаты "
            f"картой, через СБП и криптовалютой, автоматическая выдача после оплаты, "
            f"партнёрская программа и админ-панель с аналитикой."
        )
    if lang == "de":
        return (
            f"{entry['name']} — Bot rund um {topic}. Katalog mit Tarifen, Zahlung per "
            f"Karte und Krypto, automatische Auslieferung, Partnerprogramm und Admin-Panel."
        )
    if lang == "es":
        return (
            f"{entry['name']} — bot sobre {topic}. Catálogo con tarifas, pago con tarjeta "
            f"y cripto, entrega automática, programa de afiliados y panel de administración."
        )
    return (
        f"{entry['name']} — a {topic} bot. Tiered catalog, card and crypto checkout, "
        f"automatic delivery, an affiliate programme and an admin panel with analytics."
    )


def _texts(entry: dict) -> dict[str, str]:
    """Per-bot copy overrides layered on top of the language pack."""
    lang = entry["lang"]
    name, tagline, topic = entry["name"], entry["tagline"], entry["topic"]

    if lang == "ru":
        return {
            "start.welcome": (
                f"<b>{name}</b>\n\n{tagline}\n\n"
                f"Здесь всё по теме «{topic}»: тарифы, ответы на частые вопросы "
                f"и поддержка. Выберите раздел 👇"
            ),
            "reviews": (
                "<b>Отзывы</b>\n\n"
                "«Окупилось с первой недели» — Алексей\n"
                "«Наконец-то без воды, только по делу» — Марина\n"
                "«Поддержка отвечает быстро» — Дмитрий\n\n"
                "<i>Замените этот блок реальными отзывами ваших клиентов.</i>"
            ),
            "content": (
                f"<b>Материалы по теме «{topic}»</b>\n\n"
                "Здесь публикуются бесплатные разборы и полезные подборки.\n\n"
                "<i>Замените текст своими материалами.</i>"
            ),
        }
    if lang == "de":
        return {
            "start.welcome": f"<b>{name}</b>\n\n{tagline}\n\nWählen Sie einen Bereich 👇",
            "reviews": (
                "<b>Bewertungen</b>\n\n«Hat sich sofort gelohnt» — Thomas\n"
                "«Endlich ohne Geschwafel» — Julia\n\n"
                "<i>Ersetzen Sie diesen Block durch echte Kundenstimmen.</i>"
            ),
        }
    if lang == "es":
        return {
            "start.welcome": f"<b>{name}</b>\n\n{tagline}\n\nElige una sección 👇",
            "reviews": (
                "<b>Reseñas</b>\n\n«Se amortizó en una semana» — Carlos\n"
                "«Por fin algo directo al grano» — Lucía\n\n"
                "<i>Sustituye este bloque por reseñas reales.</i>"
            ),
        }
    return {
        "start.welcome": (
            f"<b>{name}</b>\n\n{tagline}\n\n"
            f"Everything about {topic} in one place: plans, answers and support. "
            f"Pick a section 👇"
        ),
        "reviews": (
            "<b>Reviews</b>\n\n"
            "“Paid for itself in the first week” — Alex\n"
            "“Finally, no fluff” — Marina\n"
            "“Support actually replies” — Daniel\n\n"
            "<i>Replace this block with real customer reviews.</i>"
        ),
        "content": (
            f"<b>Free {topic} material</b>\n\n"
            "Breakdowns and resources are posted here.\n\n"
            "<i>Replace with your own content.</i>"
        ),
    }


# --------------------------------------------------------------- file bodies

BOT_PY = '''#!/usr/bin/env python3
"""{name} — {tagline}

Run locally:   python bot.py
Run as a unit: systemctl start {unit}
"""

import sys
from pathlib import Path

# The shared engine lives in botfarm/core and is not installed system-wide.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core"))

from botcore.app import run

if __name__ == "__main__":
    run(Path(__file__).parent)
'''

ENV_EXAMPLE = """# {name} ({bot_id})
# Copy to .env and fill in. Never commit .env.

# --- Telegram ---------------------------------------------------------------
BOT_TOKEN=
# Your Telegram user id(s), comma separated. Get it from @userinfobot.
ADMIN_IDS=

# --- Storage ----------------------------------------------------------------
# SQLite is fine up to a few thousand users. For more, point at Postgres:
# DB_URL=postgresql+asyncpg://user:password@localhost/{db_name}
DB_URL=sqlite+aiosqlite:///bot.db

{payment_env}
# --- Web side-car (health checks, payment webhooks) -------------------------
WEB_HOST=0.0.0.0
WEB_PORT={port}
# Public HTTPS base for this bot, e.g. https://pay.example.com/{bot_id}
WEBHOOK_BASE=
# Random string; protects /metrics. Generate: openssl rand -hex 16
WEBHOOK_SECRET=

LOG_LEVEL=INFO
"""

PAYMENT_ENV_BLOCKS = {
    "yookassa": """# --- YooKassa (cards + SBP, RU) ---------------------------------------------
# From https://yookassa.ru/my → Settings → Shop
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
""",
    "stripe": """# --- Stripe (cards, Apple/Google Pay, EU/US) --------------------------------
# From https://dashboard.stripe.com/apikeys
STRIPE_SECRET_KEY=
# From the webhook endpoint you create for {webhook_path}
STRIPE_WEBHOOK_SECRET=
""",
    "cryptobot": """# --- Crypto Pay (@CryptoBot) ------------------------------------------------
# Open @CryptoBot → Crypto Pay → Create App
CRYPTOBOT_TOKEN=
""",
    "ton": """# --- TON direct -------------------------------------------------------------
TON_WALLET=
# Optional, raises tonapi.io rate limits: https://tonconsole.com
TONAPI_KEY=
""",
    "telegram_native": """# --- Telegram Payments ------------------------------------------------------
# @BotFather → your bot → Payments → connect an acquirer
TELEGRAM_PROVIDER_TOKEN=
""",
}

DOCKERFILE = """# {name} ({bot_id})
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY core/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY bots/{region}/{dirname}/ ./bot/

ENV PYTHONPATH=/app/core
WORKDIR /app/bot

RUN useradd --create-home --uid 10001 botuser && chown -R botuser:botuser /app
USER botuser

EXPOSE {port}
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \\
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:{port}/healthz', timeout=4).status==200 else 1)"

CMD ["python", "bot.py"]
"""

COMPOSE = """# Build from the botfarm root:  docker compose -f bots/{region}/{dirname}/docker-compose.yml up -d
services:
  {service}:
    build:
      context: ../../..
      dockerfile: bots/{region}/{dirname}/Dockerfile
    container_name: {service}
    restart: unless-stopped
    env_file: .env
    ports:
      - "{port}:{port}"
    volumes:
      - ./data:/app/bot/data
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
"""

SYSTEMD = """[Unit]
Description={name} ({bot_id})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botfarm
WorkingDirectory=/opt/botfarm/bots/{region}/{dirname}
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/botfarm/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier={unit}

# Hardening — the bot only needs its own directory.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/botfarm/bots/{region}/{dirname}
MemoryMax=384M

[Install]
WantedBy=multi-user.target
"""


def render_readme(config: dict, entry: dict, port: int, dirname: str) -> str:
    rows = []
    for product in config["catalog"]:
        kind = product["kind"]
        if product["period_days"]:
            kind = f"{kind} · {product['period_days']} дн."
        rows.append(
            f"| `{product['sku']}` | {product['title']} | "
            f"{_fmt(product['price'], config['currency'])} | {kind} |"
        )
    products = "\n".join(rows)
    rails = ", ".join(config["payments"]["providers"])
    return f"""# {config['name']}

> {config['tagline']}

**ID:** `{config['id']}` · **Регион:** {config['region'].upper()} · **Язык:** {config['lang']} ·
**Модель:** {entry['archetype']} · **Тариф цен:** {config['price_tier']}

{config['description']}

## Что уже готово

- Каталог из {len(config['catalog'])} тарифов с автоматической выдачей после оплаты
- Приём оплаты: {rails}
- Партнёрская программа {config['referral_percent']}%{' · пробный период ' + str(config['trial_days']) + ' дн.' if config['trial_days'] else ''}
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ ({len(config['faq'])} вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту {port}

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
{products}

## Запуск за 5 минут

```bash
cp .env.example .env
nano .env                     # BOT_TOKEN и ADMIN_IDS — обязательны
pip install -r ../../../core/requirements.txt
python bot.py
```

Через Docker:

```bash
cd ../../..                   # botfarm/
docker compose -f bots/{config['region']}/{dirname}/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp {dirname}.service /etc/systemd/system/
sudo systemctl enable --now {dirname}
```

## Что заменить перед продажей

1. `.env` — токен бота от @BotFather и ваши `ADMIN_IDS`
2. `config.yaml` → `support_username` — контакт поддержки
3. `config.yaml` → `catalog[].delivery` — ссылки на реальные материалы,
   инвайты в закрытый канал, ссылку на запись
4. `config.yaml` → `manual_requisites` — ваши платёжные реквизиты
5. `texts.reviews` — реальные отзывы вместо примеров
6. Ключи платёжных систем в `.env`

Пока ключи не заданы, соответствующий способ оплаты просто не показывается —
бот остаётся рабочим.
"""


def _fmt(price: float, currency: str) -> str:
    symbol = {"RUB": "₽", "EUR": "€", "USD": "$"}.get(currency, currency)
    value = Decimal(str(price))
    body = f"{int(value):,}".replace(",", " ") if value == value.to_integral_value() else f"{value}"
    return f"{body} {symbol}"


def payment_env_block(providers: list[str], webhook_path: str) -> str:
    blocks = []
    seen = set()
    for provider in providers:
        # yookassa and sbp share one credential pair.
        key = "yookassa" if provider == "sbp" else provider
        if key in seen or key not in PAYMENT_ENV_BLOCKS:
            continue
        seen.add(key)
        blocks.append(PAYMENT_ENV_BLOCKS[key].format(webhook_path=webhook_path))
    return "\n".join(blocks)


def write_bot(entry: dict, index: int, port: int, *, check_only: bool) -> dict:
    config = build_config(entry, index)
    dirname = f"{index:03d}-{entry['slug']}"
    target = BOTS / entry["region"] / dirname
    # Built from the directory name, which is unique by construction —
    # a slug alone is not, and a shared unit name breaks both deployments.
    unit = f"botfarm-{entry['region']}-{dirname}"

    # Validate through the real loader before anything touches disk.
    from botcore.config import NicheConfig

    NicheConfig.from_dict(json.loads(json.dumps(config)))

    if check_only:
        return _summary(config, entry, port, dirname, unit)

    target.mkdir(parents=True, exist_ok=True)
    (target / "config.yaml").write_text(
        "# Generated by tools/generate.py — edit freely, it is your product.\n"
        + yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    (target / "bot.py").write_text(
        BOT_PY.format(name=config["name"], tagline=config["tagline"], unit=unit),
        encoding="utf-8",
    )
    (target / ".env.example").write_text(
        ENV_EXAMPLE.format(
            name=config["name"],
            bot_id=config["id"],
            db_name=entry["slug"].replace("-", "_"),
            port=port,
            payment_env=payment_env_block(
                config["payments"]["providers"], f"/{config['id']}/webhook/stripe"
            ),
        ),
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        render_readme(config, entry, port, dirname), encoding="utf-8"
    )
    (target / "Dockerfile").write_text(
        DOCKERFILE.format(
            name=config["name"],
            bot_id=config["id"],
            region=entry["region"],
            dirname=dirname,
            port=port,
        ),
        encoding="utf-8",
    )
    (target / "docker-compose.yml").write_text(
        COMPOSE.format(region=entry["region"], dirname=dirname, service=unit, port=port),
        encoding="utf-8",
    )
    (target / f"{dirname}.service").write_text(
        SYSTEMD.format(
            name=config["name"],
            bot_id=config["id"],
            region=entry["region"],
            dirname=dirname,
            unit=unit,
        ),
        encoding="utf-8",
    )
    (target / ".gitignore").write_text(".env\n*.db\ndata/\n", encoding="utf-8")

    return _summary(config, entry, port, dirname, unit)


def _summary(config: dict, entry: dict, port: int, dirname: str, unit: str) -> dict:
    prices = [Decimal(str(p["price"])) for p in config["catalog"]]
    return {
        "id": config["id"],
        "name": config["name"],
        "slug": entry["slug"],
        "region": config["region"],
        "lang": config["lang"],
        "currency": config["currency"],
        "archetype": entry["archetype"],
        "tier": config["price_tier"],
        "topic": entry["topic"],
        "tagline": config["tagline"],
        "path": f"bots/{config['region']}/{dirname}",
        "unit": unit,
        "port": port,
        "modules": config["modules"],
        "providers": config["payments"]["providers"],
        "products": len(config["catalog"]),
        "price_min": float(min(prices)),
        "price_max": float(max(prices)),
        "referral_percent": config["referral_percent"],
        "trial_days": config["trial_days"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument("--clean", action="store_true", help="remove bots/ first")
    args = parser.parse_args()

    if args.clean and BOTS.exists() and not args.check:
        shutil.rmtree(BOTS)

    # Order matters: the original 300 keep their numbering, the shop
    # niches are appended after them.
    entries = (
        ru_entries() + ru_shop_entries() + eu_entries() + eu_shop_entries()
    )
    index: list[dict] = []
    port = BASE_PORT

    ru_index = eu_index = 0
    for entry in entries:
        if entry["region"] == "ru":
            ru_index += 1
            number = ru_index
        else:
            eu_index += 1
            number = eu_index
        index.append(write_bot(entry, number, port, check_only=args.check))
        port += 1

    if args.check:
        print(f"✓ {len(index)} bot configurations are valid")
        return 0

    _write_fleet_files(index)
    ru_count = sum(1 for b in index if b["region"] == "ru")
    print(f"✓ generated {len(index)} bots ({ru_count} RU, {len(index) - ru_count} EU/US)")
    print(f"  → {BOTS}")
    return 0


def _write_fleet_files(index: list[dict]) -> None:
    (BOTS / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    with (docs / "pricelist.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "id", "name", "region", "lang", "currency", "archetype", "tier",
                "topic", "products", "price_min", "price_max", "providers",
                "referral_percent", "port", "path",
            ],
        )
        writer.writeheader()
        for bot in index:
            row = {k: bot[k] for k in writer.fieldnames if k in bot}
            row["providers"] = "|".join(bot["providers"])
            writer.writerow(row)

    lines = [
        "# Каталог ботов",
        "",
        f"Всего: **{len(index)}** ботов — "
        f"{sum(1 for b in index if b['region'] == 'ru')} для RU, "
        f"{sum(1 for b in index if b['region'] == 'eu')} для EU/USA.",
        "",
    ]
    for region, title in (("ru", "RU-сегмент"), ("eu", "EU/USA-сегмент")):
        subset = [b for b in index if b["region"] == region]
        lines += [f"## {title} ({len(subset)})", ""]
        lines += ["| # | Бот | Тема | Модель | Цены | Оплата |", "|---|-----|------|--------|------|--------|"]
        for bot in subset:
            rails = ", ".join(bot["providers"][:3])
            lines.append(
                f"| {bot['id'].split('-')[1]} | **{bot['name']}** | {bot['topic']} | "
                f"{bot['archetype']} | {_fmt(bot['price_min'], bot['currency'])}–"
                f"{_fmt(bot['price_max'], bot['currency'])} | {rails} |"
            )
        lines.append("")
    (docs / "CATALOG.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
