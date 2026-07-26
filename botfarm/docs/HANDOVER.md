# Передача бота клиенту

Инструкция на случай «клиент появился». От «бот лежит в архиве» до «клиент
получил рабочий продукт» — 20–30 минут.

---

## Шаг 1. Выбрать бота

```bash
python tools/fleet.py list --region ru --archetype course
python tools/fleet.py list --grep крипт
python tools/fleet.py show ru-019-crypto-base
```

## Шаг 2. Получить токен

Клиент (или вы) создаёт бота у [@BotFather](https://t.me/BotFather):
`/newbot` → имя → username → приходит токен вида `1234567890:AAH...`.

ID администратора берётся у [@userinfobot](https://t.me/userinfobot).

## Шаг 3. Активировать

```bash
python tools/fleet.py activate ru-019-crypto-base \
  --token 1234567890:AAH... \
  --admin 555000111
```

Команда создаёт `.env` с правами `600` и генерирует `WEBHOOK_SECRET`.

## Шаг 4. Заменить заглушки

Открыть `config.yaml` бота и заменить:

| Поле | Что вписать |
|------|-------------|
| `support_username` | `@ваш_саппорт` |
| `catalog[].delivery.links` | ссылки на реальные материалы |
| `catalog[].delivery.invite_link` | инвайт в закрытый канал (для подписок) |
| `catalog[].delivery.booking_url` | ссылка на запись (для услуг и консультаций) |
| `manual_requisites` | ваши реквизиты для перевода |
| `texts.reviews` | реальные отзывы |

Проверить, что ничего не забыто:

```bash
python tools/fleet.py doctor --grep crypto-base
```

## Шаг 5. Подключить платежи

Достаточно **одного** способа, чтобы бот начал продавать. Не заданные ключи
просто не показываются покупателю — бот от этого не ломается.

### RU: YooKassa (карты + СБП)

1. Зарегистрировать магазин на [yookassa.ru](https://yookassa.ru) (нужны ИП или ООО)
2. Настройки → Магазин → скопировать `shopId` и секретный ключ
3. В `.env`: `YOOKASSA_SHOP_ID=...`, `YOOKASSA_SECRET_KEY=...`
4. В личном кабинете YooKassa указать вебхук:
   `https://ваш-домен/<bot-id>/webhook/yookassa` (событие `payment.succeeded`)

### EU/USA: Stripe

1. [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) → секретный ключ
2. Developers → Webhooks → добавить `https://ваш-домен/<bot-id>/webhook/stripe`,
   событие `checkout.session.completed` → скопировать signing secret
3. В `.env`: `STRIPE_SECRET_KEY=...`, `STRIPE_WEBHOOK_SECRET=...`

### Крипта: @CryptoBot (работает везде, юрлицо не нужно)

1. Открыть [@CryptoBot](https://t.me/CryptoBot) → Crypto Pay → Create App
2. В `.env`: `CRYPTOBOT_TOKEN=...`
3. В настройках приложения указать вебхук `https://ваш-домен/<bot-id>/webhook/cryptobot`

### Telegram Stars

Ничего подключать не нужно — работает сразу. Уже включён у ботов, где сумма
помещается в лимит Telegram (2500 ⭐ на счёт).

> Без вебхуков бот **всё равно работает**: фоновая задача перепроверяет
> неоплаченные счета каждую минуту. Вебхуки нужны для мгновенной выдачи.

## Шаг 6. Запустить

```bash
cd bots/ru/019-crypto-base
pip install -r ../../../core/requirements.txt
python bot.py
```

На VPS — как systemd-сервис:

```bash
sudo cp 019-crypto-base.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 019-crypto-base
sudo journalctl -u 019-crypto-base -f
```

При старте админ получает в Telegram сообщение «✅ Бот запущен» со списком
подключённых способов оплаты. Это и есть проверка, что всё поднялось.

## Шаг 7. Проверить перед сдачей

- [ ] `/start` показывает меню
- [ ] Каталог открывается, цены верные
- [ ] Тестовая покупка проходит (у YooKassa и Stripe есть тестовый режим)
- [ ] После оплаты приходит товар
- [ ] `/admin` открывает панель со статистикой
- [ ] `curl http://127.0.0.1:<порт>/healthz` возвращает `"status":"ok"`

## Что передавать клиенту

1. Токен бота и доступ к @BotFather
2. Папку бота **без `.env`** (в нём ваши ключи) — либо с его собственными ключами
3. Этот файл и `README.md` бота
4. Доступ к VPS, если хостинг ваш

## Что говорить о цене

Ориентиры по рынку (Kwork, Telegram-биржи, фриланс):

| Что продаём | RU | EU/USA |
|-------------|-----|--------|
| Бот «как есть», клиент сам ставит | 8 000 – 20 000 ₽ | €150 – 400 |
| Бот + установка на VPS + настройка платежей | 25 000 – 60 000 ₽ | €400 – 900 |
| Бот + наполнение контентом под нишу | 50 000 – 150 000 ₽ | €800 – 2 000 |
| Сопровождение (в месяц) | 5 000 – 15 000 ₽ | €100 – 300 |

Аргумент в переговорах: приём карт, СБП и крипты, автовыдача, партнёрская
программа и админка с воронкой — это уже готово. С нуля такое пишут 2–4 недели.
