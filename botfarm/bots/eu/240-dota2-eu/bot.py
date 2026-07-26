#!/usr/bin/env python3
"""Dota 2 Accounts — Dota 2 accounts — instant delivery, warranty included

Run locally:   python bot.py
Run as a unit: systemctl start botfarm-eu-240-dota2-eu
"""

import sys
from pathlib import Path

# The shared engine lives in botfarm/core and is not installed system-wide.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core"))

from botcore.app import run

if __name__ == "__main__":
    run(Path(__file__).parent)
