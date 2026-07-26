"""Shared fixtures: an in-memory database and a minimal but valid bot config."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

from botcore.config import NicheConfig, Secrets  # noqa: E402
from botcore.db import Database, Repos  # noqa: E402
from botcore.i18n import Translator  # noqa: E402


def make_config(**overrides: Any) -> NicheConfig:
    base: dict[str, Any] = {
        "id": "ru-000-test",
        "name": "ТестБот",
        "region": "ru",
        "lang": "ru",
        "currency": "RUB",
        "niche": "course/test",
        "tagline": "Тестовый бот",
        "description": "Бот для тестов",
        "modules": ["catalog", "subscription", "support", "referral", "faq"],
        "referral_percent": 20,
        "trial_days": 3,
        "payments": {
            "providers": ["cryptobot", "stars", "manual"],
            "default": "cryptobot",
            "stars_rate": "1.9",
        },
        "catalog": [
            {"sku": "start", "title": "Старт", "price": 1000, "kind": "digital",
             "delivery": {"text": "Ваши материалы"}},
            {"sku": "club", "title": "Клуб", "price": 2000, "kind": "subscription",
             "period_days": 30},
            {"sku": "call", "title": "Консультация", "price": 5000, "kind": "consult"},
        ],
        "faq": [{"q": "Вопрос?", "a": "Ответ."}],
    }
    base.update(overrides)
    return NicheConfig.from_dict(base)


@pytest.fixture
def config() -> NicheConfig:
    return make_config()


@pytest.fixture
def t(config: NicheConfig) -> Translator:
    return Translator(config.lang, config.texts)


@pytest_asyncio.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all()
    yield database
    await database.dispose()


@pytest_asyncio.fixture
async def session(db: Database):
    """A single long-lived session so in-memory SQLite keeps its schema."""
    async with db.session_factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def repos(session) -> Repos:
    return Repos(session)


@pytest.fixture
def secrets() -> Secrets:
    return Secrets(
        bot_token="123:TEST",
        admin_ids=(1,),
        db_url="sqlite+aiosqlite:///:memory:",
        cryptobot_token="cb-token",
    )


class FakeBot:
    """Records outgoing messages instead of calling Telegram."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_for: set[int] = set()

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        if chat_id in self.fail_for:
            raise RuntimeError("bot was blocked by the user")
        self.sent.append((chat_id, text))

    async def send_document(self, chat_id: int, document: Any, **kwargs: Any) -> None:
        self.sent.append((chat_id, f"<document {document}>"))

    def texts_for(self, chat_id: int) -> list[str]:
        return [text for cid, text in self.sent if cid == chat_id]


@pytest.fixture
def fake_bot() -> FakeBot:
    return FakeBot()


def money(value: str) -> Decimal:
    return Decimal(value)
