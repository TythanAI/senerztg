"""Money Toolkit — VAT maths, IBAN and card validation, invoice numbering.

Billing code that gets these wrong costs real money, and every one of them is
a closed-form check that needs no external service.
"""

from __future__ import annotations

import datetime as dt
import re
import string
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

# Standard VAT rates, in percent. Reduced rates vary far too much per product
# category to encode here — this covers the standard rate only.
VAT_RATES = {
    "AT": 20, "BE": 21, "BG": 20, "HR": 25, "CY": 19, "CZ": 21, "DK": 25,
    "EE": 22, "FI": 25.5, "FR": 20, "DE": 19, "GR": 24, "HU": 27, "IE": 23,
    "IT": 22, "LV": 21, "LT": 21, "LU": 17, "MT": 18, "NL": 21, "PL": 23,
    "PT": 23, "RO": 21, "SK": 23, "SI": 22, "ES": 21, "SE": 25,
    "GB": 20, "NO": 25, "CH": 8.1, "RU": 20, "UA": 20, "TR": 20,
}

# IBAN length per country — the first structural check any validator must do.
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27,
    "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MT": 31, "NL": 18, "NO": 15,
    "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
    "TR": 26, "UA": 29, "RS": 22, "GE": 22, "KZ": 20, "MD": 24,
}

CARD_BRANDS = (
    ("Visa", re.compile(r"^4\d{12}(\d{3})?(\d{3})?$")),
    ("Mastercard", re.compile(r"^(5[1-5]\d{14}|2(2[2-9]\d{12}|[3-6]\d{13}|7[01]\d{12}|720\d{12}))$")),
    ("American Express", re.compile(r"^3[47]\d{13}$")),
    ("Mir", re.compile(r"^220[0-4]\d{12}$")),
    ("Discover", re.compile(r"^6(?:011|5\d{2})\d{12}$")),
    ("JCB", re.compile(r"^(?:2131|1800|35\d{3})\d{11}$")),
    ("UnionPay", re.compile(r"^62\d{14,17}$")),
    ("Diners Club", re.compile(r"^3(?:0[0-5]|[68]\d)\d{11}$")),
)


class VatRequest(BaseModel):
    amount: float = Field(..., ge=0)
    country: str = Field(..., min_length=2, max_length=2, description="ISO-3166 alpha-2")
    rate: float = Field(-1, description="Override the standard rate; -1 uses the country's")
    amount_includes_vat: bool = Field(False, description="True when `amount` is gross")


class IbanRequest(BaseModel):
    iban: str = Field(..., max_length=42)


class CardRequest(BaseModel):
    number: str = Field(..., max_length=25)


