#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")/../.."
.venv/bin/python dashboard/scripts/write_feishu_bitable_report.py --setup-only

echo
echo "Feishu Bitable setup command finished. You can close this window."
