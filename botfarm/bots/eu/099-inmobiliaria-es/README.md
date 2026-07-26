# Inmobiliaria Directa

> Encuentra tu piso sin comisiones

**ID:** `eu-099-inmobiliaria-es` · **Регион:** EU · **Язык:** es ·
**Модель:** leadgen · **Тариф цен:** premium

Inmobiliaria Directa — bot sobre inmobiliaria. Catálogo con tarifas, pago con tarjeta y cripto, entrega automática, programa de afiliados y panel de administración.

## Что уже готово

- Каталог из 3 тарифов с автоматической выдачей после оплаты
- Приём оплаты: stripe, cryptobot, manual
- Партнёрская программа 5%
- Админ-панель: статистика, воронка, рассылки, промокоды, ручное подтверждение оплат
- Раздел FAQ (4 вопроса) и поддержка с тикетами
- Веб-эндпоинты `/healthz` и `/metrics` на порту 9298

## Каталог

| SKU | Название | Цена | Тип |
|-----|----------|------|-----|
| `audit` | Visita y presupuesto | 27 € | consult |
| `package` | Encargo estándar | 125 € | service |
| `turnkey` | Llave en mano | 315 € | service |

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
docker compose -f bots/eu/099-inmobiliaria-es/docker-compose.yml up -d
```

Как systemd-сервис на VPS:

```bash
sudo cp 099-inmobiliaria-es.service /etc/systemd/system/
sudo systemctl enable --now 099-inmobiliaria-es
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
