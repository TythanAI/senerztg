"""SQLAlchemy 2.0 models. Same schema for every bot in the farm."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Set when a broadcast hits "bot was blocked by the user". Cleared as soon
    #: as they interact again — unlike is_banned, it never locks anyone out.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    referral_earned: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    source: Mapped[str | None] = mapped_column(String(64))  # deep-link utm
    last_seen: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user", lazy="selectin")

    def display(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.first_name or str(self.tg_id)


class Order(Base, TimestampMixin):
    """One purchase attempt. Lives from 'user tapped buy' to paid/expired."""

    __tablename__ = "orders"

    STATUSES = ("pending", "paid", "delivered", "cancelled", "refunded", "expired")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    promo_code: Mapped[str | None] = mapped_column(String(32))

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    pay_url: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, nullable=False)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="orders", lazy="joined")

    __table_args__ = (
        Index("ix_orders_provider_external", "provider", "external_id"),
        Index("ix_orders_status_created", "status", "created_at"),
    )

    def is_open(self) -> bool:
        return self.status == "pending"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "sku", name="uq_sub_user_sku"),)

    def is_active(self, now: dt.datetime | None = None) -> bool:
        now = now or utcnow()
        expires = self.expires_at
        if expires.tzinfo is None:  # SQLite round-trips naive datetimes
            expires = expires.replace(tzinfo=dt.timezone.utc)
        return expires > now


class StockItem(Base, TimestampMixin):
    """One unit of sellable inventory — an account, a key, a code.

    This is what makes an account shop work: each row is issued to exactly
    one buyer. `status` moves available → sold and never back, and the
    transition is done with a conditional UPDATE so two simultaneous buyers
    can never receive the same credentials.
    """

    __tablename__ = "stock"

    STATUSES = ("available", "sold", "hold")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="available", nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    sold_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (Index("ix_stock_sku_status", "sku", "status"),)


class Payment(Base, TimestampMixin):
    """Immutable ledger row — written once, when money actually lands."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    raw: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_payment_provider_external"),
    )


class Promo(Base, TimestampMixin):
    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = unlimited
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def is_usable(self, now: dt.datetime | None = None) -> bool:
        now = now or utcnow()
        if not self.active or not 0 < self.percent <= 100:
            return False
        if self.max_uses and self.used >= self.max_uses:
            return False
        if self.expires_at:
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=dt.timezone.utc)
            if expires <= now:
                return False
        return True


class Lead(Base, TimestampMixin):
    """Captured contact from the leadgen / quiz / booking modules."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="leadgen", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[str | None] = mapped_column(Text)
    handled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Event(Base):
    """Lightweight funnel analytics: start → view → checkout → paid."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    value: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )


class Setting(Base):
    """Key/value store for runtime toggles set from the admin panel."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
