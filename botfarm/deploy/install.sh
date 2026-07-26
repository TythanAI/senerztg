#!/usr/bin/env bash
# Bare Ubuntu 22.04/24.04 → ready to launch bots.
#
#   curl -fsSL <raw-url>/deploy/install.sh | sudo bash
#   # or, from a clone:
#   sudo bash deploy/install.sh
#
# Installs system packages, creates an unprivileged user, sets up the venv
# and the firewall. Does not start any bot — that is `tools/setup.py`.

set -euo pipefail

BOTFARM_USER="${BOTFARM_USER:-botfarm}"
BOTFARM_HOME="${BOTFARM_HOME:-/opt/botfarm}"
REPO_URL="${REPO_URL:-}"

log()  { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Запустите под root: sudo bash deploy/install.sh"

log "Обновляю пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3 python3-venv python3-pip git curl ca-certificates \
  nginx certbot python3-certbot-nginx ufw sqlite3

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
log "Python ${PYTHON_VERSION}"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Нужен Python 3.11+. На Ubuntu 22.04: add-apt-repository ppa:deadsnakes/ppa"

if ! id "$BOTFARM_USER" >/dev/null 2>&1; then
  log "Создаю пользователя ${BOTFARM_USER} (боты не должны работать от root)"
  useradd --system --create-home --home-dir "$BOTFARM_HOME" --shell /bin/bash "$BOTFARM_USER"
fi
mkdir -p "$BOTFARM_HOME"
chown "$BOTFARM_USER:$BOTFARM_USER" "$BOTFARM_HOME"

if [ -n "$REPO_URL" ] && [ ! -d "$BOTFARM_HOME/botfarm" ]; then
  log "Клонирую ${REPO_URL}"
  sudo -u "$BOTFARM_USER" git clone --depth 1 "$REPO_URL" "$BOTFARM_HOME/repo"
  ln -sfn "$BOTFARM_HOME/repo/botfarm" "$BOTFARM_HOME/botfarm"
fi

[ -d "$BOTFARM_HOME/botfarm" ] || warn "Код не найден в ${BOTFARM_HOME}/botfarm — скопируйте его туда."

log "Виртуальное окружение"
sudo -u "$BOTFARM_USER" python3 -m venv "$BOTFARM_HOME/venv"
sudo -u "$BOTFARM_USER" "$BOTFARM_HOME/venv/bin/pip" install --quiet --upgrade pip
if [ -f "$BOTFARM_HOME/botfarm/core/requirements.txt" ]; then
  sudo -u "$BOTFARM_USER" "$BOTFARM_HOME/venv/bin/pip" install --quiet \
    -r "$BOTFARM_HOME/botfarm/core/requirements.txt"
fi

log "Файрвол"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
yes | ufw enable >/dev/null 2>&1 || true

# Bot ports (9000+) stay bound to localhost; only nginx reaches them.
log "Готово"
cat <<TXT

Дальше:

  cd ${BOTFARM_HOME}/botfarm
  sudo -u ${BOTFARM_USER} ${BOTFARM_HOME}/venv/bin/python tools/setup.py ru-201-steam

Мастер спросит токен и ключи оплаты и проверит их по-настоящему.
Затем:

  sudo cp bots/ru/201-steam/*.service /etc/systemd/system/
  sudo systemctl enable --now botfarm-ru-201-steam
  sudo journalctl -u botfarm-ru-201-steam -f

HTTPS для вебхуков (не обязателен — платежи досверяются опросом):

  python tools/fleet.py nginx --domain pay.example.com > /etc/nginx/sites-available/botfarm
  ln -sf /etc/nginx/sites-available/botfarm /etc/nginx/sites-enabled/
  certbot --nginx -d pay.example.com

TXT
