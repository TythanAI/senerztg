"""Async SQLite data layer.

Everything is parameterised (no string-built SQL), stock allocation is
guarded by an in-process lock **and** conditional UPDATEs so a product can
never be sold twice, and order delivery is idempotent.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Sequence

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    created_at  TEXT NOT NULL,
    is_banned   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sku        TEXT NOT NULL,
    payload    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'available',  -- available|reserved|sold
    order_id   INTEGER,
    added_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_sku_status ON stock (sku, status);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    status         TEXT NOT NULL,   -- pending|paid|delivered|cancelled|preparing|completed
    total          REAL NOT NULL,
    currency       TEXT NOT NULL,
    fulfillment    TEXT NOT NULL,
    pay_method     TEXT,            -- telegram|cryptobot|cod
    pay_ref        TEXT,            -- provider charge / invoice id (idempotency key)
    contact_name   TEXT,
    contact_phone  TEXT,
    contact_addr   TEXT,
    comment        TEXT,
    created_at     TEXT NOT NULL,
    paid_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_payref ON orders (pay_method, pay_ref)
    WHERE pay_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS order_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL,
    sku       TEXT NOT NULL,
    title     TEXT NOT NULL,
    price     REAL NOT NULL,
    qty       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cart (
    user_id  INTEGER NOT NULL,
    sku      TEXT NOT NULL,
    qty      INTEGER NOT NULL,
    PRIMARY KEY (user_id, sku)
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Order:
    id: int
    user_id: int
    status: str
    total: float
    currency: str
    fulfillment: str
    pay_method: Optional[str]
    pay_ref: Optional[str]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    contact_addr: Optional[str]
    comment: Optional[str]
    created_at: str
    paid_at: Optional[str]


@dataclass
class OrderItem:
    sku: str
    title: str
    price: float
    qty: int


class Database:
    def __init__(self, path: str):
        self._path = path
        self._db: Optional[aiosqlite.Connection] = None
        self._alloc_lock = asyncio.Lock()

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA foreign_keys=ON;")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._db is not None, "Database not connected"
        return self._db

    # ---------------- users ----------------
    async def upsert_user(self, uid: int, username: str, full_name: str) -> None:
        await self.conn.execute(
            """INSERT INTO users (id, username, full_name, created_at)
                 VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET username=excluded.username,
                                             full_name=excluded.full_name""",
            (uid, username, full_name, _now()),
        )
        await self.conn.commit()

    async def is_banned(self, uid: int) -> bool:
        cur = await self.conn.execute("SELECT is_banned FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        return bool(row and row["is_banned"])

    async def set_banned(self, uid: int, banned: bool) -> None:
        await self.conn.execute(
            "UPDATE users SET is_banned=? WHERE id=?", (1 if banned else 0, uid)
        )
        await self.conn.commit()

    async def count_users(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM users")
        row = await cur.fetchone()
        return int(row["c"])

    async def all_user_ids(self) -> List[int]:
        cur = await self.conn.execute("SELECT id FROM users WHERE is_banned=0")
        return [r["id"] for r in await cur.fetchall()]

    # ---------------- cart ----------------
    async def cart_add(self, uid: int, sku: str, qty: int = 1, max_qty: int = 99) -> int:
        cur = await self.conn.execute(
            "SELECT qty FROM cart WHERE user_id=? AND sku=?", (uid, sku)
        )
        row = await cur.fetchone()
        new_qty = min((row["qty"] if row else 0) + qty, max_qty)
        new_qty = max(new_qty, 0)
        if new_qty == 0:
            await self.conn.execute(
                "DELETE FROM cart WHERE user_id=? AND sku=?", (uid, sku)
            )
        else:
            await self.conn.execute(
                """INSERT INTO cart (user_id, sku, qty) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, sku) DO UPDATE SET qty=excluded.qty""",
                (uid, sku, new_qty),
            )
        await self.conn.commit()
        return new_qty

    async def cart_set(self, uid: int, sku: str, qty: int) -> None:
        if qty <= 0:
            await self.conn.execute(
                "DELETE FROM cart WHERE user_id=? AND sku=?", (uid, sku)
            )
        else:
            await self.conn.execute(
                """INSERT INTO cart (user_id, sku, qty) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, sku) DO UPDATE SET qty=excluded.qty""",
                (uid, sku, qty),
            )
        await self.conn.commit()

    async def cart_items(self, uid: int) -> List[tuple[str, int]]:
        cur = await self.conn.execute(
            "SELECT sku, qty FROM cart WHERE user_id=? ORDER BY rowid", (uid,)
        )
        return [(r["sku"], r["qty"]) for r in await cur.fetchall()]

    async def cart_clear(self, uid: int) -> None:
        await self.conn.execute("DELETE FROM cart WHERE user_id=?", (uid,))
        await self.conn.commit()

    # ---------------- stock ----------------
    async def add_stock(self, sku: str, payloads: Sequence[str]) -> int:
        rows = [(sku, p.strip(), "available", None, _now()) for p in payloads if p.strip()]
        if not rows:
            return 0
        await self.conn.executemany(
            "INSERT INTO stock (sku, payload, status, order_id, added_at) VALUES (?,?,?,?,?)",
            rows,
        )
        await self.conn.commit()
        return len(rows)

    async def stock_count(self, sku: str, status: str = "available") -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM stock WHERE sku=? AND status=?", (sku, status)
        )
        row = await cur.fetchone()
        return int(row["c"])

    async def stock_counts(self) -> dict[str, int]:
        cur = await self.conn.execute(
            "SELECT sku, COUNT(*) AS c FROM stock WHERE status='available' GROUP BY sku"
        )
        return {r["sku"]: r["c"] for r in await cur.fetchall()}

    async def reserve_stock(self, sku: str, qty: int, order_id: int) -> bool:
        """Atomically reserve ``qty`` available items for an order.

        Returns True on success. On failure nothing is reserved. Guarded by an
        in-process lock so concurrent checkouts cannot both grab the last item.
        """
        async with self._alloc_lock:
            cur = await self.conn.execute(
                "SELECT id FROM stock WHERE sku=? AND status='available' "
                "ORDER BY id LIMIT ?",
                (sku, qty),
            )
            ids = [r["id"] for r in await cur.fetchall()]
            if len(ids) < qty:
                return False
            placeholders = ",".join("?" * len(ids))
            await self.conn.execute(
                f"UPDATE stock SET status='reserved', order_id=? "
                f"WHERE id IN ({placeholders}) AND status='available'",
                (order_id, *ids),
            )
            await self.conn.commit()
            return True

    async def release_order_stock(self, order_id: int) -> None:
        await self.conn.execute(
            "UPDATE stock SET status='available', order_id=NULL "
            "WHERE order_id=? AND status='reserved'",
            (order_id,),
        )
        await self.conn.commit()

    async def sell_order_stock(self, order_id: int) -> List[str]:
        """Mark an order's reserved stock as sold and return payloads."""
        async with self._alloc_lock:
            await self.conn.execute(
                "UPDATE stock SET status='sold' WHERE order_id=? AND status='reserved'",
                (order_id,),
            )
            await self.conn.commit()
            cur = await self.conn.execute(
                "SELECT payload FROM stock WHERE order_id=? AND status='sold' ORDER BY id",
                (order_id,),
            )
            return [r["payload"] for r in await cur.fetchall()]

    # ---------------- orders ----------------
    async def create_order(
        self,
        user_id: int,
        total: float,
        currency: str,
        fulfillment: str,
        items: Sequence[OrderItem],
        pay_method: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_phone: Optional[str] = None,
        contact_addr: Optional[str] = None,
        comment: Optional[str] = None,
        status: str = "pending",
    ) -> int:
        cur = await self.conn.execute(
            """INSERT INTO orders
               (user_id, status, total, currency, fulfillment, pay_method,
                contact_name, contact_phone, contact_addr, comment, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, status, total, currency, fulfillment, pay_method,
                contact_name, contact_phone, contact_addr, comment, _now(),
            ),
        )
        order_id = cur.lastrowid
        await self.conn.executemany(
            "INSERT INTO order_items (order_id, sku, title, price, qty) VALUES (?,?,?,?,?)",
            [(order_id, it.sku, it.title, it.price, it.qty) for it in items],
        )
        await self.conn.commit()
        return int(order_id)

    async def set_order_payref(self, order_id: int, pay_method: str, pay_ref: str) -> None:
        await self.conn.execute(
            "UPDATE orders SET pay_method=?, pay_ref=? WHERE id=?",
            (pay_method, pay_ref, order_id),
        )
        await self.conn.commit()

    async def get_order(self, order_id: int) -> Optional[Order]:
        cur = await self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        return _row_to_order(row) if row else None

    async def order_items(self, order_id: int) -> List[OrderItem]:
        cur = await self.conn.execute(
            "SELECT sku, title, price, qty FROM order_items WHERE order_id=?", (order_id,)
        )
        return [
            OrderItem(sku=r["sku"], title=r["title"], price=r["price"], qty=r["qty"])
            for r in await cur.fetchall()
        ]

    async def mark_paid_if_pending(
        self, order_id: int, pay_method: str, pay_ref: str
    ) -> bool:
        """Transition pending -> paid exactly once. Returns True if *this* call
        performed the transition (i.e. the caller should now deliver)."""
        cur = await self.conn.execute(
            "UPDATE orders SET status='paid', pay_method=?, pay_ref=?, paid_at=? "
            "WHERE id=? AND status='pending'",
            (pay_method, pay_ref, _now(), order_id),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def set_order_status(self, order_id: int, status: str) -> None:
        await self.conn.execute(
            "UPDATE orders SET status=? WHERE id=?", (status, order_id)
        )
        await self.conn.commit()

    async def user_orders(self, user_id: int, limit: int = 10) -> List[Order]:
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        return [_row_to_order(r) for r in await cur.fetchall()]

    async def recent_orders(self, limit: int = 15) -> List[Order]:
        cur = await self.conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [_row_to_order(r) for r in await cur.fetchall()]

    async def expire_pending_orders(self, max_age_seconds: int = 3600) -> int:
        """Cancel long-pending orders and release their reserved stock so items
        never stay locked because a customer walked away mid-payment."""
        cutoff = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=max_age_seconds)
        ).isoformat(timespec="seconds")
        cur = await self.conn.execute(
            "SELECT id FROM orders WHERE status='pending' AND created_at < ?", (cutoff,)
        )
        ids = [r["id"] for r in await cur.fetchall()]
        for oid in ids:
            await self.release_order_stock(oid)
            await self.set_order_status(oid, "cancelled")
        return len(ids)

    async def stats(self) -> dict:
        users = await self.count_users()
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(total),0) AS s FROM orders "
            "WHERE status IN ('paid','delivered','completed')"
        )
        row = await cur.fetchone()
        cur2 = await self.conn.execute("SELECT COUNT(*) AS c FROM orders")
        row2 = await cur2.fetchone()
        return {
            "users": users,
            "orders_total": int(row2["c"]),
            "orders_paid": int(row["c"]),
            "revenue": round(float(row["s"]), 2),
        }


def _row_to_order(r: aiosqlite.Row) -> Order:
    return Order(
        id=r["id"],
        user_id=r["user_id"],
        status=r["status"],
        total=r["total"],
        currency=r["currency"],
        fulfillment=r["fulfillment"],
        pay_method=r["pay_method"],
        pay_ref=r["pay_ref"],
        contact_name=r["contact_name"],
        contact_phone=r["contact_phone"],
        contact_addr=r["contact_addr"],
        comment=r["comment"],
        created_at=r["created_at"],
        paid_at=r["paid_at"],
    )
