"""Dev Toolkit — IDs, hashing, JWT inspection and cron scheduling.

The four things every backend needs and nobody wants to reimplement.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac as hmac_mod
import json
import re
import secrets
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

NANOID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # ULID alphabet: no I, L, O, U
HASH_ALGOS = ("md5", "sha1", "sha256", "sha384", "sha512", "blake2b", "blake2s", "sha3_256")


class IdRequest(BaseModel):
    kind: str = Field("uuid4", description="uuid4, uuid7, ulid or nanoid")
    count: int = Field(1, ge=1, le=1000)
    size: int = Field(21, ge=6, le=64, description="nanoid length")


class HashRequest(BaseModel):
    text: str = Field(..., max_length=1_000_000)
    algorithm: str = Field("sha256", description=f"One of: {', '.join(HASH_ALGOS)}")
    hmac_key: str = Field("", description="When set, computes an HMAC instead of a plain digest")
    encoding: str = Field("hex", description="hex or base64")


class JwtRequest(BaseModel):
    token: str = Field(..., max_length=8192)
    secret: str = Field("", description="HMAC secret; when set the signature is verified")


class CronRequest(BaseModel):
    expression: str = Field(..., max_length=120, description="Standard 5-field cron")
    count: int = Field(5, ge=1, le=50)
    start: str = Field("", description="ISO-8601 start time; defaults to now (UTC)")


_uuid7_lock = threading.Lock()
_uuid7_state = {"ms": 0, "counter": 0}
_UUID7_COUNTER_MAX = 0xFFF  # rand_a is 12 bits


def _uuid7() -> str:
    """Time-ordered UUID (RFC 9562) — index-friendly, unlike uuid4.

    The 12-bit `rand_a` field is used as a monotonic counter within a single
    millisecond, which is what makes a batch minted in the same tick sort
    correctly. Without it, UUIDv7 only orders across millisecond boundaries
    and loses the property it exists for.
    """
    with _uuid7_lock:
        ms = int(time.time() * 1000)
        if ms == _uuid7_state["ms"]:
            _uuid7_state["counter"] += 1
            if _uuid7_state["counter"] > _UUID7_COUNTER_MAX:
                # 4096 IDs in one millisecond: roll into the next tick.
                while ms <= _uuid7_state["ms"]:
                    ms = int(time.time() * 1000)
                _uuid7_state["ms"] = ms
                _uuid7_state["counter"] = 0
        elif ms > _uuid7_state["ms"]:
            _uuid7_state["ms"] = ms
            _uuid7_state["counter"] = 0
        else:
            # Clock stepped backwards; keep issuing ordered IDs anyway.
            ms = _uuid7_state["ms"]
            _uuid7_state["counter"] += 1
        counter = _uuid7_state["counter"]

    raw = bytearray(secrets.token_bytes(16))
    raw[0:6] = ms.to_bytes(6, "big")
    raw[6] = 0x70 | ((counter >> 8) & 0x0F)  # version 7 + counter high nibble
    raw[7] = counter & 0xFF                  # counter low byte
    raw[8] = (raw[8] & 0x3F) | 0x80          # RFC 4122 variant
    return str(uuid.UUID(bytes=bytes(raw)))


def _ulid() -> str:
    ms = int(time.time() * 1000)
    raw = ms.to_bytes(6, "big") + secrets.token_bytes(10)
    value = int.from_bytes(raw, "big")
    out = []
    for _ in range(26):
        out.append(CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def _parse_field(field: str, low: int, high: int) -> set[int]:
    """Expand one cron field, supporting * , - and /."""
    values: set[int] = set()
    for chunk in field.split(","):
        step = 1
        if "/" in chunk:
            chunk, _, step_raw = chunk.partition("/")
            if not step_raw.isdigit() or int(step_raw) < 1:
                raise HTTPException(400, f"Bad step in cron field: {field!r}")
            step = int(step_raw)
        if chunk in {"*", "?"}:
            start, end = low, high
        elif "-" in chunk:
            start_raw, _, end_raw = chunk.partition("-")
            if not (start_raw.isdigit() and end_raw.isdigit()):
                raise HTTPException(400, f"Bad range in cron field: {field!r}")
            start, end = int(start_raw), int(end_raw)
        elif chunk.isdigit():
            start = end = int(chunk)
        else:
            raise HTTPException(400, f"Cannot parse cron field: {field!r}")

        if not (low <= start <= high and low <= end <= high and start <= end):
            raise HTTPException(400, f"Cron field {field!r} is outside {low}-{high}")
        values.update(range(start, end + 1, step))

    if not values:
        raise HTTPException(400, f"Cron field {field!r} matches nothing")
    return values


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/id/generate")
    async def generate_ids(request: Request, body: IdRequest) -> dict:
        """UUID v4/v7, ULID or nanoid — all from `secrets`."""
        await request.app.state.require_key(request)
        kind = body.kind.lower()

        if kind == "uuid4":
            ids = [str(uuid.uuid4()) for _ in range(body.count)]
        elif kind == "uuid7":
            ids = [_uuid7() for _ in range(body.count)]
        elif kind == "ulid":
            ids = [_ulid() for _ in range(body.count)]
        elif kind == "nanoid":
            ids = [
                "".join(secrets.choice(NANOID_ALPHABET) for _ in range(body.size))
                for _ in range(body.count)
            ]
        else:
            raise HTTPException(400, "kind must be uuid4, uuid7, ulid or nanoid")

        return {"kind": kind, "count": len(ids), "ids": ids, "sortable": kind in {"uuid7", "ulid"}}

    @router.post("/hash")
    async def make_hash(request: Request, body: HashRequest) -> dict:
        """Digest or HMAC in hex or base64."""
        await request.app.state.require_key(request)
        algorithm = body.algorithm.lower()
        if algorithm not in HASH_ALGOS:
            raise HTTPException(400, f"algorithm must be one of: {', '.join(HASH_ALGOS)}")

        data = body.text.encode()
        if body.hmac_key:
            digest = hmac_mod.new(body.hmac_key.encode(), data, algorithm).digest()
        else:
            digest = hashlib.new(algorithm, data).digest()

        if body.encoding == "base64":
            value = base64.b64encode(digest).decode()
        elif body.encoding == "hex":
            value = digest.hex()
        else:
            raise HTTPException(400, "encoding must be 'hex' or 'base64'")

        return {
            "algorithm": algorithm,
            "hmac": bool(body.hmac_key),
            "encoding": body.encoding,
            "digest": value,
            "bits": len(digest) * 8,
        }

    @router.post("/jwt/decode")
    async def decode_jwt(request: Request, body: JwtRequest) -> dict:
        """Decode a JWT and, with a secret, verify its HS* signature."""
        await request.app.state.require_key(request)
        parts = body.token.strip().split(".")
        if len(parts) != 3:
            raise HTTPException(400, "A JWT has three dot-separated segments")

        def segment(raw: str) -> dict:
            padded = raw + "=" * (-len(raw) % 4)
            try:
                return json.loads(base64.urlsafe_b64decode(padded))
            except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HTTPException(400, f"Segment is not valid base64url JSON: {exc}") from exc

        header, payload = segment(parts[0]), segment(parts[1])
        now = int(time.time())

        result: dict = {
            "header": header,
            "payload": payload,
            "algorithm": header.get("alg"),
            "signature_verified": None,
            "expired": None,
        }

        if isinstance(payload.get("exp"), (int, float)):
            result["expired"] = payload["exp"] < now
            result["expires_at"] = dt.datetime.fromtimestamp(
                payload["exp"], dt.timezone.utc
            ).isoformat()
        if isinstance(payload.get("iat"), (int, float)):
            result["issued_at"] = dt.datetime.fromtimestamp(
                payload["iat"], dt.timezone.utc
            ).isoformat()

        if body.secret:
            algorithm = str(header.get("alg", "")).upper()
            mapping = {"HS256": "sha256", "HS384": "sha384", "HS512": "sha512"}
            if algorithm not in mapping:
                result["signature_verified"] = False
                result["verify_error"] = f"Only HS256/384/512 can be verified here, got {algorithm}"
            else:
                signing_input = f"{parts[0]}.{parts[1]}".encode()
                expected = hmac_mod.new(
                    body.secret.encode(), signing_input, mapping[algorithm]
                ).digest()
                given = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
                result["signature_verified"] = hmac_mod.compare_digest(expected, given)

        return result

    @router.post("/cron/next")
    async def cron_next(request: Request, body: CronRequest) -> dict:
        """Next N fire times for a 5-field cron expression, in UTC."""
        await request.app.state.require_key(request)
        fields = body.expression.split()
        if len(fields) != 5:
            raise HTTPException(
                400, "Expected 5 fields: minute hour day-of-month month day-of-week"
            )

        minutes = _parse_field(fields[0], 0, 59)
        hours = _parse_field(fields[1], 0, 23)
        days = _parse_field(fields[2], 1, 31)
        months = _parse_field(fields[3], 1, 12)
        weekdays = {d % 7 for d in _parse_field(fields[4], 0, 7)}

        if body.start:
            try:
                cursor = dt.datetime.fromisoformat(body.start.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(400, "start must be ISO-8601") from None
            if cursor.tzinfo is None:
                cursor = cursor.replace(tzinfo=dt.timezone.utc)
        else:
            cursor = dt.datetime.now(dt.timezone.utc)

        cursor = cursor.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
        dom_restricted = fields[2] not in {"*", "?"}
        dow_restricted = fields[4] not in {"*", "?"}

        runs: list[str] = []
        # Four years of minutes is enough to prove "29 Feb only" schedules fire.
        limit = 366 * 4 * 24 * 60
        checked = 0
        while len(runs) < body.count and checked < limit:
            checked += 1
            if cursor.month in months and cursor.hour in hours and cursor.minute in minutes:
                day_ok = cursor.day in days
                weekday_ok = ((cursor.weekday() + 1) % 7) in weekdays
                # cron ORs day-of-month with day-of-week when both are restricted.
                matches = (
                    (day_ok or weekday_ok)
                    if dom_restricted and dow_restricted
                    else (day_ok and weekday_ok)
                )
                if matches:
                    runs.append(cursor.isoformat())
            cursor += dt.timedelta(minutes=1)

        if not runs:
            raise HTTPException(400, "This expression never fires")

        return {
            "expression": body.expression,
            "description": _describe_cron(fields),
            "timezone": "UTC",
            "next_runs": runs,
        }

    return router


def _describe_cron(fields: list[str]) -> str:
    minute, hour, dom, month, dow = fields
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    if minute == "*" and hour == "*":
        when = "every minute"
    elif hour == "*":
        when = f"at minute {minute} of every hour"
    elif minute.isdigit() and hour.isdigit():
        when = f"at {int(hour):02d}:{int(minute):02d}"
    else:
        when = f"at minute {minute} of hour {hour}"

    if dow != "*" and dow.isdigit():
        when += f" on {names[int(dow) % 7]}"
    elif dow == "1-5":
        when += " on weekdays"
    elif dom != "*":
        when += f" on day {dom} of the month"

    if month != "*":
        when += f" in month {month}"
    return when.capitalize()


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="devkit",
        title="Dev Toolkit API",
        tagline="IDs, hashes, JWT inspection and cron maths — the backend odd jobs.",
        summary="Generate UUID/ULID/nanoid, compute hashes and HMACs, decode and verify JWTs, expand cron schedules.",
        router=build_router(),
        endpoints=[
            ("POST /v1/id/generate", "UUID v4/v7, ULID or nanoid"),
            ("POST /v1/hash", "Digest or HMAC, hex or base64"),
            ("POST /v1/jwt/decode", "Decode and optionally verify a JWT"),
            ("POST /v1/cron/next", "Next fire times for a cron expression"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/cron/next \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"expression":"0 9 * * 1-5","count":3}\''
        ),
    )
