#!/usr/bin/env bash
# Create deploy/.env with strong random secrets, so nobody types a weak password.
#   deploy/scripts/init-env.sh <site-address> <admin-email> [demo]
#   e.g.  deploy/scripts/init-env.sh stitchsense.factory.example admin@factory.example
#
# Refuses to overwrite an existing deploy/.env: replacing SS_SECRETS_KEY would make every saved camera password unreadable.
# The admin password is printed once. Save it in your password manager; it is not shown again.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/../.env"
SITE="${1:-}"
EMAIL="${2:-}"
MODE="${3:-}"

if [ -z "$SITE" ] || [ -z "$EMAIL" ]; then
  echo "usage: $0 <site-address> <admin-email> [demo]" >&2
  exit 2
fi
if [ -e "$ENV_FILE" ]; then
  echo "refusing to overwrite $ENV_FILE (it holds SS_SECRETS_KEY). Move it away first if you really mean to start over." >&2
  exit 1
fi

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1" || true; echo; }  # no Python needed on the server
DB_PASSWORD="$(rand 32)"
SECRETS_KEY="$(rand 48)"
ADMIN_PASSWORD="$(rand 20)"

umask 077  # the file holds secrets: owner only
{
  echo "SITE_ADDRESS=$SITE"
  echo "DB_PASSWORD=$DB_PASSWORD"
  echo "SS_ADMIN_EMAIL=$EMAIL"
  echo "SS_ADMIN_PASSWORD=$ADMIN_PASSWORD"
  echo "SS_SECRETS_KEY=$SECRETS_KEY"
  echo "SS_COOKIE_SECURE=true"
  if [ "$MODE" = "demo" ]; then
    echo "SS_ENV=demo"
    echo "SS_SIMULATOR_ENABLED=true"
    echo "SS_SEED_DEMO=true"
    echo "DEMO_MODE=1"
  else
    echo "SS_ENV=production"
    echo "SS_SIMULATOR_ENABLED=false"
    echo "SS_SEED_DEMO=false"
    echo "DEMO_MODE=0"
  fi
} > "$ENV_FILE"

echo "wrote $ENV_FILE"
echo
echo "  Admin login : $EMAIL"
echo "  Admin password (shown once): $ADMIN_PASSWORD"
echo
echo "Back up $ENV_FILE somewhere safe, apart from the database backups."
echo "Edge boxes have their own .env (edge/.env.example), including GO2RTC_PASSWORD for live view."
