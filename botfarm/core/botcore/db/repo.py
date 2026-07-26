"""Data access. Handlers never write raw SQL — they call these."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Event,
    Lead,
    Order,
    Payment,
    Promo,
    Setting,
    StockItem,
    Subscription,
    Ticket,
    User,
    utcnow,
)


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, tg_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_id == tg_id))

    async def get_or_create(
        self,
        tg_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        lang: str = "ru",
        referrer_id: int | None = None,
        source: str | None = None,
    ) -> tuple[User, bool]:
        """Returns (user, created). Safe under concurrent /start taps."""
        user = await self.get(tg_id)
        if user is not None:
            changed = False
            if username != user.username:
                user.username, changed = username, True
            if first_name and first_name != user.first_name:
                user.first_name, changed = first_name, True
            user.last_seen = utcnow()
            if changed:
                await self.session.flush()
            return user, False

        # A user cannot invite themselves, and the referrer must already exist.
        ref: int | None = None
        if referrer_id and referrer_id != tg_id:
            if await self.get(referrer_id) is not None:
                ref = referrer_id

        user = User(
            tg_id=tg_id,
            username=username,
            first_name=first_name,
            lang=lang,
            referrer_id=ref,
            source=source,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError:
            # Two /start messages raced; the other transaction won.
            await self.session.rollback()
            existing = await self.get(tg_id)
            if existing is None:  # pragma: no cover - should not happen
                raise
            return existing, False
        return user, True

    async def set_ban(self, tg_id: int, banned: bool) -> bool:
        result = await self.session.execute(
            update(User).where(User.tg_id == tg_id).values(is_banned=banned)
        )
        return bool(result.rowcount)

    async def add_balance(self, user_id: int, amount: Decimal) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(balance=User.balance + amount)
        )

    async def spend_balance(self, user_id: int, amount: Decimal) -> bool:
        """Debit atomically. False means insufficient funds — never overdraws.

        The balance check lives in the WHERE clause on purpose: reading the
        balance and then writing it would let two concurrent purchases both
        pass the check and spend the same money.
        """
        if amount <= 0:
            return True
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.balance >= amount)
            .values(balance=User.balance - amount)
        )
        return bool(result.rowcount)

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(User.id))) or 0)

    async def count_since(self, since: dt.datetime) -> int:
        return int(
            await self.session.scalar(select(func.count(User.id)).where(User.created_at >= since))
            or 0
        )

    async def all_tg_ids(self, only_active: bool = True) -> Sequence[int]:
        stmt = select(User.tg_id)
        if only_active:
            stmt = stmt.where(User.is_banned.is_(False), User.is_blocked.is_(False))
        return list(await self.session.scalars(stmt))

    async def set_blocked(self, tg_id: int, blocked: bool) -> bool:
        result = await self.session.execute(
            update(User).where(User.tg_id == tg_id).values(is_blocked=blocked)
        )
        return bool(result.rowcount)

    async def referrals_of(self, tg_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count(User.id)).where(User.referrer_id == tg_id)
            )
            or 0
        )


class OrderRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user: User,
        sku: str,
        title: str,
        amount: Decimal,
        currency: str,
        provider: str,
        ttl_minutes: int = 60,
        quantity: int = 1,
        promo_code: str | None = None,
    ) -> Order:
        order = Order(
            user_id=user.id,
            sku=sku,
            title=title,
            amount=amount,
            currency=currency,
            provider=provider,
            quantity=max(1, quantity),
            promo_code=promo_code,
            expires_at=utcnow() + dt.timedelta(minutes=ttl_minutes),
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def open_count_for(self, user_id: int) -> int:
        """How many unpaid orders this user is sitting on."""
        return int(
            await self.session.scalar(
                select(func.count(Order.id)).where(
                    Order.user_id == user_id, Order.status == "pending"
                )
            )
            or 0
        )

    async def drop_stale_pending_for(self, user_id: int, keep: int = 5) -> int:
        """Cancel a user's oldest unpaid orders beyond `keep`.

        Every tap on a buy button opens an order. Without this, idly browsing
        the catalog grows the table without bound, which is both a disk-fill
        vector and noise in the admin panel.
        """
        stale = list(
            await self.session.scalars(
                select(Order.id)
                .where(Order.user_id == user_id, Order.status == "pending")
                .order_by(Order.created_at.desc())
                .offset(keep)
            )
        )
        if not stale:
            return 0
        result = await self.session.execute(
            update(Order)
            .where(Order.id.in_(stale), Order.status == "pending")
            .values(status="cancelled")
        )
        return int(result.rowcount or 0)

    async def get(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def by_external(self, provider: str, external_id: str) -> Order | None:
        return await self.session.scalar(
            select(Order).where(Order.provider == provider, Order.external_id == external_id)
        )

    async def pending(self, limit: int = 200) -> Sequence[Order]:
        return list(
            await self.session.scalars(
                select(Order)
                .where(Order.status == "pending")
                .order_by(Order.created_at)
                .limit(limit)
            )
        )

    async def last_for_user(self, user_id: int, limit: int = 10) -> Sequence[Order]:
        return list(
            await self.session.scalars(
                select(Order)
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
        )

    async def mark_paid(self, order: Order) -> bool:
        """Idempotent: returns True only the first time an order flips to paid."""
        if order.status != "pending":
            return False
        order.status = "paid"
        order.paid_at = utcnow()
        await self.session.flush()
        return True

    async def expire_stale(self) -> int:
        now = utcnow()
        result = await self.session.execute(
            update(Order)
            .where(Order.status == "pending", Order.expires_at.is_not(None), Order.expires_at < now)
            .values(status="expired")
        )
        return int(result.rowcount or 0)

    async def revenue(self, since: dt.datetime | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(Order.amount), 0)).where(
            Order.status.in_(("paid", "delivered"))
        )
        if since:
            stmt = stmt.where(Order.paid_at >= since)
        return Decimal(str(await self.session.scalar(stmt) or 0))

    async def paid_count(self, since: dt.datetime | None = None) -> int:
        stmt = select(func.count(Order.id)).where(Order.status.in_(("paid", "delivered")))
        if since:
            stmt = stmt.where(Order.paid_at >= since)
        return int(await self.session.scalar(stmt) or 0)


class PaymentRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        order: Order,
        provider: str,
        external_id: str,
        amount: Decimal,
        currency: str,
        raw: dict[str, Any] | None = None,
    ) -> Payment | None:
        """Write the ledger row. Returns None if this payment was already booked."""
        existing = await self.session.scalar(
            select(Payment).where(
                Payment.provider == provider, Payment.external_id == external_id
            )
        )
        if existing is not None:
            return None
        payment = Payment(
            order_id=order.id,
            provider=provider,
            external_id=external_id,
            amount=amount,
            currency=currency,
            raw=json.dumps(raw, ensure_ascii=False, default=str)[:8000] if raw else None,
        )
        self.session.add(payment)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            return None
        return payment


class SubscriptionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, sku: str) -> Subscription | None:
        return await self.session.scalar(
            select(Subscription).where(
                Subscription.user_id == user_id, Subscription.sku == sku
            )
        )

    async def active_for(self, user_id: int) -> list[Subscription]:
        rows = await self.session.scalars(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return [s for s in rows if s.is_active()]

    async def grant(
        self, user_id: int, sku: str, days: int, *, is_trial: bool = False
    ) -> Subscription:
        """Extend from the current expiry when still active, else from now."""
        now = utcnow()
        sub = await self.get(user_id, sku)
        if sub is None:
            sub = Subscription(
                user_id=user_id,
                sku=sku,
                expires_at=now + dt.timedelta(days=days),
                is_trial=is_trial,
            )
            self.session.add(sub)
        else:
            base = sub.expires_at
            if base.tzinfo is None:
                base = base.replace(tzinfo=dt.timezone.utc)
            start = base if base > now else now
            sub.expires_at = start + dt.timedelta(days=days)
            if not is_trial:
                sub.is_trial = False
        await self.session.flush()
        return sub

    async def expiring_within(self, hours: int = 48) -> Sequence[Subscription]:
        now = utcnow()
        until = now + dt.timedelta(hours=hours)
        rows = await self.session.scalars(
            select(Subscription).where(
                Subscription.expires_at > now, Subscription.expires_at <= until
            )
        )
        return list(rows)


class StockRepo:
    """Inventory for account shops: load it, count it, issue it exactly once."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def available(self, sku: str) -> int:
        return int(
            await self.session.scalar(
                select(func.count(StockItem.id)).where(
                    StockItem.sku == sku, StockItem.status == "available"
                )
            )
            or 0
        )

    async def counts(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(StockItem.sku, func.count(StockItem.id))
            .where(StockItem.status == "available")
            .group_by(StockItem.sku)
        )
        return {sku: int(count) for sku, count in rows.all()}

    async def add(self, sku: str, payloads: Sequence[str], note: str = "") -> int:
        """Load new units. Blank lines are skipped, duplicates are allowed."""
        added = 0
        for payload in payloads:
            payload = payload.strip()
            if not payload:
                continue
            self.session.add(
                StockItem(sku=sku, payload=payload[:4000], note=note[:256] or None)
            )
            added += 1
        await self.session.flush()
        return added

    async def issue(self, sku: str, quantity: int, order_id: int) -> list[str]:
        """Hand `quantity` units to one order, or nothing at all.

        Selecting then updating with `status == 'available'` still in the
        WHERE clause makes the claim conditional: if another transaction took
        a row in between, rowcount comes back short and we raise so the whole
        purchase rolls back rather than delivering half an order.
        """
        if quantity <= 0:
            return []

        candidates = list(
            await self.session.scalars(
                select(StockItem.id)
                .where(StockItem.sku == sku, StockItem.status == "available")
                .order_by(StockItem.id)
                .limit(quantity)
                .with_for_update(skip_locked=True)
                if self.session.bind and self.session.bind.dialect.name == "postgresql"
                else select(StockItem.id)
                .where(StockItem.sku == sku, StockItem.status == "available")
                .order_by(StockItem.id)
                .limit(quantity)
            )
        )
        if len(candidates) < quantity:
            raise OutOfStock(sku, requested=quantity, available=len(candidates))

        result = await self.session.execute(
            update(StockItem)
            .where(StockItem.id.in_(candidates), StockItem.status == "available")
            .values(status="sold", order_id=order_id, sold_at=utcnow())
        )
        if int(result.rowcount or 0) != quantity:
            # Someone else claimed one mid-flight; abort rather than under-deliver.
            raise OutOfStock(sku, requested=quantity, available=int(result.rowcount or 0))

        rows = await self.session.scalars(
            select(StockItem).where(StockItem.id.in_(candidates))
        )
        return [row.payload for row in rows]

    async def issued_for(self, order_id: int) -> list[str]:
        """Re-read what an order already received, for a repeat delivery."""
        rows = await self.session.scalars(
            select(StockItem).where(StockItem.order_id == order_id).order_by(StockItem.id)
        )
        return [row.payload for row in rows]

    async def purge_sku(self, sku: str) -> int:
        result = await self.session.execute(
            delete(StockItem).where(StockItem.sku == sku, StockItem.status == "available")
        )
        return int(result.rowcount or 0)


