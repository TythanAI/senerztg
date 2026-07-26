#!/usr/bin/env python3
"""Run the Mini App server.

    export BOT_TOKEN=123456:AA...      # the bot the apps are attached to
    python serve.py                    # http://localhost:8100

The token is required: it is the key used to verify that a request really
comes from Telegram. Without it every API call is rejected, by design.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from miniapps.core.server import available_apps, create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8100")))
    parser.add_argument("--list", action="store_true", help="list apps and exit")
    args = parser.parse_args()

    if args.list:
        print(f"{'SLUG':<12} TITLE")
        print("-" * 60)
        for app in available_apps():
            print(f"{app['slug']:<12} {app['title']}")
        print(f"\n{len(available_apps())} apps")
        return 0

    if not os.getenv("BOT_TOKEN"):
        print(
            "BOT_TOKEN is not set. The server would reject every request, "
            "because initData can only be verified with the bot's own token.\n"
            "  export BOT_TOKEN=123456:AA...",
            file=sys.stderr,
        )
        return 2

    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port,
                log_level=os.getenv("LOG_LEVEL", "info").lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
