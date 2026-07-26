"""Storage for API keys, usage and invoices.

SQLite via the stdlib driver: these are sub-millisecond point queries against a
handful of rows, so a connection with a lock beats an async ORM here — one
file, no server, trivial to back up, and it survives a VPS reboot.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KEY_PREFIX = "sk_live_"
#: Plans every service inherits. `quota` is calls per 30-day period.
PLANS: dict[str, dict[str, Any]] = {
    "free":  {"quota": 500,     "rpm": 10,  "price_eur": 0},
    "basic": {"quota": 25_000,  "rpm": 60,  "price_eur": 9},
    "pro":   {"quota": 250_000, "rpm": 300, "price_eur": 29},
    "scale": {"quota": 2_000_000, "rpm": 1200, "price_eur": 99},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS keys (
    id          INTEGER PRIMARY KEY,
    key_hash    TEXT NOT NULL UNIQUE,
    prefix      TEXT NOT NULL,
    label       TEXT DEFAULT '',
    plan        TEXT NOT NULL DEFAULT 'free',
    service     TEXT NOT NULL DEFAULT '*',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL,
    expires_at  REAL,
    email       TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_keys_prefix ON keys(prefix);

CREATE TABLE IF NOT EXISTS usage (
    key_id      INTEGER NOT NULL,
    period      TEXT NOT NULL,
    endpoint    TEXT NOT NULL DEFAULT '*',
    calls       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key_id, period, endpoint)
);

CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY,
    key_id       INTEGER NOT NULL,
    provider     TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    plan         TEXT NOT NULL,
    amount       REAL NOT NULL,
    currency     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   REAL NOT NULL,
    paid_at      REAL,
    raw          TEXT,
    UNIQUE (provider, external_id)
);

CREATE TABLE IF NOT EXISTS links (
    slug        TEXT PRIMARY KEY,
    target      TEXT NOT NULL,
    key_id      INTEGER,
    clicks      INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    expires_at  REAL
);
"""


@dataclass(slots=True)
class ApiKey:
    id: int
    prefix: str
    label: str
    plan: str
    service: str
    active: bool
    created_at: float
    expires_at: float | None
    email: str

    @property
    def quota(self) -> int:
        return PLANS.get(self.plan, PLANS["free"])["quota"]

    @property
    def rpm(self) -> int:
        return PLANS.get(self.plan, PLANS["free"])["rpm"]

    def is_valid(self, now: float | None = None) -> bool:
        now = now or time.time()
        if not self.active:
            return False
        return self.expires_at is None or self.expires_at > now

    def allows(self, service: str) -> bool:
        return self.service in {"*", service}


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def current_period() -> str:
    return time.strftime("%Y-%m", time.gmtime())


