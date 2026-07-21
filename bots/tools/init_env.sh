#!/usr/bin/env bash
# Create an env/<slug>.env file for every bot config that doesn't have one yet,
# by copying env/example.env. Existing files are left untouched.
#
#   bash tools/init_env.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p env
created=0
for cfg in config/*.yaml; do
  slug="$(basename "$cfg" .yaml)"
  target="env/${slug}.env"
  if [[ ! -f "$target" ]]; then
    cp env/example.env "$target"
    echo "created $target"
    created=$((created + 1))
  fi
done
echo "done: $created new env file(s). Now edit each env/<slug>.env and set BOT_TOKEN + ADMIN_IDS."
