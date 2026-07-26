# Prompt Library

> Battle-tested prompts by profession

**ID:** `eu-031-ai-prompts` · **Регион:** EU · **Язык:** en ·
**Модель:** shop · **Тариф цен:** budget

Prompt Library — a AI prompting bot. Tiered catalog, card and crypto checkout, automatic delivery, an affiliate programme and an admin panel with analytics.

## Что уже готово

- Каталог из 4 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, stars, manual
- Партнёрская программа 30%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9530

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `pack-lite` | Mini pack | 5 € | digital |
| `pack-main` | Main pack | 12 € | digital |
| `pack-pro` | Pro pack | 24 € | digital |
| `pack-all` | Everything bundle | 39 € | digital |

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
docker compose -f bots/eu/031-ai-prompts/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 031-ai-prompts.service /etc/systemd/system/
sudo systemctl enable --now 031-ai-prompts
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
