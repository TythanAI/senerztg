"""Small logging helper so every bot logs the same way."""
from __future__ import annotations

import logging
import os
import sys


def setup_logging(name: str) -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
    # aiogram/aiohttp are chatty at DEBUG; keep them at INFO unless asked.
    if level != "DEBUG":
        logging.getLogger("aiogram").setLevel(logging.INFO)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
    return logging.getLogger(name)
