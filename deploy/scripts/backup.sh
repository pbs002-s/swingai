#!/usr/bin/env bash
# Back up the StitchSense database to a compressed, verified dump.
#   deploy/scripts/backup.sh [backup-dir]        (default: ./backups, keeps 14 days)
# Run it every night from cron, e.g.:  0 2 * * *  /opt/stitchsense/deploy/scripts/backup.sh /var/backups/stitchsense
#
# Also keep a copy of deploy/.env somewhere safe, separately from the dumps. It holds SS_SECRETS_KEY, which
# decrypts saved camera passwords: a restored database without it needs every camera re-entered.
#
# Overrides (for non-compose setups): DB_EXEC="docker exec -i some-container"  DB_USER=...  DB_NAME=...  KEEP_DAYS=...
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_EXEC="${DB_EXEC:-docker compose -f $HERE/../docker-compose.yml exec -T db}"
DB_USER="${DB_USER:-stitchsense}"
DB_NAME="${DB_NAME:-stitchsense}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DIR="${1:-./backups}"

mkdir -p "$DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DIR/stitchsense-$STAMP.dump"
PART="$OUT.partial"

trap 'rm -f "$PART"' EXIT
# -Fc: compressed custom format, restorable table by table with pg_restore
$DB_EXEC pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$PART"

# A dump that cannot be listed is not a backup: refuse it instead of keeping a silent failure.
if ! $DB_EXEC pg_restore --list < "$PART" > /dev/null; then
  echo "backup FAILED: the dump is unreadable" >&2
  exit 1
fi
SIZE="$(wc -c < "$PART")"
if [ "$SIZE" -lt 1024 ]; then
  echo "backup FAILED: the dump is suspiciously small ($SIZE bytes)" >&2
  exit 1
fi

mv "$PART" "$OUT"
trap - EXIT
find "$DIR" -name 'stitchsense-*.dump' -mtime +"$KEEP_DAYS" -delete
echo "backup ok: $OUT ($SIZE bytes)"
