#!/usr/bin/env python3
"""Run one service from the rack.

    python serve.py qr                 # http://localhost:8000
    python serve.py colorkit --port 8010
    python serve.py --list

Each service is an independent product: its own port, its own SQLite file, its
own API keys. Sell one, sell all thirteen, or run them yourself.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: name → (module, default port). Ports are contiguous so nginx config is trivial.
SERVICES: dict[str, tuple[str, int]] = {
    "qr":        ("services.qr", 8001),
    "ogimage":   ("services.ogimage", 8002),
    "imgtool":   ("services.imgtool", 8003),
    "shortlink": ("services.shortlink", 8004),
    "mailcheck": ("services.mailcheck", 8005),
    "authkit":   ("services.authkit", 8006),
    "textkit":   ("services.textkit", 8007),
    "devkit":    ("services.devkit", 8008),
    "datakit":   ("services.datakit", 8009),
    "colorkit":  ("services.colorkit", 8010),
    "geokit":    ("services.geokit", 8011),
    "moneykit":  ("services.moneykit", 8012),
    "timekit":   ("services.timekit", 8013),
}


def load_spec(name: str):
    if name not in SERVICES:
        raise SystemExit(
            f"Unknown service {name!r}. Available: {', '.join(sorted(SERVICES))}"
        )
    module = importlib.import_module(SERVICES[name][0])
    return module.spec()


def build(name: str):
    """Build the FastAPI app for one service (used by uvicorn and the tests)."""
    from saascore.app import create_app
    from saascore.store import Store

    spec = load_spec(name)
    store = Store(os.getenv("SAAS_DB", str(HERE / "data" / f"{name}.db")))
    app = create_app(spec, store=store)

    # The shortlink redirect must live at the root, outside /v1.
    if name == "shortlink":
        from services.shortlink import build_public_router

        app.include_router(build_public_router())

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("service", nargs="?", help="which service to run")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--list", action="store_true", help="list services and exit")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    if args.list or not args.service:
        print(f"{'SERVICE':<12} {'PORT':<6} TITLE")
        print("-" * 68)
        for name, (_, port) in sorted(SERVICES.items(), key=lambda kv: kv[1][1]):
            print(f"{name:<12} {port:<6} {load_spec(name).title}")
        print(f"\n{len(SERVICES)} services")
        return 0

    (HERE / "data").mkdir(exist_ok=True)
    port = args.port or int(os.getenv("PORT", "0")) or SERVICES[args.service][1]

    import uvicorn

    uvicorn.run(
        build(args.service),
        host=args.host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
