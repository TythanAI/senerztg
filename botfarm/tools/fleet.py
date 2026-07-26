#!/usr/bin/env python3
"""Fleet manager — operate 300 bots from one command.

    python tools/fleet.py list --region ru --archetype course
    python tools/fleet.py show ru-001-invest-start
    python tools/fleet.py activate ru-001-invest-start --token 123:ABC --admin 555
    python tools/fleet.py status
    python tools/fleet.py doctor
    python tools/fleet.py systemd ru-001-invest-start
    python tools/fleet.py compose --region ru --limit 20 > docker-compose.ru.yml

`activate` is the one that matters commercially: it turns a dormant bot into a
running product by writing its .env, and it refuses to overwrite an existing one.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BOTS = ROOT / "bots"
INDEX = BOTS / "index.json"

sys.path.insert(0, str(ROOT / "core"))


def load_index() -> list[dict[str, Any]]:
    if not INDEX.exists():
        sys.exit("bots/index.json is missing — run: python tools/generate.py")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def select(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    out = rows
    if getattr(args, "region", None):
        out = [r for r in out if r["region"] == args.region]
    if getattr(args, "archetype", None):
        out = [r for r in out if r["archetype"] == args.archetype]
    if getattr(args, "tier", None):
        out = [r for r in out if r["tier"] == args.tier]
    if getattr(args, "lang", None):
        out = [r for r in out if r["lang"] == args.lang]
    if getattr(args, "grep", None):
        needle = args.grep.lower()
        out = [
            r
            for r in out
            if needle in r["name"].lower()
            or needle in r["topic"].lower()
            or needle in r["id"].lower()
        ]
    if getattr(args, "limit", None):
        out = out[: args.limit]
    return out


# ------------------------------------------------------------------ commands


def cmd_list(args: argparse.Namespace) -> int:
    rows = select(load_index(), args)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print(f"{'ID':<28} {'NAME':<26} {'MODEL':<9} {'PRICES':>16}  PAYMENTS")
    print("-" * 110)
    for row in rows:
        symbol = {"RUB": "₽", "EUR": "€", "USD": "$"}.get(row["currency"], "")
        prices = f"{row['price_min']:.0f}–{row['price_max']:.0f}{symbol}"
        rails = ",".join(row["providers"][:4])
        print(f"{row['id']:<28} {row['name'][:25]:<26} {row['archetype']:<9} {prices:>16}  {rails}")
    print(f"\n{len(rows)} bots")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    row = _find(args.bot_id)
    directory = ROOT / row["path"]
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print(f"\nDirectory: {directory}")
    print(f"Activated: {'yes' if (directory / '.env').exists() else 'no'}")
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    """Write a bot's .env so it can actually start."""
    row = _find(args.bot_id)
    directory = ROOT / row["path"]
    env_path = directory / ".env"

    if env_path.exists() and not args.force:
        print(f"{env_path} already exists — pass --force to overwrite", file=sys.stderr)
        return 1

    body = (directory / ".env.example").read_text(encoding="utf-8")
    body = _set_env(body, "BOT_TOKEN", args.token)
    body = _set_env(body, "ADMIN_IDS", args.admin)
    if args.webhook_base:
        body = _set_env(body, "WEBHOOK_BASE", args.webhook_base.rstrip("/"))
    if args.db_url:
        body = _set_env(body, "DB_URL", args.db_url)

    import secrets as _secrets

    body = _set_env(body, "WEBHOOK_SECRET", _secrets.token_hex(16))

    env_path.write_text(body, encoding="utf-8")
    env_path.chmod(0o600)

    print(f"✓ activated {row['id']}")
    print(f"  {env_path}")
    print(f"  port {row['port']} · rails: {', '.join(row['providers'])}")
    print("\nNext:")
    print(f"  cd {directory} && python bot.py")
    print(f"  # or: sudo cp {directory}/*.service /etc/systemd/system/ && "
          f"sudo systemctl enable --now {row['unit']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Which bots are activated, and are the running ones healthy?"""
    rows = select(load_index(), args)
    activated = ready = 0

    for row in rows:
        directory = ROOT / row["path"]
        has_env = (directory / ".env").exists()
        if not has_env:
            continue
        activated += 1
        health = _probe(f"http://127.0.0.1:{row['port']}/healthz") if args.probe else None
        mark = {"ok": "🟢", "degraded": "🟡", None: "⚪️"}.get(health, "🔴")
        if health == "ok":
            ready += 1
        print(f"{mark} {row['id']:<28} port {row['port']}  {row['name']}")

    print(f"\n{activated}/{len(rows)} activated" + (f", {ready} healthy" if args.probe else ""))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Pre-flight check before handing a bot to a buyer."""
    from botcore.config import ConfigError, NicheConfig

    rows = select(load_index(), args)
    problems: list[str] = []

    for row in rows:
        directory = ROOT / row["path"]
        try:
            config = NicheConfig.load(directory / "config.yaml")
        except ConfigError as exc:
            problems.append(f"{row['id']}: {exc}")
            continue

        for product in config.catalog:
            for value in _delivery_values(product.delivery):
                if "REPLACE" in value:
                    problems.append(
                        f"{row['id']}/{product.sku}: delivery still has a placeholder"
                    )
                    break

        if "REPLACE" in config.support_username:
            problems.append(f"{row['id']}: support_username is still a placeholder")

        env = directory / ".env"
        if env.exists():
            text = env.read_text(encoding="utf-8")
            if not _env_value(text, "BOT_TOKEN"):
                problems.append(f"{row['id']}: .env exists but BOT_TOKEN is empty")
            if not _env_value(text, "ADMIN_IDS"):
                problems.append(f"{row['id']}: .env exists but ADMIN_IDS is empty")

    if not problems:
        print(f"✓ {len(rows)} bots checked, nothing blocking")
        return 0

    print(f"⚠️  {len(problems)} issue(s) across {len(rows)} bots:\n")
    for line in problems[: args.max_issues]:
        print(f"  · {line}")
    if len(problems) > args.max_issues:
        print(f"  … and {len(problems) - args.max_issues} more")
    print(
        "\nPlaceholders are expected on a dormant bot — replace them "
        "when you sell it (see docs/HANDOVER.md)."
    )
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    """Emit one compose file covering a slice of the fleet."""
    rows = select(load_index(), args)
    lines = [
        "# Generated by tools/fleet.py compose — run from the botfarm root.",
        "services:",
    ]
    for row in rows:
        lines += [
            f"  {row['unit']}:",
            "    build:",
            "      context: .",
            f"      dockerfile: {row['path']}/Dockerfile",
            f"    container_name: {row['unit']}",
            "    restart: unless-stopped",
            f"    env_file: {row['path']}/.env",
            "    ports:",
            f'      - "{row["port"]}:{row["port"]}"',
            "    volumes:",
            f"      - ./{row['path']}/data:/app/bot/data",
            "    logging:",
            "      driver: json-file",
            "      options:",
            '        max-size: "10m"',
            '        max-file: "3"',
            "",
        ]
    print("\n".join(lines))
    return 0


def cmd_systemd(args: argparse.Namespace) -> int:
    row = _find(args.bot_id)
    unit = next((ROOT / row["path"]).glob("*.service"))
    print(unit.read_text(encoding="utf-8"))
    return 0


def cmd_nginx(args: argparse.Namespace) -> int:
    """One server block routing /<bot-id>/ to each bot's side-car."""
    rows = select(load_index(), args)
    body = [
        "# Generated by tools/fleet.py nginx",
        "server {",
        "    listen 443 ssl http2;",
        f"    server_name {args.domain};",
        "",
        f"    ssl_certificate     /etc/letsencrypt/live/{args.domain}/fullchain.pem;",
        f"    ssl_certificate_key /etc/letsencrypt/live/{args.domain}/privkey.pem;",
        "",
        "    client_max_body_size 1m;",
        "",
    ]
    for row in rows:
        body += [
            f"    # {row['name']}",
            f"    location /{row['id']}/ {{",
            f"        proxy_pass http://127.0.0.1:{row['port']}/;",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }",
            "",
        ]
    body.append("}")
    print("\n".join(body))
    return 0


