# Free Fire

> Free Fire: пополнение по выгодному курсу за 15 минут

**ID:** `ru-431-free-fire-diamonds` · **Регион:** RU · **Язык:** ru ·
**Модель:** topup · **Тариф цен:** budget

Free Fire — бот по теме «алмазы Free Fire». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, stars, manual
- Партнёрская программа 10%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9430

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `small` | Малый пакет | 480 ₽ | service |
| `medium` | Средний пакет | 1 210 ₽ | service |
| `large` | Большой пакет | 2 690 ₽ | service |

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
docker compose -f bots/ru/431-free-fire-diamonds/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 431-free-fire-diamonds.service /etc/systemd/system/
sudo systemctl enable --now 431-free-fire-diamonds
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
