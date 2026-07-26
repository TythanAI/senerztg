"""Telegram Mini App authentication.

This is the one piece of a Mini App that must be exactly right. The browser
sends `initData` — a query string describing the current Telegram user — and
it is trivially forgeable by anyone who opens devtools. The server is the only
place that can tell a real user from an invented one, and it does so by
recomputing Telegram's HMAC over the payload.

Getting this wrong is the standard Mini App vulnerability: half the tutorials
online parse `initData` client-side and trust `user.id`, which means any
visitor can claim to be any customer and drain their balance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

#: Telegram's fixed HMAC salt for Mini App payloads.
_SECRET_SALT = b"WebAppData"

#: How old an initData payload may be. Telegram refreshes it on every launch,
#: so a day is generous; anything older is a replay of a captured session.
DEFAULT_MAX_AGE = 24 * 3600


class AuthError(Exception):
    """initData is missing, malformed, forged or stale."""


@dataclass(slots=True)
class TelegramUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = "en"
    is_premium: bool = False
    photo_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or (f"@{self.username}" if self.username else str(self.id))


@dataclass(slots=True)
class InitData:
    user: TelegramUser
    auth_date: int
    query_id: str = ""
    start_param: str = ""
    chat_type: str = ""
    raw: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def age_seconds(self) -> int:
        return max(0, int(time.time()) - self.auth_date)


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(_SECRET_SALT, bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Produce the hash Telegram would produce. Used by the test suite.

    Kept next to the verifier on purpose: if the check string is ever built
    differently in the two places, the tests stop passing.
    """
    check_string = _check_string(fields)
    return hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()


def _check_string(fields: dict[str, str]) -> str:
    """`key=value` pairs, hash excluded, sorted by key, joined with newlines."""
    return "\n".join(f"{k}={fields[k]}" for k in sorted(fields) if k != "hash")


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
) -> InitData:
    """Validate a raw initData string and return the user it describes.

    Raises AuthError on anything suspicious. Callers must never fall back to
    trusting the payload when this raises.
    """
    if not init_data:
        raise AuthError("initData is empty — open this app from inside Telegram")
    if not bot_token:
        raise AuthError("server is misconfigured: BOT_TOKEN is not set")

    # keep_blank_values matters: dropping an empty field would change the
    # check string and make a legitimate payload fail verification.
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise AuthError(f"initData is not a valid query string: {exc}") from exc

    received_hash = pairs.get("hash", "")
    if not received_hash:
        raise AuthError("initData carries no hash")

    expected = hmac.new(
        _secret_key(bot_token), _check_string(pairs).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise AuthError("initData signature does not match — refusing the request")

    raw_auth_date = pairs.get("auth_date", "")
    if not raw_auth_date.isdigit():
        raise AuthError("initData has no usable auth_date")
    auth_date = int(raw_auth_date)

    age = int(time.time()) - auth_date
    if max_age and age > max_age:
        raise AuthError(f"initData is {age}s old — reopen the app")
    # A payload from the future means a forged or badly skewed clock.
    if age < -300:
        raise AuthError("initData auth_date is in the future")

    try:
        user_blob = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise AuthError("initData user field is not valid JSON") from exc

    if not isinstance(user_blob, dict) or not user_blob.get("id"):
        raise AuthError("initData contains no user")

    user = TelegramUser(
        id=int(user_blob["id"]),
        first_name=str(user_blob.get("first_name", "")),
        last_name=str(user_blob.get("last_name", "")),
        username=str(user_blob.get("username", "")),
        language_code=str(user_blob.get("language_code", "en")),
        is_premium=bool(user_blob.get("is_premium", False)),
        photo_url=str(user_blob.get("photo_url", "")),
        raw=user_blob,
    )

    return InitData(
        user=user,
        auth_date=auth_date,
        query_id=pairs.get("query_id", ""),
        start_param=pairs.get("start_param", ""),
        chat_type=pairs.get("chat_type", ""),
        raw=pairs,
    )


def build_init_data(
    bot_token: str,
    user: dict[str, Any] | None = None,
    *,
    auth_date: int | None = None,
    **extra: str,
) -> str:
    """Build a correctly signed initData string — for tests and local dev."""
    from urllib.parse import urlencode

    fields: dict[str, str] = {
        "user": json.dumps(user or {"id": 1, "first_name": "Test"}, separators=(",", ":")),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        **{k: str(v) for k, v in extra.items()},
    }
    fields["hash"] = sign_init_data(fields, bot_token)
    return urlencode(fields)
