"""Auth Toolkit — TOTP two-factor, password generation and strength scoring.

Everything is stdlib `hmac`/`secrets`: no third-party crypto to audit, and
nothing sensitive is ever written to disk.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import re
import secrets
import struct
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

WORDS = (
    "anchor apple amber arrow autumn basil beacon birch bison bloom bridge cactus "
    "canyon cedar cobalt comet copper coral crimson delta dune ember falcon fern "
    "flint forest garnet glacier granite harbor hazel indigo ivory jasper juniper "
    "kelp lagoon lantern lemon lichen lotus lunar maple marble meadow mint nectar "
    "nimbus oasis onyx opal orbit otter pebble pepper pine plume quartz quill raven "
    "reef ridge river rowan saffron sage sierra silver slate solar spruce summit "
    "thistle thunder tiger topaz tundra umber valley velvet violet walnut willow "
    "winter zenith zephyr"
).split()

COMMON_PASSWORDS = {
    "password", "123456", "123456789", "qwerty", "abc123", "111111", "letmein",
    "monkey", "dragon", "iloveyou", "admin", "welcome", "login", "master",
    "qwerty123", "password1", "123123", "sunshine", "princess", "football",
}


class TotpNewRequest(BaseModel):
    issuer: str = Field("MyApp", max_length=64)
    account: str = Field(..., max_length=128, description="Usually the user's email")
    digits: int = Field(6, ge=6, le=8)
    period: int = Field(30, ge=15, le=120)


class TotpVerifyRequest(BaseModel):
    secret: str = Field(..., description="Base32 secret from /totp/new")
    code: str = Field(..., max_length=8)
    digits: int = Field(6, ge=6, le=8)
    period: int = Field(30, ge=15, le=120)
    window: int = Field(1, ge=0, le=10, description="How many steps of clock drift to accept")


class PasswordRequest(BaseModel):
    count: int = Field(1, ge=1, le=100)
    length: int = Field(20, ge=8, le=128)
    style: str = Field("random", description="'random' or 'passphrase'")
    words: int = Field(4, ge=3, le=10, description="Passphrase length in words")
    symbols: bool = True
    digits: bool = True


class StrengthRequest(BaseModel):
    password: str = Field(..., max_length=256)


def _totp_at(secret: str, counter: int, digits: int) -> str:
    try:
        key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    except Exception as exc:
        raise HTTPException(400, "secret is not valid base32") from exc
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def _strength(password: str) -> dict:
    """Entropy-based scoring — length beats character-class theatre."""
    pool = 0
    if re.search(r"[a-z]", password):
        pool += 26
    if re.search(r"[A-Z]", password):
        pool += 26
    if re.search(r"\d", password):
        pool += 10
    if re.search(r"[^\w\s]", password):
        pool += 33
    if re.search(r"\s", password):
        pool += 1

    entropy = len(password) * math.log2(pool) if pool else 0.0
    lowered = password.lower()

    penalties = []
    if lowered in COMMON_PASSWORDS:
        entropy = min(entropy, 8.0)
        penalties.append("This is one of the most common passwords in existence")
    if re.search(r"(.)\1{2,}", password):
        entropy -= 6
        penalties.append("Contains a character repeated three or more times")
    if re.search(r"(?:012|123|234|345|456|567|678|789|abc|qwe|asd)", lowered):
        entropy -= 8
        penalties.append("Contains a keyboard or numeric sequence")

    entropy = max(0.0, entropy)
    if entropy < 28:
        verdict, crackable = "very weak", "instantly"
    elif entropy < 36:
        verdict, crackable = "weak", "minutes"
    elif entropy < 60:
        verdict, crackable = "reasonable", "months"
    elif entropy < 80:
        verdict, crackable = "strong", "centuries"
    else:
        verdict, crackable = "very strong", "longer than the age of the universe"

    return {
        "length": len(password),
        "character_pool": pool,
        "entropy_bits": round(entropy, 1),
        "verdict": verdict,
        "offline_crack_estimate": crackable,
        "warnings": penalties,
        "score": min(4, int(entropy // 20)),
    }


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/totp/new")
    async def totp_new(request: Request, body: TotpNewRequest) -> dict:
        """Create a TOTP secret plus the otpauth:// URI for the QR code."""
        await request.app.state.require_key(request)
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        uri = (
            f"otpauth://totp/{quote(body.issuer)}:{quote(body.account)}"
            f"?secret={secret}&issuer={quote(body.issuer)}"
            f"&digits={body.digits}&period={body.period}"
        )
        return {
            "secret": secret,
            "otpauth_uri": uri,
            "digits": body.digits,
            "period": body.period,
            "current_code": _totp_at(secret, int(time.time()) // body.period, body.digits),
        }

    @router.post("/totp/verify")
    async def totp_verify(request: Request, body: TotpVerifyRequest) -> dict:
        """Check a six-digit code, tolerating clock drift."""
        await request.app.state.require_key(request)
        code = body.code.strip().replace(" ", "")
        if not code.isdigit():
            return {"valid": False, "reason": "code must be numeric"}

        counter = int(time.time()) // body.period
        for offset in range(-body.window, body.window + 1):
            candidate = _totp_at(body.secret, counter + offset, body.digits)
            # Constant-time: a timing oracle here leaks the valid code.
            if hmac.compare_digest(candidate, code):
                return {"valid": True, "drift_steps": offset}
        return {"valid": False, "reason": "code does not match within the accepted window"}

    @router.post("/password/generate")
    async def generate(request: Request, body: PasswordRequest) -> dict:
        """Generate cryptographically random passwords or passphrases."""
        await request.app.state.require_key(request)
        results = []

        for _ in range(body.count):
            if body.style == "passphrase":
                parts = [secrets.choice(WORDS) for _ in range(body.words)]
                password = "-".join(parts)
                if body.digits:
                    password += f"-{secrets.randbelow(9000) + 1000}"
            elif body.style == "random":
                alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                if body.digits:
                    alphabet += "0123456789"
                if body.symbols:
                    alphabet += "!@#$%^&*()-_=+[]{};:,.?"
                password = "".join(secrets.choice(alphabet) for _ in range(body.length))
            else:
                raise HTTPException(400, "style must be 'random' or 'passphrase'")

            results.append({"password": password, **_strength(password)})

        return {"count": len(results), "passwords": results}

    @router.post("/password/strength")
    async def strength(request: Request, body: StrengthRequest) -> dict:
        """Score a password. It is never logged or stored."""
        await request.app.state.require_key(request)
        return _strength(body.password)

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="authkit",
        title="Auth Toolkit API",
        tagline="TOTP two-factor and password hygiene, without pulling in a crypto library.",
        summary="Generate and verify TOTP codes, create strong passwords, score password strength by entropy.",
        router=build_router(),
        endpoints=[
            ("POST /v1/totp/new", "Create a TOTP secret and otpauth URI"),
            ("POST /v1/totp/verify", "Verify a code with drift tolerance"),
            ("POST /v1/password/generate", "Random passwords or passphrases"),
            ("POST /v1/password/strength", "Entropy-based strength scoring"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/totp/new \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"issuer":"Acme","account":"user@acme.io"}\''
        ),
    )