class Store:
    def __init__(self, path: str | Path = "saas.db") -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ keys

    def create_key(
        self,
        *,
        plan: str = "free",
        label: str = "",
        service: str = "*",
        email: str = "",
        ttl_days: int = 0,
    ) -> tuple[str, ApiKey]:
        """Returns (plaintext key, record). The plaintext is never stored."""
        if plan not in PLANS:
            raise ValueError(f"unknown plan {plan!r}; choose from {sorted(PLANS)}")

        raw = KEY_PREFIX + secrets.token_urlsafe(24)
        prefix = raw[: len(KEY_PREFIX) + 6]
        now = time.time()
        expires = now + ttl_days * 86400 if ttl_days else None

        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO keys (key_hash, prefix, label, plan, service, active, "
                "created_at, expires_at, email) VALUES (?,?,?,?,?,1,?,?,?)",
                (hash_key(raw), prefix, label, plan, service, now, expires, email),
            )
            self._conn.commit()
            key_id = int(cursor.lastrowid)

        return raw, ApiKey(key_id, prefix, label, plan, service, True, now, expires, email)

    def get_key(self, raw: str) -> ApiKey | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM keys WHERE key_hash = ?", (hash_key(raw),)
            ).fetchone()
        return _to_key(row) if row else None

    def get_key_by_id(self, key_id: int) -> ApiKey | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM keys WHERE id = ?", (key_id,)).fetchone()
        return _to_key(row) if row else None

    def list_keys(self, limit: int = 100) -> list[ApiKey]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM keys ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_key(row) for row in rows]

    def set_plan(self, key_id: int, plan: str) -> bool:
        if plan not in PLANS:
            raise ValueError(f"unknown plan {plan!r}")
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET plan = ? WHERE id = ?", (plan, key_id)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def revoke(self, key_id: int) -> bool:
        with self._lock:
            cursor = self._conn.execute("UPDATE keys SET active = 0 WHERE id = ?", (key_id,))
            self._conn.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------------- usage

    def record_call(self, key_id: int, endpoint: str = "*") -> int:
        """Increment and return this period's total for the key."""
        period = current_period()
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (key_id, period, endpoint, calls) VALUES (?,?,?,1) "
                "ON CONFLICT(key_id, period, endpoint) DO UPDATE SET calls = calls + 1",
                (key_id, period, endpoint),
            )
            total = self._conn.execute(
                "SELECT COALESCE(SUM(calls), 0) FROM usage WHERE key_id = ? AND period = ?",
                (key_id, period),
            ).fetchone()[0]
            self._conn.commit()
        return int(total)

    def usage(self, key_id: int, period: str | None = None) -> dict[str, Any]:
        period = period or current_period()
        with self._lock:
            rows = self._conn.execute(
                "SELECT endpoint, calls FROM usage WHERE key_id = ? AND period = ?",
                (key_id, period),
            ).fetchall()
        by_endpoint = {row["endpoint"]: row["calls"] for row in rows}
        return {
            "period": period,
            "total": sum(by_endpoint.values()),
            "by_endpoint": by_endpoint,
        }

    # -------------------------------------------------------------- invoices

    def create_invoice(
        self,
        *,
        key_id: int,
        provider: str,
        external_id: str,
        plan: str,
        amount: float,
        currency: str,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO invoices (key_id, provider, external_id, plan, amount, "
                "currency, status, created_at) VALUES (?,?,?,?,?,?, 'pending', ?)",
                (key_id, provider, external_id, plan, amount, currency, time.time()),
            )
            self._conn.commit()
        return int(cursor.lastrowid)

    def mark_invoice_paid(
        self, provider: str, external_id: str, raw: dict | None = None
    ) -> ApiKey | None:
        """Idempotent: upgrades the key only the first time an invoice is paid."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM invoices WHERE provider = ? AND external_id = ?",
                (provider, external_id),
            ).fetchone()
            if row is None or row["status"] == "paid":
                return None

            self._conn.execute(
                "UPDATE invoices SET status = 'paid', paid_at = ?, raw = ? WHERE id = ?",
                (time.time(), json.dumps(raw, default=str)[:4000] if raw else None, row["id"]),
            )
            self._conn.execute(
                "UPDATE keys SET plan = ? WHERE id = ?", (row["plan"], row["key_id"])
            )
            self._conn.commit()

        return self.get_key_by_id(int(row["key_id"]))

    # ------------------------------------------------------------ shortlinks

    def put_link(self, slug: str, target: str, key_id: int | None, ttl_days: int = 0) -> bool:
        now = time.time()
        expires = now + ttl_days * 86400 if ttl_days else None
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO links (slug, target, key_id, created_at, expires_at) "
                    "VALUES (?,?,?,?,?)",
                    (slug, target, key_id, now, expires),
                )
                self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def resolve_link(self, slug: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
            if row is None:
                return None
            if row["expires_at"] and row["expires_at"] < time.time():
                return None
            self._conn.execute("UPDATE links SET clicks = clicks + 1 WHERE slug = ?", (slug,))
            self._conn.commit()
        return str(row["target"])

    def link_stats(self, slug: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return {
            "slug": row["slug"],
            "target": row["target"],
            "clicks": row["clicks"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }


def _to_key(row: sqlite3.Row) -> ApiKey:
    return ApiKey(
        id=int(row["id"]),
        prefix=row["prefix"],
        label=row["label"] or "",
        plan=row["plan"],
        service=row["service"],
        active=bool(row["active"]),
        created_at=float(row["created_at"]),
        expires_at=float(row["expires_at"]) if row["expires_at"] else None,
        email=row["email"] or "",
    )
