# TON Exchange

> TON Exchange: fast, fair rate, no runaround

**ID:** `eu-483-ton-exchange-eu` · **Регион:** EU · **Язык:** en ·
**Модель:** service · **Тариф цен:** premium

TON Exchange — a TON Exchange crypto services bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, ton, manual
- Партнёрская программа 10%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9982

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `basic` | Basic package | 78 € | service |
| `standard` | Standard | 189 € | service |
| `premium` | Done for you | 394 € | service |

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
docker compose -f bots/eu/483-ton-exchange-eu/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 483-ton-exchange-eu.service /etc/systemd/system/
sudo systemctl enable --now 483-ton-exchange-eu
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
