"""Configuration model + loader.

A bot is fully described by a YAML file (catalog, texts, which payment
methods are on) plus a handful of secrets read **only** from the
environment (bot token, payment provider tokens, admin ids). Secrets never
live in the repository.
"""
from __future__ import annotations

import os
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class ProductCfg(BaseModel):
    sku: str
    title: str
    price: float
    description: str = ""
    # Optional hard cap; digital stock is otherwise tracked in the DB.
    max_per_order: int = 10

    @field_validator("price")
    @classmethod
    def _price_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("price must be >= 0")
        return round(float(v), 2)

    @field_validator("sku")
    @classmethod
    def _sku_clean(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 64:
            raise ValueError("sku must be 1..64 chars")
        return v


class CategoryCfg(BaseModel):
    id: str
    title: str
    emoji: str = "📦"
    products: List[ProductCfg] = Field(default_factory=list)


class PaymentsCfg(BaseModel):
    telegram_enabled: bool = False
    telegram_provider_token_env: str = "PROVIDER_TOKEN"
    cryptobot_enabled: bool = False
    cryptobot_token_env: str = "CRYPTOBOT_TOKEN"
    cryptobot_testnet: bool = False
    # Cash / pay-on-delivery, only meaningful for physical fulfilment.
    cod_enabled: bool = False


class BotConfig(BaseModel):
    name: str
    slug: str
    token_env: str = "BOT_TOKEN"
    admin_env: str = "ADMIN_IDS"
    admins: List[int] = Field(default_factory=list)

    support_username: str = ""
    currency: str = "USD"
    language: Literal["ru", "en"] = "ru"
    fulfillment: Literal["digital", "physical"] = "digital"

    welcome: str = ""
    rules: str = ""
    delivery_note: str = ""

    # Notifications about new/paid orders go here (channel or group id, or an
    # admin's private chat). Falls back to every admin id when empty.
    orders_chat_env: str = "ORDERS_CHAT_ID"

    payments: PaymentsCfg = Field(default_factory=PaymentsCfg)
    catalog: List[CategoryCfg] = Field(default_factory=list)

    # ----- runtime-resolved (from env), never stored in YAML -----
    @property
    def bot_token(self) -> str:
        token = os.getenv(self.token_env, "").strip()
        return token

    @property
    def provider_token(self) -> str:
        return os.getenv(self.payments.telegram_provider_token_env, "").strip()

    @property
    def cryptobot_token(self) -> str:
        return os.getenv(self.payments.cryptobot_token_env, "").strip()

    @property
    def orders_chat_id(self) -> Optional[int]:
        raw = os.getenv(self.orders_chat_env, "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def resolved_admins(self) -> List[int]:
        """Admins from YAML plus a comma-separated env override."""
        admins = list(self.admins)
        raw = os.getenv(self.admin_env, "").strip()
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                admins.append(int(part))
        # Stable, de-duplicated.
        seen: set[int] = set()
        out: List[int] = []
        for a in admins:
            if a not in seen:
                seen.add(a)
                out.append(a)
        return out

    def all_products(self) -> List[ProductCfg]:
        return [p for c in self.catalog for p in c.products]

    def find_product(self, sku: str) -> Optional[ProductCfg]:
        for p in self.all_products():
            if p.sku == sku:
                return p
        return None

    def category(self, cid: str) -> Optional[CategoryCfg]:
        for c in self.catalog:
            if c.id == cid:
                return c
        return None

    def validate_semantics(self) -> None:
        """Cheap sanity checks that pydantic can't express alone."""
        skus = [p.sku for p in self.all_products()]
        dupes = {s for s in skus if skus.count(s) > 1}
        if dupes:
            raise ValueError(f"duplicate SKUs in catalog: {sorted(dupes)}")
        cat_ids = [c.id for c in self.catalog]
        dupe_cats = {c for c in cat_ids if cat_ids.count(c) > 1}
        if dupe_cats:
            raise ValueError(f"duplicate category ids: {sorted(dupe_cats)}")
        p = self.payments
        if not (p.telegram_enabled or p.cryptobot_enabled or p.cod_enabled):
            raise ValueError("at least one payment method must be enabled")
        if p.cod_enabled and self.fulfillment != "physical":
            raise ValueError("cash-on-delivery only makes sense for physical bots")


def load_config(path: str) -> BotConfig:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cfg = BotConfig(**raw)
    cfg.validate_semantics()
    return cfg
