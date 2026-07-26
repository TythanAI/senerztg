# Обмен Крипты

> Обмен Крипты: быстро, по курсу, без лишних вопросов

**ID:** `ru-480-crypto-exchange` · **Регион:** RU · **Язык:** ru ·
**Модель:** service · **Тариф цен:** premium

Обмен Крипты — бот по теме «обмен криптовалют». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, ton, manual
- Партнёрская программа 10%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9479

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `basic` | Базовый пакет | 4 890 ₽ | service |
| `standard` | Стандарт | 11 750 ₽ | service |
| `premium` | Под ключ | 24 490 ₽ | service |

## Запуск за 5 минут

```bash
cp .env.example .env
nano .env                     # BOT_TOKEN и ADMIN_IDS — обязательны
pip install -r ../../../core/requirements.txt
python bot.py
```

Через Docker:

```bash
cd ../../..                   # botfarm/
docker compose -f bots/ru/480-crypto-exchange/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 480-crypto-exchange.service /etc/systemd/system/
sudo systemctl enable --now 480-crypto-exchange
```

## Что заменить перед продажей

1. `.env` — токен бота от @BotFather и ваши `ADMIN_IDS`
2. `config.yaml` → `support_username` — контакт поддержки
3. `config.yaml` → `catalog[].delivery` — ссылки на реальные материалы,
   инвайты в закрытый канал, ссылку на запись
4. `config.yaml` → `manual_requisites` — ваши платёжные реквизиты
5. `texts.reviews` — реальные отзывы вместо примеров
6. Ключи платёжных систем в `.env`

Пока ключи не заданы, соответствующий способ оплаты просто не показывается —
бот остаётся рабочим.
