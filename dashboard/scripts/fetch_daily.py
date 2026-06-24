#!/usr/bin/env python3
"""
Generate dashboard/data/daily.json with real A-share review data.

Primary source: AkShare wrappers over Eastmoney/THS/CNInfo-style public data.
Run with the workspace venv:

    .venv/bin/python dashboard/scripts/fetch_daily.py --date 2026-06-03
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
OUT_FILE = ROOT / "data" / "daily.json"
CALCULATOR_SCRIPT = PROJECT_ROOT / "skills" / "short-term-stock-calculator" / "scripts" / "calculator.py"
TECHNICAL_SCORE_LIMIT_PER_POOL = 5
NON_TRADING_BOARD_PATTERN = re.compile(
    "融资融券|深股通|沪股通|昨日|最近|标准普尔|富时罗素|机构重仓|"
    "小盘股|大盘成长|大盘价值|中盘|小盘|广东板块|沪企改革|"
    "MSCI|HS300|上证|深证|创业板|科创|证金持股|参股新三板"
)
THEME_KEYWORDS = [
    ("半导体", ["半导体", "芯片", "光刻", "先进封装", "存储", "晶圆"]),
    ("AI算力", ["AI", "人工智能", "算力", "数据中心", "AIDC", "服务器", "英伟达"]),
    ("机器人", ["机器人", "具身智能", "减速器", "伺服"]),
    ("新能源", ["新能源", "储能", "光伏", "风电", "锂电", "电池"]),
    ("汽车链", ["汽车", "智能驾驶", "无人驾驶", "车路云", "特斯拉"]),
    ("有色稀土", ["有色", "稀土", "铜", "铝", "钨", "锂", "黄金"]),
    ("医药", ["医药", "创新药", "医疗", "药品", "临床"]),
    ("军工", ["军工", "航天", "航空", "卫星", "导弹"]),
    ("低空经济", ["低空", "无人机", "eVTOL", "通航"]),
    ("金融", ["证券", "银行", "保险", "金融", "回购", "分红"]),
    ("能源", ["原油", "天然气", "煤炭", "电力", "能源"]),
]
NOTICE_RISK_PATTERN = re.compile("风险|退市|ST|问询|监管|诉讼|仲裁|减持|质押|冻结|异常波动")
NOTICE_CATALYST_PATTERN = re.compile("回购|增持|订单|合同|投资|重组|并购|股权激励|分红|业绩|预告")


def import_akshare():
    try:
        import akshare as ak  # type: ignore

        return ak
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "AkShare is required for accurate data. Install it with: "
            ".venv/bin/python -m pip install akshare"
        ) from exc


def get_indices(ak) -> list[dict[str, Any]]:
    try:
        return get_indices_sina(ak)
    except Exception:
        return get_indices_eastmoney(ak)


def get_indices_sina(ak) -> list[dict[str, Any]]:
    df = ak.stock_zh_index_spot_sina()
    wanted = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
    }
    result = []
    for code, display_name in wanted.items():
        row = df[df["代码"].astype(str) == code]
        if row.empty:
            continue
        item = row.iloc[0]
        result.append(
            {
                "name": display_name,
                "price": f"{to_float(item.get('最新价')):,.2f}",
                "changePct": round(to_float(item.get("涨跌幅")), 2),
            }
        )
    return result


def get_indices_eastmoney(ak) -> list[dict[str, Any]]:
    df = ak.stock_zh_index_spot_em()
    wanted = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000688": "科创50",
    }
    result = []
    for code, display_name in wanted.items():
        row = df[df["代码"].astype(str) == code]
        if row.empty:
            continue
        item = row.iloc[0]
        result.append(
            {
                "name": display_name,
                "price": f"{to_float(item.get('最新价')):,.2f}",
                "changePct": round(to_float(item.get("涨跌幅")), 2),
            }
        )
    return result


def get_limit_ups(ak, trade_date: str) -> list[dict[str, Any]]:
    df = ak.stock_zt_pool_em(date=trade_date.replace("-", ""))
    rows = []
    for _, row in df.iterrows():
        industry = clean_text(row.get("所属行业")) or "待归因"
        boards = int(to_float(row.get("连板数")) or 1)
        rows.append(
            {
                "code": str(row.get("代码", "--")).zfill(6),
                "name": clean_text(row.get("名称")) or "--",
                "boards": boards,
                "tags": [industry, board_tag(boards), limit_stat_tag(row.get("涨停统计"))],
                "sealAmount": amount_text(row.get("封板资金")),
                "turnover": f"成交 {amount_text(row.get('成交额'))}",
                "reason": build_limit_reason(row),
                "firstSeal": time_text(row.get("首次封板时间")),
                "lastSeal": time_text(row.get("最后封板时间")),
                "failCount": int(to_float(row.get("炸板次数"))),
            }
        )
    return sorted(rows, key=lambda item: (-item["boards"], item["firstSeal"], item["code"]))


def get_limit_downs(ak, trade_date: str) -> list[dict[str, Any]]:
    df = ak.stock_zt_pool_dtgc_em(date=trade_date.replace("-", ""))
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "code": str(row.get("代码", "--")).zfill(6),
                "name": clean_text(row.get("名称")) or "--",
                "changePct": f"{to_float(row.get('涨跌幅')):.2f}",
                "tags": [clean_text(row.get("所属行业")) or "待归因"],
                "reason": (
                    f"连续跌停 {int(to_float(row.get('连续跌停')))}，"
                    f"封单 {amount_text(row.get('封单资金'))}，"
                    f"开板 {int(to_float(row.get('开板次数')))} 次"
                ),
            }
        )
    return rows


def get_broken_boards(ak, trade_date: str) -> list[dict[str, Any]]:
    df = ak.stock_zt_pool_zbgc_em(date=trade_date.replace("-", ""))
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "code": str(row.get("代码", "--")).zfill(6),
                "name": clean_text(row.get("名称")) or "--",
                "changePct": round(to_float(row.get("涨跌幅")), 2),
                "industry": clean_text(row.get("所属行业")) or "待归因",
                "failCount": int(to_float(row.get("炸板次数"))),
            }
        )
    return rows


def get_flow(ak, kind: str) -> list[dict[str, Any]]:
    if kind == "concept":
        try:
            return get_ths_concept_flow(ak)
        except Exception:
            return get_eastmoney_board_change_flow(ak)

    func = ak.stock_fund_flow_industry if kind == "industry" else ak.stock_fund_flow_concept
    df = func(symbol="即时")
    name_col = "行业"
    result = []
    sorted_df = df.sort_values(by="净额", key=lambda series: series.astype(float).abs(), ascending=False)
    for _, row in sorted_df.head(12).iterrows():
        net_yi = to_float(row.get("净额"))
        leader = clean_text(row.get("领涨股")) or "--"
        leader_pct = to_float(row.get("领涨股-涨跌幅"))
        result.append(
            {
                "name": clean_text(row.get(name_col)) or "--",
                "netInflow": round(net_yi * 10000, 1),
                "changePct": round(to_float(row.get("行业-涨跌幅")), 2),
                "type": "行业",
                "note": f"涨跌幅 {format_signed(to_float(row.get('行业-涨跌幅')))}%，领涨 {leader} {format_signed(leader_pct)}%",
            }
        )
    return result


def get_ths_concept_flow(ak) -> list[dict[str, Any]]:
    df = ak.stock_fund_flow_concept(symbol="即时")
    return normalize_flow_df(df, name_col="行业", net_col="净额", net_unit="yi")


def get_eastmoney_board_change_flow(ak) -> list[dict[str, Any]]:
    df = ak.stock_board_change_em()
    filtered = df[~df["板块名称"].astype(str).str.contains(NON_TRADING_BOARD_PATTERN)]
    sorted_df = filtered.sort_values(by="主力净流入", key=lambda series: series.astype(float).abs(), ascending=False)
    result = []
    for _, row in sorted_df.head(12).iterrows():
        name = clean_text(row.get("板块名称")) or "--"
        leader = clean_text(row.get("板块异动最频繁个股及所属类型-股票名称")) or "--"
        direction = clean_text(row.get("板块异动最频繁个股及所属类型-买卖方向")) or "--"
        result.append(
            {
                "name": name,
                "netInflow": round(to_float(row.get("主力净流入")), 1),
                "changePct": round(to_float(row.get("涨跌幅")), 2),
                "type": "概念",
                "note": f"涨跌幅 {format_signed(to_float(row.get('涨跌幅')))}%，异动 {int(to_float(row.get('板块异动总次数')))} 次，频繁个股 {leader} {direction}",
            }
        )
    return result


def normalize_flow_df(df, name_col: str, net_col: str, net_unit: str) -> list[dict[str, Any]]:
    sorted_df = df.sort_values(by=net_col, key=lambda series: series.astype(float).abs(), ascending=False)
    result = []
    seen_names: set[str] = set()
    multiplier = 10000 if net_unit == "yi" else 1
    for _, row in sorted_df.iterrows():
        name = clean_text(row.get(name_col)) or "--"
        if is_non_trading_board(name) or name in seen_names:
            continue
        seen_names.add(name)
        net = to_float(row.get(net_col)) * multiplier
        leader = clean_text(row.get("领涨股")) or "--"
        leader_pct = to_float(row.get("领涨股-涨跌幅"))
        result.append(
            {
                "name": name,
                "netInflow": round(net, 1),
                "changePct": round(to_float(row.get("行业-涨跌幅")), 2),
                "type": "概念",
                "note": f"涨跌幅 {format_signed(to_float(row.get('行业-涨跌幅')))}%，领涨 {leader} {format_signed(leader_pct)}%",
            }
        )
        if len(result) >= 12:
            break
    return result


def build_ladder(limit_ups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = {}
    for item in limit_ups:
        grouped.setdefault(int(item["boards"]), []).append(item["name"])
    return [
        {"level": level, "stocks": stocks[:12]}
        for level, stocks in sorted(grouped.items(), reverse=True)
        if level >= 2
    ]


def build_emotion(
    limit_ups: list[dict[str, Any]],
    limit_downs: list[dict[str, Any]],
    broken_boards: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
) -> dict[str, Any]:
    up_count = len(limit_ups)
    down_count = len(limit_downs)
    broken_count = len(broken_boards)
    multi_count = sum(1 for item in limit_ups if int(item["boards"]) >= 2)
    max_ladder = max([int(item["boards"]) for item in limit_ups], default=0)
    fail_rate = round(broken_count / max(up_count + broken_count, 1) * 100)
    positive_concepts = sum(1 for item in concepts[:20] if to_float(item["netInflow"]) > 0)
    score = clamp(35 + up_count * 0.55 + multi_count * 2 + max_ladder * 3 - down_count * 2 - fail_rate * 0.25 + positive_concepts, 0, 100)
    tag = "强势" if score >= 75 else "中等偏强" if score >= 60 else "弱修复" if score >= 45 else "偏弱"
    title = {
        "强势": "赚钱效应强，围绕主线前排做确认",
        "中等偏强": "题材活跃，等分歧后的承接",
        "弱修复": "修复力度一般，仓位不宜激进",
        "偏弱": "亏钱效应占优，先防守再进攻",
    }[tag]
    return {
        "score": int(score),
        "tag": tag,
        "title": title,
        "brief": f"涨停 {up_count} 家，跌停 {down_count} 家，炸板 {broken_count} 家，连板 {multi_count} 家，最高 {max_ladder} 板。",
        "factors": [
            {"label": "涨停家数", "value": str(up_count), "valueClass": "up"},
            {"label": "跌停家数", "value": str(down_count), "valueClass": "down"},
            {"label": "连板家数", "value": str(multi_count), "valueClass": "up" if multi_count else "flat"},
            {"label": "炸板率", "value": f"{fail_rate}%", "valueClass": "down" if fail_rate >= 35 else "flat"},
        ],
    }


def build_daily(trade_date: str) -> dict[str, Any]:
    ak = import_akshare()
    errors: list[str] = []
    indices = safe_call(lambda: get_indices(ak), [], errors, "indices")
    limit_ups = safe_call(lambda: get_limit_ups(ak, trade_date), [], errors, "limit-ups")
    limit_downs = safe_call(lambda: get_limit_downs(ak, trade_date), [], errors, "limit-downs")
    broken_boards = safe_call(lambda: get_broken_boards(ak, trade_date), [], errors, "broken-boards")
    industries = safe_call(lambda: get_flow(ak, "industry"), [], errors, "industry-flow")
    concepts = safe_call(lambda: get_flow(ak, "concept"), [], errors, "concept-flow")
    emotion = build_emotion(limit_ups, limit_downs, broken_boards, concepts)
    max_ladder = max([int(item["boards"]) for item in limit_ups], default=0)
    fail_rate = round(len(broken_boards) / max(len(limit_ups) + len(broken_boards), 1) * 100)
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    trade_day = datetime.strptime(trade_date, "%Y-%m-%d").date()
    if trade_day < now.date():
        phase = "盘后复盘"
    elif now.hour < 15 or (now.hour == 15 and now.minute < 10):
        phase = "盘中快照"
    else:
        phase = "盘后复盘"
    benchmark = build_market_benchmark(indices)
    focus_boards = build_focus_boards(industries, concepts, benchmark)
    trend_charts = safe_call(
        lambda: build_trend_charts(ak, focus_boards["items"], trade_date),
        [],
        errors,
        "trend-charts",
    )

    temperature = {
        "limitUp": len(limit_ups),
        "limitDown": len(limit_downs),
        "failRate": fail_rate,
        "maxLadder": max_ladder,
    }
    market_level = classify_market_level(emotion.get("score", 0), temperature)
    candidate_pools = build_candidate_pools(limit_ups, broken_boards, focus_boards, market_level)
    candidate_pools = safe_call(
        lambda: enrich_candidate_pools_with_technical(candidate_pools, errors),
        candidate_pools,
        errors,
        "candidate-technical",
    )
    news_brief = safe_call(
        lambda: build_news_brief(ak, trade_date, focus_boards),
        build_empty_news_brief(trade_date, ["news: source unavailable"]),
        errors,
        "news-brief",
    )
    watch_plan = build_watch_plan(industries, concepts, max_ladder, fail_rate)
    execution_plan = build_execution_plan(candidate_pools, market_level, emotion, temperature, focus_boards)
    daily = {
        "meta": {
            "tradeDate": trade_date,
            "phase": phase,
            "generatedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "akshare: eastmoney/ths public data",
            "errors": errors,
        },
        "indices": indices,
        "emotion": emotion,
        "temperature": temperature,
        "discipline": [
            "先看主线前排和板块资金是否一致，再决定是否上仓位。",
            "题材高潮次日不追后排，分歧日只看核心承接。",
            "单票仓位超过六成时，必须先写清楚止损和减仓条件。",
            "跌停和炸板扩大时，主动降低交易频率。",
        ],
        "limitUps": limit_ups,
        "ladder": build_ladder(limit_ups),
        "flows": {"industries": industries, "concepts": concepts},
        "againstMarket": build_against_market(industries, concepts, benchmark),
        "focusBoards": focus_boards,
        "trendCharts": trend_charts,
        "risks": build_risks(limit_downs, broken_boards, concepts),
        "limitDowns": limit_downs,
        "watchPlan": watch_plan,
        "candidatePools": candidate_pools,
        "executionPlan": execution_plan,
        "newsBrief": news_brief,
        "brokenBoards": broken_boards,
    }
    daily["reports"] = build_reports(daily)
    return daily


def build_market_benchmark(indices: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not indices:
        return None
    preferred = next((item for item in indices if item.get("name") == "上证指数"), indices[0])
    return {"name": preferred["name"], "changePct": round(to_float(preferred["changePct"]), 2)}


def build_against_market(industries, concepts, benchmark) -> dict[str, Any]:
    if not benchmark:
        return {"benchmark": None, "up": [], "down": []}
    base = to_float(benchmark["changePct"])
    boards = []
    for item in industries:
        boards.append({**item, "type": item.get("type", "行业")})
    for item in concepts:
        boards.append({**item, "type": item.get("type", "概念")})

    up = []
    down = []
    for item in boards:
        if is_non_trading_board(item.get("name")):
            continue
        change = to_float(item.get("changePct"))
        enriched = {
            "name": item.get("name", "--"),
            "type": item.get("type", "--"),
            "changePct": round(change, 2),
            "excessPct": round(change - base, 2),
            "netInflow": item.get("netInflow", 0),
            "note": item.get("note", ""),
        }
        if change > base:
            up.append(enriched)
        if change < base:
            down.append(enriched)

    up.sort(key=lambda item: (item["excessPct"], item["changePct"], item["netInflow"]), reverse=True)
    down.sort(key=lambda item: (item["excessPct"], item["changePct"], item["netInflow"]))
    return {"benchmark": benchmark, "up": up[:8], "down": down[:8]}


def build_focus_boards(industries, concepts, benchmark) -> dict[str, Any]:
    if not benchmark:
        return {"items": [], "summary": [{"title": "缺少基准", "rule": "指数数据缺失，暂时无法判断抗跌和共振。"}]}
    base = to_float(benchmark["changePct"])
    boards = []
    for item in industries:
        boards.append({**item, "type": item.get("type", "行业")})
    for item in concepts:
        boards.append({**item, "type": item.get("type", "概念")})

    candidates = []
    max_inflow = max([abs(to_float(item.get("netInflow"))) for item in boards], default=1)
    for item in boards:
        if is_non_trading_board(item.get("name")):
            continue
        change = to_float(item.get("changePct"))
        inflow = to_float(item.get("netInflow"))
        excess = change - base
        labels = []
        score = 0.0

        if base <= 0.2 and change >= 0.8:
            labels.append("抗跌走强")
            score += 28
        if base > 0.2 and change > base + 0.8:
            labels.append("带盘共振")
            score += 24
        if inflow > 0:
            labels.append("资金流入")
            score += min(24, inflow / max_inflow * 24)
        if excess >= 1:
            labels.append("超额强势")
            score += min(18, excess * 5)
        if change > 0:
            score += min(10, change * 2)

        if not labels:
            continue

        reason_bits = []
        if "抗跌走强" in labels:
            reason_bits.append(f"大盘基准 {format_signed(base)}%，该板块仍上涨 {format_signed(change)}%")
        if "带盘共振" in labels:
            reason_bits.append(f"强于大盘 {format_signed(excess)} 个百分点")
        if "资金流入" in labels:
            reason_bits.append(f"主力净流入 {amount_text(inflow * 10000)}")
        reason = "；".join(reason_bits) or item.get("note", "")

        candidates.append(
            {
                "name": item.get("name", "--"),
                "type": item.get("type", "--"),
                "score": int(round(score)),
                "labels": labels[:3],
                "changePct": round(change, 2),
                "excessPct": round(excess, 2),
                "netInflow": round(inflow, 1),
                "reason": reason,
                "note": item.get("note", ""),
            }
        )

    candidates.sort(key=lambda item: (item["score"], item["excessPct"], item["netInflow"]), reverse=True)
    items = candidates[:8]
    summary = build_focus_summary(items, base)
    return {"items": items, "summary": summary}


def build_focus_summary(items, benchmark_change: float) -> list[dict[str, str]]:
    if not items:
        return [{"title": "暂无候选", "rule": "没有同时满足抗跌、共振或资金流入条件的板块，先降低出手频率。"}]
    top = items[0]
    resilient = [item for item in items if "抗跌走强" in item["labels"]]
    resonance = [item for item in items if "带盘共振" in item["labels"]]
    summary = [
        {
            "title": "首看方向",
            "rule": f"{top['name']}综合分最高，标签为 {'、'.join(top['labels'])}。明日优先看前排承接和中军量能。",
        }
    ]
    if resilient:
        summary.append(
            {
                "title": "抗跌线索",
                "rule": f"大盘基准 {format_signed(benchmark_change)}%，{resilient[0]['name']}仍明显走强，若指数回落可观察资金是否继续抱团。",
            }
        )
    if resonance:
        summary.append(
            {
                "title": "共振线索",
                "rule": f"{resonance[0]['name']}与指数同向走强，适合只盯前排和放量中军，后排不追。",
            }
        )
    return summary[:3]


def build_trend_charts(ak, focus_items: list[dict[str, Any]], trade_date: str) -> list[dict[str, Any]]:
    charts = []
    end = trade_date.replace("-", "")
    start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y%m%d")
    for item in focus_items[:4]:
        try:
            history = get_board_history(ak, item["name"], item["type"], start, end)
        except Exception:
            charts.append(build_snapshot_chart(item))
            continue
        if len(history) < 8:
            charts.append(build_snapshot_chart(item))
            continue
        closes = [point["close"] for point in history]
        latest = closes[-1]
        ret_5 = pct_change(closes[-6], latest) if len(closes) >= 6 else 0
        ret_20 = pct_change(closes[-21], latest) if len(closes) >= 21 else pct_change(closes[0], latest)
        high_20 = max(closes[-20:])
        low_20 = min(closes[-20:])
        drawdown = pct_change(high_20, latest)
        position = round((latest - low_20) / max(high_20 - low_20, 0.0001) * 100)
        charts.append(
            {
                "name": item["name"],
                "type": item["type"],
                "labels": item.get("labels", []),
                "ret5": round(ret_5, 2),
                "ret20": round(ret_20, 2),
                "drawdown": round(drawdown, 2),
                "position": int(max(0, min(100, position))),
                "trend": classify_trend(ret_5, ret_20, drawdown, position),
                "points": history[-24:],
            }
        )
    return charts


def build_snapshot_chart(item: dict[str, Any]) -> dict[str, Any]:
    change = to_float(item.get("changePct"))
    excess = to_float(item.get("excessPct"))
    inflow = to_float(item.get("netInflow"))
    score = to_float(item.get("score"))
    bars = [
        {"label": "涨幅", "value": round(change, 2), "max": 6},
        {"label": "超额", "value": round(excess, 2), "max": 6},
        {"label": "资金", "value": round(min(inflow / 500000, 6), 2), "max": 6},
        {"label": "评分", "value": round(score / 12, 2), "max": 8},
    ]
    trend = "强势结构" if change > 1 and excess > 1 and inflow > 0 else "观察结构"
    return {
        "name": item.get("name", "--"),
        "type": item.get("type", "--"),
        "labels": item.get("labels", []),
        "ret5": round(change, 2),
        "ret20": round(excess, 2),
        "drawdown": 0,
        "position": int(min(100, max(0, score))),
        "trend": trend,
        "chartType": "snapshot",
        "bars": bars,
        "points": [],
    }


def get_board_history(ak, name: str, board_type: str, start: str, end: str) -> list[dict[str, Any]]:
    if board_type == "行业":
        df = ak.stock_board_industry_hist_em(
            symbol=name,
            start_date=start,
            end_date=end,
            period="日k",
            adjust="",
        )
    else:
        df = ak.stock_board_concept_hist_em(
            symbol=name,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="",
        )
    date_col = first_existing_column(df, ["日期", "date"])
    close_col = first_existing_column(df, ["收盘", "close", "最新价"])
    pct_col = first_existing_column(df, ["涨跌幅", "changePct"])
    result = []
    for _, row in df.iterrows():
        result.append(
            {
                "date": clean_text(row.get(date_col)),
                "close": round(to_float(row.get(close_col)), 2),
                "changePct": round(to_float(row.get(pct_col)), 2) if pct_col else 0,
            }
        )
    return [item for item in result if item["close"] > 0]


def first_existing_column(df, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def pct_change(base: float, value: float) -> float:
    if not base:
        return 0.0
    return (value / base - 1) * 100


def classify_trend(ret_5: float, ret_20: float, drawdown: float, position: float) -> str:
    if ret_5 > 3 and position >= 80:
        return "加速上行"
    if ret_20 > 6 and drawdown > -3:
        return "趋势新高附近"
    if ret_20 > 4 and ret_5 < 0:
        return "强势整理"
    if ret_5 > 1 and ret_20 > 0:
        return "温和上行"
    return "震荡观察"


def is_non_trading_board(name) -> bool:
    return bool(NON_TRADING_BOARD_PATTERN.search(clean_text(name)))


def build_limit_reason(row) -> str:
    industry = clean_text(row.get("所属行业")) or "待归因"
    return (
        f"{industry}方向涨停，{limit_stat_tag(row.get('涨停统计'))}，"
        f"首次封板 {time_text(row.get('首次封板时间'))}，"
        f"炸板 {int(to_float(row.get('炸板次数')))} 次。"
    )


def build_risks(limit_downs, broken_boards, concepts) -> list[str]:
    risks = []
    if broken_boards:
        risks.append(f"今日炸板 {len(broken_boards)} 只，追高前先看前排封单和回封质量。")
    if limit_downs:
        risks.append(f"今日跌停 {len(limit_downs)} 只，负反馈未完全消失，后排题材容错率下降。")
    if concepts:
        top = concepts[0]
        risks.append(f"概念资金最活跃为 {top['name']}，若明日资金转负，相关后排股要防冲高回落。")
    risks.append("板块资金是短线情绪线索，不替代公告、财报和订单验证。")
    return risks


def build_news_brief(ak, trade_date: str, focus_boards: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    date_key = trade_date.replace("-", "")
    market_news = safe_news_call(lambda: get_market_news(ak), [], errors, "market-news")
    notices = safe_news_call(lambda: get_market_notices(ak, date_key), [], errors, "notices")
    calendar = safe_news_call(lambda: get_macro_calendar(ak, date_key), [], errors, "macro-calendar")
    all_items = market_news + notices + calendar
    themes = rank_news_themes(all_items, focus_boards)
    top_items = sorted(all_items, key=news_sort_key, reverse=True)[:18]
    return {
        "tradeDate": trade_date,
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare: eastmoney/sina/baidu/eastmoney notices",
        "errors": errors,
        "summary": build_news_summary(top_items, themes),
        "themes": themes,
        "items": top_items,
    }


def build_empty_news_brief(trade_date: str, errors: list[str]) -> dict[str, Any]:
    return {
        "tradeDate": trade_date,
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "unavailable",
        "errors": errors,
        "summary": "新闻源暂不可用，本次报告仅基于行情、资金和候选池生成。",
        "themes": [],
        "items": [],
    }


def get_market_news(ak) -> list[dict[str, Any]]:
    items = []
    try:
        df = ak.stock_info_global_em()
        for _, row in df.head(16).iterrows():
            title = clean_text(row.get("标题"))
            summary = clean_text(row.get("摘要"))
            items.append(normalize_news_item(title, summary, row.get("发布时间"), "东方财富7x24", row.get("链接"), "market"))
    except Exception:
        df = ak.stock_info_global_sina()
        for _, row in df.head(16).iterrows():
            content = clean_text(row.get("内容"))
            title = extract_bracket_title(content)
            items.append(normalize_news_item(title, content, row.get("时间"), "新浪财经7x24", "", "market"))
    return [item for item in items if item["title"]]


def get_market_notices(ak, date_key: str) -> list[dict[str, Any]]:
    df = ak.stock_notice_report(date=date_key)
    rows = []
    for _, row in df.head(80).iterrows():
        title = clean_text(row.get("公告标题"))
        notice_type = clean_text(row.get("公告类型"))
        if not is_relevant_notice(title, notice_type):
            continue
        stock = f"{clean_text(row.get('名称'))}({clean_text(row.get('代码'))})"
        summary = f"{stock}：{title}"
        rows.append(
            normalize_news_item(
                title,
                summary,
                row.get("公告日期"),
                "东方财富公告",
                row.get("网址"),
                "notice",
                tickers=[stock],
                notice_type=notice_type,
            )
        )
        if len(rows) >= 12:
            break
    return rows


def get_macro_calendar(ak, date_key: str) -> list[dict[str, Any]]:
    df = ak.news_economic_baidu(date=date_key)
    rows = []
    for _, row in df.iterrows():
        importance = int(to_float(row.get("重要性")))
        if importance < 2:
            continue
        event = clean_text(row.get("事件"))
        actual = clean_text(row.get("公布"))
        expected = clean_text(row.get("预期"))
        previous = clean_text(row.get("前值"))
        summary = f"{event}；公布 {actual or '--'}，预期 {expected or '--'}，前值 {previous or '--'}。"
        rows.append(
            normalize_news_item(
                event,
                summary,
                f"{clean_text(row.get('日期'))} {clean_text(row.get('时间'))}",
                "百度财经日历",
                "",
                "macro",
                importance=importance,
            )
        )
        if len(rows) >= 8:
            break
    return rows


def normalize_news_item(
    title,
    summary,
    published_at,
    source,
    url,
    category,
    tickers: list[str] | None = None,
    notice_type: str = "",
    importance: int = 1,
) -> dict[str, Any]:
    text = f"{clean_text(title)} {clean_text(summary)} {notice_type}"
    themes = map_themes(text)
    return {
        "title": clean_text(title),
        "summary": trim_text(clean_text(summary), 180),
        "publishedAt": clean_text(published_at),
        "source": clean_text(source),
        "url": clean_text(url),
        "category": category,
        "credibility": news_credibility(category, source),
        "impact": news_impact(text, category, importance),
        "themes": themes,
        "tickers": tickers or [],
        "importance": importance,
        "noticeType": notice_type,
    }


def news_credibility(category: str, source: str) -> str:
    if category == "notice":
        return "公告/交易所数据"
    if category == "macro":
        return "财经日历"
    if "东方财富" in source or "新浪" in source:
        return "公开快讯"
    return "待验证"


def news_impact(text: str, category: str, importance: int) -> str:
    if category == "notice":
        if NOTICE_RISK_PATTERN.search(text):
            return "风险"
        if NOTICE_CATALYST_PATTERN.search(text):
            return "催化"
        return "公司事件"
    if category == "macro":
        return "宏观关注" if importance >= 2 else "低影响"
    if any(word in text for word in ["风险", "下跌", "制裁", "冲突", "监管", "减持"]):
        return "风险"
    if any(word in text for word in ["政策", "回购", "增持", "突破", "订单", "涨价", "投资"]):
        return "催化"
    return "中性"


def rank_news_themes(items: list[dict[str, Any]], focus_boards: dict[str, Any]) -> list[dict[str, Any]]:
    scores: dict[str, int] = {}
    focus_names = {item.get("name") for item in focus_boards.get("items", [])}
    for item in items:
        for theme in item.get("themes", []):
            scores[theme] = scores.get(theme, 0) + item.get("importance", 1) + (2 if item.get("impact") == "催化" else 1)
            if theme in focus_names:
                scores[theme] += 3
    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:8]
    return [{"name": name, "score": score, "isFocusBoard": name in focus_names} for name, score in ranked]


def build_news_summary(items: list[dict[str, Any]], themes: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无可用新闻源，本次报告仅基于行情和资金数据。"
    risks = sum(1 for item in items if item.get("impact") == "风险")
    catalysts = sum(1 for item in items if item.get("impact") == "催化")
    theme_text = "、".join(item["name"] for item in themes[:3]) if themes else "暂无集中主题"
    return f"已抓取 {len(items)} 条新闻/公告/日历事件，催化 {catalysts} 条，风险 {risks} 条；主题映射集中在 {theme_text}。"


def news_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    impact_score = {"风险": 4, "催化": 3, "宏观关注": 2, "公司事件": 2, "中性": 1}.get(item.get("impact"), 1)
    category_score = {"notice": 4, "market": 3, "macro": 2}.get(item.get("category"), 1)
    return (impact_score, category_score, int(to_float(item.get("importance"))))


def is_relevant_notice(title: str, notice_type: str) -> bool:
    text = f"{title} {notice_type}"
    return bool(NOTICE_RISK_PATTERN.search(text) or NOTICE_CATALYST_PATTERN.search(text))


def map_themes(text: str) -> list[str]:
    result = []
    upper_text = text.upper()
    for theme, keywords in THEME_KEYWORDS:
        if any(keyword.upper() in upper_text for keyword in keywords):
            result.append(theme)
    return result[:4]


def extract_bracket_title(text: str) -> str:
    match = re.match(r"【([^】]+)】", text)
    if match:
        return match.group(1)
    return trim_text(text, 42)


def trim_text(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def safe_news_call(func, fallback, errors: list[str], label: str):
    try:
        return func()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}: {exc}")
        return fallback


def build_watch_plan(industries, concepts, max_ladder, fail_rate) -> list[dict[str, str]]:
    top_industry = first_positive(industries)
    top_concept = first_positive(concepts)
    plan = [
        {
            "title": "最强概念",
            "rule": f"{top_concept['name']}资金最强，明日只看前排承接和中军是否继续放量。"
            if top_concept
            else "暂无明显净流入概念，降低追涨频率。",
        },
        {
            "title": "最强行业",
            "rule": f"{top_industry['name']}净流入靠前，观察领涨股是否继续打开空间。"
            if top_industry
            else "暂无明显净流入行业，等待主线确认。",
        },
        {
            "title": "情绪条件",
            "rule": f"最高连板 {max_ladder} 板，炸板率 {fail_rate}%。只在情绪、资金、个股承接共振时加仓。",
        },
    ]
    return plan


def build_candidate_pools(
    limit_ups: list[dict[str, Any]],
    broken_boards: list[dict[str, Any]],
    focus_boards: dict[str, Any],
    market_level: str,
) -> dict[str, Any]:
    focus_names = {item.get("name") for item in focus_boards.get("items", [])}
    scored_limit_ups = [score_limit_up_candidate(item, focus_names, market_level) for item in limit_ups]
    scored_limit_ups.sort(key=lambda item: (item["score"], item["boards"], item["amountValue"]), reverse=True)

    leader_pool = [
        item
        for item in scored_limit_ups
        if item["boards"] >= 2 and item["failCount"] <= 8
    ][:8]
    if len(leader_pool) < 5:
        leader_pool = unique_candidates(leader_pool + scored_limit_ups[: 8 - len(leader_pool)])

    trend_pool = [
        item
        for item in scored_limit_ups
        if item["amountValue"] >= 500000000 and item["failCount"] <= 10
    ][:8]
    if len(trend_pool) < 5:
        trend_pool = unique_candidates(trend_pool + scored_limit_ups[: 8 - len(trend_pool)])

    elastic_from_limits = [
        item
        for item in scored_limit_ups
        if is_elastic_code(item["code"])
    ]
    elastic_from_broken = [score_broken_elastic_candidate(item, focus_names, market_level) for item in broken_boards if is_elastic_code(item.get("code", ""))]
    elastic_pool = unique_candidates(sorted(elastic_from_limits + elastic_from_broken, key=lambda item: item["score"], reverse=True))[:8]

    return {
        "marketLevel": market_level,
        "summary": build_candidate_summary(leader_pool, trend_pool, elastic_pool, market_level),
        "pools": [
            {
                "id": "leaders",
                "title": "A池 龙头池",
                "description": "连板高度、辨识度和主线承接优先，只看换手后的核心机会。",
                "items": leader_pool,
            },
            {
                "id": "trend",
                "title": "B池 容量趋势池",
                "description": "成交额和板块强度优先，等待放量突破或缩量回踩确认。",
                "items": trend_pool,
            },
            {
                "id": "elastic",
                "title": "C池 20cm弹性池",
                "description": "创业板/科创/北交弹性标的，只做分歧修复，不追一致加速。",
                "items": elastic_pool,
            },
        ],
    }


def enrich_candidate_pools_with_technical(candidate_pools: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    calculator = import_calculator()
    scored_count = 0
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    for pool in candidate_pools.get("pools", []):
        mode = mode_for_pool(pool.get("id", ""))
        pool_scored_count = 0
        for item in pool.get("items", []):
            key = (item.get("code", ""), mode)
            if key in cache:
                apply_technical_score(item, cache[key])
                continue
            if pool_scored_count >= TECHNICAL_SCORE_LIMIT_PER_POOL:
                item["technical"] = {
                    "status": "not_scored",
                    "message": f"本池本次最多技术评分 {TECHNICAL_SCORE_LIMIT_PER_POOL} 只，等待下次刷新或手动计算。",
                }
                continue
            cache[key] = score_candidate_technical(calculator, item, mode)
            scored_count += 1
            pool_scored_count += 1
            apply_technical_score(item, cache[key])

    for pool in candidate_pools.get("pools", []):
        pool["items"].sort(key=candidate_sort_key, reverse=True)

    candidate_pools["technicalCoverage"] = {
        "scored": sum(1 for pool in candidate_pools.get("pools", []) for item in pool.get("items", []) if item.get("technical", {}).get("status") == "ok"),
        "limitPerPool": TECHNICAL_SCORE_LIMIT_PER_POOL,
        "totalAttempted": scored_count,
        "source": "short-term-stock-calculator",
    }
    failed = [
        f"{item.get('code')}:{item.get('technical', {}).get('message')}"
        for pool in candidate_pools.get("pools", [])
        for item in pool.get("items", [])
        if item.get("technical", {}).get("status") == "error"
    ]
    if failed:
        errors.append("candidate-technical partial failures: " + " | ".join(failed[:6]))
    candidate_pools["summary"] = build_candidate_summary(
        candidate_pools["pools"][0]["items"],
        candidate_pools["pools"][1]["items"],
        candidate_pools["pools"][2]["items"],
        candidate_pools.get("marketLevel", "弱"),
    )
    return candidate_pools


def candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, float, float]:
    status = item.get("technical", {}).get("status")
    status_rank = 2 if status == "ok" else 1 if status == "not_scored" else 0
    return (
        status_rank,
        int(item.get("score", 0)),
        to_float(item.get("technical", {}).get("total")),
        to_float(item.get("amountValue")),
    )


def import_calculator():
    if not CALCULATOR_SCRIPT.exists():
        raise RuntimeError(f"calculator script not found: {CALCULATOR_SCRIPT}")
    spec = importlib.util.spec_from_file_location("short_term_stock_calculator", CALCULATOR_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load short-term calculator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def score_candidate_technical(calculator, item: dict[str, Any], mode: str) -> dict[str, Any]:
    code = item.get("code", "")
    try:
        quote, quote_errors = calculator.fetch_quote(code, timeout=5.0)
        bars, bar_source = calculator.fetch_bars(code, timeout=5.0)
        result = calculator.score_analysis(quote, bars, mode)
        tech = result.get("technical", {})
        score = result.get("score", {})
        labels = result.get("labels", {})
        return {
            "status": "ok",
            "mode": mode,
            "total": score.get("total"),
            "action": result.get("action"),
            "confidence": result.get("confidence"),
            "suggestedPosition": result.get("suggested_position"),
            "vetoes": result.get("vetoes", []),
            "ma20": tech.get("ma20"),
            "atrPct": tech.get("atr_pct"),
            "volumeRatio": tech.get("volume_ratio"),
            "position60Pct": tech.get("position_60_pct"),
            "buyPoint": labels.get("buy_point"),
            "riskLabel": labels.get("risk"),
            "stopLossPct": (tech.get("stop_reference") or {}).get("stop_loss_pct"),
            "barDate": result.get("bar_source_date"),
            "quoteTime": (result.get("quote") or {}).get("time"),
            "quoteSource": (result.get("quote") or {}).get("source"),
            "barSource": bar_source,
            "quoteWarnings": quote_errors,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "mode": mode,
            "message": str(exc),
        }


def apply_technical_score(item: dict[str, Any], technical: dict[str, Any]) -> None:
    item["baseScore"] = item.get("baseScore", item.get("score", 0))
    item["technical"] = technical
    if technical.get("status") != "ok":
        return
    total = to_float(technical.get("total"))
    veto_penalty = 14 if technical.get("vetoes") else 0
    blended = item["baseScore"] * 0.52 + total * 0.48 - veto_penalty
    item["score"] = int(round(clamp(blended, 0, 100)))
    item["position"] = technical.get("suggestedPosition") or item.get("position")
    if technical.get("buyPoint"):
        item["buyPoint"] = technical["buyPoint"]
    if technical.get("riskLabel"):
        item["risk"] = technical["riskLabel"]
    if technical.get("vetoes"):
        item["labels"] = unique_texts((item.get("labels") or []) + ["技术否决"])


def mode_for_pool(pool_id: str) -> str:
    if pool_id == "leaders":
        return "leader"
    if pool_id == "trend":
        return "trend"
    if pool_id == "elastic":
        return "20cm"
    return "auto"


def unique_texts(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def score_limit_up_candidate(item: dict[str, Any], focus_names: set[str], market_level: str) -> dict[str, Any]:
    code = item.get("code", "--")
    boards = int(to_float(item.get("boards")))
    fail_count = int(to_float(item.get("failCount")))
    amount_value = parse_cn_amount(item.get("turnover"))
    theme = first_theme(item)
    score = 45 + min(boards, 5) * 8 + min(amount_value / 100000000, 20) - fail_count * 1.5
    labels = [f"{boards}板" if boards >= 2 else "首板", theme]
    if theme in focus_names:
        score += 16
        labels.append("主线候选")
    if amount_value >= 1000000000:
        score += 8
        labels.append("容量活跃")
    if is_elastic_code(code):
        score += 5
        labels.append("弹性票")
    if market_level in ("弱", "冰"):
        score -= 6 if boards >= 3 else 3
    score = int(round(clamp(score, 0, 100)))
    return {
        "code": code,
        "name": item.get("name", "--"),
        "theme": theme,
        "boards": boards,
        "score": score,
        "labels": labels[:4],
        "amount": clean_text(item.get("turnover")).replace("成交 ", "") or "--",
        "amountValue": amount_value,
        "failCount": fail_count,
        "setup": choose_candidate_setup(boards, amount_value, code),
        "buyPoint": candidate_buy_point(boards, code),
        "risk": candidate_risk(fail_count, market_level),
        "position": candidate_position(score, market_level),
    }


def score_broken_elastic_candidate(item: dict[str, Any], focus_names: set[str], market_level: str) -> dict[str, Any]:
    theme = clean_text(item.get("industry")) or "待归因"
    fail_count = int(to_float(item.get("failCount")))
    change_pct = to_float(item.get("changePct"))
    score = 50 + min(max(change_pct, 0), 20) * 1.2 - fail_count * 2
    labels = ["20cm/弹性", theme, "炸板观察"]
    if theme in focus_names:
        score += 12
        labels.append("主线候选")
    if market_level in ("弱", "冰"):
        score -= 6
    score = int(round(clamp(score, 0, 100)))
    return {
        "code": item.get("code", "--"),
        "name": item.get("name", "--"),
        "theme": theme,
        "boards": 0,
        "score": score,
        "labels": labels[:4],
        "amount": "--",
        "amountValue": 0,
        "failCount": fail_count,
        "setup": "20cm反包观察",
        "buyPoint": "只看低开后快速修复、站回分时均线或关键支撑，不追高。",
        "risk": candidate_risk(fail_count, market_level),
        "position": candidate_position(score, market_level),
    }


def build_candidate_summary(leader_pool, trend_pool, elastic_pool, market_level: str) -> list[dict[str, str]]:
    return [
        {
            "title": "龙头池",
            "rule": pool_summary(leader_pool, "连板前排不足，先看首板晋级和板块修复。"),
        },
        {
            "title": "容量趋势池",
            "rule": pool_summary(trend_pool, "容量票线索不足，等待成交额重新放大。"),
        },
        {
            "title": "20cm弹性池",
            "rule": pool_summary(elastic_pool, "弹性票亏钱效应未收敛前，只看不动。"),
        },
        {
            "title": "仓位约束",
            "rule": f"当前市场温度 {market_level}，候选池只提供观察顺序，最终仍需触发买点和止损条件。",
        },
    ]


def pool_summary(items: list[dict[str, Any]], fallback: str) -> str:
    if not items:
        return fallback
    names = "、".join(f"{item['name']}({item['score']})" for item in items[:3])
    return f"优先观察 {names}，只做标准买点。"


def build_execution_plan(
    candidate_pools: dict[str, Any],
    market_level: str,
    emotion: dict[str, Any],
    temperature: dict[str, Any],
    focus_boards: dict[str, Any],
) -> dict[str, Any]:
    position_rule = position_rule_for_market(market_level)
    top_candidates = select_execution_candidates(candidate_pools)
    focus_names = [item.get("name", "--") for item in focus_boards.get("items", [])[:3]]
    return {
        "marketLevel": market_level,
        "emotionScore": emotion.get("score"),
        "totalPosition": position_rule["total"],
        "singlePosition": position_rule["single"],
        "stance": execution_stance(market_level, temperature),
        "focusThemes": focus_names,
        "topWatch": [format_watch_name(item) for item in top_candidates[:5]],
        "rules": [
            {
                "title": "开仓总则",
                "rule": execution_open_rule(market_level),
            },
            {
                "title": "加仓条件",
                "rule": "只有主线、指数、个股承接三者共振时加仓；未触发买点时只观察。",
            },
            {
                "title": "止损纪律",
                "rule": "跌破计划止损位、买入逻辑失效或单票亏损接近5%，按硬止损处理。",
            },
        ],
        "bans": build_ban_rules(market_level, temperature),
        "items": [build_execution_item(item, index + 1, market_level) for index, item in enumerate(top_candidates[:8])],
    }


def select_execution_candidates(candidate_pools: dict[str, Any]) -> list[dict[str, Any]]:
    picks = []
    for pool in candidate_pools.get("pools", []):
        for item in pool.get("items", [])[:3]:
            candidate = {**item, "poolTitle": pool.get("title", "候选池"), "poolId": pool.get("id", "")}
            picks.append(candidate)
    picks = unique_candidates(picks)
    picks.sort(key=execution_sort_key, reverse=True)
    return picks


def execution_sort_key(item: dict[str, Any]) -> tuple[int, int, float, int]:
    status = item.get("technical", {}).get("status")
    status_rank = 2 if status == "ok" else 1 if status == "not_scored" else 0
    veto_penalty = 1 if item.get("technical", {}).get("vetoes") else 0
    return (status_rank - veto_penalty, int(item.get("score", 0)), to_float(item.get("technical", {}).get("total")), int(item.get("boards", 0)))


def execution_stance(market_level: str, temperature: dict[str, Any]) -> str:
    fail_rate = to_float(temperature.get("failRate"))
    if market_level == "强":
        return "可主动围绕主线前排做确认，但后排只看不追。"
    if market_level == "中":
        return "只做主线核心和容量确认，等待分歧后的承接。"
    if market_level == "弱":
        return "防守为主，只允许核心低吸或缩量回踩确认，降低交易频率。"
    if fail_rate >= 40:
        return "空仓或极轻仓观察，先等亏钱效应收敛。"
    return "不开新仓优先，等待情绪修复。"


def execution_open_rule(market_level: str) -> str:
    if market_level in ("强", "中"):
        return "只在候选股触发分歧低吸、放量突破或缩量回踩确认时开仓。"
    if market_level == "弱":
        return "只允许10%-20%试错仓，且必须靠近支撑和止损位。"
    return "原则上不开新仓，除非市场出现明确冰点修复和核心票反核。"


def build_ban_rules(market_level: str, temperature: dict[str, Any]) -> list[str]:
    fail_rate = to_float(temperature.get("failRate"))
    limit_down = int(to_float(temperature.get("limitDown")))
    bans = [
        "候选股没有触发买点，不临盘幻想买入。",
        "一致高开且板块后排乱涨，不追非核心。",
        "买入前说不清止损位，不开仓。",
    ]
    if market_level in ("弱", "冰"):
        bans.insert(0, "市场温度偏低，非主线核心一律不做。")
    if limit_down >= 30:
        bans.append("跌停数量仍高，若负反馈继续扩散，停止开新仓。")
    if fail_rate >= 35:
        bans.append("炸板率偏高，接力票必须先看回封质量。")
    return bans


def build_execution_item(item: dict[str, Any], rank: int, market_level: str) -> dict[str, Any]:
    technical = item.get("technical", {})
    score = int(item.get("score", 0))
    vetoes = technical.get("vetoes") or []
    return {
        "rank": rank,
        "code": item.get("code", "--"),
        "name": item.get("name", "--"),
        "pool": item.get("poolTitle", "--"),
        "theme": item.get("theme", "--"),
        "score": score,
        "technicalScore": technical.get("total"),
        "action": execution_action(item, market_level),
        "timeWindow": execution_time_window(item),
        "entry": item.get("buyPoint", "--"),
        "stop": execution_stop(item),
        "position": item.get("position", candidate_position(score, market_level)),
        "watchLevel": watch_level(score, technical),
        "vetoes": vetoes[:3],
        "conditions": execution_conditions(item, market_level),
    }


def execution_action(item: dict[str, Any], market_level: str) -> str:
    technical = item.get("technical", {})
    if technical.get("vetoes"):
        return "只观察，等待技术否决解除"
    if market_level in ("弱", "冰"):
        return "低吸观察，不追高"
    if item.get("poolId") == "trend":
        return "等放量突破或缩量回踩确认"
    if item.get("poolId") == "elastic":
        return "等分歧修复，不追一致"
    return "等龙头分歧承接"


def execution_time_window(item: dict[str, Any]) -> str:
    if item.get("poolId") == "elastic":
        return "开盘15分钟后看修复强度，午后再确认"
    if item.get("poolId") == "trend":
        return "盘中突破确认或尾盘回踩确认"
    return "早盘分歧承接和午后回封质量"


def execution_stop(item: dict[str, Any]) -> str:
    technical = item.get("technical", {})
    stop_loss_pct = technical.get("stopLossPct")
    if stop_loss_pct is not None:
        return f"技术止损距离约 {stop_loss_pct}%，同时执行单票5%硬止损。"
    if technical.get("riskLabel"):
        return technical["riskLabel"]
    return "跌破关键承接位且30分钟内不能收回，或板块转弱，执行止损。"


def watch_level(score: int, technical: dict[str, Any]) -> str:
    if technical.get("vetoes"):
        return "观察"
    if score >= 85:
        return "首看"
    if score >= 75:
        return "重点"
    return "备选"


def execution_conditions(item: dict[str, Any], market_level: str) -> list[str]:
    conditions = [
        "板块前排不能明显掉队。",
        "个股必须出现承接、突破或回踩确认。",
    ]
    if market_level in ("弱", "冰"):
        conditions.append("若指数继续放量下跌，则取消计划。")
    if item.get("technical", {}).get("vetoes"):
        conditions.append("技术否决项未解除前不参与。")
    return conditions


def format_watch_name(item: dict[str, Any]) -> str:
    tech = item.get("technical", {}).get("total")
    suffix = f"/技{tech}" if tech is not None else ""
    return f"{item.get('name', '--')}({item.get('score', '--')}{suffix})"


def choose_candidate_setup(boards: int, amount_value: float, code: str) -> str:
    if is_elastic_code(code):
        return "20cm反包/分歧低吸"
    if boards >= 2:
        return "龙头分歧低吸"
    if amount_value >= 500000000:
        return "容量趋势突破"
    return "首板晋级观察"


def candidate_buy_point(boards: int, code: str) -> str:
    if is_elastic_code(code):
        return "低开不破关键位后快速修复，或放量突破分时高点再看。"
    if boards >= 2:
        return "首次分歧或二次分歧承接强，板块仍有助攻时低吸核心。"
    return "次日弱转强或缩量回踩不破，不能一致高开追后排。"


def candidate_risk(fail_count: int, market_level: str) -> str:
    if market_level in ("弱", "冰"):
        return "市场温度偏低，若跌停/炸板扩散则停止开新仓。"
    if fail_count >= 8:
        return "炸板次数偏多，次日必须先看承接和回封质量。"
    return "若板块转弱或买入逻辑失效，按计划止损。"


def candidate_position(score: int, market_level: str) -> str:
    if market_level == "冰" or score < 60:
        return "0%-10%"
    if market_level == "弱":
        return "10%-20%"
    if score >= 85:
        return "25%-35%"
    return "10%-25%"


def unique_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        code = item.get("code")
        if code in seen:
            continue
        seen.add(code)
        result.append(item)
    return result


def first_theme(item: dict[str, Any]) -> str:
    tags = item.get("tags") or []
    if tags:
        return clean_text(tags[0]) or "待归因"
    return "待归因"


def parse_cn_amount(value) -> float:
    text = clean_text(value).replace("成交", "").strip()
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([万亿]?)", text)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = match.group(2)
    if unit == "亿":
        return number * 100000000
    if unit == "万":
        return number * 10000
    return number


def is_elastic_code(code: str) -> bool:
    text = clean_text(code)
    return text.startswith(("300", "301", "688", "689", "8", "9"))


def build_reports(data: dict[str, Any]) -> dict[str, Any]:
    meta = data["meta"]
    generated_at = meta.get("generatedAt", "")
    emotion = data.get("emotion", {})
    temperature = data.get("temperature", {})
    focus_items = data.get("focusBoards", {}).get("items", [])
    risks = data.get("risks", [])
    watch_plan = data.get("watchPlan", [])
    main_lines = focus_items[:3]
    weak_lines = data.get("againstMarket", {}).get("down", [])[:3]
    limit_ups = data.get("limitUps", [])
    limit_downs = data.get("limitDowns", [])
    broken_boards = data.get("brokenBoards", [])
    candidate_pools = data.get("candidatePools", {})
    execution_plan = data.get("executionPlan", {})
    news_brief = data.get("newsBrief", {})
    market_level = classify_market_level(emotion.get("score", 0), temperature)
    cycle = classify_emotion_cycle(emotion.get("score", 0), temperature)
    position_rule = position_rule_for_market(market_level)
    phase = meta.get("phase")
    if phase == "盘前简报":
        active = "pre-market"
    elif phase == "盘中快照":
        active = "noon"
    else:
        active = "post-market"

    pre_market = {
        "id": "pre-market",
        "title": "早间新闻与今日关注",
        "stage": "盘前",
        "generatedAt": news_brief.get("generatedAt") or generated_at,
        "summary": news_brief.get("summary") or "盘前重点看隔夜消息、政策催化和主线延续性。",
        "sections": [
            {
                "title": "今日先看",
                "items": [
                    f"市场温度参考为{market_level}，总仓位按{position_rule['total']}控制。",
                    main_line_text(main_lines),
                    news_focus_text(news_brief),
                ],
            },
            {
                "title": "验证条件",
                "items": [
                    "指数不继续放量下破，短线情绪不出现跌停扩散。",
                    "主线前排强于后排，容量核心或连板核心能主动带动板块。",
                    "候选股只接受分歧低吸、放量突破或缩量回踩确认三类买点。",
                ],
            },
        ],
        "plan": watch_plan,
    }

    noon = {
        "id": "noon",
        "title": "午间复盘",
        "stage": "11:30",
        "generatedAt": generated_at,
        "summary": f"上午情绪分 {emotion.get('score', '--')}，{emotion.get('brief', '')}",
        "sections": [
            {
                "title": "上午盘面",
                "items": [
                    f"涨停 {temperature.get('limitUp', 0)} 家，跌停 {temperature.get('limitDown', 0)} 家，炸板率 {temperature.get('failRate', 0)}%，最高连板 {temperature.get('maxLadder', 0)} 板。",
                    main_line_text(main_lines),
                    weak_line_text(weak_lines),
                ],
            },
            {
                "title": "午后执行",
                "items": [
                    noon_action(market_level, temperature),
                    f"单票仓位上限参考 {position_rule['single']}，不在一致加速时追后排。",
                    "若炸板和跌停继续扩大，停止开新仓，只观察核心承接。",
                ],
            },
        ],
        "plan": watch_plan,
    }

    post_market = {
        "id": "post-market",
        "title": "盘后完整版复盘",
        "stage": "21:00",
        "generatedAt": generated_at,
        "summary": f"市场温度 {market_level}，情绪周期偏{cycle}。{emotion.get('title', '')}",
        "sections": [
            {
                "title": "市场温度",
                "items": [
                    f"情绪分 {emotion.get('score', '--')}，涨停 {temperature.get('limitUp', 0)}，跌停 {temperature.get('limitDown', 0)}，炸板 {len(broken_boards)}。",
                    f"连板高度 {temperature.get('maxLadder', 0)} 板，当前仓位纪律：总仓位 {position_rule['total']}，单票 {position_rule['single']}。",
                    f"今日负反馈：跌停 {len(limit_downs)} 只，炸板 {len(broken_boards)} 只。",
                ],
            },
            {
                "title": "主线与候选",
                "items": [
                    main_line_text(main_lines),
                    leader_text(limit_ups),
                    candidate_pool_text(candidate_pools),
                    execution_plan_text(execution_plan),
                ],
            },
            {
                "title": "风险与纪律",
                "items": risks[:3]
                + [
                    news_risk_text(news_brief),
                    "任何买卖计划都必须同时写清买点、止损、仓位和失效条件。",
                ],
            },
        ],
        "plan": watch_plan,
    }

    return {
        "active": active,
        "marketLevel": market_level,
        "emotionCycle": cycle,
        "positionRule": position_rule,
        "disclaimer": "免责声明：本页面内容仅为个人/团队交易复盘、数据整理与策略研究记录，不构成任何投资建议、收益承诺或买卖依据。市场有风险，交易需独立判断并自行承担风险。",
        "items": [pre_market, noon, post_market],
    }


def classify_market_level(score: float, temperature: dict[str, Any]) -> str:
    fail_rate = to_float(temperature.get("failRate"))
    limit_down = to_float(temperature.get("limitDown"))
    max_ladder = to_float(temperature.get("maxLadder"))
    if score >= 75 and fail_rate < 30 and limit_down <= 10 and max_ladder >= 4:
        return "强"
    if score >= 60 and fail_rate < 40 and limit_down <= 25:
        return "中"
    if score >= 45 and limit_down <= 50:
        return "弱"
    return "冰"


def classify_emotion_cycle(score: float, temperature: dict[str, Any]) -> str:
    fail_rate = to_float(temperature.get("failRate"))
    limit_down = to_float(temperature.get("limitDown"))
    max_ladder = to_float(temperature.get("maxLadder"))
    if limit_down >= 40 or score < 40:
        return "退潮/冰点"
    if score >= 78 and max_ladder >= 5:
        return "高潮"
    if score >= 65 and fail_rate <= 30:
        return "发酵"
    if score >= 50 and fail_rate <= 40:
        return "修复"
    return "分歧"


def position_rule_for_market(level: str) -> dict[str, str]:
    rules = {
        "强": {"total": "75%-100%", "single": "不超过50%"},
        "中": {"total": "50%-75%", "single": "不超过35%"},
        "弱": {"total": "25%-50%", "single": "不超过25%"},
        "冰": {"total": "0%-25%", "single": "10%-15%"},
    }
    return rules.get(level, rules["弱"])


def main_line_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无清晰主线，优先等待资金和前排共振确认。"
    names = "、".join(item.get("name", "--") for item in items[:3])
    top = items[0]
    return f"主线候选：{names}；首看 {top.get('name', '--')} 的前排承接和中军量能。"


def weak_line_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无明显弱势板块，继续观察负反馈是否扩散。"
    names = "、".join(item.get("name", "--") for item in items[:3])
    return f"弱势方向：{names}，相关后排不做反包幻想。"


def leader_text(limit_ups: list[dict[str, Any]]) -> str:
    leaders = [item for item in limit_ups if int(item.get("boards", 0)) >= 2][:5]
    if not leaders:
        return "连板高度不足，明日重点观察首板晋级和容量核心承接。"
    text = "、".join(f"{item['name']}{item['boards']}板" for item in leaders)
    return f"连板前排：{text}。只看换手承接和板块带动，不追一致后排。"


def candidate_pool_text(candidate_pools: dict[str, Any]) -> str:
    pools = candidate_pools.get("pools", [])
    if not pools:
        return "明日只保留 A 池龙头、B 池容量趋势、C 池 20cm 弹性三类机会。"
    parts = []
    for pool in pools:
        items = pool.get("items", [])
        if not items:
            continue
        names = "、".join(item.get("name", "--") for item in items[:2])
        parts.append(f"{pool.get('title', '候选池')}：{names}")
    if not parts:
        return "候选池暂无高质量标的，明日先等主线和情绪确认。"
    return "明日候选观察：" + "；".join(parts) + "。"


def execution_plan_text(execution_plan: dict[str, Any]) -> str:
    items = execution_plan.get("items", [])
    if not items:
        return "明日执行表暂无标的，先等待候选池更新。"
    names = "、".join(f"{item.get('name')}({item.get('watchLevel')})" for item in items[:4])
    return f"明日执行首看：{names}；总仓位上限 {execution_plan.get('totalPosition', '--')}。"


def news_focus_text(news_brief: dict[str, Any]) -> str:
    themes = news_brief.get("themes", [])
    if not themes:
        return "新闻源暂无集中主题，仍以板块资金和前排承接为准。"
    names = "、".join(item.get("name", "--") for item in themes[:3])
    return f"新闻/公告映射主题：{names}；需要与板块资金、前排承接和成交额共同验证。"


def news_risk_text(news_brief: dict[str, Any]) -> str:
    items = [item for item in news_brief.get("items", []) if item.get("impact") == "风险"]
    if not items:
        return "新闻风险暂未集中，但公告、监管和外围扰动仍需盘前复核。"
    names = "；".join(item.get("title", "--") for item in items[:2])
    return f"新闻/公告风险：{names}。"


def noon_action(level: str, temperature: dict[str, Any]) -> str:
    fail_rate = to_float(temperature.get("failRate"))
    if level in ("强", "中") and fail_rate < 35:
        return "午后可围绕主线核心做确认，优先等分歧承接。"
    if level == "弱":
        return "午后只看核心低吸和趋势回踩，降低交易频率。"
    return "午后防守优先，不开新仓或仅保留极轻仓观察。"


def first_positive(items):
    for item in items:
        if is_non_trading_board(item.get("name")):
            continue
        if to_float(item.get("netInflow")) > 0:
            return item
    return None


def safe_call(func, fallback, errors: list[str], label: str):
    try:
        return func()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}: {exc}")
        return fallback


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_float(value) -> float:
    try:
        if value in (None, "", "-", "--"):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def format_signed(value: float) -> str:
    return f"+{value:.2f}" if value > 0 else f"{value:.2f}"


def amount_text(value) -> str:
    number = to_float(value)
    if abs(number) >= 100000000:
        return f"{number / 100000000:.1f}亿"
    if abs(number) >= 10000:
        return f"{number / 10000:.1f}万"
    return f"{number:.0f}"


def time_text(value) -> str:
    text = clean_text(value)
    if len(text) == 6 and text.isdigit():
        return f"{text[:2]}:{text[2:4]}:{text[4:]}"
    if len(text) == 4 and text.isdigit():
        return f"{text[:2]}:{text[2:]}"
    return text or "--"


def board_tag(boards: int) -> str:
    return "首板" if boards <= 1 else f"{boards}连板"


def limit_stat_tag(value) -> str:
    text = clean_text(value)
    return f"涨停统计 {text}" if text else "涨停统计 --"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date, e.g. 2026-06-03")
    parser.add_argument("--out", default=str(OUT_FILE))
    args = parser.parse_args()

    data = build_daily(args.date)
    out = Path(args.out)
    if not has_usable_market_data(data):
        print("Fetch produced no usable market data; keeping previous daily.json if present.")
        if data["meta"]["errors"]:
            print("Errors:")
            for error in data["meta"]["errors"]:
                print(f"- {error}")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"date={data['meta']['tradeDate']} source={data['meta']['source']}")
    print(
        f"limit_up={data['temperature']['limitUp']} "
        f"limit_down={data['temperature']['limitDown']} "
        f"fail_rate={data['temperature']['failRate']}% "
        f"max_ladder={data['temperature']['maxLadder']}"
    )
    if data["meta"]["errors"]:
        print("Warnings:")
        for error in data["meta"]["errors"]:
            print(f"- {error}")
    return 0


def has_usable_market_data(data: dict[str, Any]) -> bool:
    has_market_context = bool(data.get("indices") and data.get("flows", {}).get("industries"))
    has_review_core = bool(data.get("limitUps") or data.get("limitDowns") or data.get("brokenBoards"))
    return has_market_context and has_review_core


if __name__ == "__main__":
    sys.exit(main())
