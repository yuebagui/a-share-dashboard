#!/usr/bin/env python3
"""Scan Shanghai/Shenzhen main boards and ChiNext for technical scores above 60."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import fetch_daily


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "universe-candidates.json"
DEFAULT_DAILY = ROOT / "data" / "daily.json"
MAIN_BOARD_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")
CHINEXT_PREFIXES = ("300", "301")


def get_universe(ak) -> list[dict[str, str]]:
    frame = ak.stock_info_a_code_name()
    items = []
    for _, row in frame.iterrows():
        code = str(row.get("code", "")).zfill(6)
        name = str(row.get("name", "")).strip()
        board = board_for_code(code)
        if not board or not name or is_excluded_name(name):
            continue
        items.append({"code": code, "name": name, "board": board})
    return items


def board_for_code(code: str) -> str | None:
    if code.startswith(CHINEXT_PREFIXES):
        return "chinext"
    if code.startswith(MAIN_BOARD_PREFIXES):
        return "main"
    return None


def is_excluded_name(name: str) -> bool:
    upper = name.upper()
    return "ST" in upper or "退" in name


def scan_one(calculator, stock: dict[str, str], timeout: float) -> dict[str, Any]:
    bars, source = calculator.fetch_bars(stock["code"], timeout=timeout)
    last = bars[-1]
    previous_close = bars[-2].close if len(bars) >= 2 else last.close
    quote = calculator.Quote(
        code=stock["code"],
        market="sh" if stock["code"].startswith("6") else "sz",
        name=stock["name"],
        price=last.close,
        change_pct=((last.close / previous_close) - 1) * 100 if previous_close else 0,
        open=last.open,
        high=last.high,
        low=last.low,
        prev_close=previous_close,
        volume=last.volume * 100,
        amount=last.amount,
        time=last.date,
        source=source,
    )
    result = calculator.score_analysis(quote, bars, "auto")
    result["kline_source"] = source
    return build_candidate(stock, result)


def build_candidate(stock: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    score = result["score"]
    technical = result["technical"]
    labels = result["labels"]
    quote = result["quote"]
    total = int(score["total"])
    board_label = "创业板" if stock["board"] == "chinext" else "沪深主板"
    return {
        "code": stock["code"],
        "name": stock["name"],
        "theme": board_label,
        "boards": 0,
        "score": total,
        "labels": [board_label, labels.get("mode", "自动模式"), result.get("action", "--")],
        "amount": fetch_daily.amount_text(quote.get("amount")),
        "amountValue": quote.get("amount") or 0,
        "failCount": 0,
        "setup": labels.get("mode", "全市场技术扫描"),
        "buyPoint": labels.get("buy_point", "--"),
        "risk": labels.get("risk", "--"),
        "position": result.get("suggested_position", "0%-10%"),
        "technical": {
            "status": "ok",
            "mode": "auto",
            "total": total,
            "action": result.get("action"),
            "confidence": result.get("confidence"),
            "suggestedPosition": result.get("suggested_position"),
            "vetoes": result.get("vetoes", []),
            "ma20": technical.get("ma20"),
            "atrPct": technical.get("atr_pct"),
            "volumeRatio": technical.get("volume_ratio"),
            "position60Pct": technical.get("position_60_pct"),
            "buyPoint": labels.get("buy_point"),
            "riskLabel": labels.get("risk"),
            "stopLossPct": (technical.get("stop_reference") or {}).get("stop_loss_pct"),
            "barDate": result.get("bar_source_date"),
            "quoteTime": quote.get("time"),
            "quoteSource": quote.get("source"),
            "barSource": result.get("kline_source"),
        },
    }


def build_payload(
    trade_date: str,
    universe: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    failures: list[str],
) -> dict[str, Any]:
    main_items = sorted(
        [item for item in candidates if item["theme"] == "沪深主板" and item["score"] > 60],
        key=candidate_order,
        reverse=True,
    )
    chinext_items = sorted(
        [item for item in candidates if item["theme"] == "创业板" and item["score"] > 60],
        key=candidate_order,
        reverse=True,
    )
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "tradeDate": trade_date,
        "generatedAt": generated_at,
        "scoreThreshold": 60,
        "universe": "沪深主板+创业板，排除ST/退市/数据不足",
        "marketLevel": "--",
        "summary": [
            {"title": "沪深主板", "rule": f"全量扫描后 {len(main_items)} 只评分大于60，按评分和成交额排序。"},
            {"title": "创业板", "rule": f"全量扫描后 {len(chinext_items)} 只评分大于60，按评分和成交额排序。"},
            {"title": "覆盖率", "rule": f"股票池 {len(universe)} 只，成功 {len(candidates)} 只，失败 {len(failures)} 只。"},
            {"title": "执行纪律", "rule": "评分只决定观察顺序；仍需结合市场温度、题材主线和标准买点。"},
        ],
        "technicalCoverage": {
            "universe": len(universe),
            "scored": len(candidates),
            "qualified": len(main_items) + len(chinext_items),
            "failed": len(failures),
            "source": "Tencent/Eastmoney daily K-line",
        },
        "failures": failures[:50],
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


def candidate_order(item: dict[str, Any]) -> tuple[int, int, float]:
    veto_penalty = 1 if item.get("technical", {}).get("vetoes") else 0
    return (int(item.get("score", 0)), -veto_penalty, float(item.get("amountValue", 0)))


def update_daily(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        return
    daily = json.loads(path.read_text(encoding="utf-8"))
    payload["marketLevel"] = daily.get("reports", {}).get("marketLevel", "--")
    daily["candidatePools"] = payload
    daily["executionPlan"] = fetch_daily.build_execution_plan(
        payload,
        payload["marketLevel"],
        daily.get("emotion", {}),
        daily.get("temperature", {}),
        daily.get("focusBoards", {}),
    )
    daily["reports"] = fetch_daily.build_reports(daily)
    write_json(path, daily)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--daily", default=str(DEFAULT_DAILY))
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=0, help="Development-only universe limit")
    args = parser.parse_args()

    ak = fetch_daily.import_akshare()
    calculator = fetch_daily.import_calculator()
    universe = get_universe(ak)
    if args.limit > 0:
        universe = universe[: args.limit]
    if not universe:
        print("Universe is empty; keeping previous candidate cache.")
        return 1

    candidates: list[dict[str, Any]] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(scan_one, calculator, stock, args.timeout): stock
            for stock in universe
        }
        for index, future in enumerate(as_completed(futures), 1):
            stock = futures[future]
            try:
                candidates.append(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{stock['code']} {stock['name']}: {exc}")
            if index % 100 == 0 or index == len(universe):
                print(f"scanned={index}/{len(universe)} success={len(candidates)} failed={len(failures)}")

    payload = build_payload(args.date, universe, candidates, failures)
    if payload["technicalCoverage"]["scored"] < max(10, int(len(universe) * 0.5)):
        print("Universe scan coverage is below 50%; keeping previous cache.")
        return 1
    out = Path(args.out)
    write_json(out, payload)
    update_daily(Path(args.daily), payload)
    print(
        f"Wrote {out}: scanned={len(universe)} scored={len(candidates)} "
        f"qualified={payload['technicalCoverage']['qualified']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
