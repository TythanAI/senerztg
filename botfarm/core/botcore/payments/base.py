"""Payment provider contract.

Every rail — YooKassa, CryptoBot, Stripe, Telegram Stars, TON — is reduced to
the same three questions: how do I bill this order, did it get paid, and what
did the webhook just tell me. Handlers only ever see this interface.
"""

from __future__ import annotations

import abc
import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any


class PaymentError(RuntimeError):
    """Provider rejected the call or is unreachable."""

    def __init__(self, message: str, *, provider: str = "", retryable: bool = False) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class InvoiceKind(str, Enum):
    URL = "url"        # send the user a pay button pointing at an external page
    NATIVE = "native"  # bot.send_invoice — Telegram Payments / Stars
    MANUAL = "manual"  # show requisites, an admin confirms by hand


@dataclass(slots=True)
class Invoice:
    """What the provider handed back when we asked to bill an order."""

    kind: InvoiceKind
    external_id: str
    url: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    expires_at: dt.datetime | None = None
    instructions: str = ""


@dataclass(slots=True)
class PaymentResult:
    """Outcome of a status check or a parsed webhook."""

    status: PaymentStatus
    external_id: str = ""
    amount: Decimal | None = None
    currency: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_paid(self) -> bool:
        return self.status is PaymentStatus.PAID


@dataclass(slots=True)
class OrderContext:
    """Everything a provider needs about the sale, with no ORM dependency."""

    order_id: int
    user_tg_id: int
    sku: str
    title: str
    description: str
    amount: Decimal
    currency: str
    return_url: str = ""
    webhook_url: str = ""
    email: str = ""
    lang: str = "ru"

    def label(self) -> str:
        return f"{self.title} · #{self.order_id}"


def to_minor_units(amount: Decimal, currency: str) -> int:
    """Money → smallest unit (kopecks/cents). Stars are already integral."""
    if currency.upper() == "XTR":
        return int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    cents = (Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def from_minor_units(value: int | str, currency: str) -> Decimal:
    if currency.upper() == "XTR":
        return Decimal(str(value))
    return (Decimal(str(value)) / 100).quantize(Decimal("0.01"))


def money(amount: Decimal) -> str:
    """Two-decimal string, the form every payment API expects."""
    return str(Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class PaymentProvider(abc.ABC):
    """Base class for all rails."""

    #: registry key, e.g. "yookassa"
    name: str = ""
    #: what the pay button says
    title: str = ""
    #: currencies this rail can settle in
    currencies: tuple[str, ...] = ()
    #: True when Telegram itself renders the invoice (no external redirect)
    native: bool = False

    def __init__(self, **options: Any) -> None:
        self.options = options

    @abc.abstractmethod
    async def create_invoice(self, ctx: OrderContext) -> Invoice:
        """Ask the provider to bill this order."""

    @abc.abstractmethod
    async def check(self, external_id: str, ctx: OrderContext | None = None) -> PaymentResult:
        """Poll the provider for the current state of a payment."""

    async def parse_webhook(
        self, body: bytes, headers: dict[str, str]
    ) -> PaymentResult | None:
        """Turn a raw webhook into a result. None means 'not for me / ignore'."""
        return None

    async def close(self) -> None:
        """Release HTTP resources."""

    def supports(self, currency: str) -> bool:
        return not self.currencies or currency.upper() in self.currencies

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} name={self.name!r}>"
