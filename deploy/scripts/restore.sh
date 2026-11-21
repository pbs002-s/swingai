#!/usr/bin/env bash
# Restore a StitchSense backup.
#   deploy/scripts/restore.sh --verify  backups/stitchsense-<stamp>.dump    prove a backup works, touches nothing live
#   deploy/scripts/restore.sh --replace backups/stitchsense-<stamp>.dump    REPLACE the live database with the backup
#
# --verify restores into a scratch database, checks that the key tables have rows, and drops it again.
# Run it after every backup change and at least monthly: a backup nobody has restored is only a hope.
#
# --replace stops the API, drops the live database and loads the dump. Everything written since the backup is lost.
# Overrides: DB_EXEC="docker exec -i some-container"  DB_USER=...  DB_NAME=...  API_STOP="..."  API_START="..."
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f $HERE/../docker-compose.yml"
DB_EXEC="${DB_EXEC:-$COMPOSE exec -T db}"
DB_USER="${DB_USER:-stitchsense}"
DB_NAME="${DB_NAME:-stitchsense}"
API_STOP="${API_STOP:-$COMPOSE stop api}"
API_START="${API_START:-$COMPOSE start api}"
CHECK_TABLES="${CHECK_TABLES:-users factories stations events}"

MODE="${1:-}"
FILE="${2:-}"
if [[ ! "$MODE" =~ ^--(verify|replace)$ ]] || [ ! -f "$FILE" ]; then
  echo "usage: $0 --verify|--replace <backup.dump>" >&2
  exit 2
fi
psql_db() { $DB_EXEC psql -U "$DB_USER" -d "$1" -tA -c "$2"; }

if [ "$MODE" = "--verify" ]; then
  SCRATCH="${DB_NAME}_verify"
  trap 'psql_db postgres "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null 2>&1 || true' EXIT
  psql_db postgres "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null
  psql_db postgres "CREATE DATABASE $SCRATCH" >/dev/null
  $DB_EXEC pg_restore -U "$DB_USER" -d "$SCRATCH" --no-owner < "$FILE"
  for t in $CHECK_TABLES; do
    n="$(psql_db "$SCRATCH" "SELECT count(*) FROM $t")"
    echo "  $t: $n rows"
    if [ "$t" = "users" ] && [ "$n" -lt 1 ]; then
      echo "verify FAILED: no users in the restored database" >&2
      exit 1
    fi
  done
  echo "verify ok: $FILE restores cleanly"
  exit 0
fi

read -r -p "This REPLACES the live database '$DB_NAME' with $FILE. Type the database name to continue: " ANSWER
[ "$ANSWER" = "$DB_NAME" ] || { echo "cancelled"; exit 1; }
$API_STOP
psql_db postgres "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)" >/dev/null
psql_db postgres "CREATE DATABASE $DB_NAME" >/dev/null
$DB_EXEC pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner < "$FILE"
$API_START
echo "restore ok: $DB_NAME now matches $FILE"
