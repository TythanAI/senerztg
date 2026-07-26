"""aiohttp side-car: payment webhooks, health check, Prometheus-ish metrics.

Runs in the same process as the bot. One VPS hosting many bots gives each one
its own port; nginx maps `/<bot-id>/webhook/<provider>` to it.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING

from aiohttp import web

from .db import Database, Repos
from .payments import ProviderRegistry

if TYPE_CHECKING:  # pragma: no cover
    from aiogram import Bot

    from .config import NicheConfig, Secrets
    from .services import CheckoutService

log = logging.getLogger(__name__)


def build_webapp(
    *,
    config: "NicheConfig",
    secrets: "Secrets",
    db: Database,
    bot: "Bot",
    registry: ProviderRegistry,
    checkout: "CheckoutService",
) -> web.Application:
    app = web.Application()
    started = dt.datetime.now(dt.timezone.utc)

    async def health(request: web.Request) -> web.Response:
        """Used by systemd, Docker HEALTHCHECK and the fleet monitor."""
        try:
            async with db.session() as session:
                await Repos(session).users.count()
            db_ok = True
        except Exception as exc:
            log.error("health check: database unreachable: %s", exc)
            db_ok = False

        payload = {
            "status": "ok" if db_ok else "degraded",
            "bot": config.id,
            "name": config.name,
            "region": config.region,
            "version": _version(),
            "uptime_seconds": int(
                (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
            ),
            "providers": list(registry.names),
            "database": "ok" if db_ok else "error",
        }
        return web.json_response(payload, status=200 if db_ok else 503)

    async def metrics(request: web.Request) -> web.Response:
        if secrets.webhook_secret:
            if request.query.get("token") != secrets.webhook_secret:
                return web.Response(status=403, text="forbidden")

        now = dt.datetime.now(dt.timezone.utc)
        async with db.session() as session:
            repos = Repos(session)
            users = await repos.users.count()
            day_users = await repos.users.count_since(now - dt.timedelta(days=1))
            paid = await repos.orders.paid_count()
            revenue = await repos.orders.revenue()
            revenue_day = await repos.orders.revenue(now - dt.timedelta(days=1))

        bot_id = config.id
        lines = [
            "# HELP bot_users_total Registered users",
            "# TYPE bot_users_total gauge",
            f'bot_users_total{{bot="{bot_id}"}} {users}',
            "# HELP bot_users_day New users in the last 24h",
            "# TYPE bot_users_day gauge",
            f'bot_users_day{{bot="{bot_id}"}} {day_users}',
            "# HELP bot_orders_paid_total Paid orders",
            "# TYPE bot_orders_paid_total counter",
            f'bot_orders_paid_total{{bot="{bot_id}"}} {paid}',
            "# HELP bot_revenue_total Gross revenue",
            "# TYPE bot_revenue_total counter",
            f'bot_revenue_total{{bot="{bot_id}",currency="{config.currency}"}} {revenue}',
            "# HELP bot_revenue_day Revenue in the last 24h",
            "# TYPE bot_revenue_day gauge",
            f'bot_revenue_day{{bot="{bot_id}",currency="{config.currency}"}} {revenue_day}',
        ]
        return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")

    async def payment_webhook(request: web.Request) -> web.Response:
        provider_name = request.match_info["provider"]
        provider = registry.get(provider_name)
        if provider is None:
            return web.Response(status=404, text="unknown provider")

        body = await request.read()
        headers = {k.lower(): v for k, v in request.headers.items()}

        try:
            result = await provider.parse_webhook(body, headers)
        except Exception:
            log.exception("%s: webhook parsing failed", provider_name)
            # 200 keeps the provider from hammering us over a bug on our side.
            return web.Response(status=200, text="error")

        if result is None:
            return web.Response(status=200, text="ignored")

        if result.is_paid:
            async with db.session() as session:
                repos = Repos(session)
                settled = await checkout.settle_by_external(repos, bot, provider_name, result)
            if settled:
                log.info("%s: webhook settled payment %s", provider_name, result.external_id)

        return web.Response(status=200, text="ok")

    async def paid_landing(request: web.Request) -> web.Response:
        """Where card providers send the buyer back after checkout."""
        return web.Response(
            text=(
                "Оплата получена. Вернитесь в Telegram — бот уже выдал заказ."
                if config.lang == "ru"
                else "Payment received. Return to Telegram — your order has been delivered."
            ),
            content_type="text/plain",
            charset="utf-8",
        )

    app.router.add_get("/healthz", health)
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    app.router.add_post("/webhook/{provider}", payment_webhook)
    app.router.add_get("/paid", paid_landing)

    return app


async def run_webapp(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("web server listening on %s:%s", host, port)
    return runner


def _version() -> str:
    from . import __version__

    return __version__
