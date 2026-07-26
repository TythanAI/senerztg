# Online Marketing DE

> Kunden gewinnen im DACH-Raum

**ID:** `eu-070-marketing-de` · **Регион:** EU · **Язык:** de ·
**Модель:** course · **Тариф цен:** premium

Online Marketing DE — Bot rund um Online-Marketing. Katalog mit Tarifen, Zahlung per Karte und Krypto, automatische Auslieferung, Partnerprogramm und Admin-Panel.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 25%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9569

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `start` | Starter-Paket | 78 € | digital |
| `pro` | Komplettkurs | 212 € | digital |
| `vip` | VIP mit Betreuung | 473 € | consult |

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
docker compose -f bots/eu/070-marketing-de/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 070-marketing-de.service /etc/systemd/system/
sudo systemctl enable --now 070-marketing-de
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
