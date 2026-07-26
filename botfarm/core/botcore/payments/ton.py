"""Direct TON wallet payments, verified on-chain via tonapi.io.

The buyer sends TON with the order memo in the comment; `check()` scans recent
incoming transfers for that memo. No merchant account, no intermediary, but
also no automatic refunds — the memo is the only thing tying a transfer to an
order, so the comment is mandatory.
"""

from __future__ import annotations

import logging
from decimal import ROUND_UP, Decimal
from typing import Any
from urllib.parse import quote

from .base import (
    Invoice,
    InvoiceKind,
    OrderContext,
    PaymentError,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
)
from .http import HttpClient

log = logging.getLogger(__name__)

NANOTON = Decimal("1000000000")
#: Accept a transfer that is within 1.5% of the quoted amount — the rate moves
#: between quoting and sending, and wallets round.
TOLERANCE = Decimal("0.985")


class TonProvider(PaymentProvider):
    name = "ton"
    title = "TON (кошелёк)"
    currencies = ("RUB", "EUR", "USD")

    def __init__(
        self,
        wallet: str,
        *,
        api_key: str = "",
        api_base: str = "https://tonapi.io/v2",
        lookback: int = 50,
        **options: Any,
    ) -> None:
        super().__init__(**options)
        if not wallet:
            raise PaymentError("TON payments need TON_WALLET", provider=self.name)
        self.wallet = wallet
        self.lookback = lookback
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.http = HttpClient(api_base, headers=headers, provider=self.name)
        self._rate_cache: dict[str, tuple[float, Decimal]] = {}

    async def rate(self, currency: str) -> Decimal:
        """Currency units per 1 TON, cached for 5 minutes."""
        import time

        currency = currency.upper()
        cached = self._rate_cache.get(currency)
        now = time.time()
        if cached and now - cached[0] < 300:
            return cached[1]

        data = await self.http.get(
            "/rates", params={"tokens": "ton", "currencies": currency.lower()}
        )
        try:
            price = (data["rates"]["TON"]["prices"])[currency]
        except (KeyError, TypeError) as exc:
            raise PaymentError(f"tonapi gave no {currency} rate: {data}", provider=self.name) from exc
        value = Decimal(str(price))
        if value <= 0:
            raise PaymentError(f"tonapi returned a non-positive TON rate: {value}",
                               provider=self.name)
        self._rate_cache[currency] = (now, value)
        return value

    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        rate = await self.rate(ctx.currency)
        ton_amount = (Decimal(ctx.amount) / rate).quantize(Decimal("0.000000001"), rounding=ROUND_UP)
        memo = f"ORDER{ctx.order_id}"
        nano = int(ton_amount * NANOTON)

        url = f"ton://transfer/{self.wallet}?amount={nano}&text={quote(memo)}"
        instructions = (
            f"Отправьте <b>{ton_amount} TON</b> на адрес:\n<code>{self.wallet}</code>\n\n"
            f"Обязательно укажите комментарий:\n<code>{memo}</code>\n\n"
            "Без комментария платёж невозможно связать с заказом."
        )
        return Invoice(
            kind=InvoiceKind.URL,
            external_id=memo,
            url=url,
            payload={"ton_amount": str(ton_amount), "memo": memo, "rate": str(rate)},
            instructions=instructions,
        )

    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        """Look for an incoming transfer carrying our memo."""
        data = await self.http.get(
            f"/accounts/{self.wallet}/events", params={"limit": self.lookback}
        )
        expected_nano: int | None = None
        if ctx is not None:
            try:
                rate = await self.rate(ctx.currency)
                expected = (Decimal(ctx.amount) / rate) * TOLERANCE
                expected_nano = int(expected * NANOTON)
            except PaymentError:
                expected_nano = None

        for event in data.get("events") or []:
            for action in event.get("actions") or []:
                transfer = action.get("TonTransfer")
                if not transfer:
                    continue
                comment = (transfer.get("comment") or "").strip()
                if comment != external_id:
                    continue
                amount_nano = int(transfer.get("amount") or 0)
                if expected_nano is not None and amount_nano < expected_nano:
                    log.warning(
                        "ton: %s underpaid (%s < %s nanoton)", external_id, amount_nano, expected_nano
                    )
                    continue
                return PaymentResult(
                    status=PaymentStatus.PAID,
                    external_id=external_id,
                    amount=Decimal(amount_nano) / NANOTON,
                    currency="TON",
                    raw=event,
                )

        return PaymentResult(status=PaymentStatus.PENDING, external_id=external_id)

    async def close(self) -> None:
        await self.http.close()
