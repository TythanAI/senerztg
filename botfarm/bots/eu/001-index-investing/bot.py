#!/usr/bin/env python3
"""Index Investing 101 — Build a lazy portfolio that beats most funds

Run locally:   python bot.py
Run as a unit: systemctl start botfarm-eu-index-investing
"""

import sys
from pathlib import Path

# The shared engine lives in botfarm/core and is not installed system-wide.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core"))

from botcore.app import run

if __name__ == "__main__":
    run(Path(__file__).parent)