class InvoiceNumberRequest(BaseModel):
    prefix: str = Field("INV", max_length=12)
    sequence: int = Field(..., ge=1, le=99_999_999)
    pattern: str = Field(
        "{prefix}-{year}-{seq:05d}",
        description="Placeholders: prefix, year, month, day, seq",
    )
    date: str = Field("", description="ISO date; defaults to today (UTC)")


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/money/vat")
    async def vat(request: Request, body: VatRequest) -> dict:
        """Split a price into net, VAT and gross — either direction."""
        await request.app.state.require_key(request)
        country = body.country.upper()

        if body.rate >= 0:
            rate = Decimal(str(body.rate))
        elif country in VAT_RATES:
            rate = Decimal(str(VAT_RATES[country]))
        else:
            raise HTTPException(
                400, f"No standard VAT rate on file for {country!r} — pass `rate` explicitly"
            )

        try:
            amount = Decimal(str(body.amount))
        except InvalidOperation:
            raise HTTPException(400, "amount is not a number") from None

        multiplier = Decimal(1) + rate / Decimal(100)
        if body.amount_includes_vat:
            gross = amount
            net = amount / multiplier
        else:
            net = amount
            gross = amount * multiplier

        return {
            "country": country,
            "rate_percent": float(rate),
            "net": _money(net),
            "vat": _money(gross - net),
            "gross": _money(gross),
            "note": "Standard rate only — reduced rates depend on the product category.",
        }

    @router.get("/money/vat-rates")
    async def vat_rates(request: Request) -> dict:
        """The standard VAT rate table this service uses."""
        await request.app.state.require_key(request)
        return {"count": len(VAT_RATES), "rates": VAT_RATES}

    @router.post("/money/iban")
    async def iban(request: Request, body: IbanRequest) -> dict:
        """Validate an IBAN by structure and ISO 7064 mod-97 checksum."""
        await request.app.state.require_key(request)
        raw = re.sub(r"[\s-]", "", body.iban).upper()

        result: dict = {"iban": raw, "valid": False, "country": raw[:2] if len(raw) >= 2 else ""}

        if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]+$", raw):
            result["error"] = "An IBAN is two letters, two check digits, then alphanumerics"
            return result

        country = raw[:2]
        expected = IBAN_LENGTHS.get(country)
        if expected is None:
            result["error"] = f"Unknown IBAN country code {country!r}"
            return result
        if len(raw) != expected:
            result["error"] = f"{country} IBANs are {expected} characters, got {len(raw)}"
            result["expected_length"] = expected
            return result

        # mod-97: move the first four chars to the end, letters → numbers.
        rearranged = raw[4:] + raw[:4]
        digits = "".join(
            str(ord(c) - 55) if c in string.ascii_uppercase else c for c in rearranged
        )
        checksum = int(digits) % 97

        result["valid"] = checksum == 1
        result["length"] = len(raw)
        result["bank_code"] = raw[4:12]
        result["formatted"] = " ".join(raw[i : i + 4] for i in range(0, len(raw), 4))
        if not result["valid"]:
            result["error"] = "Checksum failed — this IBAN contains a typo"
        return result

    @router.post("/money/card")
    async def card(request: Request, body: CardRequest) -> dict:
        """Luhn check and brand detection. The number is never stored."""
        await request.app.state.require_key(request)
        digits = re.sub(r"[\s-]", "", body.number)

        if not digits.isdigit():
            raise HTTPException(400, "Card number must contain only digits, spaces or dashes")
        if not 12 <= len(digits) <= 19:
            return {"valid": False, "error": "A card number is 12-19 digits", "length": len(digits)}

        # Luhn: double every second digit from the right, subtract 9 if over 9.
        total = 0
        for index, char in enumerate(reversed(digits)):
            value = int(char)
            if index % 2 == 1:
                value *= 2
                if value > 9:
                    value -= 9
            total += value

        brand = next((name for name, pattern in CARD_BRANDS if pattern.match(digits)), "Unknown")
        return {
            "valid": total % 10 == 0,
            "brand": brand,
            "length": len(digits),
            "masked": f"{digits[:6]}{'*' * (len(digits) - 10)}{digits[-4:]}",
            "bin": digits[:6],
            "last4": digits[-4:],
        }

    @router.post("/money/invoice-number")
    async def invoice_number(request: Request, body: InvoiceNumberRequest) -> dict:
        """Format a sequential invoice number from a pattern."""
        await request.app.state.require_key(request)
        if body.date:
            try:
                when = dt.date.fromisoformat(body.date)
            except ValueError:
                raise HTTPException(400, "date must be ISO-8601 (YYYY-MM-DD)") from None
        else:
            when = dt.datetime.now(dt.timezone.utc).date()

        try:
            number = body.pattern.format(
                prefix=body.prefix,
                year=when.year,
                month=f"{when.month:02d}",
                day=f"{when.day:02d}",
                seq=body.sequence,
            )
        except (KeyError, ValueError, IndexError) as exc:
            raise HTTPException(
                400, f"Bad pattern: {exc}. Use prefix, year, month, day, seq."
            ) from exc

        return {"invoice_number": number, "sequence": body.sequence, "date": when.isoformat()}

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="moneykit",
        title="Money Toolkit API",
        tagline="VAT maths, IBAN and card checks — the billing details that cost you when wrong.",
        summary="Compute VAT both directions, validate IBANs by mod-97, Luhn-check cards, format invoice numbers.",
        router=build_router(),
        endpoints=[
            ("POST /v1/money/vat", "Net ⇄ gross VAT split"),
            ("GET /v1/money/vat-rates", "Standard VAT rate table"),
            ("POST /v1/money/iban", "IBAN structure and checksum"),
            ("POST /v1/money/card", "Luhn check and brand detection"),
            ("POST /v1/money/invoice-number", "Sequential invoice numbering"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/money/vat \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"amount":100,"country":"DE"}\'   # → net 100, vat 19, gross 119'
        ),
    )
