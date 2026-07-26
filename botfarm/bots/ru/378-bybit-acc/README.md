# Bybit Аккаунты

> Bybit: верифицированные аккаунты под задачи

**ID:** `ru-378-bybit-acc` · **Регион:** RU · **Язык:** ru ·
**Модель:** accounts · **Тариф цен:** premium

Bybit Аккаунты — бот по теме «аккаунты Bybit». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, manual
- Партнёрская программа 15%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (5 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9377

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `basic` | Базовый | 4 890 ₽ | account |
| `standard` | Стандарт | 8 810 ₽ | account |
| `premium` | Премиум | 16 650 ₽ | account |

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
docker compose -f bots/ru/378-bybit-acc/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 378-bybit-acc.service /etc/systemd/system/
sudo systemctl enable --now 378-bybit-acc
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
