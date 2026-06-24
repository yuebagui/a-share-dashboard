#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")/../.."

PORT="${DASHBOARD_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/"

if ! /usr/bin/curl -fsS "${URL}" >/dev/null 2>&1; then
  echo "Starting A-share dashboard on ${URL}"
  nohup .venv/bin/python dashboard/scripts/serve_dashboard.py "${PORT}" \
    > dashboard/dashboard-server.log 2>&1 &
  sleep 1
fi

/usr/bin/open "${URL}"
echo "Dashboard opened: ${URL}"