class OutOfStock(RuntimeError):
    """Raised when inventory cannot cover an order."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"{sku}: requested {requested}, only {available} available")
        self.sku = sku
        self.requested = requested
        self.available = available


class PromoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, code: str) -> Promo | None:
        return await self.session.scalar(select(Promo).where(Promo.code == code.upper().strip()))

    async def create(
        self, code: str, percent: int, max_uses: int = 0, days: int = 0
    ) -> Promo:
        promo = Promo(
            code=code.upper().strip(),
            percent=percent,
            max_uses=max_uses,
            expires_at=utcnow() + dt.timedelta(days=days) if days else None,
        )
        self.session.add(promo)
        await self.session.flush()
        return promo

    async def redeem(self, code: str) -> Promo | None:
        """Consume one use. Call this when an order is *paid*, not when the
        code is typed — otherwise anyone can exhaust a limited promo for free.

        The `used < max_uses` check is part of the UPDATE so two buyers
        redeeming the last use at once cannot both succeed.
        """
        promo = await self.get(code)
        if promo is None or not promo.is_usable():
            return None

        stmt = update(Promo).where(Promo.id == promo.id, Promo.active.is_(True))
        if promo.max_uses:
            stmt = stmt.where(Promo.used < promo.max_uses)
        result = await self.session.execute(stmt.values(used=Promo.used + 1))
        if not result.rowcount:
            return None

        await self.session.refresh(promo)
        return promo

    async def all(self) -> Sequence[Promo]:
        return list(await self.session.scalars(select(Promo).order_by(Promo.id.desc())))


class MiscRepo:
    """Leads, tickets, events, settings — small tables with small APIs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_lead(
        self,
        user_id: int,
        kind: str,
        *,
        phone: str | None = None,
        email: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Lead:
        lead = Lead(
            user_id=user_id,
            kind=kind,
            phone=phone,
            email=email,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def open_leads(self, limit: int = 50) -> Sequence[Lead]:
        return list(
            await self.session.scalars(
                select(Lead).where(Lead.handled.is_(False)).order_by(Lead.id.desc()).limit(limit)
            )
        )

    async def add_ticket(self, user_id: int, message: str) -> Ticket:
        ticket = Ticket(user_id=user_id, message=message[:4000])
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def open_tickets(self, limit: int = 50) -> Sequence[Ticket]:
        return list(
            await self.session.scalars(
                select(Ticket)
                .where(Ticket.closed.is_(False))
                .order_by(Ticket.id.desc())
                .limit(limit)
            )
        )

    async def track(self, tg_id: int, name: str, value: str | None = None) -> None:
        self.session.add(Event(tg_id=tg_id, name=name, value=value[:128] if value else None))

    async def funnel(self, since: dt.datetime | None = None) -> dict[str, int]:
        stmt = select(Event.name, func.count(Event.id)).group_by(Event.name)
        if since:
            stmt = stmt.where(Event.created_at >= since)
        rows = await self.session.execute(stmt)
        return {name: int(count) for name, count in rows.all()}

    async def prune_events(self, keep_days: int = 90) -> int:
        """Analytics rows are cheap individually and unbounded in aggregate."""
        cutoff = utcnow() - dt.timedelta(days=keep_days)
        result = await self.session.execute(delete(Event).where(Event.created_at < cutoff))
        return int(result.rowcount or 0)

    async def count_recent_events(self, tg_id: int, name: str, minutes: int) -> int:
        """Used to rate-limit sensitive actions such as promo-code guessing."""
        since = utcnow() - dt.timedelta(minutes=minutes)
        return int(
            await self.session.scalar(
                select(func.count(Event.id)).where(
                    Event.tg_id == tg_id, Event.name == name, Event.created_at >= since
                )
            )
            or 0
        )

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.session.get(Setting, key)
        return row.value if row else default

    async def set_setting(self, key: str, value: str) -> None:
        row = await self.session.get(Setting, key)
        if row is None:
            self.session.add(Setting(key=key, value=value))
        else:
            row.value = value
        await self.session.flush()


class Repos:
    """One handle passed into handlers via middleware."""

    __slots__ = (
        "session", "users", "orders", "payments", "subs", "promos", "stock", "misc",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepo(session)
        self.orders = OrderRepo(session)
        self.payments = PaymentRepo(session)
        self.subs = SubscriptionRepo(session)
        self.promos = PromoRepo(session)
        self.stock = StockRepo(session)
        self.misc = MiscRepo(session)
