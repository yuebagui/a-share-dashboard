#!/usr/bin/env python3
"""Write a small status file for the dashboard refresh job."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "refresh-status.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--success", choices=["true", "false"], required=True)
    parser.add_argument("--message", default="")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    status = {
        "tradeDate": args.trade_date,
        "lastAttemptAt": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        "success": args.success == "true",
        "message": args.message,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
