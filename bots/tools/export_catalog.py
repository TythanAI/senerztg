#!/usr/bin/env python3
"""Export a buyer-facing catalog of every bot to CATALOG.md.

Useful when selling: one document that shows a prospective buyer exactly what a
shop contains — categories, products and prices — for all bots at once.

    python tools/export_catalog.py
"""
from __future__ import annotations

import glob
import os

import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from core.config import BotConfig, load_config  # noqa: E402

TYPE_LABEL = {"digital": "цифровой", "physical": "физический"}


def _load_all() -> list[BotConfig]:
    cfgs = [load_config(p) for p in sorted(glob.glob(os.path.join(HERE, "config", "*.yaml")))]
    # Digital first, then physical; alphabetical within each group.
    return sorted(cfgs, key=lambda c: (c.fulfillment != "digital", c.slug))


def build_md(cfgs: list[BotConfig]) -> str:
    dig = sum(c.fulfillment == "digital" for c in cfgs)
    phys = len(cfgs) - dig
    out: list[str] = []
    out.append("# Каталог ботов-магазинов\n")
    out.append(
        f"_Сгенерировано автоматически (`tools/export_catalog.py`)._ "
        f"Всего магазинов: **{len(cfgs)}** — цифровых {dig}, физических {phys}.\n"
    )
    out.append("## Сводка\n")
    out.append("| # | Слаг | Магазин | Тип | Валюта | Позиций |")
    out.append("|---|------|---------|-----|--------|---------|")
    for i, c in enumerate(cfgs, 1):
        out.append(
            f"| {i} | `{c.slug}` | {c.name} | {TYPE_LABEL[c.fulfillment]} | "
            f"{c.currency} | {len(c.all_products())} |"
        )
    out.append("")
    out.append("---\n")
    for c in cfgs:
        out.append(f"## {c.name}  ·  `{c.slug}`")
        out.append(
            f"*Тип:* {TYPE_LABEL[c.fulfillment]} · *Валюта:* {c.currency}"
            + (f" · *Поддержка:* {c.support_username}" if c.support_username else "")
        )
        out.append("")
        for cat in c.catalog:
            out.append(f"**{cat.emoji} {cat.title}**")
            out.append("")
            out.append("| Товар / услуга | Цена |")
            out.append("|----------------|------|")
            for p in cat.products:
                out.append(f"| {p.title} | {p.price:.2f} {c.currency} |")
            out.append("")
        out.append("---\n")
    return "\n".join(out)


def main():
    cfgs = _load_all()
    md = build_md(cfgs)
    path = os.path.join(HERE, "CATALOG.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote {path} ({len(cfgs)} shops, {sum(len(c.all_products()) for c in cfgs)} products)")


if __name__ == "__main__":
    main()
