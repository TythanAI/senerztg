# NFT Дроп

> Ранние дропы и вайтлисты

**ID:** `ru-021-nft-drop` · **Регион:** RU · **Язык:** ru ·
**Модель:** signals · **Тариф цен:** standard

NFT Дроп — бот по теме «NFT». Каталог с тарифами, приём оплаты картой, через СБП и криптовалютой, автоматическая выдача после оплаты, партнёрская программа и админ-панель с аналитикой.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: yookassa, sbp, cryptobot, ton, manual
- Партнёрская программа 20% · пробный период 2 дн.
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9020

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `week` | Неделя | 660 ₽ | subscription · 7 дн. |
| `month` | Месяц | 2 080 ₽ | subscription · 30 дн. |
| `quarter` | Квартал | 5 210 ₽ | subscription · 90 дн. |

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
docker compose -f bots/ru/021-nft-drop/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 021-nft-drop.service /etc/systemd/system/
sudo systemctl enable --now 021-nft-drop
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
