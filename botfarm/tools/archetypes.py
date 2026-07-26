"""Business-model templates.

An archetype answers: what does this bot sell, in how many tiers, which
modules does it need, and what does the copy say. Twelve archetypes (eight
here, four stock-backed ones in archetypes_shop) across 1000 niches give every
bot a coherent, sellable product line instead of a stub catalog.

Copy is authored per language; `de` and `es` cover the archetypes actually used
by German/Spanish bots and fall back to `en` otherwise.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Base price for one "unit" of value, by tier and currency.
BASE_PRICES: dict[str, dict[str, Decimal]] = {
    "RUB": {
        "budget": Decimal("490"),
        "standard": Decimal("1490"),
        "premium": Decimal("4900"),
        "elite": Decimal("14900"),
    },
    "EUR": {
        "budget": Decimal("9"),
        "standard": Decimal("29"),
        "premium": Decimal("79"),
        "elite": Decimal("199"),
    },
}

#: How many currency units one Telegram Star is worth. Stars pay out at roughly
#: €0.013 net, so these are deliberately conservative for the seller.
STARS_RATE = {"RUB": 2, "EUR": 1, "USD": 1}


def price_for(tier: str, currency: str, multiplier: float) -> Decimal:
    base = BASE_PRICES[currency][tier] * Decimal(str(multiplier))
    if currency == "RUB":
        # Round to a psychologically clean price: 1490, 3990, 12900.
        rounded = (base / 10).to_integral_value() * 10 - 10
        return max(Decimal("90"), rounded)
    rounded = base.to_integral_value()
    return max(Decimal("5"), rounded - 1)


# --------------------------------------------------------------------- copy

_COURSE = {
    "ru": {
        "products": [
            ("start", "Стартовый пакет", 1.0, "digital", 0,
             "Основы {topic}: пошаговая программа, чек-листы и шаблоны. Доступ навсегда."),
            ("pro", "Расширенный курс", 2.7, "digital", 0,
             "Полная программа по теме «{topic}»: разборы кейсов, домашние задания с проверкой, закрытый чат."),
            ("vip", "VIP с сопровождением", 6.0, "consult", 0,
             "Всё из расширенного курса плюс три личные встречи и разбор вашей ситуации по теме «{topic}»."),
        ],
        "faq": [
            ("Сколько длится обучение?", "Материалы открываются сразу, темп выбираете сами. Средний срок прохождения — 4-6 недель."),
            ("Нужен ли опыт?", "Нет. Программа рассчитана на старт с нуля, все термины объясняются по ходу."),
            ("Что если не подойдёт?", "Возврат в течение 7 дней после покупки, если вы прошли не более 20% материалов."),
            ("Доступ ограничен по времени?", "Нет, доступ бессрочный, включая все будущие обновления."),
        ],
        "quiz": [
            ("Какой у вас опыт в теме «{topic}»?", ["Совсем новичок", "Что-то пробовал", "Есть практика"]),
            ("Сколько времени готовы уделять?", ["До часа в неделю", "2-3 часа в неделю", "Готов заниматься плотно"]),
            ("Что важнее?", ["Понять базу", "Получить результат быстрее", "Личное сопровождение"]),
        ],
    },
    "en": {
        "products": [
            ("start", "Starter pack", 1.0, "digital", 0,
             "The fundamentals of {topic}: a step-by-step programme, checklists and templates. Lifetime access."),
            ("pro", "Full course", 2.7, "digital", 0,
             "The complete {topic} programme: case studies, graded assignments and a private chat."),
            ("vip", "VIP with coaching", 6.0, "consult", 0,
             "Everything in the full course plus three one-to-one sessions applied to your own situation."),
        ],
        "faq": [
            ("How long does it take?", "Everything unlocks immediately and you set the pace. Most people finish in 4-6 weeks."),
            ("Do I need experience?", "No. The programme starts from zero and explains every term as it comes up."),
            ("What if it is not for me?", "Full refund within 7 days if you have completed less than 20% of the material."),
            ("Does access expire?", "No. Access is permanent and includes every future update."),
        ],
        "quiz": [
            ("How much {topic} experience do you have?", ["Complete beginner", "Tried a little", "Already practising"]),
            ("How much time can you commit?", ["Under an hour a week", "2-3 hours a week", "As much as it takes"]),
            ("What matters most?", ["Understanding the basics", "Getting results fast", "One-to-one guidance"]),
        ],
    },
    "de": {
        "products": [
            ("start", "Starter-Paket", 1.0, "digital", 0,
             "Die Grundlagen zu {topic}: Schritt-für-Schritt-Programm, Checklisten und Vorlagen. Dauerhafter Zugang."),
            ("pro", "Komplettkurs", 2.7, "digital", 0,
             "Das vollständige Programm zu {topic}: Fallbeispiele, korrigierte Aufgaben und ein privater Chat."),
            ("vip", "VIP mit Betreuung", 6.0, "consult", 0,
             "Alles aus dem Komplettkurs plus drei persönliche Termine zu Ihrer Situation."),
        ],
        "faq": [
            ("Wie lange dauert der Kurs?", "Alle Inhalte sind sofort verfügbar, das Tempo bestimmen Sie. Üblich sind 4-6 Wochen."),
            ("Brauche ich Vorkenntnisse?", "Nein. Der Kurs beginnt bei null und erklärt jeden Fachbegriff."),
            ("Und wenn es nicht passt?", "Volle Rückerstattung innerhalb von 7 Tagen, wenn weniger als 20% bearbeitet wurden."),
            ("Läuft der Zugang ab?", "Nein. Der Zugang bleibt dauerhaft und enthält alle künftigen Updates."),
        ],
        "quiz": [
            ("Wie viel Erfahrung haben Sie mit {topic}?", ["Ganz neu", "Etwas ausprobiert", "Schon in der Praxis"]),
            ("Wie viel Zeit haben Sie?", ["Unter einer Stunde pro Woche", "2-3 Stunden pro Woche", "So viel wie nötig"]),
            ("Was ist Ihnen wichtiger?", ["Grundlagen verstehen", "Schnelle Ergebnisse", "Persönliche Betreuung"]),
        ],
    },
    "es": {
        "products": [
            ("start", "Pack inicial", 1.0, "digital", 0,
             "Los fundamentos de {topic}: programa paso a paso, checklists y plantillas. Acceso de por vida."),
            ("pro", "Curso completo", 2.7, "digital", 0,
             "El programa completo de {topic}: casos prácticos, ejercicios corregidos y chat privado."),
            ("vip", "VIP con acompañamiento", 6.0, "consult", 0,
             "Todo el curso completo más tres sesiones individuales sobre tu caso."),
        ],
        "faq": [
            ("¿Cuánto dura?", "Todo se desbloquea al instante y marcas tu ritmo. La media son 4-6 semanas."),
            ("¿Necesito experiencia?", "No. El programa empieza desde cero y explica cada término."),
            ("¿Y si no me sirve?", "Reembolso completo en 7 días si has visto menos del 20% del material."),
            ("¿El acceso caduca?", "No. El acceso es permanente e incluye todas las actualizaciones."),
        ],
        "quiz": [
            ("¿Qué experiencia tienes con {topic}?", ["Ninguna", "He probado algo", "Ya practico"]),
            ("¿Cuánto tiempo puedes dedicar?", ["Menos de una hora semanal", "2-3 horas semanales", "Todo el necesario"]),
            ("¿Qué es más importante?", ["Entender la base", "Resultados rápidos", "Acompañamiento personal"]),
        ],
    },
}

_CLUB = {
    "ru": {
        "products": [
            ("month", "Месяц доступа", 1.0, "subscription", 30,
             "Доступ к клубу «{topic}» на 30 дней: закрытый канал, материалы недели, ответы на вопросы."),
            ("quarter", "Три месяца", 2.6, "subscription", 90,
             "Три месяца доступа со скидкой. Все материалы, эфиры и архив по теме «{topic}»."),
            ("year", "Год доступа", 8.0, "subscription", 365,
             "Год в клубе по лучшей цене плюс личный разбор при вступлении."),
        ],
        "faq": [
            ("Что входит в подписку?", "Закрытый канал, еженедельные материалы, архив и ответы на вопросы участников."),
            ("Можно отменить?", "Да. Подписка не продлевается автоматически — вы сами решаете, продлевать ли."),
            ("Как получить доступ?", "Сразу после оплаты бот пришлёт ссылку-приглашение в закрытый канал."),
            ("Есть пробный период?", "Да, первые дни доступа бесплатны — кнопка появляется в разделе подписки."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("month", "One month", 1.0, "subscription", 30,
             "30 days inside the {topic} club: private channel, weekly material and member Q&A."),
            ("quarter", "Three months", 2.6, "subscription", 90,
             "Three months at a discount. Everything in the club plus the full archive."),
            ("year", "Twelve months", 8.0, "subscription", 365,
             "A year at the best rate, with a personal onboarding review."),
        ],
        "faq": [
            ("What is included?", "A private channel, weekly material, the full archive and member Q&A."),
            ("Can I cancel?", "Yes. Nothing renews automatically — you decide whether to extend."),
            ("How do I get access?", "The invite link arrives from the bot the moment your payment clears."),
            ("Is there a trial?", "Yes, the first days are free — the button appears in the subscription section."),
        ],
        "quiz": [],
    },
    "de": {
        "products": [
            ("month", "Ein Monat", 1.0, "subscription", 30,
             "30 Tage Zugang zum {topic}-Club: privater Kanal, wöchentliche Inhalte und Q&A."),
            ("quarter", "Drei Monate", 2.6, "subscription", 90,
             "Drei Monate vergünstigt. Alle Inhalte plus komplettes Archiv."),
            ("year", "Zwölf Monate", 8.0, "subscription", 365,
             "Ein Jahr zum besten Preis, inklusive persönlichem Onboarding."),
        ],
        "faq": [
            ("Was ist enthalten?", "Privater Kanal, wöchentliche Inhalte, Archiv und Antworten auf Ihre Fragen."),
            ("Kann ich kündigen?", "Ja. Es verlängert sich nichts automatisch."),
            ("Wie erhalte ich Zugang?", "Der Einladungslink kommt direkt nach Zahlungseingang."),
            ("Gibt es eine Testphase?", "Ja, die ersten Tage sind kostenlos — Button im Abo-Bereich."),
        ],
        "quiz": [],
    },
    "es": {
        "products": [
            ("month", "Un mes", 1.0, "subscription", 30,
             "30 días en el club de {topic}: canal privado, material semanal y preguntas."),
            ("quarter", "Tres meses", 2.6, "subscription", 90,
             "Tres meses con descuento. Todo el club más el archivo completo."),
            ("year", "Doce meses", 8.0, "subscription", 365,
             "Un año al mejor precio, con una sesión de bienvenida."),
        ],
        "faq": [
            ("¿Qué incluye?", "Canal privado, material semanal, archivo completo y respuestas a tus dudas."),
            ("¿Puedo cancelar?", "Sí. Nada se renueva automáticamente."),
            ("¿Cómo accedo?", "El enlace de invitación llega en cuanto se confirma el pago."),
            ("¿Hay prueba gratis?", "Sí, los primeros días son gratuitos — el botón está en la sección de suscripción."),
        ],
        "quiz": [],
    },
}

_SIGNALS = {
    "ru": {
        "products": [
            ("week", "Неделя", 0.45, "subscription", 7,
             "Тестовая неделя: все сигналы и разборы по теме «{topic}»."),
            ("month", "Месяц", 1.4, "subscription", 30,
             "Месяц сигналов с точками входа, целями и стоп-уровнями. Статистика открыта."),
            ("quarter", "Квартал", 3.5, "subscription", 90,
             "Три месяца доступа со скидкой плюс еженедельные обзоры рынка."),
        ],
        "faq": [
            ("Какая статистика?", "Публикуем результат каждой идеи — и прибыльные, и убыточные. Архив открыт подписчикам."),
            ("Это инвестиционная рекомендация?", "Нет. Это аналитика в информационных целях, решения вы принимаете сами."),
            ("Как приходят сигналы?", "В закрытый канал, доступ к нему бот выдаёт сразу после оплаты."),
            ("Сколько сигналов в неделю?", "В среднем 5-12, в зависимости от состояния рынка. Качество важнее количества."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("week", "One week", 0.45, "subscription", 7,
             "A trial week of every {topic} call and breakdown."),
            ("month", "One month", 1.4, "subscription", 30,
             "A month of calls with entries, targets and stops. Track record is public."),
            ("quarter", "One quarter", 3.5, "subscription", 90,
             "Three months at a discount plus weekly market reviews."),
        ],
        "faq": [
            ("Do you publish results?", "Every idea is logged — winners and losers. Subscribers see the full archive."),
            ("Is this financial advice?", "No. It is informational analysis; every decision remains yours."),
            ("How are calls delivered?", "To a private channel, which the bot unlocks the moment you pay."),
            ("How many calls per week?", "Typically 5-12 depending on conditions. Quality over quantity."),
        ],
        "quiz": [],
    },
}

_SERVICE = {
    "ru": {
        "products": [
            ("basic", "Базовый пакет", 1.0, "service", 0,
             "{topic_cap} — базовый объём работ. Сроки и состав фиксируем до старта."),
            ("standard", "Стандарт", 2.4, "service", 0,
             "Расширенный пакет: больше объём, приоритетные сроки, две итерации правок."),
            ("premium", "Под ключ", 5.0, "service", 0,
             "Полное сопровождение под ключ с ответственным менеджером и гарантией результата в договоре."),
        ],
        "faq": [
            ("Как начинается работа?", "После оплаты менеджер связывается в течение рабочего дня и согласует бриф."),
            ("Есть договор?", "Да, работаем по договору с фиксированным составом работ и сроками."),
            ("Сколько занимает?", "Базовый пакет — от 3 рабочих дней, под ключ — от двух недель."),
            ("Возможен возврат?", "Да, если работы ещё не начаты. После старта — по фактически выполненному объёму."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("basic", "Basic package", 1.0, "service", 0,
             "{topic_cap} — core scope of work. Timeline and deliverables agreed before we start."),
            ("standard", "Standard", 2.4, "service", 0,
             "Extended scope, priority turnaround and two rounds of revisions."),
            ("premium", "Done for you", 5.0, "service", 0,
             "Full delivery with a dedicated manager and results guaranteed in the contract."),
        ],
        "faq": [
            ("How does it start?", "After payment a manager contacts you within one business day to agree the brief."),
            ("Is there a contract?", "Yes — fixed scope, fixed deadlines, signed before work begins."),
            ("How long does it take?", "Basic from 3 business days, done-for-you from two weeks."),
            ("Can I get a refund?", "Yes, before work begins. After that, pro rata for work not yet delivered."),
        ],
        "quiz": [],
    },
}

_CONSULT = {
    "ru": {
        "products": [
            ("consult30", "Консультация 30 минут", 1.0, "consult", 0,
             "Быстрый разбор одного вопроса по теме «{topic}» с конкретными рекомендациями."),
            ("consult60", "Консультация 60 минут", 1.8, "consult", 0,
             "Полноценная встреча: разбор ситуации, план действий и запись встречи."),
            ("pack5", "Пакет из 5 встреч", 7.5, "consult", 0,
             "Пять встреч со скидкой и сопровождение в переписке между ними."),
        ],
        "faq": [
            ("Как проходит встреча?", "Видеозвонок в удобное время. Ссылка приходит после согласования слота."),
            ("Что если нужно перенести?", "Перенос бесплатно при предупреждении минимум за 12 часов."),
            ("Будет ли запись?", "Да, запись и конспект с рекомендациями приходят в течение суток."),
            ("Есть гарантия?", "Если после первой встречи вы решите, что формат не подошёл — вернём оплату."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("consult30", "30-minute session", 1.0, "consult", 0,
             "A focused review of one {topic} question with concrete next steps."),
            ("consult60", "60-minute session", 1.8, "consult", 0,
             "A full session: situation review, action plan and a recording."),
            ("pack5", "Five-session package", 7.5, "consult", 0,
             "Five sessions at a discount, with async support in between."),
        ],
        "faq": [
            ("How does the session work?", "A video call at a time that suits you. The link arrives once the slot is agreed."),
            ("Can I reschedule?", "Free of charge with at least 12 hours' notice."),
            ("Do I get a recording?", "Yes — recording and written recommendations within 24 hours."),
            ("Any guarantee?", "If the format does not work for you after the first session, we refund it."),
        ],
        "quiz": [],
    },
}

_SHOP = {
    "ru": {
        "products": [
            ("pack-lite", "Мини-набор", 0.6, "digital", 0,
             "Компактный набор материалов по теме «{topic}» — попробовать формат."),
            ("pack-main", "Основной набор", 1.4, "digital", 0,
             "Главный продукт: полная подборка материалов, готовых к использованию."),
            ("pack-pro", "Профи-набор", 2.8, "digital", 0,
             "Расширенная библиотека плюс обновления в течение года."),
            ("pack-all", "Всё сразу", 4.5, "digital", 0,
             "Полный доступ ко всем наборам и будущим дополнениям."),
        ],
        "faq": [
            ("В каком формате материалы?", "PDF и редактируемые файлы, ссылки приходят в бот сразу после оплаты."),
            ("Можно использовать в работе?", "Да, лицензия разрешает применение в коммерческих проектах."),
            ("Будут ли обновления?", "Для наборов «Профи» и «Всё сразу» — да, в течение года."),
            ("Как получить файлы повторно?", "Раздел «Профиль» хранит все покупки, доступ восстанавливается в один тап."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("pack-lite", "Mini pack", 0.6, "digital", 0,
             "A compact {topic} set — a low-risk way to try the format."),
            ("pack-main", "Main pack", 1.4, "digital", 0,
             "The flagship product: the complete, ready-to-use collection."),
            ("pack-pro", "Pro pack", 2.8, "digital", 0,
             "The extended library plus a year of updates."),
            ("pack-all", "Everything bundle", 4.5, "digital", 0,
             "Full access to every pack, including future additions."),
        ],
        "faq": [
            ("What format are the files?", "PDF and editable source files; links arrive in the bot right after payment."),
            ("Can I use these commercially?", "Yes, the licence covers commercial projects."),
            ("Do I get updates?", "Pro and Everything include a year of updates."),
            ("How do I re-download?", "Your Profile keeps every purchase — one tap restores access."),
        ],
        "quiz": [],
    },
}

_SAAS = {
    "ru": {
        "products": [
            ("lite", "Lite", 0.8, "subscription", 30,
             "Базовый тариф: основные функции для личного использования."),
            ("pro", "Pro", 2.0, "subscription", 30,
             "Все функции без ограничений, экспорт данных и приоритетная поддержка."),
            ("team", "Team", 5.0, "subscription", 30,
             "До пяти пользователей, общий доступ и командная статистика."),
        ],
        "faq": [
            ("Есть бесплатный период?", "Да, пробный доступ активируется в разделе подписки одной кнопкой."),
            ("Что при отмене?", "Доступ работает до конца оплаченного периода, данные сохраняются 90 дней."),
            ("Можно сменить тариф?", "Да, в любой момент — разница пересчитывается пропорционально."),
            ("Где хранятся данные?", "На серверах в защищённом контуре, экспорт доступен в любой момент."),
        ],
        "quiz": [],
    },
    "en": {
        "products": [
            ("lite", "Lite", 0.8, "subscription", 30,
             "Core features for personal use."),
            ("pro", "Pro", 2.0, "subscription", 30,
             "Everything unlocked, data export and priority support."),
            ("team", "Team", 5.0, "subscription", 30,
             "Up to five seats, shared access and team analytics."),
        ],
        "faq": [
            ("Is there a free trial?", "Yes — one tap in the subscription section starts it."),
            ("What happens if I cancel?", "Access runs to the end of the paid period; data is kept for 90 days."),
            ("Can I change plan?", "Any time. The difference is prorated."),
            ("Where is my data stored?", "On secured servers, and you can export it whenever you like."),
        ],
        "quiz": [],
    },
}

_LEADGEN = {
    "ru": {
        "products": [
            ("audit", "Выезд и замер", 0.35, "consult", 0,
             "Специалист приезжает, оценивает объём работ и составляет смету по теме «{topic}»."),
            ("package", "Стандартный заказ", 1.6, "service", 0,
             "Работы стандартного объёма с фиксированной ценой и гарантией."),
            ("turnkey", "Под ключ", 4.0, "service", 0,
             "Полный цикл: материалы, работы, вывоз мусора, гарантия в договоре."),
        ],
        "faq": [
            ("Сколько стоит выезд?", "Стоимость выезда засчитывается в счёт заказа, если работы согласованы."),
            ("Есть гарантия?", "Да, гарантия фиксируется в договоре — от 12 месяцев в зависимости от работ."),
            ("Как быстро приедете?", "В большинстве районов — в течение суток, срочные вызовы принимаем круглосуточно."),
            ("Как оплатить?", "Картой или через СБП прямо в боте, для юрлиц — по счёту."),
        ],
        "quiz": [
            ("Что нужно сделать?", ["Небольшой объём", "Стандартный заказ", "Комплексно, под ключ"]),
            ("Когда планируете начать?", ["Срочно", "В ближайшие недели", "Пока присматриваюсь"]),
            ("Нужны ли материалы?", ["Есть свои", "Частично", "Полностью ваши"]),
        ],
    },
    "en": {
        "products": [
            ("audit", "Site visit and quote", 0.35, "consult", 0,
             "A specialist visits, assesses the scope and prepares a written quote."),
            ("package", "Standard job", 1.6, "service", 0,
             "Standard scope at a fixed price, with a guarantee."),
            ("turnkey", "Turnkey", 4.0, "service", 0,
             "The full cycle: materials, labour, clean-up and a contractual guarantee."),
        ],
        "faq": [
            ("What does the visit cost?", "The visit fee is credited against the job if you go ahead."),
            ("Is the work guaranteed?", "Yes, written into the contract — from 12 months depending on the work."),
            ("How soon can you come?", "Usually within 24 hours; urgent call-outs are taken around the clock."),
            ("How do I pay?", "Card or crypto right in the bot; invoicing available for companies."),
        ],
        "quiz": [
            ("What do you need done?", ["Something small", "A standard job", "Full turnkey"]),
            ("When do you want to start?", ["Urgently", "In the next few weeks", "Just researching"]),
            ("Do you need materials?", ["I have my own", "Partly", "Supply everything"]),
        ],
    },
    "de": {
        "products": [
            ("audit", "Besichtigung und Angebot", 0.35, "consult", 0,
             "Ein Fachmann kommt vorbei, prüft den Umfang und erstellt ein schriftliches Angebot."),
            ("package", "Standardauftrag", 1.6, "service", 0,
             "Standardumfang zum Festpreis, mit Garantie."),
            ("turnkey", "Komplettservice", 4.0, "service", 0,
             "Alles aus einer Hand: Material, Arbeit, Entsorgung und vertragliche Garantie."),
        ],
        "faq": [
            ("Was kostet die Besichtigung?", "Die Anfahrt wird bei Auftragserteilung verrechnet."),
            ("Gibt es eine Garantie?", "Ja, vertraglich festgehalten — ab 12 Monaten je nach Leistung."),
            ("Wie schnell sind Sie da?", "Meist innerhalb von 24 Stunden, Notfälle rund um die Uhr."),
            ("Wie bezahle ich?", "Karte oder Krypto direkt im Bot; für Firmen auch auf Rechnung."),
        ],
        "quiz": [
            ("Was soll gemacht werden?", ["Kleiner Umfang", "Standardauftrag", "Komplett"]),
            ("Wann soll es losgehen?", ["Dringend", "In den nächsten Wochen", "Erst mal informieren"]),
            ("Material benötigt?", ["Habe eigenes", "Teilweise", "Bitte alles stellen"]),
        ],
    },
    "es": {
        "products": [
            ("audit", "Visita y presupuesto", 0.35, "consult", 0,
             "Un especialista acude, evalúa el alcance y prepara un presupuesto por escrito."),
            ("package", "Encargo estándar", 1.6, "service", 0,
             "Alcance estándar a precio cerrado, con garantía."),
            ("turnkey", "Llave en mano", 4.0, "service", 0,
             "Ciclo completo: materiales, trabajo, limpieza y garantía en contrato."),
        ],
        "faq": [
            ("¿Cuánto cuesta la visita?", "El coste se descuenta del encargo si sigues adelante."),
            ("¿Hay garantía?", "Sí, por contrato — desde 12 meses según el trabajo."),
            ("¿Con qué rapidez venís?", "Normalmente en 24 horas; urgencias las 24 h."),
            ("¿Cómo pago?", "Tarjeta o cripto en el propio bot; para empresas, con factura."),
        ],
        "quiz": [
            ("¿Qué necesitas?", ["Algo pequeño", "Un encargo estándar", "Llave en mano"]),
            ("¿Cuándo quieres empezar?", ["Urgente", "En las próximas semanas", "Solo me informo"]),
            ("¿Necesitas materiales?", ["Tengo los míos", "En parte", "Ponedlo todo"]),
        ],
    },
}

from archetypes_shop import (  # noqa: E402
    SHOP_MODULES,
    SHOP_REFERRAL,
    SHOP_TEMPLATES,
    SHOP_TRIAL_DAYS,
    shop_delivery,
)

TEMPLATES: dict[str, dict[str, Any]] = {
    "course": _COURSE,
    "club": _CLUB,
    "signals": _SIGNALS,
    "service": _SERVICE,
    "consult": _CONSULT,
    "shop": _SHOP,
    "saas": _SAAS,
    "leadgen": _LEADGEN,
    **SHOP_TEMPLATES,
}

#: Which bot modules each archetype switches on.
MODULES: dict[str, tuple[str, ...]] = {
    "course": ("catalog", "faq", "support", "referral", "quiz", "reviews"),
    "club": ("catalog", "subscription", "faq", "support", "referral", "content"),
    "signals": ("catalog", "subscription", "faq", "support", "referral"),
    "service": ("catalog", "faq", "support", "leadgen", "reviews"),
    "consult": ("catalog", "faq", "support", "booking"),
    "shop": ("catalog", "faq", "support", "referral"),
    "saas": ("catalog", "subscription", "faq", "support", "referral"),
    "leadgen": ("catalog", "faq", "support", "booking", "quiz", "reviews"),
    **SHOP_MODULES,
}

#: Affiliate payout per archetype — high-margin digital goods can afford more.
REFERRAL: dict[str, int] = {
    "course": 25,
    "club": 20,
    "signals": 20,
    "service": 10,
    "consult": 10,
    "shop": 30,
    "saas": 20,
    "leadgen": 5,
    **SHOP_REFERRAL,
}

#: Free-trial length in days (0 = no trial). Only meaningful with subscriptions.
TRIAL_DAYS: dict[str, int] = {"club": 3, "signals": 2, "saas": 7, **SHOP_TRIAL_DAYS}


def template_for(archetype: str, lang: str) -> dict[str, Any]:
    pack = TEMPLATES[archetype]
    return pack.get(lang) or pack["en"]


def build_catalog(entry: dict) -> list[dict]:
    """Expand an archetype into a priced, ready-to-sell catalog."""
    tpl = template_for(entry["archetype"], entry["lang"])
    topic = entry["topic"]
    topic_cap = topic[:1].upper() + topic[1:]

    catalog = []
    for sort, (sku, title, mult, kind, period, desc) in enumerate(tpl["products"]):
        catalog.append(
            {
                "sku": sku,
                "title": title,
                "price": float(price_for(entry["tier"], entry["currency"], mult)),
                "kind": kind,
                "period_days": period,
                "description": desc.format(topic=topic, topic_cap=topic_cap, name=entry["name"]),
                "sort": sort,
                "delivery": _delivery_for(kind, entry),
            }
        )
    return catalog


def _delivery_for(kind: str, entry: dict) -> dict:
    """What the buyer receives. Placeholders the owner replaces before launch."""
    if entry["archetype"] in SHOP_TEMPLATES:
        return shop_delivery(entry["archetype"], entry["lang"], kind)
    if kind == "subscription":
        # No invite_link by default. Access is granted in the database either
        # way; the owner adds a channel invite here once they have a channel.
        return {
            "text": _t(
                entry["lang"],
                ru="Добро пожаловать! Доступ открыт. Материалы приходят в этот чат.",
                en="Welcome aboard! Your access is active. Material arrives in this chat.",
                de="Willkommen! Ihr Zugang ist aktiv. Inhalte kommen in diesen Chat.",
                es="¡Bienvenido! Tu acceso está activo. El material llega a este chat.",
            ),
        }
    if kind in {"service", "consult"}:
        # No booking_url by default either: the order already creates a lead
        # and pings the admin, which is a complete flow on its own.
        return {
            "text": _t(
                entry["lang"],
                ru="Заявка принята. Мы свяжемся с вами здесь, чтобы согласовать детали.",
                en="Your request is in. We will message you here to agree the details.",
                de="Ihre Anfrage ist eingegangen. Wir melden uns hier zur Abstimmung.",
                es="Solicitud recibida. Te escribimos aquí para acordar los detalles.",
            ),
        }
    # Digital goods are the one case that genuinely cannot ship ready: the
    # material is the seller's. The product stays hidden until they add it.
    return {
        "text": _t(
            entry["lang"],
            ru="Ваши материалы готовы. Вопросы — в поддержку.",
            en="Your materials are ready. Support is one tap away.",
            de="Ihre Unterlagen sind fertig. Der Support ist einen Tipp entfernt.",
            es="Tus materiales están listos. El soporte está a un toque.",
        ),
        "links": ["https://REPLACE-WITH-YOUR-DELIVERY-LINK"],
    }


def build_faq(entry: dict) -> list[dict]:
    tpl = template_for(entry["archetype"], entry["lang"])
    topic = entry["topic"]
    return [
        {"q": q.format(topic=topic), "a": a.format(topic=topic, name=entry["name"])}
        for q, a in tpl["faq"]
    ]


def build_quiz(entry: dict) -> list[dict]:
    tpl = template_for(entry["archetype"], entry["lang"])
    return [
        {"q": q.format(topic=entry["topic"]), "options": list(options)}
        for q, options in tpl.get("quiz", [])
    ]


def _t(lang: str, *, ru: str, en: str, de: str = "", es: str = "") -> str:
    return {"ru": ru, "en": en, "de": de or en, "es": es or en}.get(lang, en)
