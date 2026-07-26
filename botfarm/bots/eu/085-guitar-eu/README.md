# Guitar in 30 Days

> Your first songs, fast

**ID:** `eu-085-guitar-eu` · **Регион:** EU · **Язык:** en ·
**Модель:** course · **Тариф цен:** budget

Guitar in 30 Days — a guitar bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 25%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9284

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `start` | Starter pack | 8 € | digital |
| `pro` | Full course | 23 € | digital |
| `vip` | VIP with coaching | 53 € | consult |

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
docker compose -f bots/eu/085-guitar-eu/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 085-guitar-eu.service /etc/systemd/system/
sudo systemctl enable --now 085-guitar-eu
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
