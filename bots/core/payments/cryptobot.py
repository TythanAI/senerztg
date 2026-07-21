"""Minimal async client for the CryptoBot "Crypto Pay" API.

Docs: https://help.crypt.bot/crypto-pay-api

We create fiat-denominated invoices (the customer pays the crypto equivalent)
and verify payment on demand by polling ``getInvoices`` — no public webhook
endpoint is required, which keeps deployment to "just run it on a VPS".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

log = logging.getLogger("core.cryptobot")

MAINNET = "https://pay.crypt.bot/api/"
TESTNET = "https://testnet-pay.crypt.bot/api/"


class CryptoBotError(Exception):
    pass


@dataclass
class Invoice:
    invoice_id: int
    status: str          # active | paid | expired
    pay_url: str


class CryptoBot:
    def __init__(self, token: str, testnet: bool = False, timeout: int = 20):
        self._token = token
        self._base = TESTNET if testnet else MAINNET
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={"Crypto-Pay-API-Token": self._token},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call(self, method: str, params: dict) -> dict:
        session = await self._ensure_session()
        url = self._base + method
        try:
            async with session.post(url, json=params) as resp:
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise CryptoBotError(f"network error: {exc}") from exc
        except Exception as exc:  # malformed body, etc.
            raise CryptoBotError(f"bad response: {exc}") from exc
        if not isinstance(data, dict) or not data.get("ok"):
            raise CryptoBotError(f"API error: {data}")
        return data["result"]

    async def create_invoice(
        self, amount: float, fiat: str, description: str, payload: str
    ) -> Invoice:
        result = await self._call(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": fiat,
                "amount": f"{amount:.2f}",
                "description": description[:1024],
                "payload": payload[:4096],
                "allow_comments": False,
                "allow_anonymous": True,
                "expires_in": 3600,
            },
        )
        pay_url = (
            result.get("bot_invoice_url")
            or result.get("mini_app_invoice_url")
            or result.get("web_app_invoice_url")
            or result.get("pay_url")
            or ""
        )
        return Invoice(
            invoice_id=int(result["invoice_id"]),
            status=result.get("status", "active"),
            pay_url=pay_url,
        )

    async def get_status(self, invoice_id: int) -> str:
        result = await self._call("getInvoices", {"invoice_ids": str(invoice_id)})
        items = result.get("items") or []
        if not items:
            return "unknown"
        return items[0].get("status", "unknown")
