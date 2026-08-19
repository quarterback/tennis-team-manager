#!/bin/bash
# Launch a standalone JHSAA "lab" instance: a full copy of the app, bound to
# its own scratch database (never your real save), with a browser-driven
# "Generate new season" control at /jhsaa-lab. Once running, everything is
# clicks — no more CLI needed to produce a season.
#
# Usage:
#   scripts/jhsaa_lab_server.sh [db-path] [port]
#
# Defaults to /tmp/jhsaa_lab.db on port 5050, so it can run alongside your
# real app (which normally listens on 5000) without colliding. See
# docs/PLAN-jhsaa-standalone-lab-mode.md for the design.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:-/tmp/jhsaa_lab.db}"
PORT="${2:-5050}"

echo "JHSAA Lab starting — db=$DB port=$PORT"
echo "Open http://localhost:$PORT/jhsaa-lab to generate a season."

TENNIS_DB_PATH="$DB" JHSAA_LAB_MODE=1 PORT="$PORT" python3 -m app.web.server
