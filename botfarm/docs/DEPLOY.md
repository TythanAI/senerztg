# Развёртывание на VPS

Как разместить ботов и API на одном сервере: от голой Ubuntu до работающего
продакшена.

---

## Сколько ботов влезет на один VPS

Каждый бот в простое ест ~45–70 МБ RAM (Python + aiogram + SQLite).

| VPS | RAM | Ботов комфортно | Ботов максимум |
|-----|-----|-----------------|----------------|
| 1 vCPU / 1 GB | 1 GB | 8–10 | 14 |
| 2 vCPU / 2 GB | 2 GB | 20–25 | 32 |
| 2 vCPU / 4 GB | 4 GB | 45–55 | 70 |
| 4 vCPU / 8 GB | 8 GB | 100–120 | 150 |

Считайте по активным ботам, а не по всем 300 — лежащие в архиве ничего не едят.
Юнит-файлы уже ограничены `MemoryMax=384M`, так что один разросшийся бот не
уронит остальных.

## Установка с нуля (Ubuntu 24.04)

```bash
# 1. Система
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip \
    nginx certbot python3-certbot-nginx git ufw

# 2. Отдельный пользователь — боты не должны ходить под root
sudo useradd -m -d /opt/botfarm -s /bin/bash botfarm
sudo mkdir -p /opt/botfarm && sudo chown botfarm:botfarm /opt/botfarm

# 3. Код
sudo -u botfarm git clone <ваш-репозиторий> /opt/botfarm
cd /opt/botfarm/botfarm

# 4. Виртуальное окружение
sudo -u botfarm python3.12 -m venv /opt/botfarm/venv
sudo -u botfarm /opt/botfarm/venv/bin/pip install -r core/requirements.txt

# 5. Файрвол
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

Порты ботов (9000+) наружу **не открываются** — до них ходит только nginx
с локального адреса.

## Запуск бота

```bash
python tools/fleet.py activate ru-001-invest-start --token ... --admin ...

sudo cp bots/ru/001-invest-start/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now botfarm-ru-invest-start
```

Полезные команды:

```bash
sudo systemctl status botfarm-ru-invest-start
sudo journalctl -u botfarm-ru-invest-start -f       # живой лог
sudo systemctl restart botfarm-ru-invest-start
```

## HTTPS и вебхуки

Вебхуки платёжных систем требуют валидный HTTPS. Один домен обслуживает всех.

```bash
python tools/fleet.py nginx --domain pay.example.com --region ru > /tmp/botfarm.conf
sudo cp /tmp/botfarm.conf /etc/nginx/sites-available/botfarm
sudo ln -sf /etc/nginx/sites-available/botfarm /etc/nginx/sites-enabled/
sudo certbot --nginx -d pay.example.com
sudo nginx -t && sudo systemctl reload nginx
```

Каждый бот получает свой префикс:

```
https://pay.example.com/ru-001-invest-start/webhook/yookassa
https://pay.example.com/ru-001-invest-start/healthz
```

В `.env` бота пропишите `WEBHOOK_BASE=https://pay.example.com/ru-001-invest-start`.

## Docker вместо systemd

```bash
python tools/fleet.py compose --region ru --limit 20 > docker-compose.ru.yml
docker compose -f docker-compose.ru.yml up -d
docker compose -f docker-compose.ru.yml ps
```

## Мониторинг

```bash
# Какие боты активированы и живы
python tools/fleet.py status --probe

# Метрики одного бота (Prometheus-формат)
curl "http://127.0.0.1:9000/metrics?token=<WEBHOOK_SECRET>"
```

Отдаются: `bot_users_total`, `bot_users_day`, `bot_orders_paid_total`,
`bot_revenue_total`, `bot_revenue_day`.

Минимальная проверка живости без Prometheus — cron раз в 5 минут:

```bash
*/5 * * * * curl -sf http://127.0.0.1:9000/healthz > /dev/null || \
  systemctl restart botfarm-ru-invest-start
```

## Бэкапы

Все данные бота — один файл `bot.db` рядом с кодом.

```bash
#!/bin/bash
# /opt/botfarm/backup.sh — в cron на 4 утра
DEST=/opt/backups/$(date +%F)
mkdir -p "$DEST"
find /opt/botfarm/botfarm/bots -name '*.db' -exec sh -c '
  out="$1/$(echo "$2" | sed "s|/opt/botfarm/botfarm/bots/||; s|/|_|g")"
  sqlite3 "$2" ".backup $out"' _ "$DEST" {} \;
tar czf "$DEST.tar.gz" -C "$DEST" . && rm -rf "$DEST"
find /opt/backups -name '*.tar.gz' -mtime +30 -delete
```

`.backup` вместо `cp` — иначе можно скопировать базу в момент записи.

## Переход на PostgreSQL

SQLite держит несколько тысяч пользователей на бота. Дальше:

```bash
sudo apt install -y postgresql
sudo -u postgres createdb invest_start
sudo -u postgres psql -c "CREATE USER botfarm WITH PASSWORD 'СЛОЖНЫЙ_ПАРОЛЬ';"
sudo -u postgres psql -c "GRANT ALL ON DATABASE invest_start TO botfarm;"

/opt/botfarm/venv/bin/pip install asyncpg
```

В `.env`:

```
DB_URL=postgresql+asyncpg://botfarm:СЛОЖНЫЙ_ПАРОЛЬ@localhost/invest_start
```

Схема создастся сама при старте. Код менять не нужно.

## Безопасность

- `.env` держать в режиме `600` — `fleet.py activate` делает это сам
- `.env` **никогда** не коммитить: `.gitignore` уже настроен
- Порты 9000+ не выставлять наружу
- `/metrics` защищён `WEBHOOK_SECRET` — не публикуйте его
- Обновления: `sudo apt update && sudo apt upgrade` раз в месяц
- SSH только по ключу: `PasswordAuthentication no` в `/etc/ssh/sshd_config`

## Частые проблемы

| Симптом | Причина и решение |
|---------|-------------------|
| `Cannot reach api.telegram.org` | нет сети или DNS; на РФ-хостинге может потребоваться прокси |
| `Telegram rejected BOT_TOKEN` | токен скопирован с пробелом или отозван в @BotFather |
| Бот молчит, в логах пусто | запущено два экземпляра с одним токеном — Telegram отдаёт апдейты одному |
| Оплата прошла, товар не пришёл | смотрите `journalctl` по слову `delivery`; заглушка в `delivery` не заменена |
| `payment provider ... disabled` | не заданы ключи в `.env` — это предупреждение, а не ошибка |
| Порт занят | два бота с одним `WEB_PORT`; проверьте `python tools/fleet.py ports` |
