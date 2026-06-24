#!/usr/bin/env python3
"""Resolve the default review date for scheduled/manual refreshes."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def main() -> int:
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    print(day.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
