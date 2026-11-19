#!/usr/bin/env bash
# One-shot health check for cron or an uptime monitor. Exit 0 = healthy, 1 = something needs attention.
#   deploy/scripts/healthcheck.sh [base-url]        (default: http://localhost, through Caddy)
# Checks: the API answers and can reach the database, and the disk holding the data is not nearly full.
# Example cron (mail on failure):  */5 * * * *  /opt/stitchsense/deploy/scripts/healthcheck.sh || echo "StitchSense unhealthy" | mail -s alert you@example.com
set -uo pipefail

BASE="${1:-http://localhost}"
DISK_PATH="${DISK_PATH:-/}"
DISK_LIMIT_PCT="${DISK_LIMIT_PCT:-85}"
bad=0

if ! out="$(curl -fsS --max-time 10 "$BASE/api/v1/readyz" 2>&1)"; then
  echo "FAIL api/readyz: $out"
  bad=1
else
  echo "ok   api and database"
fi

used="$(df -P "$DISK_PATH" | awk 'NR==2 {gsub("%","",$5); print $5}')"
if [ -n "$used" ] && [ "$used" -le 100 ] && [ "$used" -ge "$DISK_LIMIT_PCT" ]; then
  echo "FAIL disk $DISK_PATH is ${used}% full (limit ${DISK_LIMIT_PCT}%)"
  bad=1
else
  echo "ok   disk ${used:-?}% used"
fi
exit "$bad"
