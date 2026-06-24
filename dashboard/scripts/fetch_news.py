#!/usr/bin/env python3
"""Refresh pre-market news while preserving the latest market snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch_daily


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "daily.json"


def refresh_news(data: dict, news_date: str) -> dict:
    ak = fetch_daily.import_akshare()
    updated = deepcopy(data)
    news_brief = fetch_daily.build_news_brief(
        ak,
        news_date,
        updated.get("focusBoards", {}),
    )
    if not news_brief.get("items"):
        errors = " | ".join(news_brief.get("errors", [])) or "all news sources returned no items"
        raise RuntimeError(f"News refresh produced no usable items: {errors}")

    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    meta = updated.setdefault("meta", {})
    meta.setdefault("marketGeneratedAt", meta.get("generatedAt", ""))
    meta["phase"] = "盘前简报"
    meta["lastNewsAt"] = now
    updated["newsBrief"] = news_brief
    updated["reports"] = fetch_daily.build_reports(updated)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="News date, e.g. 2026-06-24")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out = Path(args.out)
    if not out.exists():
        print(f"Existing market snapshot not found: {out}")
        return 1

    try:
        current = json.loads(out.read_text(encoding="utf-8"))
        updated = refresh_news(current, args.date)
    except Exception as exc:  # noqa: BLE001
        print(f"Pre-market news refresh failed; keeping existing snapshot: {exc}")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(".tmp")
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(out)
    print(f"Wrote pre-market news to {out}")
    print(
        f"news_date={updated['newsBrief']['tradeDate']} "
        f"items={len(updated['newsBrief']['items'])} "
        f"market_snapshot={updated.get('meta', {}).get('tradeDate', '--')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
