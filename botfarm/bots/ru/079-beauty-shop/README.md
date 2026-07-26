# Бьюти Гайды

> Готовые гайды по уходу и макияжу

**ID:** `ru-079-beauty-shop` · **Регион:** RU · **Язык:** ru ·
**Модель:** shop · **Тариф цен:** budget

Бьюти Гайды — бот по теме «бьюти-гайды». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 4 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, stars, manual
- Партнёрская программа 30%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9078

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `pack-lite` | Мини-набор | 280 ₽ | digital |
| `pack-main` | Основной набор | 680 ₽ | digital |
| `pack-pro` | Профи-набор | 1 360 ₽ | digital |
| `pack-all` | Всё сразу | 2 190 ₽ | digital |

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
docker compose -f bots/ru/079-beauty-shop/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 079-beauty-shop.service /etc/systemd/system/
sudo systemctl enable --now 079-beauty-shop
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
