#!/usr/bin/env python3
"""
Append a generated A-share market brief to Feishu Bitable.

Required environment is the same as write_feishu_bitable_report.py:
  FEISHU_APP_ID=cli_...
  FEISHU_APP_SECRET=...
  FEISHU_BITABLE_APP_TOKEN=app...
  FEISHU_BITABLE_TABLE_ID=tbl...
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from write_feishu_bitable_report import (
    DAILY_JSON,
    append_bitable_record,
    create_field,
    field,
    get_config,
    get_tenant_access_token,
    list_fields,
    load_local_env,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent

FIELD_SCHEMA = [
    {"field_name": "日期", "type": 1},
    {"field_name": "阶段", "type": 1},
    {"field_name": "生成时间", "type": 1},
    {"field_name": "标题", "type": 1},
    {"field_name": "十大新闻", "type": 1},
    {"field_name": "影响板块", "type": 1},
    {"field_name": "操作建议", "type": 1},
    {"field_name": "风险提示", "type": 1},
    {"field_name": "推送全文", "type": 1},
    {"field_name": "看板数据", "type": 1},
]


def main() -> int:
    args = parse_args()
    load_local_env(PROJECT_ROOT / ".env")
    load_local_env(ROOT / ".feishu.env")

    report = args.report_file.read_text(encoding="utf-8")
    data = load_daily_data()
    trade_date = args.date or data.get("meta", {}).get("tradeDate") or today()
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    config = get_config()
    token = get_tenant_access_token(config["app_id"], config["app_secret"])
    if not args.skip_field_setup and os.environ.get("FEISHU_SKIP_FIELD_SETUP", "").strip() != "1":
        ensure_fields(token, config["app_token"], config["table_id"])

    record = {
        field("日期"): trade_date,
        field("阶段"): args.phase,
        field("生成时间"): generated_at,
        field("标题"): args.title,
        field("十大新闻"): extract_section(report, ["十大", "十条", "影响新闻"], fallback_limit=3000),
        field("影响板块"): extract_section(report, ["板块", "主线", "观察清单"], fallback_limit=1800),
        field("操作建议"): extract_section(report, ["策略", "预案", "操作", "风控"], fallback_limit=1800),
        field("风险提示"): extract_section(report, ["风险"], fallback_limit=1200),
        field("推送全文"): report,
        field("看板数据"): json.dumps(data, ensure_ascii=False) if data else "",
    }
    result = append_bitable_record(token, config["app_token"], config["table_id"], record)
    record_id = result.get("data", {}).get("records", [{}])[0].get("record_id", "--")
    print(f"Feishu market brief written: {record_id}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a market brief markdown file to Feishu Bitable.")
    parser.add_argument("--report-file", type=Path, required=True)
    parser.add_argument("--phase", required=True, help="例如：盘前分析、午间策略")
    parser.add_argument("--title", default="A股专业策略推送")
    parser.add_argument("--date", default="")
    parser.add_argument("--skip-field-setup", action="store_true")
    return parser.parse_args()


def ensure_fields(token: str, app_token: str, table_id: str) -> None:
    existing = list_fields(token, app_token, table_id)
    existing_names = {item.get("field_name") for item in existing}
    for spec in FIELD_SCHEMA:
        name = field(spec["field_name"])
        if name in existing_names:
            continue
        payload = dict(spec)
        payload["field_name"] = name
        create_field(token, app_token, table_id, payload)


def load_daily_data() -> dict:
    if not DAILY_JSON.exists():
        return {}
    return json.loads(DAILY_JSON.read_text(encoding="utf-8"))


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def extract_section(report: str, keywords: list[str], fallback_limit: int) -> str:
    lines = report.splitlines()
    starts = [
        idx
        for idx, line in enumerate(lines)
        if is_heading(line) and any(keyword in line for keyword in keywords)
    ]
    if not starts:
        return compact(report, fallback_limit)

    start = starts[0]
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if is_heading(lines[idx]):
            end = idx
            break
    return compact("\n".join(lines[start:end]).strip(), fallback_limit)


def is_heading(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    return bool(
        text.startswith("#")
        or text.startswith("**")
        or re.match(r"^([一二三四五六七八九十]+、|\d+[.、])", text)
    )


def compact(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...（已截断）"


if __name__ == "__main__":
    raise SystemExit(main())
