#!/usr/bin/env python3
"""Аудит Рекламы — Находим слив бюджета за час

Run locally:   python bot.py
Run as a unit: systemctl start botfarm-ru-ads-audit
"""

import sys
from pathlib import Path

# The shared engine lives in botfarm/core and is not installed system-wide.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core"))

from botcore.app import run

if __name__ == "__main__":
    run(Path(__file__).parent)