def cmd_ports(args: argparse.Namespace) -> int:
    rows = load_index()
    used = sorted(r["port"] for r in rows)
    print(f"ports {used[0]}–{used[-1]} ({len(used)} bots)")
    clashes = [p for p in used if used.count(p) > 1]
    print("clashes:", sorted(set(clashes)) or "none")
    return 0


# ------------------------------------------------------------------- helpers


def _find(bot_id: str) -> dict:
    rows = load_index()
    for row in rows:
        if row["id"] == bot_id or row["path"].endswith(bot_id):
            return row
    matches = [r for r in rows if bot_id in r["id"]]
    if len(matches) == 1:
        return matches[0]
    if matches:
        sys.exit(f"{bot_id!r} is ambiguous: {', '.join(r['id'] for r in matches[:5])}")
    sys.exit(f"no bot matches {bot_id!r}")


def _set_env(body: str, key: str, value: str) -> str:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            return "\n".join(lines) + "\n"
    lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _env_value(body: str, key: str) -> str:
    for line in body.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _delivery_values(delivery: dict) -> list[str]:
    out: list[str] = []
    for value in delivery.values():
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, (list, tuple)):
            out.extend(str(v) for v in value)
    return out


def _probe(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read()).get("status", "ok")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_filters(p: argparse.ArgumentParser) -> None:
        p.add_argument("--region", choices=["ru", "eu"])
        p.add_argument("--archetype")
        p.add_argument("--tier", choices=["budget", "standard", "premium", "elite"])
        p.add_argument("--lang")
        p.add_argument("--grep", help="substring of name, topic or id")
        p.add_argument("--limit", type=int)

    p_list = sub.add_parser("list", help="list bots")
    add_filters(p_list)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="show one bot")
    p_show.add_argument("bot_id")
    p_show.set_defaults(func=cmd_show)

    p_act = sub.add_parser("activate", help="write .env for one bot")
    p_act.add_argument("bot_id")
    p_act.add_argument("--token", required=True, help="BOT_TOKEN from @BotFather")
    p_act.add_argument("--admin", required=True, help="your Telegram id(s), comma separated")
    p_act.add_argument("--webhook-base", default="")
    p_act.add_argument("--db-url", default="")
    p_act.add_argument("--force", action="store_true")
    p_act.set_defaults(func=cmd_activate)

    p_status = sub.add_parser("status", help="which bots are activated / healthy")
    add_filters(p_status)
    p_status.add_argument("--probe", action="store_true", help="call each /healthz")
    p_status.set_defaults(func=cmd_status)

    p_doc = sub.add_parser("doctor", help="pre-sale checks")
    add_filters(p_doc)
    p_doc.add_argument("--max-issues", type=int, default=25)
    p_doc.set_defaults(func=cmd_doctor)

    p_comp = sub.add_parser("compose", help="emit a docker compose file")
    add_filters(p_comp)
    p_comp.set_defaults(func=cmd_compose)

    p_sys = sub.add_parser("systemd", help="print a systemd unit")
    p_sys.add_argument("bot_id")
    p_sys.set_defaults(func=cmd_systemd)

    p_ngx = sub.add_parser("nginx", help="emit an nginx server block")
    add_filters(p_ngx)
    p_ngx.add_argument("--domain", default="bots.example.com")
    p_ngx.set_defaults(func=cmd_nginx)

    p_ports = sub.add_parser("ports", help="port allocation summary")
    p_ports.set_defaults(func=cmd_ports)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
