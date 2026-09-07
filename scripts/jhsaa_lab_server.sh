#!/bin/bash
# Launch a standalone JHSAA "lab" instance: a full copy of the app, bound to
# its own database (separate from the college save), with a browser-driven
# "Generate new season" control at /jhsaa-lab. Once running, everything is
# clicks — no more CLI needed to produce a season.
#
# Usage: scripts/jhsaa_lab_server.sh [port]
#
# ‼️ DEFAULTS TO A PERSISTENT PATH, not /tmp (owner incident 2026-09). The lab
# began as a throwaway analysis tool and defaulted to /tmp/jhsaa_lab.db — but a
# JHSAA-only save is a real, long-lived universe (47 seasons in the field), and
# /tmp is erased on every reboot. The default now lives beside the persistent
# per-user save dir the app already uses for fallback, so a lab world survives a
# restart exactly like the normal game DB. The normal launcher has no DB-path
# argument: scratch files require the explicit developer/test override.
# See docs/PLAN-jhsaa-standalone-lab-mode.md and
# docs/AAR-name-era-self-reset-scrambled-names.md.
set -euo pipefail
cd "$(dirname "$0")/.."

DEFAULT_DB="${HOME}/.tennis-team-manager/jhsaa_lab.db"
PORT="${1:-5050}"
if [[ $# -gt 1 || ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "Usage: scripts/jhsaa_lab_server.sh [port]" >&2
  echo "The database is fixed at $DEFAULT_DB; arbitrary paths are not accepted." >&2
  exit 2
fi
if [[ -n "${TENNIS_DB_PATH:-}" ]]; then
  GOT="$(python3 -c 'import os; print(os.path.abspath(os.path.expanduser(os.environ["TENNIS_DB_PATH"])))')"
  if [[ "$GOT" != "$DEFAULT_DB" ]]; then
    echo "JHSAA lab startup refused: inherited TENNIS_DB_PATH=$GOT" >&2
    echo "The canonical database is $DEFAULT_DB. Unset TENNIS_DB_PATH and retry." >&2
    exit 2
  fi
fi

echo "JHSAA Lab starting — db=$DEFAULT_DB port=$PORT"
echo "Open http://localhost:$PORT/jhsaa-lab to generate a season."

TENNIS_DB_PATH="$DEFAULT_DB" JHSAA_LAB_MODE=1 PORT="$PORT" python3 -m app.web.server
