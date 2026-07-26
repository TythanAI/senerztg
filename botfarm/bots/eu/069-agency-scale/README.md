# Agency Scaling

> From freelancer to a team of ten

**ID:** `eu-069-agency-scale` · **Регион:** EU · **Язык:** en ·
**Модель:** consult · **Тариф цен:** elite

Agency Scaling — a agency growth bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 10%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9568

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `consult30` | 30-minute session | 198 € | consult |
| `consult60` | 60-minute session | 357 € | consult |
| `pack5` | Five-session package | 1 491 € | consult |

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
docker compose -f bots/eu/069-agency-scale/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 069-agency-scale.service /etc/systemd/system/
sudo systemctl enable --now 069-agency-scale
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
