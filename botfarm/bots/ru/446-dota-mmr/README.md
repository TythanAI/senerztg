# Dota 2 MMR

> Dota 2 MMR: результат под ключ, оплата после согласования

**ID:** `ru-446-dota-mmr` · **Регион:** RU · **Язык:** ru ·
**Модель:** service · **Тариф цен:** standard

Dota 2 MMR — бот по теме «буст MMR в Dota 2». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, manual
- Партнёрская программа 10%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9445

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `basic` | Базовый пакет | 1 480 ₽ | service |
| `standard` | Стандарт | 3 570 ₽ | service |
| `premium` | Под ключ | 7 440 ₽ | service |

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
docker compose -f bots/ru/446-dota-mmr/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 446-dota-mmr.service /etc/systemd/system/
sudo systemctl enable --now 446-dota-mmr
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
