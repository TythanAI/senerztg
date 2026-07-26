# n8n Cloud Access

> n8n Cloud without a yearly commitment

**ID:** `eu-226-n8n-cloud-eu` · **Регион:** EU · **Язык:** en ·
**Модель:** accounts · **Тариф цен:** standard

n8n Cloud Access — a n8n Cloud automation access bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 15%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (5 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9725

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `basic` | Basic | 28 € | account |
| `standard` | Standard | 51 € | account |
| `premium` | Premium | 98 € | account |

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
docker compose -f bots/eu/226-n8n-cloud-eu/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 226-n8n-cloud-eu.service /etc/systemd/system/
sudo systemctl enable --now 226-n8n-cloud-eu
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
