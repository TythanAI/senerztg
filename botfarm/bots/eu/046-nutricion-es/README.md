# Nutrición Práctica

> Come bien sin dietas imposibles

**ID:** `eu-046-nutricion-es` · **Регион:** EU · **Язык:** es ·
**Модель:** course · **Тариф цен:** standard

Nutrición Práctica — bot sobre nutrición. Catálogo con tarifas, pago con tarjeta y cripto, entrega automática, programa de afiliados y panel de administración.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 25%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9245

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `start` | Pack inicial | 28 € | digital |
| `pro` | Curso completo | 77 € | digital |
| `vip` | VIP con acompañamiento | 173 € | consult |

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
docker compose -f bots/eu/046-nutricion-es/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 046-nutricion-es.service /etc/systemd/system/
sudo systemctl enable --now 046-nutricion-es
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
