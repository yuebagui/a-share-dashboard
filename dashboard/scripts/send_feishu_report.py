#!/usr/bin/env python3
"""
Generate the daily A-share review and send it to Feishu.

Required environment:
  FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...

Optional environment:
  FEISHU_SECRET=...
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
FETCH_SCRIPT = ROOT / "scripts" / "fetch_daily.py"
DAILY_JSON = ROOT / "data" / "daily.json"


def main() -> int:
    trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    run_fetch(trade_date)
    data = json.loads(DAILY_JSON.read_text(encoding="utf-8"))
    report = build_report(data)
    webhook = os.environ.get("FEISHU_WEBHOOK", "").strip()
    if not webhook:
        print(report)
        print("\nFEISHU_WEBHOOK is not set; report was generated but not sent.")
        return 2
    send_feishu_text(webhook, report, os.environ.get("FEISHU_SECRET", "").strip())
    print("Feishu report sent.")
    return 0


def run_fetch(trade_date: str) -> None:
    result = subprocess.run(
        [sys.executable, str(FETCH_SCRIPT), "--date", trade_date],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"fetch_daily failed:\n{result.stdout}\n{result.stderr}")


def build_report(data: dict) -> str:
    meta = data["meta"]
    indices = "\n".join(
        f"{item['name']}：{item['price']}，{format_signed(item['changePct'])}%"
        for item in data.get("indices", [])
    )
    temp = data["temperature"]
    emotion = data["emotion"]
    focus = data.get("focusBoards", {}).get("items", [])[:6]
    focus_text = "\n".join(
        f"{idx}. {item['name']}｜{item['type']}｜{item['labels'][0] if item.get('labels') else '观察'}｜"
        f"涨跌 {format_signed(item['changePct'])}%｜超额 {format_signed(item['excessPct'])}%｜资金 {format_money(item['netInflow'])}"
        for idx, item in enumerate(focus, 1)
    ) or "暂无明确后续关注板块"
    strong_stocks = pick_strong_stocks(data)
    strong_text = "\n".join(
        f"{idx}. {item['name']}({item['code']})｜{item['boards']}板｜{','.join(item['tags'][:2])}｜封单 {item['sealAmount']}｜{item['reason']}"
        for idx, item in enumerate(strong_stocks, 1)
    ) or "暂无强势个股"
    weak = data.get("againstMarket", {}).get("down", [])[:5]
    weak_text = "\n".join(
        f"{idx}. {item['name']}｜{format_signed(item['changePct'])}%｜超额 {format_signed(item['excessPct'])}%｜资金 {format_money(item['netInflow'])}"
        for idx, item in enumerate(weak, 1)
    ) or "暂无明显弱势板块"
    risks = "\n".join(f"- {item}" for item in data.get("risks", [])[:4])

    return (
        f"【A股每日复盘】{meta['tradeDate']} {meta['phase']}\n"
        f"生成时间：{meta.get('generatedAt', '--')}\n\n"
        f"一、指数环境\n{indices}\n\n"
        f"二、情绪温度\n"
        f"情绪：{emotion['tag']}｜{emotion['title']}\n"
        f"涨停 {temp['limitUp']} 家，跌停 {temp['limitDown']} 家，炸板率 {temp['failRate']}%，最高 {temp['maxLadder']} 板。\n\n"
        f"三、后续关注板块\n{focus_text}\n\n"
        f"四、强势个股\n{strong_text}\n\n"
        f"五、弱势/回避方向\n{weak_text}\n\n"
        f"六、风险提示\n{risks}\n\n"
        "结论：只做核心方向的前排和放量中军，后排冲高不追；若炸板率继续抬升，主动降低仓位。"
    )


def pick_strong_stocks(data: dict) -> list[dict]:
    limit_ups = data.get("limitUps", [])
    sorted_items = sorted(
        limit_ups,
        key=lambda item: (
            int(item.get("boards", 0)),
            parse_amount(item.get("sealAmount", "0")),
            -int(item.get("failCount", 0)),
        ),
        reverse=True,
    )
    return sorted_items[:10]


def send_feishu_text(webhook: str, text: str, secret: str = "") -> None:
    payload = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
        sign = base64.b64encode(hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()).decode("utf-8")
        payload["timestamp"] = timestamp
        payload["sign"] = sign
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") not in (0, None):
        raise RuntimeError(f"Feishu send failed: {result}")


def format_signed(value) -> str:
    number = float(value or 0)
    return f"+{number:.2f}" if number > 0 else f"{number:.2f}"


def format_money(value) -> str:
    number = float(value or 0)
    if abs(number) >= 10000:
        return f"{number / 10000:.1f}亿"
    return f"{number:.1f}万"


def parse_amount(text: str) -> float:
    value = str(text).replace(",", "").strip()
    try:
        if value.endswith("亿"):
            return float(value[:-1]) * 100000000
        if value.endswith("万"):
            return float(value[:-1]) * 10000
        return float(value)
    except ValueError:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
