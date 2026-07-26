"""Data access. Handlers never write raw SQL — they call these."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Event,
    Lead,
    Order,
    Payment,
    Promo,
    Setting,
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
    ) -> Order:
        order = Order(
            user_id=user.id,
            sku=sku,
            title=title,
            amount=amount,
            currency=currency,
            provider=provider,
            expires_at=utcnow() + dt.timedelta(minutes=ttl_minutes),
        )
        self.session.add(order)
        await self.session.flush()
        return order

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
        promo = await self.get(code)
        if promo is None or not promo.is_usable():
            return None
        promo.used += 1
        await self.session.flush()
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

    __slots__ = ("session", "users", "orders", "payments", "subs", "promos", "misc")

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepo(session)
        self.orders = OrderRepo(session)
        self.payments = PaymentRepo(session)
        self.subs = SubscriptionRepo(session)
        self.promos = PromoRepo(session)
        self.misc = MiscRepo(session)
