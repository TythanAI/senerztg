"""Bootstrap: turn a config.yaml + .env into a running bot.

Every bot's `bot.py` is three lines that call `run()`.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientError

from .config import ConfigError, NicheConfig, Secrets
from .db import Database
from .handlers import build_router
from .i18n import Translator
from .keyboards import MenuCB  # noqa: F401 - ensures the factory is registered
from .middlewares import (
    ContextMiddleware,
    DatabaseMiddleware,
    ErrorShieldMiddleware,
    ThrottleMiddleware,
    UserMiddleware,
)
from .payments import build_registry
from .services import BackgroundJobs, CheckoutService, DeliveryService
from .webapp import build_webapp, run_webapp

log = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # aiogram's per-update INFO lines drown out everything else in production.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


class BotApp:
    """Wires the whole thing together and owns its lifecycle."""

    def __init__(self, config: NicheConfig, secrets: Secrets, base_dir: Path) -> None:
        self.config = config
        self.secrets = secrets
        self.base_dir = base_dir

        self.t = Translator(config.lang, config.texts)
        self.db = Database(secrets.db_url)
        self.bot = Bot(
            token=secrets.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.registry = build_registry(config, secrets)
        self.delivery = DeliveryService(
            config,
            self.t,
            assets_dir=str(base_dir / "assets"),
            admin_ids=secrets.admin_ids,
        )
        self.checkout = CheckoutService(
            config, self.registry, self.delivery, admin_ids=secrets.admin_ids
        )
        self.dp = Dispatcher(storage=MemoryStorage())
        self.jobs: BackgroundJobs | None = None
        self._runner = None
        self._install_middlewares()

    def _install_middlewares(self) -> None:
        dp = self.dp
        context = ContextMiddleware(
            config=self.config,
            t=self.t,
            registry=self.registry,
            checkout=self.checkout,
            delivery=self.delivery,
            admin_ids=self.secrets.admin_ids,
            bot_username="",  # filled in once we know it
        )
        self._context = context

        dp.update.outer_middleware(ErrorShieldMiddleware(self.secrets.admin_ids))
        dp.update.outer_middleware(context)
        dp.update.outer_middleware(DatabaseMiddleware(self.db))
        dp.update.outer_middleware(UserMiddleware(self.secrets.admin_ids, self.config.lang))

        throttle = ThrottleMiddleware()
        dp.message.middleware(throttle)
        dp.callback_query.middleware(throttle)
        self._throttle = throttle

    async def start(self) -> None:
        if not self.secrets.bot_token:
            raise ConfigError(
                "BOT_TOKEN is not set. Copy .env.example to .env and paste the "
                "token from @BotFather."
            )

        await self.db.create_all()

        try:
            me = await self.bot.get_me()
        except TelegramUnauthorizedError as exc:
            raise ConfigError(
                "Telegram rejected BOT_TOKEN. Check the token in .env against "
                "@BotFather — it must look like 1234567890:AA...."
            ) from exc
        except (TelegramNetworkError, ClientError, asyncio.TimeoutError, OSError) as exc:
            raise ConfigError(
                f"Cannot reach api.telegram.org ({exc}). Check the VPS network, "
                "DNS, and whether outbound HTTPS is blocked."
            ) from exc

        self._context.context["bot_username"] = me.username or ""
        self.checkout.bot_username = me.username or ""
        log.info(
            "starting %s (@%s) — region=%s lang=%s providers=%s",
            self.config.id,
            me.username,
            self.config.region,
            self.config.lang,
            ", ".join(self.registry.names) or "none",
        )

        missing = self.secrets.missing_for(self.config.payments.providers)
        if missing:
            log.warning(
                "these payment providers have no credentials and are disabled: %s",
                ", ".join(missing),
            )

        self.dp.include_router(build_router(self.config.modules))

        self.jobs = BackgroundJobs(self.db, self.bot, self.checkout, self.config, self.t)
        self.jobs.start()

        if self.secrets.webhook_base or self.secrets.web_port:
            app = build_webapp(
                config=self.config,
                secrets=self.secrets,
                db=self.db,
                bot=self.bot,
                registry=self.registry,
                checkout=self.checkout,
            )
            self._runner = await run_webapp(
                app, self.secrets.web_host, self.secrets.web_port
            )

        for admin_id in self.secrets.admin_ids:
            try:
                await self.bot.send_message(
                    admin_id,
                    f"✅ <b>{self.config.name}</b> запущен\n"
                    f"Способы оплаты: {', '.join(self.registry.names) or '—'}\n"
                    f"Команда панели: /admin",
                )
            except Exception:  # pragma: no cover
                log.info("could not greet admin %s", admin_id)

    async def run_polling(self) -> None:
        await self.bot.delete_webhook(drop_pending_updates=True)
        await self.dp.start_polling(self.bot, allowed_updates=self.dp.resolve_used_update_types())

    async def stop(self) -> None:
        log.info("shutting down %s", self.config.id)
        if self.jobs is not None:
            await self.jobs.stop()
        if self._runner is not None:
            await self._runner.cleanup()
        await self.registry.close()
        await self.bot.session.close()
        await self.db.dispose()


def load(base_dir: str | Path) -> tuple[NicheConfig, Secrets, Path]:
    """Read config.yaml next to the bot and the env that was loaded for it."""
    base = Path(base_dir).resolve()
    if base.is_file():
        base = base.parent

    env_file = base / ".env"
    if env_file.exists():
        _load_dotenv(env_file)

    config = NicheConfig.load(base / "config.yaml")
    secrets = Secrets.from_env()

    if secrets.db_url.startswith("sqlite") and "///" in secrets.db_url:
        # Keep each bot's database beside its own code, not in the CWD.
        prefix, _, tail = secrets.db_url.partition("///")
        if not tail.startswith("/"):
            secrets.db_url = f"{prefix}///{base / tail}"

    return config, secrets, base


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader — no dependency, no surprises with quoting."""
    import os

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def run(base_dir: str | Path) -> None:
    """Entry point used by every bot's `bot.py`."""
    config, secrets, base = load(base_dir)
    setup_logging(secrets.log_level)

    app = BotApp(config, secrets, base)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        stopping = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stopping.set)
            except NotImplementedError:  # pragma: no cover - Windows
                pass

        try:
            await app.start()
            polling = asyncio.create_task(app.run_polling())
            stop_wait = asyncio.create_task(stopping.wait())
            done, pending = await asyncio.wait(
                {polling, stop_wait}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc
        finally:
            # Always release the HTTP sessions, even when startup failed.
            await app.stop()

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("interrupted")
    except ConfigError as exc:
        log.error("configuration error: %s", exc)
        raise SystemExit(2) from exc
