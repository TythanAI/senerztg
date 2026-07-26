# Dividend Income Club

> Monthly dividend picks and payout tracking

**ID:** `eu-002-dividend-income` · **Регион:** EU · **Язык:** en ·
**Модель:** club · **Тариф цен:** premium

Dividend Income Club — a dividend investing bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 20% · пробный период 3 дн.
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9501

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `month` | One month | 78 € | subscription · 30 дн. |
| `quarter` | Three months | 204 € | subscription · 90 дн. |
| `year` | Twelve months | 631 € | subscription · 365 дн. |

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
docker compose -f bots/eu/002-dividend-income/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 002-dividend-income.service /etc/systemd/system/
sudo systemctl enable --now 002-dividend-income
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
