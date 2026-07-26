# Etsy Shop Growth

> From first listing to full-time

**ID:** `eu-073-etsy-shop` · **Регион:** EU · **Язык:** en ·
**Модель:** course · **Тариф цен:** standard

Etsy Shop Growth — a Etsy bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 25%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9272

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `start` | Starter pack | 28 € | digital |
| `pro` | Full course | 77 € | digital |
| `vip` | VIP with coaching | 173 € | consult |

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
docker compose -f bots/eu/073-etsy-shop/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 073-etsy-shop.service /etc/systemd/system/
sudo systemctl enable --now 073-etsy-shop
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
