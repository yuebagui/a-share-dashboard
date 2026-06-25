#!/usr/bin/env python3
"""Merge full-universe scan shards and update the dashboard snapshot."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch_daily


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--daily", required=True)
    args = parser.parse_args()

    files = sorted(Path(args.input_dir).glob("**/universe-shard-*.json"))
    if not files:
        print("No universe scan shards found.")
        return 1
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    expected = max(int(item.get("shard", {}).get("count", 1)) for item in payloads)
    indexes = {int(item.get("shard", {}).get("index", -1)) for item in payloads}
    minimum_shards = math.ceil(expected * 0.8)
    if len(payloads) < minimum_shards or not indexes.issubset(set(range(expected))):
        print(
            f"Insufficient shards: expected={expected} minimum={minimum_shards} "
            f"found={sorted(indexes)}"
        )
        return 1

    main_items = []
    chinext_items = []
    failures = []
    for payload in payloads:
        pools = {pool["id"]: pool for pool in payload.get("pools", [])}
        main_items.extend(pools.get("main", {}).get("items", []))
        chinext_items.extend(pools.get("chinext", {}).get("items", []))
        failures.extend(payload.get("failures", []))

    main_items.sort(key=fetch_daily.candidate_sort_key, reverse=True)
    chinext_items.sort(key=fetch_daily.candidate_sort_key, reverse=True)
    full_universe = max(
        int(item.get("shard", {}).get("fullUniverseSize", 0))
        for item in payloads
    )
    scored = sum(int(item.get("technicalCoverage", {}).get("scored", 0)) for item in payloads)
    coverage = {
        "universe": full_universe,
        "scored": scored,
        "qualified": len(main_items) + len(chinext_items),
        "failed": max(0, full_universe - scored),
        "source": f"Tencent/Eastmoney daily K-line, {expected}-runner sharded scan",
    }
    if coverage["scored"] < max(10, int(coverage["universe"] * 0.8)):
        print(f"Merged coverage below 80%: {coverage}")
        return 1

    trade_date = payloads[0].get("tradeDate", "")
    merged = {
        "tradeDate": trade_date,
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        "scoreThreshold": 60,
        "universe": "沪深主板+创业板，排除ST/退市/数据不足",
        "marketLevel": "--",
        "summary": [
            {"title": "沪深主板", "rule": f"全量扫描后 {len(main_items)} 只评分大于60，按评分和成交额排序。"},
            {"title": "创业板", "rule": f"全量扫描后 {len(chinext_items)} 只评分大于60，按评分和成交额排序。"},
            {"title": "覆盖率", "rule": f"股票池 {coverage['universe']} 只，成功 {coverage['scored']} 只，失败 {coverage['failed']} 只。"},
            {"title": "执行纪律", "rule": "评分只决定观察顺序；仍需结合市场温度、题材主线和标准买点。"},
        ],
        "technicalCoverage": coverage,
        "failures": failures[:100],
        "pools": [
            {
                "id": "main",
                "title": "沪深主板 >60",
                "description": "覆盖沪深主板全部正常交易股票，不要求前一日涨停或跌停。",
                "items": main_items,
            },
            {
                "id": "chinext",
                "title": "创业板 >60",
                "description": "覆盖300/301开头创业板股票，不要求前一日涨停或跌停。",
                "items": chinext_items,
            },
        ],
    }
    out = Path(args.out)
    fetch_daily_json = json.dumps(merged, ensure_ascii=False, indent=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(fetch_daily_json, encoding="utf-8")

    daily_path = Path(args.daily)
    if daily_path.exists():
        daily = json.loads(daily_path.read_text(encoding="utf-8"))
        merged["marketLevel"] = daily.get("reports", {}).get("marketLevel", "--")
        daily["candidatePools"] = merged
        daily["executionPlan"] = fetch_daily.build_execution_plan(
            merged,
            merged["marketLevel"],
            daily.get("emotion", {}),
            daily.get("temperature", {}),
            daily.get("focusBoards", {}),
        )
        daily["reports"] = fetch_daily.build_reports(daily)
        daily_path.write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged {len(files)} shards: {coverage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
