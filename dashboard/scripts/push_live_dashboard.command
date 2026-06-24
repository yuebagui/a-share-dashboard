#!/bin/zsh
set -euo pipefail

WORKSPACE="/Users/kingkevin/Documents/征战大A"
PUBLISH_DIR="/private/tmp/a-share-dashboard-publish-$(date +%Y%m%d%H%M%S)"
REMOTE_URL="https://github.com/yuebagui/a-share-dashboard.git"

cd "$WORKSPACE"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python3"
fi

TRADE_DATE="$("$PYTHON_BIN" dashboard/scripts/resolve_trade_date.py)"

echo "Fetching latest A-share data for ${TRADE_DATE}..."
if "$PYTHON_BIN" dashboard/scripts/fetch_daily.py --date "$TRADE_DATE" --out dashboard/data/daily.json; then
  "$PYTHON_BIN" dashboard/scripts/write_refresh_status.py \
    --trade-date "$TRADE_DATE" \
    --success true \
    --message "Local publish refreshed market data."
else
  echo "Market data refresh failed; keeping previous dashboard/data/daily.json and publishing config changes."
  "$PYTHON_BIN" dashboard/scripts/write_refresh_status.py \
    --trade-date "$TRADE_DATE" \
    --success false \
    --message "Local publish could not refresh market data; kept previous snapshot."
fi

echo "Building latest GitHub Pages files..."
python3 dashboard/scripts/build_static_site.py --out .

echo "Preparing publish repository..."
mkdir -p "$PUBLISH_DIR"
cd "$PUBLISH_DIR"
git init -b main
git config user.name "kingkevin"
git config user.email "kingkevin@users.noreply.github.com"

rsync -a --delete \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude ".env" \
  --exclude "dashboard/.feishu.env" \
  --exclude "dashboard/dashboard-server.log" \
  --exclude "dashboard/public-lite.html" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  "$WORKSPACE"/ "$PUBLISH_DIR"/

git add .
git commit -m "Make dashboard live auto-refresh"
git remote add origin "$REMOTE_URL"

echo "Pushing to GitHub..."
git push --force origin main

echo
echo "Done. Public dashboard:"
echo "https://yuebagui.github.io/a-share-dashboard/"
echo
echo "You can close this window."
