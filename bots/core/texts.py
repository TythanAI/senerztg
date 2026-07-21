"""All user-facing message bodies (Russian).

Kept in one place so wording/branding is easy to tweak per sale. Every value
that can contain user input is HTML-escaped by the callers before it reaches
these templates.
"""
from __future__ import annotations

import html
from typing import Iterable

from .config import BotConfig
from .db import Order, OrderItem


def esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def money(amount: float, currency: str) -> str:
    return f"{amount:.2f} {currency}"


def start(cfg: BotConfig) -> str:
    body = cfg.welcome.strip() or (
        f"Добро пожаловать в <b>{esc(cfg.name)}</b>!\n\n"
        "Выберите товар в каталоге, добавьте в корзину и оформите заказ. "
        "Оплата проходит автоматически, выдача — мгновенная."
    )
    return body


def rules(cfg: BotConfig) -> str:
    return cfg.rules.strip() or (
        "<b>Правила магазина</b>\n\n"
        "• Оплаченный цифровой товар возврату не подлежит.\n"
        "• Проверяйте товар сразу после получения.\n"
        "• По любым вопросам пишите в поддержку."
    )


def support(cfg: BotConfig) -> str:
    lines = ["<b>Поддержка</b>\n"]
    if cfg.support_username:
        u = cfg.support_username.lstrip("@")
        lines.append(f"Напишите оператору: @{esc(u)}")
    lines.append("Или отправьте сообщение прямо здесь — мы ответим.")
    return "\n".join(lines)


def category_header(title: str, emoji: str) -> str:
    return f"{emoji} <b>{esc(title)}</b>\n\nВыберите товар:"


def product_card(
    title: str, description: str, price: float, currency: str, stock: int | None
) -> str:
    lines = [f"<b>{esc(title)}</b>\n"]
    if description:
        lines.append(esc(description) + "\n")
    lines.append(f"Цена: <b>{money(price, currency)}</b>")
    if stock is not None:
        lines.append("В наличии: " + ("<b>нет</b>" if stock <= 0 else f"<b>{stock} шт.</b>"))
    return "\n".join(lines)


def cart_view(
    rows: Iterable[tuple[str, float, int]], total: float, currency: str
) -> str:
    lines = ["🛒 <b>Ваша корзина</b>\n"]
    rows = list(rows)
    if not rows:
        return "🛒 Корзина пуста."
    for title, price, qty in rows:
        lines.append(f"• {esc(title)} — {qty} × {money(price, currency)}")
    lines.append(f"\nИтого: <b>{money(total, currency)}</b>")
    return "\n".join(lines)


def order_summary(items: Iterable[OrderItem], total: float, currency: str) -> str:
    lines = ["<b>Ваш заказ</b>\n"]
    for it in items:
        lines.append(f"• {esc(it.title)} — {it.qty} × {money(it.price, currency)}")
    lines.append(f"\nК оплате: <b>{money(total, currency)}</b>")
    return "\n".join(lines)


def out_of_stock(title: str) -> str:
    return (
        f"К сожалению, «{esc(title)}» только что закончился или его не хватает "
        "на нужное количество. Мы вернули позицию из заказа — попробуйте позже "
        "или выберите другой товар."
    )


def payment_pending_crypto(pay_url: str, total: float, currency: str) -> str:
    return (
        f"Счёт на <b>{money(total, currency)}</b> создан.\n\n"
        "Оплатите по кнопке ниже, затем нажмите <b>«Проверить оплату»</b>.\n"
        "Счёт действует ограниченное время."
    )


def digital_delivery(order_id: int, payloads: list[str]) -> str:
    body = "\n".join(f"<code>{esc(p)}</code>" for p in payloads)
    return (
        f"✅ Оплата заказа <b>#{order_id}</b> получена. Ваш товар:\n\n"
        f"{body}\n\n"
        "Спасибо за покупку! Сохраните данные в надёжном месте."
    )


def physical_created(cfg: BotConfig, order: Order, items: list[OrderItem]) -> str:
    note = f"\n\n{esc(cfg.delivery_note)}" if cfg.delivery_note else ""
    body = order_summary(items, order.total, order.currency)
    method = {
        "cod": "Оплата при получении",
        "telegram": "Оплата картой",
        "cryptobot": "Оплата криптовалютой",
    }.get(order.pay_method or "", "—")
    return (
        f"✅ Заказ <b>#{order.id}</b> принят!\n\n"
        f"{body}\n\n"
        f"Имя: {esc(order.contact_name or '—')}\n"
        f"Телефон: {esc(order.contact_phone or '—')}\n"
        f"Адрес: {esc(order.contact_addr or '—')}\n"
        f"Оплата: {method}"
        f"{note}\n\n"
        "Мы свяжемся с вами для подтверждения."
    )


def ask_name() -> str:
    return "Как к вам обращаться? Напишите имя."


def ask_phone() -> str:
    return "Укажите номер телефона для связи (например, +7 900 000-00-00)."


def ask_address() -> str:
    return "Укажите адрес доставки: город, улица, дом, квартира."


def ask_comment() -> str:
    return "Комментарий к заказу (подъезд, время, пожелания). Или нажмите «Пропустить»."


def order_status_line(order: Order) -> str:
    labels = {
        "pending": "⏳ Ожидает оплаты",
        "paid": "💳 Оплачен",
        "delivered": "✅ Выдан",
        "cancelled": "❌ Отменён",
        "preparing": "👨‍🍳 Готовится",
        "completed": "✅ Выполнен",
    }
    st = labels.get(order.status, order.status)
    return f"#{order.id} · {order.created_at[:10]} · {money(order.total, order.currency)} · {st}"


ANTIFLOOD = "⏳ Слишком часто. Подождите пару секунд."
ERROR_GENERIC = "⚠️ Что-то пошло не так. Попробуйте ещё раз или напишите в поддержку."
BANNED = "🚫 Доступ к боту ограничен."
NOT_ADMIN = "Команда доступна только администратору."
SUPPORT_SENT = "✅ Сообщение отправлено в поддержку. Мы ответим в ближайшее время."
BROADCAST_DONE = "Рассылка завершена. Доставлено: {ok}, ошибок: {fail}."
