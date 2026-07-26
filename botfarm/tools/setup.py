#!/usr/bin/env python3
"""Interactive launch wizard — from a dormant bot to a selling one.

    python tools/setup.py ru-201-steam

Asks for the few things only you can supply, and — this is the point —
**checks each one against the real API before writing it down**. A wrong
token or a revoked key is caught here, not by a customer.

Non-interactive use (for scripting a batch):

    python tools/setup.py ru-201-steam --token 123:ABC --admin 555 --yes
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

TIMEOUT = 15
OK, BAD, WARN, INFO = "✅", "❌", "⚠️ ", "  "


def http_json(url: str, *, headers: dict[str, str] | None = None,
              data: bytes | None = None) -> tuple[int, Any]:
    """Small JSON fetch that never raises — returns (status, parsed-or-text)."""
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except (urllib.error.URLError, ssl.SSLError, OSError, TimeoutError) as exc:
        return 0, str(exc)


# ------------------------------------------------------------------- checks


def check_bot_token(token: str) -> tuple[bool, str]:
    if not re.match(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$", token.strip()):
        return False, "не похоже на токен — должен быть вида 1234567890:AA..."
    status, body = http_json(f"https://api.telegram.org/bot{token.strip()}/getMe")
    if status == 0:
        return False, f"нет связи с Telegram: {body}"
    if isinstance(body, dict) and body.get("ok"):
        me = body["result"]
        return True, f"@{me.get('username')} ({me.get('first_name')})"
    detail = body.get("description") if isinstance(body, dict) else body
    return False, f"Telegram отклонил токен: {detail}"


def check_admin_ids(raw: str) -> tuple[bool, str]:
    ids = [chunk.strip() for chunk in raw.replace(";", ",").split(",") if chunk.strip()]
    if not ids:
        return False, "нужен хотя бы один ID"
    for value in ids:
        if not value.lstrip("-").isdigit():
            return False, f"{value!r} — не число. ID узнаётся у @userinfobot"
    return True, f"{len(ids)} админ(ов)"


def check_cryptobot(token: str) -> tuple[bool, str]:
    status, body = http_json(
        "https://pay.crypt.bot/api/getMe", headers={"Crypto-Pay-API-Token": token.strip()}
    )
    if status == 0:
        return False, f"нет связи с Crypto Pay: {body}"
    if isinstance(body, dict) and body.get("ok"):
        app = body.get("result", {})
        return True, f"приложение «{app.get('name', '?')}»"
    error = body.get("error") if isinstance(body, dict) else body
    return False, f"Crypto Pay отклонил токен: {error}"


def check_yookassa(shop_id: str, secret: str) -> tuple[bool, str]:
    import base64

    auth = base64.b64encode(f"{shop_id.strip()}:{secret.strip()}".encode()).decode()
    # /me is a read-only endpoint, so this validates without side effects.
    status, body = http_json(
        "https://api.yookassa.ru/v3/me", headers={"Authorization": f"Basic {auth}"}
    )
    if status == 0:
        return False, f"нет связи с YooKassa: {body}"
    if status == 200 and isinstance(body, dict):
        return True, f"магазин {body.get('account_id', shop_id)} · {body.get('status', '')}"
    if status == 401:
        return False, "YooKassa: неверный shopId или секретный ключ"
    return False, f"YooKassa вернула {status}: {str(body)[:120]}"


def check_stripe(secret_key: str) -> tuple[bool, str]:
    status, body = http_json(
        "https://api.stripe.com/v1/balance",
        headers={"Authorization": f"Bearer {secret_key.strip()}"},
    )
    if status == 0:
        return False, f"нет связи со Stripe: {body}"
    if status == 200:
        return True, "ключ принят"
    detail = body.get("error", {}).get("message") if isinstance(body, dict) else body
    return False, f"Stripe отклонил ключ: {detail}"


# --------------------------------------------------------------------- flow


def ask(prompt: str, *, default: str = "", secret: bool = False,
        allow_empty: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"{prompt}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nОтменено.")
            raise SystemExit(1)
        value = value or default
        if value or allow_empty:
            return value
        print("  Нужно значение (или Ctrl+C для отмены).")


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "д", "да"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bot_id")
    parser.add_argument("--token", default="", help="BOT_TOKEN (иначе спросит)")
    parser.add_argument("--admin", default="", help="ADMIN_IDS (иначе спросит)")
    parser.add_argument("--cryptobot", default="")
    parser.add_argument("--webhook-base", default="")
    parser.add_argument("--yes", action="store_true", help="не задавать лишних вопросов")
    parser.add_argument("--force", action="store_true", help="перезаписать существующий .env")
    args = parser.parse_args()

    from fleet import _find, _set_env  # noqa: E402  (same tools/ directory)
    from botcore.config import NicheConfig  # noqa: E402

    row = _find(args.bot_id)
    directory = ROOT / row["path"]
    env_path = directory / ".env"
    config = NicheConfig.load(directory / "config.yaml")

    print(f"\n=== {config.name} ({row['id']}) ===")
    print(f"{INFO}Модель: {row['archetype']} · регион: {row['region']} · порт: {row['port']}")
    print(f"{INFO}Товаров в каталоге: {len(config.catalog)}")

    if env_path.exists() and not args.force:
        print(f"\n{BAD} {env_path} уже существует. Запустите с --force, чтобы перезаписать.")
        return 1

    values: dict[str, str] = {}

    # --- Telegram -----------------------------------------------------------
    print("\n1. Токен бота — @BotFather → /newbot")
    while True:
        token = args.token or ask("   BOT_TOKEN")
        ok, detail = check_bot_token(token)
        print(f"   {OK if ok else BAD} {detail}")
        if ok:
            values["BOT_TOKEN"] = token.strip()
            break
        if args.token:
            return 1
    bot_username = detail.split()[0].lstrip("@").rstrip(")")

    print("\n2. Ваш Telegram ID — @userinfobot пришлёт его")
    while True:
        admin = args.admin or ask("   ADMIN_IDS")
        ok, detail = check_admin_ids(admin)
        print(f"   {OK if ok else BAD} {detail}")
        if ok:
            values["ADMIN_IDS"] = admin.strip()
            break
        if args.admin:
            return 1

    # --- Payments -----------------------------------------------------------
    print("\n3. Приём оплаты — нужен минимум один способ")
    rails = list(config.payments.providers)
    connected: list[str] = []

    if "cryptobot" in rails:
        print(f"\n{INFO}Crypto Pay (@CryptoBot → Crypto Pay → Create App)")
        print(f"{INFO}Быстрее всего: 5 минут, юрлицо не нужно.")
        token = args.cryptobot or (
            "" if args.yes else ask("   CRYPTOBOT_TOKEN (Enter — пропустить)", allow_empty=True)
        )
        if token:
            ok, detail = check_cryptobot(token)
            print(f"   {OK if ok else BAD} {detail}")
            if ok:
                values["CRYPTOBOT_TOKEN"] = token.strip()
                connected.append("cryptobot")

    if "yookassa" in rails and not args.yes:
        print(f"\n{INFO}YooKassa — карты и СБП. Нужны ИП/ООО.")
        shop = ask("   YOOKASSA_SHOP_ID (Enter — пропустить)", allow_empty=True)
        if shop:
            secret = ask("   YOOKASSA_SECRET_KEY")
            ok, detail = check_yookassa(shop, secret)
            print(f"   {OK if ok else BAD} {detail}")
            if ok:
                values["YOOKASSA_SHOP_ID"] = shop.strip()
                values["YOOKASSA_SECRET_KEY"] = secret.strip()
                connected += ["yookassa", "sbp"]

    if "stripe" in rails and not args.yes:
        print(f"\n{INFO}Stripe — карты для EU/USA. Нужна компания.")
        key = ask("   STRIPE_SECRET_KEY (Enter — пропустить)", allow_empty=True)
        if key:
            ok, detail = check_stripe(key)
            print(f"   {OK if ok else BAD} {detail}")
            if ok:
                values["STRIPE_SECRET_KEY"] = key.strip()
                connected.append("stripe")

    if "stars" in rails:
        connected.append("stars")
        print(f"\n   {OK} Telegram Stars — работают без настройки")

    if not connected:
        print(f"\n{WARN}Ни один способ оплаты не подключён. Бот запустится, "
              f"но продавать не сможет.")
        if not args.yes and not ask_yes("   Всё равно продолжить?", default=False):
            return 1

    # --- Write --------------------------------------------------------------
    body = (directory / ".env.example").read_text(encoding="utf-8")
    for key, value in values.items():
        body = _set_env(body, key, value)
    if args.webhook_base:
        body = _set_env(body, "WEBHOOK_BASE", args.webhook_base.rstrip("/"))

    import secrets as _secrets

    body = _set_env(body, "WEBHOOK_SECRET", _secrets.token_hex(16))

    env_path.write_text(body, encoding="utf-8")
    env_path.chmod(0o600)
    print(f"\n{OK} Записан {env_path}")

    # --- What is still missing ---------------------------------------------
    sellable = config.active_products()
    blocked = config.blocked_products()

    print(f"\n=== Готовность ===")
    print(f"{OK if sellable else WARN}К продаже: {len(sellable)} из {len(config.catalog)}")
    print(f"{OK if connected else BAD}Оплата: {', '.join(connected) or 'не подключена'}")

    todo: list[str] = []
    if blocked:
        todo.append(
            f"Заполнить выдачу у {len(blocked)} товаров в config.yaml "
            f"({', '.join(p.sku for p in blocked[:4])}) — сейчас они скрыты"
        )
    if config.has_placeholder_support():
        todo.append("Указать support_username в config.yaml")
    if config.has("stock"):
        todo.append(
            f"Загрузить товар: python tools/fleet.py stock {row['id']} "
            f"{next((p.sku for p in config.catalog if p.kind == 'account'), 'SKU')} файл.txt"
        )
    if not config.manual_requisites() and "manual" in rails:
        todo.append("Вписать manual_requisites в config.yaml (или не использовать этот способ)")

    if todo:
        print("\nОсталось сделать:")
        for item in todo:
            print(f"  • {item}")
    else:
        print(f"\n{OK} Всё готово — бот можно запускать и продавать.")

    print("\nЗапуск:")
    print(f"  cd {directory} && python bot.py")
    print(f"  sudo cp {directory}/*.service /etc/systemd/system/ && "
          f"sudo systemctl enable --now {row['unit']}")
    if bot_username and bot_username != "?":
        print(f"\nБот: https://t.me/{bot_username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
