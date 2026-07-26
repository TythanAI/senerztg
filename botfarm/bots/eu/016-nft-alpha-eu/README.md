# NFT Alpha

> Mints and floor moves before the crowd

**ID:** `eu-016-nft-alpha-eu` · **Регион:** EU · **Язык:** en ·
**Модель:** signals · **Тариф цен:** standard

NFT Alpha — a NFT trading bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, ton, manual
- Партнёрская программа 20% · пробный период 2 дн.
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9515

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `week` | One week | 12 € | subscription · 7 дн. |
| `month` | One month | 40 € | subscription · 30 дн. |
| `quarter` | One quarter | 101 € | subscription · 90 дн. |

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
docker compose -f bots/eu/016-nft-alpha-eu/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 016-nft-alpha-eu.service /etc/systemd/system/
sudo systemctl enable --now 016-nft-alpha-eu
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
