# Майнинг Калькулятор

> Окупаемость ферм в реальном времени

**ID:** `ru-026-mining-calc` · **Регион:** RU · **Язык:** ru ·
**Модель:** saas · **Тариф цен:** standard

Майнинг Калькулятор — бот по теме «майнинг». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, ton, manual
- Партнёрская программа 20% · пробный период 7 дн.
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9025

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `lite` | Lite | 1 180 ₽ | subscription · 30 дн. |
| `pro` | Pro | 2 970 ₽ | subscription · 30 дн. |
| `team` | Team | 7 440 ₽ | subscription · 30 дн. |

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
docker compose -f bots/ru/026-mining-calc/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 026-mining-calc.service /etc/systemd/system/
sudo systemctl enable --now 026-mining-calc
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
