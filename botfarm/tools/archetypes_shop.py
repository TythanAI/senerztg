"""Archetypes for stock-backed shops — accounts, keys, top-ups, monitoring.

These are the models that actually move volume on Telegram: a shelf of
credentials, instant delivery, a wallet, and a warranty window. They differ
from the content archetypes in one structural way — `kind: account` products
are issued from real inventory, so the bot knows when it is sold out.
"""

from __future__ import annotations

from typing import Any

# Account tiers. The same three-step ladder works for every brand: a cheap
# unverified unit, the standard one most people buy, and a premium unit.
_ACCOUNTS = {
    "ru": {
        "products": [
            ("basic", "Базовый", 1.0, "account", 0,
             "{topic_cap} — базовый аккаунт. Выдача моментальная, сразу после оплаты."),
            ("standard", "Стандарт", 1.8, "account", 0,
             "{topic_cap} — проверенный аккаунт с полным доступом и гарантией на замену."),
            ("premium", "Премиум", 3.4, "account", 0,
             "{topic_cap} — премиум-аккаунт: отлежавшийся, с историей, максимальная гарантия."),
        ],
        "faq": [
            ("Как быстро придёт заказ?", "Моментально. Бот выдаёт данные автоматически сразу после оплаты — ждать оператора не нужно."),
            ("Что если аккаунт не подошёл?", "Действует гарантия: если данные не подошли, напишите в поддержку в течение гарантийного срока — заменим или вернём деньги."),
            ("Данные точно рабочие?", "Каждая позиция проверяется перед загрузкой на склад. Если попалась нерабочая — замена по гарантии."),
            ("Можно купить несколько?", "Да, выберите количество при заказе. Бот выдаст ровно столько позиций, сколько вы оплатили."),
            ("Как оплатить?", "Картой, через СБП или криптовалютой. Можно пополнить баланс и покупать в один тап."),
        ],
        "warranty": "Гарантия 24 часа с момента выдачи. Проблемы — сразу в поддержку.",
        "instructions": (
            "❗️ Сразу после получения смените пароль и привязанную почту.\n"
            "Не передавайте данные третьим лицам — гарантия в этом случае не действует."
        ),
    },
    "en": {
        "products": [
            ("basic", "Basic", 1.0, "account", 0,
             "{topic_cap} — entry-level account. Delivered instantly after payment."),
            ("standard", "Standard", 1.8, "account", 0,
             "{topic_cap} — verified account with full access and a replacement warranty."),
            ("premium", "Premium", 3.4, "account", 0,
             "{topic_cap} — premium account: aged, with history, longest warranty."),
        ],
        "faq": [
            ("How fast is delivery?", "Instant. The bot issues the credentials automatically the moment payment clears — no waiting for an operator."),
            ("What if the account does not work?", "It is covered by warranty: message support within the warranty window and we replace it or refund you."),
            ("Are the details verified?", "Every unit is checked before it goes on the shelf. If one still fails, you get a replacement."),
            ("Can I buy several?", "Yes — pick the quantity at checkout and the bot issues exactly what you paid for."),
            ("How do I pay?", "Card, Apple/Google Pay or crypto. You can also top up your balance and buy in one tap."),
        ],
        "warranty": "24-hour warranty from delivery. Any problem, message support straight away.",
        "instructions": (
            "❗️ Change the password and the linked email immediately after receiving it.\n"
            "Do not share the details with anyone — the warranty does not cover that."
        ),
    },
}

# Keys, licences and gift cards: one-off codes, also issued from stock.
_KEYS = {
    "ru": {
        "products": [
            ("key1", "1 ключ", 1.0, "account", 0,
             "{topic_cap} — один ключ. Активируется сразу, выдача автоматическая."),
            ("key3", "3 ключа", 2.7, "account", 0,
             "Три ключа со скидкой. Удобно взять про запас или для друзей."),
            ("key10", "10 ключей", 8.0, "account", 0,
             "Оптовая пачка из десяти ключей по минимальной цене за штуку."),
        ],
        "faq": [
            ("Ключ точно активируется?", "Да, все ключи проверяются перед загрузкой. Если не активировался — замена в течение гарантийного срока."),
            ("Как быстро приходит ключ?", "Моментально после оплаты, прямо в этот чат."),
            ("На какой регион ключи?", "Регион указан в описании позиции. Если сомневаетесь — уточните в поддержке до покупки."),
            ("Можно вернуть?", "Ключ — цифровой товар одноразовой активации. Возврат возможен, только если ключ не сработал."),
        ],
        "warranty": "Гарантия на активацию — 24 часа.",
        "instructions": "Активируйте ключ как можно скорее и сохраните его до активации.",
    },
    "en": {
        "products": [
            ("key1", "1 key", 1.0, "account", 0,
             "{topic_cap} — a single key. Activates immediately, delivered automatically."),
            ("key3", "3 keys", 2.7, "account", 0,
             "Three keys at a discount — handy as spares or for friends."),
            ("key10", "10 keys", 8.0, "account", 0,
             "Bulk pack of ten keys at the lowest per-unit price."),
        ],
        "faq": [
            ("Will the key activate?", "Yes — every key is checked before it goes on the shelf. If one fails, it is replaced under warranty."),
            ("How fast do I get it?", "Instantly after payment, right here in this chat."),
            ("Which region?", "The region is stated in the item description. Ask support first if you are unsure."),
            ("Can I get a refund?", "A key is a single-use digital good. Refunds apply only if the key itself failed."),
        ],
        "warranty": "24-hour activation warranty.",
        "instructions": "Activate the key promptly and keep it safe until you do.",
    },
}

