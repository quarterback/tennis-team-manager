#!/bin/bash
# Launch a standalone JHSAA "lab" instance: a full copy of the app, bound to
# its own database (separate from the college save), with a browser-driven
# "Generate new season" control at /jhsaa-lab. Once running, everything is
# clicks — no more CLI needed to produce a season.
#
# Usage:
#   scripts/jhsaa_lab_server.sh [db-path] [port]
#
# ‼️ DEFAULTS TO A PERSISTENT PATH, not /tmp (owner incident 2026-09). The lab
# began as a throwaway analysis tool and defaulted to /tmp/jhsaa_lab.db — but a
# JHSAA-only save is a real, long-lived universe (47 seasons in the field), and
# /tmp is erased on every reboot. The default now lives beside the persistent
# per-user save dir the app already uses for fallback, so a lab world survives a
# restart exactly like the normal game DB. Pass an explicit path to override.
# See docs/PLAN-jhsaa-standalone-lab-mode.md and
# docs/AAR-name-era-self-reset-scrambled-names.md.
set -euo pipefail
cd "$(dirname "$0")/.."

DEFAULT_DB="${HOME}/.tennis-team-manager/jhsaa_lab.db"
DB="${1:-$DEFAULT_DB}"
PORT="${2:-5050}"

# Never silently start on a reboot-volatile path; if a caller passes /tmp, warn.
case "$DB" in
  /tmp/*|/private/tmp/*|/var/tmp/*)
    echo "⚠️  WARNING: db=$DB is on a temp filesystem that is ERASED ON REBOOT."
    echo "   A JHSAA universe kept here will be lost on restart. Pass a path under"
    echo "   your home folder instead, e.g. scripts/jhsaa_lab_server.sh \"$DEFAULT_DB\"" ;;
esac

mkdir -p "$(dirname "$DB")"
echo "JHSAA Lab starting — db=$DB port=$PORT"
echo "Open http://localhost:$PORT/jhsaa-lab to generate a season."

TENNIS_DB_PATH="$DB" JHSAA_LAB_MODE=1 PORT="$PORT" python3 -m app.web.server