# Top-ups: game currency, service balances. Fulfilled by an operator, so the
# products are `service`, not stock.
_TOPUP = {
    "ru": {
        "products": [
            ("small", "Малый пакет", 1.0, "service", 0,
             "{topic_cap} — небольшой пакет. Зачисление в течение 15 минут."),
            ("medium", "Средний пакет", 2.5, "service", 0,
             "Средний пакет по выгодному курсу. Самый популярный вариант."),
            ("large", "Большой пакет", 5.5, "service", 0,
             "Большой пакет с лучшим курсом за единицу."),
        ],
        "faq": [
            ("Сколько ждать зачисления?", "Обычно 5-15 минут в рабочее время. При загрузке — до часа, статус подскажет оператор."),
            ("Что нужно для пополнения?", "После оплаты бот запросит ID или логин аккаунта. Пароль не нужен и никогда не запрашивается."),
            ("Это безопасно?", "Да, пополнение идёт официальными способами. Пароль от вашего аккаунта мы не спрашиваем."),
            ("Если не зачислили?", "Полный возврат средств. Пишите в поддержку — разберёмся в течение часа."),
        ],
    },
    "en": {
        "products": [
            ("small", "Small pack", 1.0, "service", 0,
             "{topic_cap} — a small pack. Credited within 15 minutes."),
            ("medium", "Medium pack", 2.5, "service", 0,
             "A medium pack at a better rate. The most popular option."),
            ("large", "Large pack", 5.5, "service", 0,
             "A large pack with the best per-unit rate."),
        ],
        "faq": [
            ("How long does it take?", "Usually 5-15 minutes during working hours, up to an hour at peak. An operator keeps you posted."),
            ("What do you need from me?", "After payment the bot asks for your account ID or login. We never ask for your password."),
            ("Is this safe?", "Yes — top-ups go through official channels and we never request your password."),
            ("What if it does not arrive?", "Full refund. Message support and we sort it within the hour."),
        ],
    },
}

# Monitoring and alerting, sold as a subscription.
_MONITOR = {
    "ru": {
        "products": [
            ("week", "Неделя", 0.5, "subscription", 7,
             "{topic_cap} — пробная неделя со всеми уведомлениями."),
            ("month", "Месяц", 1.5, "subscription", 30,
             "Месяц мониторинга: уведомления приходят в этот чат в реальном времени."),
            ("quarter", "Три месяца", 3.6, "subscription", 90,
             "Три месяца со скидкой плюс приоритетная скорость уведомлений."),
        ],
        "faq": [
            ("Как быстро приходят уведомления?", "В течение минуты после появления события. Приоритетный тариф — до 15 секунд."),
            ("Можно настроить фильтры?", "Да, в разделе настроек задаются нужные параметры, чтобы не приходило лишнее."),
            ("Что если пропущу уведомление?", "Все события сохраняются в истории — можно посмотреть в любой момент."),
            ("Есть пробный период?", "Да, короткий пробный доступ включается кнопкой в разделе подписки."),
        ],
    },
    "en": {
        "products": [
            ("week", "One week", 0.5, "subscription", 7,
             "{topic_cap} — a trial week with every alert enabled."),
            ("month", "One month", 1.5, "subscription", 30,
             "A month of monitoring: alerts arrive in this chat in real time."),
            ("quarter", "Three months", 3.6, "subscription", 90,
             "Three months at a discount, with priority alert speed."),
        ],
        "faq": [
            ("How fast are alerts?", "Within a minute of the event. The priority tier delivers in under 15 seconds."),
            ("Can I filter them?", "Yes — set your parameters in settings so you only get what matters."),
            ("What if I miss one?", "Every event is kept in history and can be reviewed at any time."),
            ("Is there a trial?", "Yes, a short trial is one button away in the subscription section."),
        ],
    },
}

SHOP_TEMPLATES: dict[str, dict[str, Any]] = {
    "accounts": _ACCOUNTS,
    "keys": _KEYS,
    "topup": _TOPUP,
    "monitor": _MONITOR,
}

SHOP_MODULES: dict[str, tuple[str, ...]] = {
    "accounts": ("catalog", "stock", "balance", "faq", "support", "referral", "reviews"),
    "keys": ("catalog", "stock", "balance", "faq", "support", "referral"),
    "topup": ("catalog", "balance", "faq", "support", "referral", "reviews"),
    "monitor": ("catalog", "subscription", "balance", "faq", "support", "referral"),
}

SHOP_REFERRAL = {"accounts": 15, "keys": 15, "topup": 10, "monitor": 20}
SHOP_TRIAL_DAYS = {"monitor": 3}


def shop_template(archetype: str, lang: str) -> dict[str, Any]:
    pack = SHOP_TEMPLATES[archetype]
    return pack.get(lang) or pack["en"]


def shop_delivery(archetype: str, lang: str, kind: str) -> dict[str, Any]:
    """Delivery block for a shop product. Stock items carry a warranty."""
    tpl = shop_template(archetype, lang)
    if kind == "account":
        return {
            "text": tpl.get("instructions", ""),
            "warranty": tpl.get("warranty", ""),
        }
    if kind == "subscription":
        return {
            "text": (
                "Доступ открыт. Уведомления начнут приходить в этот чат."
                if lang == "ru"
                else "Access granted. Alerts start arriving in this chat."
            ),
        }
    return {
        "text": (
            "Заказ принят. Оператор запросит ID аккаунта и выполнит пополнение."
            if lang == "ru"
            else "Order received. An operator will ask for your account ID and top it up."
        )
    }
